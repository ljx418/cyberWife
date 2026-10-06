"""Stable-fact extraction, candidate policy and bounded memory retrieval."""
from __future__ import annotations

import re
import threading
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Iterable

from cyberwife.application.prompt_compiler import estimate_tokens
from cyberwife.domain.memory import MemoryRecord


@dataclass(frozen=True)
class MemoryCandidate:
    content: str
    confidence: float
    source_session_id: int
    source_turn_id: int
    reason: str


class MemoryService:
    """Keeps uncertain candidates in process and persists only stable facts."""

    _STABLE_PATTERNS = (
        (re.compile(r"我叫(.{1,24}?)(?=我喜欢|我住在|我的生日|我对|$)"), "用户叫{0}", 0.96, "identity"),
        (re.compile(r"我住在(.{1,40}?)(?=我叫|我喜欢|我的生日|我对|$)"), "用户住在{0}", 0.92, "residence"),
        (re.compile(r"我喜欢(.{1,60}?)(?=我叫|我住在|我的生日|我对|$)"), "用户喜欢{0}", 0.90, "preference"),
        (re.compile(r"我的生日(?:是|在)(.{1,24}?)(?=我叫|我喜欢|我住在|我对|$)"), "用户生日是{0}", 0.95, "birthday"),
        (re.compile(r"我对(.{1,30}?)过敏"), "用户对{0}过敏", 0.98, "safety"),
    )
    _TEMPORARY = re.compile(r"今天|现在|刚才|待会|可能|也许|天气")
    _TEMPORARY_CLAUSE = re.compile(
        r"(?:今天|现在|刚才|待会|也许).+?(?=(?:今天|现在|刚才|待会|也许)|$)"
    )

    def __init__(self, session_repository, memory_repository, embedding) -> None:
        self._sessions = session_repository
        self._memories = memory_repository
        self._embedding = embedding
        self._candidates: dict[int, list[MemoryCandidate]] = {}
        self._lock = threading.RLock()

    def candidates(self, session_id: int) -> list[dict]:
        with self._lock:
            return [asdict(item) for item in self._candidates.get(session_id, [])]

    def all_candidates(self) -> list[dict]:
        """Return pending candidates without making them available to recall."""
        with self._lock:
            items = [item for values in self._candidates.values() for item in values]
        return [asdict(item) for item in sorted(
            items,
            key=lambda item: (item.source_session_id, item.source_turn_id, item.content),
        )]

    def create_manual(self, content: str) -> dict:
        """Create a user-authored fact through the same indexed transaction as extraction."""
        content = self._validate_content(content)
        normalized = self._normalize(content)
        existing = next(
            (item for item in self._memories.list_all() if self._normalize(item.content) == normalized),
            None,
        )
        if existing is not None:
            return self._serialize(existing, 1.0)
        now = datetime.now(timezone.utc)
        record = MemoryRecord(
            id=0,
            source_session_id=None,
            content=content,
            confidence=1.0,
            edited=True,
            created_at=now,
            updated_at=now,
        )
        memory_id = self._memories.upsert(record, self._embedding.embed(content))
        stored = self._memories.get(memory_id)
        assert stored is not None
        return self._serialize(stored, 1.0)

    def confirm_candidate(
        self,
        *,
        session_id: int,
        turn_id: int,
        content: str,
    ) -> dict | None:
        """Persist exactly one still-pending candidate and consume it idempotently."""
        content = self._validate_content(content)
        normalized = self._normalize(content)
        with self._lock:
            values = self._candidates.get(session_id, [])
            selected = next(
                (
                    item
                    for item in values
                    if item.source_turn_id == turn_id
                    and self._normalize(item.content) == normalized
                ),
                None,
            )
            if selected is None:
                existing = next(
                    (
                        item
                        for item in self._memories.list_all()
                        if item.source_session_id == session_id
                        and self._normalize(item.content) == normalized
                    ),
                    None,
                )
                return self._serialize(existing, 1.0) if existing is not None else None
            existing = next(
                (item for item in self._memories.list_all() if self._normalize(item.content) == normalized),
                None,
            )
            if existing is None:
                now = datetime.now(timezone.utc)
                memory_id = self._memories.upsert(
                    MemoryRecord(
                        id=0,
                        source_session_id=session_id,
                        content=selected.content,
                        confidence=1.0,
                        created_at=now,
                        updated_at=now,
                    ),
                    self._embedding.embed(selected.content),
                )
                existing = self._memories.get(memory_id)
            remaining = [item for item in values if item is not selected]
            if remaining:
                self._candidates[session_id] = remaining
            else:
                self._candidates.pop(session_id, None)
        assert existing is not None
        return self._serialize(existing, 1.0)

    def reject_candidate(self, *, session_id: int, turn_id: int, content: str) -> bool:
        normalized = self._normalize(content)
        with self._lock:
            values = self._candidates.get(session_id, [])
            remaining = [
                item
                for item in values
                if not (
                    item.source_turn_id == turn_id
                    and self._normalize(item.content) == normalized
                )
            ]
            if len(remaining) == len(values):
                return False
            if remaining:
                self._candidates[session_id] = remaining
            else:
                self._candidates.pop(session_id, None)
            return True

    def extract_session(self, session_id: int) -> dict:
        turns = self._sessions.list_session_turns(session_id)
        committed: list[int] = []
        pending: list[MemoryCandidate] = []
        discarded = 0
        seen = {self._normalize(item.content) for item in self._memories.list_all()}
        for turn in turns:
            if turn.status != "completed" or not turn.user_text.strip():
                continue
            for candidate in self.extract_text(session_id, turn.id, turn.user_text):
                normalized = self._normalize(candidate.content)
                if normalized in seen:
                    continue
                if candidate.confidence >= 0.80:
                    vector = self._embedding.embed(candidate.content)
                    now = datetime.now(timezone.utc)
                    memory_id = self._memories.upsert(
                        MemoryRecord(
                            id=0,
                            source_session_id=session_id,
                            content=candidate.content,
                            confidence=candidate.confidence,
                            created_at=now,
                            updated_at=now,
                        ),
                        vector,
                    )
                    committed.append(memory_id)
                    seen.add(normalized)
                elif candidate.confidence >= 0.60:
                    pending.append(candidate)
                else:
                    discarded += 1
        with self._lock:
            self._candidates[session_id] = pending
        return {
            "session_id": session_id,
            "turns_scanned": len(turns),
            "committed_ids": committed,
            "pending_count": len(pending),
            "discarded_count": discarded,
        }

    def extract_text(self, session_id: int, turn_id: int, text: str) -> list[MemoryCandidate]:
        candidates: list[MemoryCandidate] = []
        for pattern, template, confidence, reason in self._STABLE_PATTERNS:
            for match in pattern.finditer(text):
                value = match.group(1).strip(" ，。！？")
                if value:
                    candidates.append(
                        MemoryCandidate(template.format(value), confidence, session_id, turn_id, reason)
                    )
        if not candidates and self._TEMPORARY.search(text):
            clauses = self._TEMPORARY_CLAUSE.findall(text) or [text]
            candidates.extend(
                MemoryCandidate(
                    clause.strip(" ，。！？"), 0.65, session_id, turn_id, "temporary_context"
                )
                for clause in clauses
                if clause.strip(" ，。！？")
            )
        return candidates

    def recall(self, query: str) -> list[tuple[MemoryRecord, float]]:
        if not query.strip():
            return []
        clauses = self._query_clauses(query)
        vectors = self._embedding.embed_batch(clauses)
        merged: dict[int, tuple[MemoryRecord, float]] = {}
        for clause, vector in zip(clauses, vectors):
            for record, score in self._memories.search(
                clause, vector, top_k_vector=4, top_k_fts=6, min_score=0.55
            ):
                previous = merged.get(record.id)
                if previous is None or score > previous[1]:
                    merged[record.id] = (record, score)
        raw = sorted(merged.values(), key=lambda item: (-item[1], item[0].id))
        selected: list[tuple[MemoryRecord, float]] = []
        tokens = 0
        for record, score in raw:
            cost = estimate_tokens(record.content)
            if score < 0.55 or tokens + cost > 800:
                continue
            selected.append((record, score))
            tokens += cost
            if len(selected) == 4:
                break
        return selected

    def prompt_memories(self, query: str) -> list[tuple[str, float]]:
        return [(record.content, score) for record, score in self.recall(query)]

    def list_or_search(self, query: str = "") -> list[dict]:
        if query.strip():
            rows = self.recall(query)
        else:
            rows = [(record, 1.0) for record in self._memories.list_all()]
        return [self._serialize(record, score) for record, score in rows]

    def edit(self, memory_id: int, content: str) -> dict | None:
        content = self._validate_content(content)
        record = self._memories.get(memory_id)
        if record is None:
            return None
        record.content = content
        record.edited = True
        record.confidence = 1.0
        record.updated_at = datetime.now(timezone.utc)
        self._memories.upsert(record, self._embedding.embed(content))
        return self._serialize(record, 1.0)

    def delete(self, memory_id: int) -> bool:
        return self._memories.delete(memory_id)

    def purge_all(self) -> int:
        with self._lock:
            self._candidates.clear()
        return self._memories.purge_all()

    def layer_counts(self) -> dict[str, int]:
        return self._memories.layer_counts()

    def enable_no_record(self, session_id: int) -> dict[str, int]:
        with self._lock:
            self._candidates.pop(session_id, None)
        return self._memories.purge_session_business_data(session_id)

    @staticmethod
    def _serialize(record: MemoryRecord, score: float) -> dict:
        return {
            "id": record.id,
            "source_session_id": record.source_session_id,
            "content": record.content,
            "confidence": record.confidence,
            "edited": record.edited,
            "created_at": record.created_at.isoformat(),
            "updated_at": record.updated_at.isoformat(),
            "score": score,
            "source": "manual" if record.source_session_id is None else "conversation",
        }

    @staticmethod
    def _validate_content(content: str) -> str:
        content = content.strip()
        if not content or len(content) > 2000:
            raise ValueError("memory_content_invalid")
        return content

    @staticmethod
    def _normalize(content: str) -> str:
        return re.sub(r"[\s，。！？,.!?]+", "", content).casefold()

    @staticmethod
    def _query_clauses(query: str) -> list[str]:
        clauses = []
        for raw in re.split(r"[，,。！？?；;]+", query):
            clause = re.sub(r"^(?:还记得|你记得|请问|周末|平时|通常)+", "", raw.strip())
            clause = re.sub(r"^我(?:周末|平时|通常)", "我", clause)
            if not clause:
                continue
            if clause.startswith(("住", "喜欢", "爱", "叫", "生日", "对")):
                clause = "我" + clause
            clauses.append(clause)
        return clauses or [query.strip()]
