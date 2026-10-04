"""身份素材域：Profile / Consent / AssetVersion。

按 FR-02/04/05/06 与 target-architecture §4 不变量。

不变量：
- 未授权不可激活真人资产（consent_granted == false 时 asset.activate 拒绝）
- active version 切换失败时旧版本不变（AssetService.activate 必须原子）
- Profile version 乐观并发（PUT /profile 携带 If-Match: version）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class AssetKind(str, Enum):
    PORTRAIT = "portrait"
    VOICE = "voice"


class AssetStatus(str, Enum):
    UPLOADED = "uploaded"
    PREVIEWED = "previewed"
    ACTIVE = "active"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class ConsentScope(str, Enum):
    PORTRAIT = "portrait"
    VOICE = "voice"
    ALL = "all"


@dataclass
class Consent:
    """用户授权；FR-02 撤销授权后阻止相应素材继续使用。"""

    id: int
    scope: ConsentScope
    policy_version: str
    granted: bool
    granted_at: Optional[datetime] = None
    revoked_at: Optional[datetime] = None

    def revoke(self) -> None:
        self.granted = False
        self.revoked_at = datetime.now(timezone.utc)


@dataclass
class AssetVersion:
    """人物 / 声音 资产的一个版本；FR-04/05。"""

    id: int
    kind: AssetKind
    relative_path: str
    sha256: str
    size_bytes: int
    status: AssetStatus = AssetStatus.UPLOADED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    filename_or_revision: str = ""


@dataclass
class Profile:
    """人设；FR-06 + FR-19 乐观并发。"""

    id: int
    name: str
    user_nickname: str
    persona: str = ""
    relationship_context: str = ""
    example_dialogue: str = ""
    version: int = 0  # 乐观并发
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def bump_version(self) -> None:
        """更新前自增版本号。"""
        self.version += 1
        self.updated_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "user_nickname": self.user_nickname,
            "persona": self.persona,
            "relationship_context": self.relationship_context,
            "example_dialogue": self.example_dialogue,
            "version": self.version,
            "updated_at": self.updated_at.isoformat(),
        }
