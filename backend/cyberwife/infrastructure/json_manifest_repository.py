"""Crash-safe local repository for the V2-X source-pack manifest."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from contextlib import contextmanager

from cyberwife.domain.source_pack import SourcePackManifest
from cyberwife.ports.assets import ManifestRevisionConflict


class JsonManifestRepository:
    def __init__(self, private_data_root: Path) -> None:
        self._root = Path(private_data_root).resolve() / "v2x" / "manifests"
        self._root.mkdir(parents=True, exist_ok=True)
        self._active = self._root / "source-pack.v1.json"
        self._staged = self._root / ".source-pack.v1.staged.json"
        self._lock = self._root / ".source-pack.v1.lock"

    @staticmethod
    def _encode(manifest: SourcePackManifest) -> bytes:
        return (json.dumps(manifest.to_dict(), ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")

    @staticmethod
    def _read(path: Path) -> SourcePackManifest:
        return SourcePackManifest.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def load(self) -> SourcePackManifest | None:
        return self._read(self._active) if self._active.is_file() else None

    def stage(self, manifest: SourcePackManifest) -> str:
        payload = self._encode(manifest)
        self._atomic_bytes(self._staged, payload)
        return hashlib.sha256(payload).hexdigest()

    def commit(self, *, expected_revision: int | None, staged_sha256: str) -> SourcePackManifest:
        with self._locked():
            if not self._staged.is_file():
                raise FileNotFoundError("no staged manifest")
            actual_staged_sha256 = hashlib.sha256(self._staged.read_bytes()).hexdigest()
            if actual_staged_sha256 != staged_sha256:
                raise ManifestRevisionConflict("staged manifest was replaced by another writer")
            current = self.load()
            current_revision = current.revision if current else None
            if current_revision != expected_revision:
                raise ManifestRevisionConflict(
                    f"expected revision {expected_revision}, current revision {current_revision}"
                )
            staged = self._read(self._staged)
            required_revision = 1 if current is None else current.revision + 1
            if staged.revision != required_revision:
                raise ManifestRevisionConflict(
                    f"staged revision {staged.revision}, required revision {required_revision}"
                )
            if current is not None:
                history = self._history(current.revision)
                if not history.exists():
                    self._atomic_bytes(history, self._encode(current))
            os.replace(self._staged, self._active)
            self._fsync_directory()
            return self._read(self._active)

    def rollback(self, revision: int) -> SourcePackManifest:
        with self._locked():
            target = self._history(revision)
            if not target.is_file():
                raise FileNotFoundError(f"manifest history revision {revision} not found")
            restored = self._read(target)
            current = self.load()
            if current is not None and current.revision != revision:
                current_history = self._history(current.revision)
                if not current_history.exists():
                    self._atomic_bytes(current_history, self._encode(current))
            self._atomic_bytes(self._active, self._encode(restored))
            return self._read(self._active)

    def discard_staging(self) -> None:
        self._staged.unlink(missing_ok=True)

    def active_bytes(self) -> bytes | None:
        return self._active.read_bytes() if self._active.is_file() else None

    def _history(self, revision: int) -> Path:
        if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
            raise ValueError("revision must be positive")
        return self._root / f"source-pack.v1.r{revision}.json"

    def _atomic_bytes(self, target: Path, payload: bytes) -> None:
        temporary = target.with_name(f".{target.name}.tmp")
        try:
            with temporary.open("wb") as stream:
                stream.write(payload)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, target)
            self._fsync_directory()
        finally:
            temporary.unlink(missing_ok=True)

    def _fsync_directory(self) -> None:
        try:
            descriptor = os.open(self._root, os.O_RDONLY)
        except OSError:
            return
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    @contextmanager
    def _locked(self):
        """Serialize CAS across Gateway processes on the supported WSL/POSIX host."""
        with self._lock.open("a+b") as stream:
            try:
                import fcntl
                fcntl.flock(stream.fileno(), fcntl.LOCK_EX)
            except ImportError:  # pragma: no cover - backend production host is WSL2.
                fcntl = None
            try:
                yield
            finally:
                if fcntl is not None:
                    fcntl.flock(stream.fileno(), fcntl.LOCK_UN)
