"""B4-AC05 purge confirmation, rollback matrix and idempotent retry."""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import httpx

from cyberwife.adapters.speech_embedding_adapter import SpeechEmbeddingAdapter
from cyberwife.application.memory_service import MemoryService
from cyberwife.domain.memory import MemoryRecord
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-session-id", type=int, default=488)
    parser.add_argument("--db", type=Path, default=Path("/home/administrator/.cyberWife/cyberwife.db"))
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--speech-base", default="http://127.0.0.1:8091")
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B4/B4.3-purge"))
    args = parser.parse_args()
    embedding = SpeechEmbeddingAdapter(args.speech_base, timeout_s=120)
    vector = embedding.embed("用于全清回滚的真实向量")
    fault_rows = []
    for point in ("after_indexes", "after_source", "before_commit"):
        with tempfile.TemporaryDirectory(prefix="cyberwife-purge-") as tmp:
            repo = SqliteRepository(Path(tmp) / "fault.db", schema_sql_path=ROOT / "migrations" / "0001_init.sql")
            clean = SqliteMemoryRepository(repo.conn, repo.lock)
            now = datetime.now(timezone.utc)
            clean.upsert(MemoryRecord(0, "回滚事实甲", 0.9, created_at=now, updated_at=now), vector)
            clean.upsert(MemoryRecord(0, "回滚事实乙", 0.9, created_at=now, updated_at=now), vector)

            def inject(current: str, wanted=point) -> None:
                if current == wanted:
                    raise RuntimeError(f"fault:{wanted}")

            failing = SqliteMemoryRepository(repo.conn, repo.lock, fault_injector=inject)
            try:
                failing.purge_all()
            except RuntimeError as exc:
                error = str(exc)
            else:
                error = "not_raised"
            counts = failing.layer_counts()
            fault_rows.append({"point": point, "error": error, "counts": counts, "pass": counts == {"source": 2, "fts": 2, "vector": 2, "meta": 2}})
            repo.close()

    repo = SqliteRepository(args.db, schema_sql_path=ROOT / "migrations" / "0001_init.sql")
    memory_repo = SqliteMemoryRepository(repo.conn, repo.lock)
    service = MemoryService(repo, memory_repo, embedding)
    service.purge_all()
    extraction = service.extract_session(args.real_session_id)
    before = service.layer_counts()
    client = httpx.Client(timeout=120, trust_env=False)
    missing = client.request("DELETE", f"{args.http_base}/api/v1/memories", json={})
    wrong = client.request("DELETE", f"{args.http_base}/api/v1/memories", json={"confirmation": "purge_all"})
    success = client.request("DELETE", f"{args.http_base}/api/v1/memories", json={"confirmation": "PURGE_ALL"})
    retry = client.request("DELETE", f"{args.http_base}/api/v1/memories", json={"confirmation": "PURGE_ALL"})
    after = service.layer_counts()
    integrity = repo.conn.execute("PRAGMA integrity_check").fetchone()[0]
    result = {
        "schema_version": 1,
        "evidence_level": "real_session_live_rest_real_bge_sqlite_vec_plus_deterministic_faults",
        "session_id": args.real_session_id,
        "extraction": extraction,
        "fault_matrix": fault_rows,
        "before": before,
        "missing_confirmation": {"status": missing.status_code, "body": missing.json()},
        "wrong_confirmation": {"status": wrong.status_code, "body": wrong.json()},
        "success": {"status": success.status_code, "body": success.json()},
        "retry": {"status": retry.status_code, "body": retry.json()},
        "after": after,
        "integrity_check": integrity,
    }
    result["pass"] = bool(
        all(item["pass"] for item in fault_rows)
        and before["source"] == 5
        and missing.status_code == 412
        and wrong.status_code == 412
        and success.status_code == 200
        and success.json().get("deleted") == 5
        and retry.status_code == 200
        and retry.json().get("deleted") == 0
        and after == {"source": 0, "fts": 0, "vector": 0, "meta": 0}
        and integrity == "ok"
    )
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    repo.close(); client.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
