"""AssetStore — 私有资产目录管理。

按 ADR-006：源码 C 盘、运行数据 WSL2 ext4。
M1 阶段实现：路径校验 + magic bytes 校验 + 简单元数据写入；不动文件内容。
"""
from __future__ import annotations

import hashlib
import re
import shutil
from pathlib import Path
from typing import Optional

# 禁止的字符（防路径穿越）
_FORBIDDEN = re.compile(r"[\\\x00]|/\\.\\./|^/|^[A-Za-z]:[\\\\/]")


def is_safe_relative_path(path: str) -> bool:
    """判断是否为安全相对路径（不指向绝对路径、不含 ../ 逃逸）。"""
    if not path:
        return False
    if _FORBIDDEN.search(path):
        return False
    parts = Path(path).parts
    if any(p == ".." for p in parts):
        return False
    return True


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# 已知 magic bytes（用于 M2 实际校验）
_MAGIC_SIGNATURES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "audio/wav",  # WAV：RIFF....WAVE
    b"ID3": "audio/mp3",  # MP3 with ID3 tag
    b"\xff\xfb": "audio/mp3",  # MP3 without ID3
    b"OggS": "audio/ogg",
    b"fLaC": "audio/flac",
    b"\x1a\x45\xdf\xa3": "video/webm",  # Matroska/WebM
    b"\x00\x00\x00": "video/mp4",  # MP4 (ftyp box)
}


def detect_magic(data: bytes) -> Optional[str]:
    """返回文件 magic bytes 对应的 MIME；不匹配返回 None。"""
    for sig, mime in _MAGIC_SIGNATURES.items():
        if data.startswith(sig):
            return mime
    return None


class AssetStore:
    """私有资产目录管理（人物/声音版本）；路径相对化、magic bytes 校验、SHA256 校验。

    M2 强化：临时文件写入走 tempfile.NamedTemporaryFile + 自动清理；
    文件名严格按白名单 (portrait|voice)/<basename> 规则；
    所有 ingest 调用走 try/except 清理临时残留。
    """

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    @property
    def root(self) -> Path:
        return self._root

    def resolve(self, relative_path: str) -> Path:
        """解析相对路径为绝对路径；越界抛 ValueError。"""
        if not is_safe_relative_path(relative_path):
            raise ValueError(f"unsafe relative_path: {relative_path!r}")
        target = (self._root / relative_path).resolve()
        try:
            target.relative_to(self._root.resolve())
        except ValueError:
            raise ValueError(f"path escapes asset root: {relative_path!r}")
        return target

    def validate_filename(self, kind: str, filename: str) -> str:
        """校验 kind 与 filename，返回 basename（去除路径与可疑字符）。

        禁止：
        - 含 ..
        - 含路径分隔符（kind 由调用方提供，不允许在 filename 内）
        - 含空字节或控制字符
        """
        if kind not in {"portrait", "voice"}:
            raise ValueError(f"invalid asset kind: {kind!r}")
        if not isinstance(filename, str) or not filename:
            raise ValueError(f"invalid filename: empty")
        if "/" in filename or "\\" in filename or "\x00" in filename:
            raise ValueError(f"invalid filename (path sep / NUL): {filename!r}")
        # 限制 basename 仅含 ASCII 安全字符
        import re
        if not re.match(r"^[A-Za-z0-9._-]+$", filename):
            raise ValueError(f"invalid filename (non-safe chars): {filename!r}")
        return filename

    def ingest(
        self,
        kind: str,
        filename: str,
        source: Path,
        *,
        max_bytes: int = 50 * 1024 * 1024,
    ) -> dict:
        """入库一份资产：magic bytes + size + SHA256 + 相对路径。返回元数据 dict。"""
        safe_filename = self.validate_filename(kind, filename)
        size = source.stat().st_size
        if size > max_bytes:
            raise ValueError(f"asset_too_large: {size} > {max_bytes}")
        # magic bytes 校验
        with source.open("rb") as f:
            head = f.read(16)
        mime = detect_magic(head)
        if mime is None:
            raise ValueError(f"asset_invalid: unknown magic bytes")
        if kind == "portrait" and mime not in {"image/jpeg", "image/png"}:
            raise ValueError(f"asset_invalid: portrait requires JPEG or PNG, received {mime}")
        if kind == "voice" and not mime.startswith("audio/"):
            raise ValueError(f"asset_invalid: voice requires audio, received {mime}")
        sha = sha256_file(source)
        target = self.resolve(f"{kind}/{safe_filename}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        return {
            "kind": kind,
            "relative_path": str(target.relative_to(self._root)),
            "filename_or_revision": safe_filename,
            "size_bytes": size,
            "sha256": sha,
            "mime": mime,
        }

    def delete(self, relative_path: str) -> None:
        """Delete one validated private asset; never accepts an absolute path."""
        target = self.resolve(relative_path)
        target.unlink(missing_ok=True)

    def ingest_temporary(self, suffix: str = ".tmp") -> "TemporaryAsset":
        """返回一个 context manager，临时目录内写入资产，退出时自动清理。

        使用方式：
            with store.ingest_temporary() as tmp:
                tmp.write_bytes(data)
                # tmp.path 是临时文件路径
            # 退出 with 时自动删除
        """
        return TemporaryAsset(self._root, suffix)


import tempfile
import contextlib


class TemporaryAsset:
    """AssetStore 临时文件 context manager：写入 tmpdir，退出自动清理。"""

    def __init__(self, root: Path, suffix: str = ".tmp") -> None:
        self._root = Path(root)
        self._suffix = suffix
        self._tmpdir: Optional[tempfile.TemporaryDirectory] = None
        self._path: Optional[Path] = None

    def __enter__(self) -> "TemporaryAsset":
        self._tmpdir = tempfile.TemporaryDirectory(prefix="cw-asset-", suffix=self._suffix)
        self._path = Path(self._tmpdir.name) / f"payload{self._suffix}"
        self._path.write_bytes(b"")
        return self

    @property
    def path(self) -> Path:
        if self._path is None:
            raise RuntimeError("TemporaryAsset not entered")
        return self._path

    def write_bytes(self, data: bytes) -> None:
        self.path.write_bytes(data)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self._tmpdir is not None:
            self._tmpdir.cleanup()
        self._path = None
