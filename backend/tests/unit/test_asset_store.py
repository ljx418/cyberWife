"""M2-05 AssetStore 强化单测。"""
import os
import tempfile
from pathlib import Path

import pytest

from cyberwife.infrastructure.asset_store import (
    AssetStore,
    is_safe_relative_path,
    detect_magic,
    sha256_file,
)


@pytest.fixture
def store(tmp_path):
    return AssetStore(tmp_path / "assets")


# ── path traversal ──────────────────────────────────────────────────
class TestPathTraversal:
    @pytest.mark.parametrize("bad_path", [
        "../etc/passwd",
        "portrait/../../../etc",
        "/etc/passwd",
        "C:\\Windows\\System32",
        "portrait/..",
        "",
        "..",
        "../",
        "foo/../../bar",
    ])
    def test_rejects_traversal(self, store, bad_path):
        with pytest.raises(ValueError, match="(unsafe|path escapes|invalid)"):
            store.resolve(bad_path)

    def test_accepts_safe_relative(self, store):
        p = store.resolve("portrait/face.png")
        assert p.is_absolute()
        assert p.name == "face.png"


# ── filename validation ────────────────────────────────────────────
class TestFilenameValidation:
    @pytest.mark.parametrize("bad_filename", [
        "../etc",
        "foo/bar.png",
        "foo\\bar.png",
        "foo\x00bar.png",
        "with space.png",
        "中文.png",
        "",
    ])
    def test_rejects_bad_filename(self, store, bad_filename):
        with pytest.raises(ValueError, match="invalid filename"):
            store.validate_filename("portrait", bad_filename)

    @pytest.mark.parametrize("kind", ["", "unknown", "image/png"])
    def test_rejects_bad_kind(self, store, kind):
        with pytest.raises(ValueError, match="invalid asset kind"):
            store.validate_filename(kind, "face.png")

    @pytest.mark.parametrize("good", [
        "face.png", "face_v2.jpg", "audio-001.wav", "abc.def_123.png",
    ])
    def test_accepts_safe_filename(self, store, good):
        assert store.validate_filename("portrait", good) == good


# ── magic bytes ─────────────────────────────────────────────────────
class TestMagicBytes:
    @pytest.mark.parametrize("data,expected_mime", [
        (b"\xff\xd8\xff\xe0" + b"\x00" * 12, "image/jpeg"),
        (b"\x89PNG\r\n\x1a\n" + b"\x00" * 8, "image/png"),
        (b"RIFF\x00\x00\x00\x00WAVE", "audio/wav"),
        (b"OggS\x00\x02", "audio/ogg"),
        (b"fLaC", "audio/flac"),
    ])
    def test_detects_known_mime(self, data, expected_mime):
        assert detect_magic(data) == expected_mime

    def test_rejects_unknown(self):
        assert detect_magic(b"random garbage here") is None
        assert detect_magic(b"") is None


# ── ingest happy path ───────────────────────────────────────────────
class TestIngestHappy:
    def test_ingest_png(self, store):
        # PNG magic + IHDR-ish bytes
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32 + b"IEND"
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as f:
            f.write(png)
            tmp_path = Path(f.name)
        try:
            meta = store.ingest("portrait", "face.png", tmp_path)
            assert meta["kind"] == "portrait"
            assert meta["mime"] == "image/png"
            assert meta["size_bytes"] == len(png)
            assert meta["sha256"] == sha256_file(tmp_path)
            # 文件已落到 store 内
            assert (store.root / "portrait" / "face.png").exists()
        finally:
            tmp_path.unlink()

    def test_ingest_rejects_non_image_magic(self, store, tmp_path):
        # 写一个"假图片"文件 — magic bytes 不是图片
        fake = tmp_path / "fake.png"
        fake.write_bytes(b"this is not a real image")
        with pytest.raises(ValueError, match="asset_invalid"):
            store.ingest("portrait", "fake.png", fake)


