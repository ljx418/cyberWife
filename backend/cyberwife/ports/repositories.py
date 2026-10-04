"""Repository Ports — 数据访问抽象接口（target-architecture §3 ports/Repository Ports）。

按 implementation-contracts §2/§3 表的 CRUD + 删除一致性语义。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from cyberwife.domain.conversation import Session, Turn
from cyberwife.domain.profile import Profile, Consent, AssetVersion, ConsentScope
from cyberwife.domain.memory import MemoryRecord, OnboardingDraft


class SessionRepository(ABC):
    @abstractmethod
    def create(self, recording_policy: str) -> Session: ...

    @abstractmethod
    def get(self, session_id: int) -> Optional[Session]: ...

    @abstractmethod
    def end(self, session_id: int, ended_at: datetime) -> None: ...


class TurnRepository(ABC):
    @abstractmethod
    def create(self, session_id: int, ordinal: int) -> Turn: ...

    @abstractmethod
    def update(self, turn_id: int, *, user_text: str = "", assistant_text: str = "", status: str = "") -> None: ...


class MemoryRepository(ABC):
    @abstractmethod
    def upsert(self, record: MemoryRecord, embedding: list[float]) -> int:
        """插入或更新记忆 + 向量；返回 memory_id。"""
        ...

    @abstractmethod
    def delete(self, memory_id: int) -> bool:
        """原子删除 source + FTS + vector；返回是否成功。"""
        ...

    @abstractmethod
    def search(
        self,
        query: str,
        query_embedding: list[float],
        top_k_vector: int = 4,
        top_k_fts: int = 6,
        min_score: float = 0.55,
    ) -> list[tuple[MemoryRecord, float]]:
        """FTS + 向量融合检索；返回 (record, score) 列表。"""
        ...

    @abstractmethod
    def purge_all(self) -> int:
        """全清记忆；返回删除条数。"""
        ...


class ProfileRepository(ABC):
    @abstractmethod
    def get(self) -> Optional[Profile]: ...

    @abstractmethod
    def upsert(self, profile: Profile, expected_version: int) -> Profile:
        """乐观并发；expected_version 不匹配抛 ConcurrencyError。"""
        ...


class ConsentRepository(ABC):
    @abstractmethod
    def grant(self, scope: ConsentScope, policy_version: str) -> Consent: ...

    @abstractmethod
    def revoke(self, scope: ConsentScope) -> None: ...

    @abstractmethod
    def is_granted(self, scope: ConsentScope) -> bool: ...


class AssetRepository(ABC):
    @abstractmethod
    def register(self, asset: AssetVersion) -> int: ...

    @abstractmethod
    def activate(self, asset_id: int) -> int:
        """原子切换 active version；返回新 active id。"""
        ...

    @abstractmethod
    def rollback(self, asset_id: int) -> int: ...

    @abstractmethod
    def list_versions(self, kind: str) -> list[AssetVersion]: ...


class OnboardingDraftRepository(ABC):
    @abstractmethod
    def get(self) -> OnboardingDraft: ...

    @abstractmethod
    def upsert(self, draft: OnboardingDraft) -> None: ...


class RetentionServicePort(ABC):
    """保留任务接口；按 ended_at + 30d 清理会话（implementation-contracts §13）。"""

    @abstractmethod
    def scan_once(self, now: datetime) -> int:
        """执行一次清理；返回删除条数。失败重试由实现决定。"""
        ...

    @abstractmethod
    def next_scan_at(self) -> datetime: ...
