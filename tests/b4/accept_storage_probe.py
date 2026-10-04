"""B4.1 real BGE + sqlite-vec functional and rollback acceptance."""
from __future__ import annotations

import argparse
import json
import sqlite3
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from cyberwife.adapters.bge_embedding_adapter import BgeEmbeddingAdapter
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.domain.memory import MemoryRecord
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    entry = ModelRegistry(ROOT).get("bge-small-zh-v1.5")
    if entry is None:
        raise SystemExit("embedding registry entry missing")
    started = time.perf_counter()
    embedding = BgeEmbeddingAdapter(entry.absolute_path, device="cpu")
    vectors = embedding.embed_batch(["我喜欢周日徒步", "周末我常去爬山"])
    load_embed_ms = round((time.perf_counter() - started) * 1000, 3)

    with tempfile.TemporaryDirectory(prefix="cyberwife-b4-") as tmp:
        conn = sqlite3.connect(str(Path(tmp) / "accept.db"), isolation_level=None, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.executescript((ROOT / "migrations" / "0001_init.sql").read_text(encoding="utf-8"))
        repo = SqliteMemoryRepository(conn, threading.RLock())
        now = datetime.now(timezone.utc)
        memory_id = repo.upsert(
            MemoryRecord(id=0, content="我喜欢周日徒步", confidence=0.93, created_at=now, updated_at=now),
            vectors[0],
        )
        hits = repo.search("周末有什么爱好", vectors[1], min_score=0.55)
        before_fault = repo.layer_counts()

        def inject(point: str) -> None:
            if point == "after_vector":
                raise RuntimeError("injected_after_vector")

        failing = SqliteMemoryRepository(conn, fault_injector=inject)
        try:
            failing.upsert(
                MemoryRecord(id=0, content="不应留下的事实", confidence=0.99, created_at=now, updated_at=now),
                vectors[0],
            )
        except RuntimeError as exc:
            fault = str(exc)
        else:
            fault = "not_raised"
        after_fault = repo.layer_counts()
        result = {
            "schema_version": 1,
            "evidence_level": "real_bge_real_sqlite_vec_temporary_database",
            "embedding_health": embedding.health(),
            "embedding_ms_including_load": load_embed_ms,
            "vector_dim": len(vectors[0]),
            "memory_id": memory_id,
            "semantic_hit_ids": [item[0].id for item in hits],
            "before_fault": before_fault,
            "after_fault": after_fault,
            "fault": fault,
            "pass": bool(
                len(vectors[0]) == 512
                and hits
                and hits[0][0].id == memory_id
                and before_fault == after_fault
                and fault == "injected_after_vector"
            ),
        }
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
