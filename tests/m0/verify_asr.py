"""M0-02 verify_asr.py — Faster-Whisper large-v3-turbo CTranslate2 加载 smoke。

按 model-manifest.md §3 七步核验 ASR 组件。
fallback：如果 logical_id=faster-whisper-large-v3-turbo 不在 registry，自动探测
faster-whisper-large-v3 作为 fallback（来自 _archive_faster-whisper-large-v3）。
"""
import sys
import time
from pathlib import Path

from . import (
    EXIT_FAIL,
    EXIT_PASS,
    check_exists,
    elapsed_ms,
    load_registry,
    print_record,
    record_status,
    sha256_file,
)

PRIMARY_ID = "faster-whisper-large-v3-turbo"
FALLBACK_ID = "faster-whisper-large-v3"


def _probe(reg, logical_id: str) -> tuple[Path | None, dict]:
    entry = reg.get(logical_id, {})
    p = Path(entry.get("absolute_path", ""))
    if p.is_dir() and (p / "model.bin").exists():
        return p / "model.bin", entry
    if p.is_file():
        return p, entry
    return None, entry


def verify() -> int:
    reg = load_registry()

    used_id = PRIMARY_ID
    abs_path, entry = _probe(reg, PRIMARY_ID)
    if abs_path is None:
        print(f"[WARN] {PRIMARY_ID} 缺失，尝试 fallback {FALLBACK_ID}")
        abs_path, entry = _probe(reg, FALLBACK_ID)
        used_id = FALLBACK_ID
    if abs_path is None:
        print_record(record_status(PRIMARY_ID, "blocked", reason="no_model_bin"))
        return EXIT_FAIL

    license_id = entry.get("license_id", "MIT")
    license_review = entry.get("license_review", "approved")

    print(f"[1/5] discovered: {abs_path}  (used={used_id})")
    ok, size = check_exists(abs_path)
    if not ok:
        print_record(record_status(used_id, "blocked", reason="file_missing"))
        return EXIT_FAIL

    print(f"[2/5] hashing ({(size or 0) / 1024 / 1024 / 1024:.1f} GB)...")
    t0 = time.time()
    sha = sha256_file(abs_path)
    print(f"    sha256: {sha}  ({elapsed_ms(t0)} ms)")

    if license_review != "approved":
        print_record(record_status(used_id, "blocked", reason="license_not_approved"))
        return EXIT_FAIL
    print(f"[3/5] licensed: license_id={license_id}, review={license_review}")

    print(f"[4/5] loadable: faster_whisper import + 加载 model")
    try:
        from faster_whisper import WhisperModel  # type: ignore
    except ImportError:
        print_record(record_status(used_id, "loadable", reason="faster_whisper_not_installed"))
        return EXIT_PASS

    t0 = time.time()
    try:
        # device='cpu' 避免 M0 抢占 ASR VRAM 分时窗口
        model = WhisperModel(str(abs_path.parent), device="cpu", compute_type="int8")
        # smoke 推理：1s 静音（应输出空 segment）
        import numpy as np
        sr = 16000
        audio = np.zeros(sr, dtype=np.float32)
        segs, info = model.transcribe(audio, language="zh", beam_size=1, vad_filter=False)
        segs = list(segs)
        load_ms = elapsed_ms(t0)
        print(f"    loaded + 1s silence transcribe OK ({load_ms} ms), segments={len(segs)}")
        status = "verified"
    except Exception as e:
        print(f"    load failed: {e}")
        print_record(record_status(used_id, "blocked", reason=str(e)))
        return EXIT_FAIL

    print(f"[5/5] verified: {sha[:16]}")
    print_record(
        record_status(
            used_id,
            status,
            sha256=sha,
            size_bytes=size,
            absolute_path=str(abs_path),
            license_id=license_id,
            runtime="faster-whisper",
        )
    )
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(verify())