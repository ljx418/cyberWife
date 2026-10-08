"""Asset storage boundary used by application services."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol

from cyberwife.domain.source_pack import SourcePackManifest


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


class ExperienceManifestRepository(Protocol):
    """Atomic, revision-checked V2-X manifest storage."""

    def load(self) -> SourcePackManifest | None: ...

    def stage(self, manifest: SourcePackManifest) -> str: ...

    def commit(self, *, expected_revision: int | None, staged_sha256: str) -> SourcePackManifest: ...

    def rollback(self, revision: int) -> SourcePackManifest: ...

    def discard_staging(self) -> None: ...
