"""Thirty-day session retention with an injectable clock and atomic batches."""
from __future__ import annotations

import hashlib
import os
import secrets
import shutil
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("retention.invalid_clock")
    return value.astimezone(timezone.utc)


class RetentionService:
    """Deletes expired session material while preserving long-term memory."""

    def __init__(
        self,
        repository,
        *,
        clock: Callable[[], datetime] | None = None,
        data_root: Path | None = None,
        low_disk_bytes: int = 10 * 1024**3,
        fault_injector: Callable[[str], None] | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._repo = repository
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._data_root = Path(data_root or "/")
        self._low_disk_bytes = int(low_disk_bytes)
        self._fault_injector = fault_injector
        self._sleep = sleep

    def now(self) -> datetime:
        injected = os.environ.get("RETENTION_NOW")
        if injected:
            try:
                return _utc(datetime.fromisoformat(injected.replace("Z", "+00:00")))
            except (TypeError, ValueError) as exc:
                raise ValueError("retention.invalid_clock") from exc
        return _utc(self._clock())

    def disk_status(self) -> dict:
        free = int(shutil.disk_usage(self._data_root).free)
        return {
            "free_bytes": free,
            "threshold_bytes": self._low_disk_bytes,
            "cache_writes_allowed": free >= self._low_disk_bytes,
            "action": "allow" if free >= self._low_disk_bytes else "block_rebuildable_cache",
        }

    def scan_once(self, now: datetime | None = None) -> dict:
        observed = _utc(now) if now is not None else self.now()
        conn, lock = self._repo.conn, self._repo.lock
        with lock:
            candidates = conn.execute(
                "SELECT id, expires_at FROM sessions WHERE expires_at IS NOT NULL ORDER BY id"
            ).fetchall()
            expired = [
                int(row["id"])
                for row in candidates
                if _utc(datetime.fromisoformat(str(row["expires_at"]))) < observed
            ]
            before = self._counts(conn, expired)
            conn.execute("BEGIN IMMEDIATE")
            try:
                if expired:
                    placeholders = ",".join("?" for _ in expired)
                    conn.execute(f"DELETE FROM sessions WHERE id IN ({placeholders})", expired)
                self._fault("after_delete")
                deleted = sum(before.values())
                conn.execute(
                    "INSERT INTO audit_events(action, entity_type, entity_id_hash, result, "
                    "deleted_row_count, created_at) VALUES "
                    "('retention.expired', 'retention', ?, 'success', ?, ?)",
                    (hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:16], deleted, observed.isoformat()),
                )
                self._fault("after_audit")
                self._fault("before_commit")
                conn.execute("COMMIT")
            except BaseException as exc:
                conn.execute("ROLLBACK")
                conn.execute(
                    "INSERT INTO audit_events(action, entity_type, entity_id_hash, result, error_code, created_at) "
                    "VALUES ('retention.failed', 'retention', ?, 'failure', ?, ?)",
                    (
                        hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:16],
                        type(exc).__name__, observed.isoformat(),
                    ),
                )
                raise
        return {
            "now": observed.isoformat(),
            "expired_session_ids": expired,
            "deleted": before,
            "deleted_total": sum(before.values()),
            "disk": self.disk_status(),
        }

    def scan_with_retry(
        self,
        now: datetime | None = None,
        *,
        initial_s: float = 60.0,
        max_attempts: int = 6,
    ) -> dict:
        last: BaseException | None = None
        for attempt in range(1, max_attempts + 1):
            try:
                result = self.scan_once(now)
                result["attempts"] = attempt
                return result
            except ValueError:
                # Invalid injected clocks are operator configuration errors,
                # not transient storage failures.
                raise
            except BaseException as exc:
                last = exc
                if attempt < max_attempts:
                    self._sleep(initial_s * (2 ** (attempt - 1)))
        assert last is not None
        raise last

    def next_scan_at(self, now: datetime | None = None) -> datetime:
        local = (now or self.now()).astimezone()
        candidate = local.replace(hour=3, minute=0, second=0, microsecond=0)
        if candidate <= local:
            candidate += timedelta(days=1)
        return candidate

    def _fault(self, point: str) -> None:
        if self._fault_injector is not None:
            self._fault_injector(point)

    @staticmethod
    def _counts(conn, session_ids: list[int]) -> dict[str, int]:
        if not session_ids:
            return {"sessions": 0, "turns": 0, "transcripts": 0, "summaries": 0}
        placeholders = ",".join("?" for _ in session_ids)
        return {
            "sessions": len(session_ids),
            "turns": int(conn.execute(f"SELECT COUNT(*) FROM turns WHERE session_id IN ({placeholders})", session_ids).fetchone()[0]),
            "transcripts": int(conn.execute(f"SELECT COUNT(*) FROM session_transcripts WHERE session_id IN ({placeholders})", session_ids).fetchone()[0]),
            "summaries": int(conn.execute(f"SELECT COUNT(*) FROM session_summaries WHERE session_id IN ({placeholders})", session_ids).fetchone()[0]),
        }
