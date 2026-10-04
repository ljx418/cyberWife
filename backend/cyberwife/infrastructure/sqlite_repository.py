"""SqliteRepository — 数据访问层（M1 阶段含 Profile/OnboardingDraft，剩余表 schema 在 migrations/0001_init.sql）。

按 implementation-contracts §2/§3 表与 ports/repositories.py 抽象。
"""
from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cyberwife.domain.conversation import Session, Turn, RecordingPolicy, SessionState
from cyberwife.domain.memory import MemoryRecord, OnboardingDraft
from cyberwife.domain.profile import (
    AssetKind,
    AssetStatus,
    AssetVersion,
    Consent,
    ConsentScope,
    Profile,
)


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteRepository:
    """sqlite3 仓库；多线程安全用 check_same_thread=False + 自管 lock。"""

    def __init__(self, db_path: str | Path, schema_sql_path: Optional[str | Path] = None) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False, isolation_level=None)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        # Privacy erasure must overwrite deleted payload cells rather than
        # leave their previous bytes on SQLite's freelist.
        self._conn.execute("PRAGMA secure_delete=ON")
        self._conn.row_factory = sqlite3.Row
        if schema_sql_path:
            self._apply_schema(Path(schema_sql_path))

    @property
    def conn(self) -> sqlite3.Connection:
        return self._conn

    @property
    def lock(self) -> threading.RLock:
        return self._lock

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def _apply_schema(self, schema_path: Path) -> None:
        if not schema_path.exists():
            return
        sql = schema_path.read_text(encoding="utf-8")
        with self._lock:
            self._conn.executescript(sql)

    # ── Profile ─────────────────────────────────────────────────────────
    def get_profile(self) -> Optional[Profile]:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, name, user_nickname, persona, relationship_context, "
                "example_dialogue, version, updated_at FROM profiles LIMIT 1"
            ).fetchone()
        if row is None:
            return None
        return Profile(
            id=row["id"],
            name=row["name"],
            user_nickname=row["user_nickname"],
            persona=row["persona"] or "",
            relationship_context=row["relationship_context"] or "",
            example_dialogue=row["example_dialogue"] or "",
            version=row["version"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def upsert_profile(self, profile: Profile) -> None:
        with self._lock:
            existing = self._conn.execute("SELECT id FROM profiles LIMIT 1").fetchone()
            if existing:
                self._conn.execute(
                    "UPDATE profiles SET name=?, user_nickname=?, persona=?, "
                    "relationship_context=?, example_dialogue=?, version=?, updated_at=? WHERE id=?",
                    (
                        profile.name,
                        profile.user_nickname,
                        profile.persona,
                        profile.relationship_context,
                        profile.example_dialogue,
                        profile.version,
                        _utcnow(),
                        existing["id"],
                    ),
                )
            else:
                self._conn.execute(
                    "INSERT INTO profiles(name, user_nickname, persona, relationship_context, "
                    "example_dialogue, version, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        profile.name,
                        profile.user_nickname,
                        profile.persona,
                        profile.relationship_context,
                        profile.example_dialogue,
                        profile.version,
                        _utcnow(),
                    ),
                )

    def save_profile(self, profile: Profile, expected_version: int) -> Profile:
        """Atomically check version, archive the old snapshot, and save."""
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute("SELECT * FROM profiles WHERE id=1").fetchone()
                current = int(row["version"]) if row is not None else 0
                if expected_version != current:
                    raise ValueError("asset.version_conflict")
                if row is not None:
                    snapshot = {key: row[key] for key in row.keys()}
                    self._conn.execute(
                        "INSERT INTO profile_history(profile_id, version, snapshot_json, created_at) VALUES (1, ?, ?, ?)",
                        (current, json.dumps(snapshot, ensure_ascii=False), _utcnow()),
                    )
                profile.id = 1
                profile.version = current + 1
                profile.updated_at = datetime.now(timezone.utc)
                self._conn.execute(
                    "INSERT INTO profiles(id, name, user_nickname, persona, relationship_context, example_dialogue, version, updated_at) "
                    "VALUES (1, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET "
                    "name=excluded.name, user_nickname=excluded.user_nickname, persona=excluded.persona, "
                    "relationship_context=excluded.relationship_context, example_dialogue=excluded.example_dialogue, "
                    "version=excluded.version, updated_at=excluded.updated_at",
                    (profile.name, profile.user_nickname, profile.persona, profile.relationship_context,
                     profile.example_dialogue, profile.version, profile.updated_at.isoformat()),
                )
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        return profile

    # ── Consent and versioned assets ────────────────────────────────────
    def list_consents(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM consents ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def consent_active(self, scope: str) -> bool:
        with self._lock:
            row = self._conn.execute(
                "SELECT granted FROM consents WHERE scope IN (?, 'all') ORDER BY id DESC LIMIT 1",
                (scope,),
            ).fetchone()
        return bool(row and row["granted"])

    def grant_consent(self, scope: str, policy_version: str) -> dict:
        if scope not in {"portrait", "voice", "all"}:
            raise ValueError("invalid_scope")
        now = _utcnow()
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO consents(scope, policy_version, granted, granted_at) VALUES (?, ?, 1, ?)",
                (scope, policy_version, now),
            )
            self._audit_event("consent.granted", "consent", f"{scope}:{cursor.lastrowid}")
        return dict(self._conn.execute("SELECT * FROM consents WHERE id=?", (cursor.lastrowid,)).fetchone())

    def revoke_consent(self, scope: str) -> dict:
        if scope not in {"portrait", "voice", "all"}:
            raise ValueError("invalid_scope")
        now = _utcnow()
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                targets = ("portrait", "voice") if scope == "all" else (scope,)
                for target in targets:
                    self._conn.execute(
                        "INSERT INTO consents(scope, policy_version, granted, revoked_at) VALUES (?, 'v1', 0, ?)",
                        (target, now),
                    )
                    self._conn.execute("DELETE FROM active_assets WHERE kind=?", (target,))
                    self._conn.execute("UPDATE asset_versions SET status='archived' WHERE kind=? AND status='active'", (target,))
                self._audit_event("consent.revoked", "consent", scope)
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        return {"scope": scope, "granted": False, "revoked_at": now}

    def create_asset_version(self, metadata: dict) -> dict:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO asset_versions(kind, relative_path, sha256, size_bytes, status, filename_or_revision, created_at) "
                "VALUES (?, ?, ?, ?, 'previewed', ?, ?)",
                (metadata["kind"], metadata["relative_path"], metadata["sha256"], metadata["size_bytes"], metadata["filename_or_revision"], _utcnow()),
            )
            self._audit_event("asset.previewed", "asset", cursor.lastrowid)
            return self.get_asset_version(int(cursor.lastrowid))

    def get_asset_version(self, asset_id: int) -> dict | None:
        row = self._conn.execute("SELECT * FROM asset_versions WHERE id=?", (asset_id,)).fetchone()
        return dict(row) if row else None

    def list_asset_versions(self, kind: str) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT v.*, CASE WHEN a.asset_id=v.id THEN 1 ELSE 0 END AS is_active "
                "FROM asset_versions v LEFT JOIN active_assets a ON a.kind=v.kind WHERE v.kind=? ORDER BY v.id DESC",
                (kind,),
            ).fetchall()
        return [dict(row) for row in rows]

    def get_active_asset(self, kind: str) -> dict | None:
        if kind not in {"portrait", "voice"}:
            raise ValueError("invalid_asset_kind")
        with self._lock:
            row = self._conn.execute(
                "SELECT v.* FROM active_assets a JOIN asset_versions v ON v.id=a.asset_id "
                "WHERE a.kind=? AND v.kind=? AND v.status='active'",
                (kind, kind),
            ).fetchone()
        return dict(row) if row else None

    def activate_asset(self, asset_id: int, *, fault_injector=None, action: str = "asset.activated") -> dict:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                row = self._conn.execute("SELECT * FROM asset_versions WHERE id=?", (asset_id,)).fetchone()
                if row is None:
                    raise KeyError(asset_id)
                kind = str(row["kind"])
                if not self.consent_active(kind):
                    raise PermissionError("auth.consent_required")
                self._conn.execute("UPDATE asset_versions SET status='archived' WHERE kind=? AND status='active'", (kind,))
                if fault_injector:
                    fault_injector("after_archive")
                self._conn.execute("UPDATE asset_versions SET status='active' WHERE id=?", (asset_id,))
                self._conn.execute(
                    "INSERT INTO active_assets(kind, asset_id) VALUES (?, ?) ON CONFLICT(kind) DO UPDATE SET asset_id=excluded.asset_id",
                    (kind, asset_id),
                )
                if fault_injector:
                    fault_injector("after_pointer")
                self._audit_event(action, "asset", asset_id)
                if fault_injector:
                    fault_injector("before_commit")
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise
        result = self.get_asset_version(asset_id)
        assert result is not None
        result["is_active"] = 1
        return result

    def restore_previous_asset(self, kind: str) -> dict:
        with self._lock:
            current = self._conn.execute("SELECT asset_id FROM active_assets WHERE kind=?", (kind,)).fetchone()
            params = [kind]
            sql = "SELECT id FROM asset_versions WHERE kind=? AND status IN ('archived','previewed')"
            if current is not None:
                sql += " AND id<>?"
                params.append(int(current["asset_id"]))
            row = self._conn.execute(sql + " ORDER BY id DESC LIMIT 1", params).fetchone()
        if row is None:
            raise KeyError(kind)
        return self.activate_asset(int(row["id"]), action="asset.rollback")

    def _audit_event(self, action: str, entity_type: str, entity_id) -> None:
        import hashlib
        digest = hashlib.sha256(f"{entity_type}:{entity_id}".encode()).hexdigest()[:16]
        self._conn.execute(
            "INSERT INTO audit_events(action, entity_type, entity_id_hash, result, created_at) VALUES (?, ?, ?, 'success', ?)",
            (action, entity_type, digest, _utcnow()),
        )
    # ── OnboardingDraft ──────────────────────────────────────────────────
    def get_onboarding_draft(self) -> OnboardingDraft:
        with self._lock:
            row = self._conn.execute(
                "SELECT id, consent_granted, step_completed, asset_consent_at, "
                "profile_draft_json, settings_json, device_snapshot_json, updated_at "
                "FROM onboarding_drafts WHERE id=1"
            ).fetchone()
        if row is None:
            d = OnboardingDraft()
            self.upsert_onboarding_draft(d)
            return d
        return OnboardingDraft(
            id=row["id"],
            consent_granted=bool(row["consent_granted"]),
            step_completed=row["step_completed"],
            asset_consent_at=datetime.fromisoformat(row["asset_consent_at"]) if row["asset_consent_at"] else None,
            profile_draft_json=json.loads(row["profile_draft_json"] or "{}"),
            settings_json=json.loads(row["settings_json"] or "{}"),
            device_snapshot_json=json.loads(row["device_snapshot_json"] or "{}"),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def upsert_onboarding_draft(self, draft: OnboardingDraft) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO onboarding_drafts(id, consent_granted, step_completed, "
                "asset_consent_at, profile_draft_json, settings_json, device_snapshot_json, updated_at) "
                "VALUES (1, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET consent_granted=excluded.consent_granted, "
                "step_completed=excluded.step_completed, asset_consent_at=excluded.asset_consent_at, "
                "profile_draft_json=excluded.profile_draft_json, settings_json=excluded.settings_json, "
                "device_snapshot_json=excluded.device_snapshot_json, updated_at=excluded.updated_at",
                (
                    int(draft.consent_granted),
                    draft.step_completed,
                    draft.asset_consent_at.isoformat() if draft.asset_consent_at else None,
                    json.dumps(draft.profile_draft_json, ensure_ascii=False),
                    json.dumps(draft.settings_json, ensure_ascii=False),
                    json.dumps(draft.device_snapshot_json, ensure_ascii=False),
                    _utcnow(),
                ),
            )

    # ── Conversation ─────────────────────────────────────────────────────
    def create_session(self, recording_policy: str = "standard") -> int:
        if recording_policy not in {"standard", "none"}:
            raise ValueError("recording_policy must be standard or none")
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO sessions(started_at, recording_policy) VALUES (?, ?)",
                (_utcnow(), recording_policy),
            )
            return int(cursor.lastrowid)

    def end_session(self, session_id: int, ended_at: datetime) -> bool:
        expires_at = ended_at.timestamp() + 30 * 86400
        expiry = datetime.fromtimestamp(expires_at, timezone.utc).isoformat()
        with self._lock:
            cursor = self._conn.execute(
                "UPDATE sessions SET ended_at=?, expires_at=? WHERE id=?",
                (ended_at.isoformat(), expiry, session_id),
            )
            return cursor.rowcount == 1

    def create_turn(self, turn: Turn, *, persist_text: bool = True) -> int:
        with self._lock:
            cursor = self._conn.execute(
                "INSERT INTO turns(session_id, ordinal, user_text, assistant_text, status, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (
                    turn.session_id,
                    turn.ordinal,
                    turn.user_text if persist_text else "",
                    turn.assistant_text if persist_text else "",
                    turn.status,
                    turn.created_at.isoformat(),
                ),
            )
            return int(cursor.lastrowid)

    def update_turn(self, turn: Turn, *, persist_text: bool = True) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE turns SET user_text=?, assistant_text=?, status=? "
                "WHERE session_id=? AND ordinal=?",
                (
                    turn.user_text if persist_text else "",
                    turn.assistant_text if persist_text else "",
                    turn.status,
                    turn.session_id,
                    turn.ordinal,
                ),
            )

    def list_session_turns(self, session_id: int) -> list[Turn]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT id, session_id, ordinal, user_text, assistant_text, status, created_at "
                "FROM turns WHERE session_id=? ORDER BY ordinal",
                (session_id,),
            ).fetchall()
        return [
            Turn(
                id=int(row["id"]),
                session_id=int(row["session_id"]),
                ordinal=int(row["ordinal"]),
                user_text=str(row["user_text"]),
                assistant_text=str(row["assistant_text"]),
                status=str(row["status"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]
