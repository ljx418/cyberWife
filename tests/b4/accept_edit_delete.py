"""B4-AC03/04 real-session edit and four-layer delete acceptance."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import httpx

from cyberwife.adapters.speech_embedding_adapter import SpeechEmbeddingAdapter
from cyberwife.application.memory_service import MemoryService
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-session-id", type=int, default=488)
    parser.add_argument("--db", type=Path, default=Path("/home/administrator/.cyberWife/cyberwife.db"))
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--speech-base", default="http://127.0.0.1:8091")
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B4/B4.3-edit-delete"))
    args = parser.parse_args()
    repo = SqliteRepository(args.db, schema_sql_path=ROOT / "migrations" / "0001_init.sql")
    memory_repo = SqliteMemoryRepository(repo.conn, repo.lock)
    embedding = SpeechEmbeddingAdapter(args.speech_base, timeout_s=120)
    service = MemoryService(repo, memory_repo, embedding)
    service.purge_all()
    extraction = service.extract_session(args.real_session_id)
    records = memory_repo.list_all()
    target = next(item for item in records if item.content == "用户喜欢红茶")
    delete_target = next(item for item in records if item.content == "用户住在杭州")
    client = httpx.Client(timeout=120, trust_env=False)
    before = service.layer_counts()
    old_exact_before = client.get(f"{args.http_base}/api/v1/memories", params={"q": "用户喜欢红茶"}).json()["items"]
    edited = client.patch(
        f"{args.http_base}/api/v1/memories/{target.id}", json={"content": "用户喜欢绿茶"}
    )
    edited.raise_for_status()
    old_after = client.get(f"{args.http_base}/api/v1/memories", params={"q": "用户喜欢红茶"}).json()["items"]
    new_after = client.get(f"{args.http_base}/api/v1/memories", params={"q": "我爱喝哪种绿茶"}).json()["items"]
    after_edit = service.layer_counts()
    deleted = client.delete(f"{args.http_base}/api/v1/memories/{delete_target.id}")
    deleted.raise_for_status()
    query_results = {}
    for label, query in {
        "exact": "用户住在杭州",
        "fuzzy": "杭州",
        "semantic": "我住在哪里",
    }.items():
        response = client.get(f"{args.http_base}/api/v1/memories", params={"q": query})
        response.raise_for_status()
        query_results[label] = response.json()["items"]
    after_delete = service.layer_counts()
    audit = [dict(row) for row in repo.conn.execute(
        "SELECT action, result, deleted_row_count, fts_count_before, fts_count_after, "
        "vector_count_before, vector_count_after FROM audit_events "
        "WHERE action IN ('memory.updated','memory.deleted') ORDER BY id DESC LIMIT 4"
    ).fetchall()]
    result = {
        "schema_version": 1,
        "evidence_level": "real_session_real_bge_sqlite_vec_live_rest",
        "session_id": args.real_session_id,
        "extraction": extraction,
        "before": before,
        "old_exact_before": old_exact_before,
        "edited": edited.json(),
        "old_content_after_count": sum(item["content"] == "用户喜欢红茶" for item in old_after),
        "new_content_hit": any(item["id"] == target.id and item["content"] == "用户喜欢绿茶" for item in new_after),
        "after_edit": after_edit,
        "deleted_id": delete_target.id,
        "delete_queries": query_results,
        "after_delete": after_delete,
        "audit": audit,
    }
    result["pass"] = bool(
        old_exact_before
        and edited.json().get("edited") is True
        and result["old_content_after_count"] == 0
        and result["new_content_hit"]
        and after_edit == before
        and all(not any(item["id"] == delete_target.id for item in items) for items in query_results.values())
        and after_delete == {key: value - 1 for key, value in before.items()}
        and any(item["action"] == "memory.deleted" for item in audit)
    )
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    client.request("DELETE", f"{args.http_base}/api/v1/memories", json={"confirmation": "PURGE_ALL"})
    repo.close()
    client.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
