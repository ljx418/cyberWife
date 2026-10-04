"""B4-AC08/09 real SQLite/sqlite-vec retention and fail-closed evidence."""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from cyberwife.application.retention_service import RetentionService
from cyberwife.domain.conversation import Turn
from cyberwife.domain.memory import MemoryRecord
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository
from cyberwife.infrastructure.sqlite_repository import SqliteRepository
from cyberwife.infrastructure.vector_index import VectorIndex


ROOT = Path(__file__).resolve().parents[2]
NOW = datetime(2026, 9, 26, 0, 0, 0, tzinfo=timezone.utc)


def seed(repo, memories, age):
    sid = repo.create_session("standard")
    ended = NOW - timedelta(days=age)
    repo.conn.execute(
        "UPDATE sessions SET ended_at=?, expires_at=? WHERE id=?",
        (ended.isoformat(), (ended + timedelta(days=30)).isoformat(), sid),
    )
    repo.create_turn(Turn(id=age, session_id=sid, ordinal=1, user_text=f"第{age}天文本", assistant_text="答复", status="completed"))
    repo.conn.execute("INSERT INTO session_transcripts VALUES (?, ?, ?, ?)", (sid, f"第{age}天逐字稿", str(age), NOW.isoformat()))
    repo.conn.execute("INSERT INTO session_summaries VALUES (?, ?, 3, ?)", (sid, f"第{age}天摘要", NOW.isoformat()))
    memory_id = memories.upsert(
        MemoryRecord(id=0, source_session_id=sid, content=f"长期事实{age}", confidence=.9, created_at=NOW, updated_at=NOW),
        [1.0] + [0.0] * 511,
    )
    return sid, memory_id


def table_counts(repo):
    return {
        name: int(repo.conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0])
        for name in ("sessions", "turns", "session_transcripts", "session_summaries", "memories", "memory_vectors_meta")
    }


def run(args):
    with tempfile.TemporaryDirectory(prefix="cw-b45-") as temporary:
        root = Path(temporary)
        repo = SqliteRepository(root / "retention.db", ROOT / "migrations" / "0001_init.sql")
        memories = SqliteMemoryRepository(repo.conn, repo.lock)
        ids = {age: seed(repo, memories, age) for age in (29, 30, 31)}
        service = RetentionService(repo, clock=lambda: NOW, data_root=args.data_root)
        before = table_counts(repo)
        scan = service.scan_once(NOW)
        after = table_counts(repo)
        memory_31 = memories.get(ids[31][1])
        retry = service.scan_once(NOW)
        audit = [dict(row) for row in repo.conn.execute(
            "SELECT action, entity_type, result, deleted_row_count, error_code FROM audit_events "
            "WHERE action LIKE 'retention.%' ORDER BY id"
        ).fetchall()]
        disk_real = service.disk_status()
        with patch("cyberwife.application.retention_service.shutil.disk_usage") as usage:
            usage.return_value.free = 9 * 1024**3
            disk_low = service.disk_status()

        failures = {}
        for point in ("after_delete", "after_audit", "before_commit"):
            fail_repo = SqliteRepository(root / f"failure-{point}.db", ROOT / "migrations" / "0001_init.sql")
            fail_memories = SqliteMemoryRepository(fail_repo.conn, fail_repo.lock)
            seed(fail_repo, fail_memories, 31)

            def inject(observed, target=point):
                if observed == target:
                    raise RuntimeError(f"fault:{target}")

            failing = RetentionService(fail_repo, clock=lambda: NOW, data_root=args.data_root, fault_injector=inject)
            try:
                failing.scan_once(NOW)
                raised = False
            except RuntimeError:
                raised = True
            failures[point] = {
                "raised": raised,
                "counts": table_counts(fail_repo),
                "failure_audit": int(fail_repo.conn.execute(
                    "SELECT COUNT(*) FROM audit_events WHERE action='retention.failed'"
                ).fetchone()[0]),
            }
            fail_repo.close()

        wrong_dimension_rejected = False
        try:
            VectorIndex(repo.conn).insert(99999, [0.0] * 511)
        except ValueError:
            wrong_dimension_rejected = True

        result = {
            "schema_version": 1,
            "evidence_level": "real_sqlite_sqlite_vec_real_volume_injected_clock",
            "clock": NOW.isoformat(),
            "before": before,
            "scan": scan,
            "after": after,
            "retry_deleted_total": retry["deleted_total"],
            "long_term_memory": {
                "count": memories.layer_counts(),
                "expired_source_detached": memory_31 is not None and memory_31.source_session_id is None,
            },
            "audit": audit,
            "fault_matrix": failures,
            "disk_real": disk_real,
            "disk_low_simulated": disk_low,
            "wrong_dimension_rejected": wrong_dimension_rejected,
        }
        result["pass"] = all((
            scan["expired_session_ids"] == [ids[31][0]],
            after == {"sessions": 2, "turns": 2, "session_transcripts": 2, "session_summaries": 2, "memories": 3, "memory_vectors_meta": 3},
            retry["deleted_total"] == 0,
            result["long_term_memory"]["expired_source_detached"],
            result["long_term_memory"]["count"] == {"source": 3, "fts": 3, "vector": 3, "meta": 3},
            all(item["raised"] and item["failure_audit"] == 1 and item["counts"]["sessions"] == 1 and item["counts"]["turns"] == 1 for item in failures.values()),
            disk_real["free_bytes"] > 0,
            disk_low["cache_writes_allowed"] is False,
            wrong_dimension_rejected,
        ))
        args.evidence.mkdir(parents=True, exist_ok=True)
        (args.evidence / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        repo.close()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-storage", action="store_true")
    parser.add_argument("--data-root", type=Path, default=Path("/home/administrator/.cyberWife"))
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B4/B4.5"))
    args = parser.parse_args()
    if not args.real_storage:
        raise SystemExit(3)
    result = run(args)
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
