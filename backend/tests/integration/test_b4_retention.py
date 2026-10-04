from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from cyberwife.application.retention_service import RetentionService
from cyberwife.domain.conversation import Turn
from cyberwife.domain.memory import MemoryRecord
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


ROOT = Path(__file__).resolve().parents[3]
NOW = datetime(2026, 9, 26, 0, 0, 0, tzinfo=timezone.utc)


def stack(tmp_path, *, fault=None, sleep=lambda _: None):
    repo = SqliteRepository(tmp_path / "retention.db", ROOT / "migrations" / "0001_init.sql")
    memories = SqliteMemoryRepository(repo.conn, repo.lock)
    service = RetentionService(repo, clock=lambda: NOW, data_root=tmp_path, fault_injector=fault, sleep=sleep)
    return repo, memories, service


def seed(repo, memories, age_days: int, *, suffix: str):
    session_id = repo.create_session("standard")
    ended = NOW - timedelta(days=age_days)
    repo.conn.execute(
        "UPDATE sessions SET ended_at=?, expires_at=? WHERE id=?",
        (ended.isoformat(), (ended + timedelta(days=30)).isoformat(), session_id),
    )
    turn = Turn(id=session_id, session_id=session_id, ordinal=1, user_text=f"文本{suffix}", assistant_text="回复", status="completed")
    repo.create_turn(turn)
    repo.conn.execute(
        "INSERT INTO session_transcripts VALUES (?, ?, ?, ?)",
        (session_id, f"逐字稿{suffix}", suffix, NOW.isoformat()),
    )
    repo.conn.execute(
        "INSERT INTO session_summaries VALUES (?, ?, ?, ?)",
        (session_id, f"摘要{suffix}", 3, NOW.isoformat()),
    )
    memory = MemoryRecord(
        id=0, source_session_id=session_id, content=f"长期记忆{suffix}", confidence=.9,
        created_at=NOW, updated_at=NOW,
    )
    vector = [1.0] + [0.0] * 511
    memory_id = memories.upsert(memory, vector)
    return session_id, memory_id


def test_29_30_31_day_boundary_and_long_term_memory_preserved(tmp_path):
    repo, memories, service = stack(tmp_path)
    ids = {age: seed(repo, memories, age, suffix=str(age)) for age in (29, 30, 31)}
    result = service.scan_once(NOW)
    assert result["expired_session_ids"] == [ids[31][0]]
    assert repo.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 2
    assert repo.conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0] == 2
    assert repo.conn.execute("SELECT COUNT(*) FROM session_transcripts").fetchone()[0] == 2
    assert repo.conn.execute("SELECT COUNT(*) FROM session_summaries").fetchone()[0] == 2
    assert memories.layer_counts() == {"source": 3, "fts": 3, "vector": 3, "meta": 3}
    retained = memories.get(ids[31][1])
    assert retained is not None and retained.source_session_id is None
    assert service.scan_once(NOW)["deleted_total"] == 0


@pytest.mark.parametrize("fault_point", ["after_delete", "after_audit", "before_commit"])
def test_retention_failure_rolls_back_entire_batch_and_audits(tmp_path, fault_point):
    calls = []

    def fault(point):
        if point == fault_point:
            raise RuntimeError("injected")

    repo, memories, service = stack(tmp_path, fault=fault)
    seed(repo, memories, 31, suffix="rollback")
    with pytest.raises(RuntimeError, match="injected"):
        service.scan_once(NOW)
    assert repo.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    assert repo.conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0] == 1
    assert memories.layer_counts() == {"source": 1, "fts": 1, "vector": 1, "meta": 1}
    assert repo.conn.execute("SELECT COUNT(*) FROM audit_events WHERE action='retention.failed'").fetchone()[0] == 1


def test_retry_backoff_then_idempotent_success(tmp_path):
    failures = {"remaining": 2}
    sleeps = []

    def fault(point):
        if point == "before_commit" and failures["remaining"]:
            failures["remaining"] -= 1
            raise RuntimeError("transient")

    repo, memories, service = stack(tmp_path, fault=fault, sleep=sleeps.append)
    seed(repo, memories, 31, suffix="retry")
    result = service.scan_with_retry(NOW, initial_s=1, max_attempts=6)
    assert result["attempts"] == 3 and sleeps == [1, 2]
    assert result["deleted"]["sessions"] == 1
    assert service.scan_once(NOW)["deleted_total"] == 0


def test_invalid_clock_and_low_disk_are_fail_safe(tmp_path, monkeypatch):
    repo, memories, service = stack(tmp_path)
    seed(repo, memories, 29, suffix="safe")
    monkeypatch.setenv("RETENTION_NOW", "not-a-clock")
    with pytest.raises(ValueError, match="retention.invalid_clock"):
        service.scan_with_retry()
    assert repo.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    with patch("cyberwife.application.retention_service.shutil.disk_usage") as usage:
        usage.return_value.free = 9 * 1024**3
        assert service.disk_status()["cache_writes_allowed"] is False
    assert repo.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
