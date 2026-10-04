from __future__ import annotations

import sqlite3
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from cyberwife.domain.memory import MemoryRecord
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository
from cyberwife.infrastructure.vector_index import VectorIndex, VectorIndexUnavailable
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


SCHEMA = Path(__file__).resolve().parents[3] / "migrations" / "0001_init.sql"


def make_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", isolation_level=None, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript(SCHEMA.read_text(encoding="utf-8"))
    return conn


def record(content: str = "我喜欢在周日徒步") -> MemoryRecord:
    now = datetime.now(timezone.utc)
    return MemoryRecord(id=0, content=content, confidence=0.91, created_at=now, updated_at=now)


def test_vector_index_fails_closed_without_sqlite_vec() -> None:
    with patch.dict(sys.modules, {"sqlite_vec": None}):
        with pytest.raises(VectorIndexUnavailable, match="sqlite_vec_unavailable"):
            VectorIndex(sqlite3.connect(":memory:"))


def test_memory_upsert_search_delete_all_layers() -> None:
    conn = make_conn()
    repo = SqliteMemoryRepository(conn, threading.RLock())
    vector = [0.0] * 512
    vector[0] = 1.0
    memory_id = repo.upsert(record(), vector)
    assert repo.layer_counts() == {"source": 1, "fts": 1, "vector": 1, "meta": 1}
    found = repo.search("我喜欢在周日徒步", vector)
    assert found[0][0].id == memory_id
    assert repo.delete(memory_id)
    assert repo.layer_counts() == {"source": 0, "fts": 0, "vector": 0, "meta": 0}


@pytest.mark.parametrize(
    "fault_point",
    ["after_source", "after_fts", "after_vector", "after_meta", "after_audit", "before_commit"],
)
def test_upsert_fault_rolls_back_every_layer(fault_point: str) -> None:
    conn = make_conn()

    def inject(point: str) -> None:
        if point == fault_point:
            raise RuntimeError(f"fault:{point}")

    repo = SqliteMemoryRepository(conn, threading.RLock(), fault_injector=inject)
    vector = [0.0] * 512
    vector[0] = 1.0
    with pytest.raises(RuntimeError, match="fault:"):
        repo.upsert(record(), vector)
    assert repo.layer_counts() == {"source": 0, "fts": 0, "vector": 0, "meta": 0}
    assert conn.execute("SELECT COUNT(*) FROM audit_events").fetchone()[0] == 0


def test_edit_replaces_fts_and_vector_atomically() -> None:
    conn = make_conn()
    repo = SqliteMemoryRepository(conn)
    old_vector = [0.0] * 512
    old_vector[0] = 1.0
    memory_id = repo.upsert(record("我喜欢红茶"), old_vector)
    updated = repo.get(memory_id)
    assert updated is not None
    updated.content = "我喜欢绿茶"
    updated.edited = True
    updated.updated_at = datetime.now(timezone.utc)
    new_vector = [0.0] * 512
    new_vector[1] = 1.0
    repo.upsert(updated, new_vector)
    assert repo.search("我喜欢红茶", old_vector, min_score=0.9) == []
    assert repo.search("我喜欢绿茶", new_vector, min_score=0.9)[0][0].edited


def test_purge_fault_rolls_back_source_and_indexes() -> None:
    conn = make_conn()
    vector = [0.0] * 512
    vector[0] = 1.0
    initial = SqliteMemoryRepository(conn)
    initial.upsert(record("事实一"), vector)
    initial.upsert(record("事实二"), vector)

    def inject(point: str) -> None:
        if point == "after_indexes":
            raise RuntimeError("fault:after_indexes")

    failing = SqliteMemoryRepository(conn, fault_injector=inject)
    with pytest.raises(RuntimeError):
        failing.purge_all()
    assert failing.layer_counts() == {"source": 2, "fts": 2, "vector": 2, "meta": 2}


@pytest.mark.parametrize("fault_point", ["after_fts", "after_vector", "after_source", "before_commit"])
def test_delete_fault_rolls_back_every_layer(fault_point: str) -> None:
    conn = make_conn()
    vector = [0.0] * 512
    vector[0] = 1.0
    initial = SqliteMemoryRepository(conn)
    memory_id = initial.upsert(record("必须完整保留"), vector)

    def inject(point: str) -> None:
        if point == fault_point:
            raise RuntimeError(f"fault:{point}")

    failing = SqliteMemoryRepository(conn, fault_injector=inject)
    with pytest.raises(RuntimeError, match="fault:"):
        failing.delete(memory_id)
    assert failing.layer_counts() == {"source": 1, "fts": 1, "vector": 1, "meta": 1}
    assert failing.get(memory_id) is not None


