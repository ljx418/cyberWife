from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from cyberwife.application.memory_service import MemoryService
from cyberwife.application.prompt_compiler import PromptCompiler, estimate_tokens
from cyberwife.domain.conversation import Turn
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


SCHEMA = Path(__file__).resolve().parents[3] / "migrations" / "0001_init.sql"


class _Embedding:
    def embed(self, text: str) -> list[float]:
        vector = [0.0] * 512
        vector[0] = 1.0
        return vector

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self.embed(text) for text in texts]


def make_service(tmp_path):
    repo = SqliteRepository(tmp_path / "memory.db", schema_sql_path=SCHEMA)
    memory_repo = SqliteMemoryRepository(repo.conn, repo.lock)
    return repo, memory_repo, MemoryService(repo, memory_repo, _Embedding())


def add_turn(repo, session_id: int, ordinal: int, text: str, status: str = "completed") -> None:
    turn = Turn(
        id=ordinal,
        session_id=session_id,
        ordinal=ordinal,
        user_text=text,
        assistant_text="知道了",
        status=status,
        created_at=datetime.now(timezone.utc),
    )
    repo.create_turn(turn)


def test_extract_commits_stable_keeps_temporary_in_process_and_skips_cancelled(tmp_path) -> None:
    repo, memory_repo, service = make_service(tmp_path)
    session_id = repo.create_session("standard")
    add_turn(repo, session_id, 1, "我喜欢红茶。我的生日是五月六日。")
    add_turn(repo, session_id, 2, "今天天气不错")
    add_turn(repo, session_id, 3, "我住在杭州", status="cancelled")
    result = service.extract_session(session_id)
    assert len(result["committed_ids"]) == 2
    assert result["pending_count"] == 1
    assert memory_repo.layer_counts() == {"source": 2, "fts": 2, "vector": 2, "meta": 2}
    assert all(item["confidence"] < 0.8 for item in service.candidates(session_id))
    assert all(item.content != "用户住在杭州" for item in memory_repo.list_all())


def test_recall_and_prompt_are_bounded_and_hide_retrieval_details(tmp_path) -> None:
    repo, _, service = make_service(tmp_path)
    session_id = repo.create_session("standard")
    for ordinal, text in enumerate(
        ["我喜欢红茶", "我喜欢徒步", "我住在杭州", "我叫小林", "我对花生过敏"], 1
    ):
        add_turn(repo, session_id, ordinal, text)
    service.extract_session(session_id)
    memories = service.prompt_memories("周末有什么爱好")
    assert 1 <= len(memories) <= 4
    assert sum(estimate_tokens(content) for content, _ in memories) <= 800
    compiled = PromptCompiler().compile(
        profile={"name": "她", "persona": "温柔", "relationship_context": "伴侣"},
        memories=memories,
        user_input="周末做什么？",
    )
    assert "sqlite" not in compiled.memories.lower()
    assert "vector" not in compiled.memories.lower()
    assert "以下是你记得的" in compiled.memories


def test_extract_is_idempotent_by_normalized_content(tmp_path) -> None:
    repo, memory_repo, service = make_service(tmp_path)
    session_id = repo.create_session("standard")
    add_turn(repo, session_id, 1, "我喜欢红茶")
    first = service.extract_session(session_id)
    second = service.extract_session(session_id)
    assert len(first["committed_ids"]) == 1
    assert second["committed_ids"] == []
    assert memory_repo.layer_counts()["source"] == 1


def test_composite_query_is_split_and_temporal_fillers_are_removed() -> None:
    assert MemoryService._query_clauses("我周末喜欢喝什么，住在哪里？") == [
        "我喜欢喝什么",
        "我住在哪里",
    ]
