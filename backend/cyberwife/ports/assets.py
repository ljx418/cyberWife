"""Asset storage boundary used by application services."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class AssetStorePort(Protocol):
    """Store private user assets without exposing infrastructure details."""

    def resolve(self, relative_path: str) -> Path: ...

    def ingest(
        self,
        kind: str,
        filename: str,
        source: Path,
        *,
        max_bytes: int = 50 * 1024 * 1024,
    ) -> dict: ...