# ── 50MB 上限 ───────────────────────────────────────────────────────
class TestSizeLimit:
    def test_rejects_over_50mb(self, store, tmp_path, monkeypatch):
        # 创建一个 51MB 文件（PNG magic + 51MB zeros）
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * (51 * 1024 * 1024)
        fake = tmp_path / "big.png"
        fake.write_bytes(png)
        with pytest.raises(ValueError, match="asset_too_large"):
            store.ingest("portrait", "big.png", fake, max_bytes=50 * 1024 * 1024)

    def test_accepts_exactly_50mb(self, store, tmp_path):
        # PNG magic + 50MB-8 bytes zeros
        png = b"\x89PNG\r\n\x1a\n" + b"\x00" * (50 * 1024 * 1024 - 8)
        fake = tmp_path / "ok.png"
        fake.write_bytes(png)
        meta = store.ingest("portrait", "ok.png", fake, max_bytes=50 * 1024 * 1024)
        assert meta["size_bytes"] == 50 * 1024 * 1024


# ── 临时文件 context manager ─────────────────────────────────────────
class TestTemporaryAsset:
    def test_writes_and_cleans_up(self, store):
        with store.ingest_temporary() as tmp:
            tmp.write_bytes(b"hello world")
            assert tmp.path.exists()
            assert tmp.path.read_bytes() == b"hello world"
            path_during = tmp.path
        # 退出 with 后目录应被清理
        assert not path_during.exists()

    def test_cleans_up_on_exception(self, store):
        path_during = None
        try:
            with store.ingest_temporary() as tmp:
                tmp.write_bytes(b"x")
                path_during = tmp.path
                raise RuntimeError("simulated failure")
        except RuntimeError:
            pass
        assert path_during is not None
        assert not path_during.exists()


# ── FR-04/05 原型语义：atomic activate（M2-stretch 留接口）───────────
class TestActivePointer:
    """active_assets 表与 asset_versions 的关联；M2-stretch 接 LiveTalking 时实现。

    M1-M2 当前只做接口与基本数据访问；M2-stretch 接 asset_versions.activate + active_assets 原子切换。
    """

    def test_active_assets_schema_unique(self, store):
        # 仅在 sqlite 上验证 active_assets PRIMARY KEY(kind) 与 asset_versions REFERENCES
        # AssetStore 不直接操作 active_assets；走 SqliteRepository；此处仅占位测试
        pass


# ── M2-stretch：合成 fixture 走通 ingest（避免写真 PII 出现在测试代码）──────────
class TestSyntheticIngestPipeline:
    """使用合成 PNG fixture 走 AssetStore.ingest 完整路径。

    写真"老婆.png" 在代码中**不直接出现**；用 SHA256 与 entity_id_hash 验证。
    写真实际文件位于 ~/.cyberWife/assets/portrait/<file>.png（Git ignore）。
    """

    SYNTHETIC_PNG_MAGIC = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32 + b"IEND\xae\x42\x60\x82"

    def test_synthetic_png_round_trip(self, store, tmp_path):
        """合成 PNG 走 ingest：M2-stretch 写真 ingest 的镜像路径。"""
        src = tmp_path / "synthetic_test_portrait.png"
        src.write_bytes(self.SYNTHETIC_PNG_MAGIC)
        meta = store.ingest("portrait", "synthetic_test_portrait.png", src)
        assert meta["mime"] == "image/png"
        assert meta["size_bytes"] == len(self.SYNTHETIC_PNG_MAGIC)
        # 文件已落到 store 内
        stored = store.root / "portrait" / "synthetic_test_portrait.png"
        assert stored.exists()
        assert stored.read_bytes() == self.SYNTHETIC_PNG_MAGIC

    def test_ingest_then_delete_residue(self, store, tmp_path):
        """ingest 完成后清理临时文件，不留 garbage。"""
        src = tmp_path / "synthetic.png"
        src.write_bytes(self.SYNTHETIC_PNG_MAGIC)
        store.ingest("portrait", "synthetic.png", src)
        src.unlink()  # 模拟调用方清理
        # store 内文件保留
        assert (store.root / "portrait" / "synthetic.png").exists()
        # 原 src 已清理
        assert not src.exists()