@pytest.mark.parametrize("fault_point", ["after_indexes", "after_source", "before_commit"])
def test_purge_fault_matrix_rolls_back_all_rows(fault_point: str) -> None:
    conn = make_conn()
    vector = [0.0] * 512
    vector[0] = 1.0
    initial = SqliteMemoryRepository(conn)
    initial.upsert(record("事实甲"), vector)
    initial.upsert(record("事实乙"), vector)

    def inject(point: str) -> None:
        if point == fault_point:
            raise RuntimeError(f"fault:{point}")

    failing = SqliteMemoryRepository(conn, fault_injector=inject)
    with pytest.raises(RuntimeError, match="fault:"):
        failing.purge_all()
    assert failing.layer_counts() == {"source": 2, "fts": 2, "vector": 2, "meta": 2}


def _seed_session_business_data(repo: SqliteRepository, memory_repo: SqliteMemoryRepository) -> int:
    from cyberwife.domain.conversation import Session, Turn

    session_id = repo.create_session("standard")
    turn = Turn(id=1, session_id=session_id, ordinal=1, user_text="隐私测试唯一文本", status="completed")
    turn.assistant_text = "不会保留"
    repo.create_turn(turn)
    repo.conn.execute(
        "INSERT INTO session_transcripts(session_id, full_text, sha256, updated_at) VALUES (?, ?, 'x', ?)",
        (session_id, "隐私测试唯一文本", datetime.now(timezone.utc).isoformat()),
    )
    repo.conn.execute(
        "INSERT INTO session_summaries(session_id, summary, token_est, updated_at) VALUES (?, ?, 4, ?)",
        (session_id, "隐私摘要", datetime.now(timezone.utc).isoformat()),
    )
    item = record("用户喜欢紫色风筝")
    item.source_session_id = session_id
    vector = [0.0] * 512
    vector[0] = 1.0
    memory_repo.upsert(item, vector)
    return session_id


def test_session_privacy_purge_removes_every_business_layer(tmp_path) -> None:
    repo = SqliteRepository(tmp_path / "privacy.db", SCHEMA)
    memory_repo = SqliteMemoryRepository(repo.conn, repo.lock)
    session_id = _seed_session_business_data(repo, memory_repo)
    result = memory_repo.purge_session_business_data(session_id)
    assert result == {
        "sessions": 1, "turns": 1, "transcripts": 1, "summaries": 1,
        "memories": 1, "wal_checkpoint_busy": 0,
    }
    for table in ("sessions", "turns", "session_transcripts", "session_summaries", "memories"):
        assert repo.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] == 0
    assert memory_repo.layer_counts() == {"source": 0, "fts": 0, "vector": 0, "meta": 0}
    audit = repo.conn.execute(
        "SELECT action, entity_id_hash FROM audit_events WHERE action='session.no_record'"
    ).fetchone()
    assert audit is not None and "隐私" not in audit["entity_id_hash"]
    repo.close()


@pytest.mark.parametrize("fault_point", ["after_indexes", "after_source", "before_commit"])
def test_session_privacy_purge_fault_rolls_back_all_business_layers(tmp_path, fault_point: str) -> None:
    repo = SqliteRepository(tmp_path / f"privacy-{fault_point}.db", SCHEMA)
    initial = SqliteMemoryRepository(repo.conn, repo.lock)
    session_id = _seed_session_business_data(repo, initial)

    def inject(point: str) -> None:
        if point == fault_point:
            raise RuntimeError(f"fault:{point}")

    failing = SqliteMemoryRepository(repo.conn, repo.lock, fault_injector=inject)
    with pytest.raises(RuntimeError, match="fault:"):
        failing.purge_session_business_data(session_id)
    assert repo.conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0] == 1
    assert repo.conn.execute("SELECT COUNT(*) FROM turns").fetchone()[0] == 1
    assert repo.conn.execute("SELECT COUNT(*) FROM session_transcripts").fetchone()[0] == 1
    assert repo.conn.execute("SELECT COUNT(*) FROM session_summaries").fetchone()[0] == 1
    assert failing.layer_counts() == {"source": 1, "fts": 1, "vector": 1, "meta": 1}
    repo.close()
