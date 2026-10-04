"""M1-07 integration test: 0001_init.sql 迁移可从空库运行 + schema 完整。"""
import sqlite3
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA = REPO_ROOT / "migrations" / "0001_init.sql"


@pytest.fixture
def fresh_db():
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "test.db"
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        yield conn, db_path
        conn.close()


def test_schema_file_exists():
    assert SCHEMA.exists(), f"schema file not found: {SCHEMA}"
    content = SCHEMA.read_text(encoding="utf-8")
    # 校验关键表名全部出现
    expected_tables = [
        "consents", "profiles", "profile_history",
        "asset_versions", "active_assets",
        "sessions", "turns",
        "memories", "session_transcripts", "session_summaries",
        "memory_fts", "memory_vectors_meta",
        "audit_events", "onboarding_drafts",
        "schema_migrations",
    ]
    for t in expected_tables:
        assert f"TABLE IF NOT EXISTS {t}" in content or f"TABLE IF NOT EXISTS" in content and t in content, f"missing {t}"


def test_migration_runs_on_empty_db(fresh_db):
    conn, _ = fresh_db
    sql = SCHEMA.read_text(encoding="utf-8")
    conn.executescript(sql)
    cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
    tables = [row[0] for row in cur.fetchall()]
    expected = {
        "consents", "profiles", "profile_history",
        "asset_versions", "active_assets",
        "sessions", "turns",
        "memories", "session_transcripts", "session_summaries",
        "memory_fts", "memory_vectors_meta",
        "audit_events", "onboarding_drafts",
        "schema_migrations",
    }
    missing = expected - set(tables)
    assert not missing, f"missing tables: {missing}"


def test_migration_idempotent(fresh_db):
    """同一 schema 执行两次不应破坏原库（PRAGMA IF NOT EXISTS + INSERT OR IGNORE）。"""
    conn, _ = fresh_db
    sql = SCHEMA.read_text(encoding="utf-8")
    conn.executescript(sql)
    # 插入一条测试数据
    conn.execute(
        "INSERT INTO profiles(id, name, user_nickname, version, updated_at) VALUES (1, 'A', 'B', 0, datetime('now'))"
    )
    conn.commit()
    # 再次执行
    conn.executescript(sql)
    # profile 仍在
    row = conn.execute("SELECT name FROM profiles WHERE id=1").fetchone()
    assert row[0] == "A", "profile data lost after re-running schema"


def test_schema_migrations_recorded(fresh_db):
    conn, _ = fresh_db
    sql = SCHEMA.read_text(encoding="utf-8")
    conn.executescript(sql)
    row = conn.execute("SELECT version FROM schema_migrations WHERE version=1").fetchone()
    assert row is not None
    assert row[0] == 1


def test_audit_events_constraints(fresh_db):
    """audit_events.action / entity_type / result 受 CHECK 约束。"""
    conn, _ = fresh_db
    sql = SCHEMA.read_text(encoding="utf-8")
    conn.executescript(sql)
    # 合法的枚举值应能插入
    conn.execute(
        "INSERT INTO audit_events(action, entity_type, entity_id_hash, result, created_at) "
        "VALUES ('memory.committed', 'memory', 'abcdef0123456789', 'success', datetime('now'))"
    )
    conn.commit()
    # 非法 entity_type 应被拒
    import sqlite3 as _sq
    with pytest.raises(_sq.IntegrityError):
        conn.execute(
            "INSERT INTO audit_events(action, entity_type, entity_id_hash, result, created_at) "
            "VALUES ('memory.committed', 'invalid_type', 'abcdef0123456789', 'success', datetime('now'))"
        )


def test_onboarding_draft_singleton_constraint(fresh_db):
    """onboarding_drafts 必须 id=1（CHECK 约束）。"""
    conn, _ = fresh_db
    sql = SCHEMA.read_text(encoding="utf-8")
    conn.executescript(sql)
    conn.execute(
        "INSERT INTO onboarding_drafts(id, step_completed, updated_at) VALUES (1, 0, datetime('now'))"
    )
    conn.commit()
    # 插入 id=2 应被 CHECK 拒绝
    import sqlite3 as _sq
    with pytest.raises(_sq.IntegrityError):
        conn.execute(
            "INSERT INTO onboarding_drafts(id, step_completed, updated_at) VALUES (2, 0, datetime('now'))"
        )
