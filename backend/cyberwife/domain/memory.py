"""记忆域：MemoryRecord + 保留规则。

按 FR-12/14 与 implementation-contracts §2/§3。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class MemoryRecord:
    """长期记忆事实记录；FR-12。"""

    id: int
    content: str
    confidence: float  # 0..1
    source_session_id: Optional[int] = None
    edited: bool = False
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MemoryWithVector:
    """MemoryRecord + sqlite-vec 嵌入；维度 512（BGE small zh v1.5）。"""

    memory: MemoryRecord
    embedding: list[float]  # 512 维

    def __post_init__(self) -> None:
        if len(self.embedding) != 512:
            raise ValueError(
                f"embedding dim must be 512 (BGE small zh v1.5), got {len(self.embedding)}"
            )


@dataclass
class OnboardingDraft:
    """FR-01 五步草稿；单线（id=1）允许随时覆盖。"""

    id: int = 1
    consent_granted: bool = False
    step_completed: int = 0  # 0..4
    asset_consent_at: Optional[datetime] = None
    profile_draft_json: dict = field(default_factory=dict)
    settings_json: dict = field(default_factory=dict)
    device_snapshot_json: dict = field(default_factory=dict)
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def bump_step(self, new_step: int) -> None:
        if not (0 <= new_step <= 4):
            raise ValueError(f"step_completed must be in [0, 4], got {new_step}")
        if new_step > self.step_completed:
            self.step_completed = new_step
            self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "consent_granted": self.consent_granted,
            "step_completed": self.step_completed,
            "asset_consent_at": self.asset_consent_at.isoformat() if self.asset_consent_at else None,
            "profile_draft_json": self.profile_draft_json,
            "settings_json": self.settings_json,
            "device_snapshot_json": self.device_snapshot_json,
            "updated_at": self.updated_at.isoformat(),
        }
