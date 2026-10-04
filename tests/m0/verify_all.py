"""M0-99 verify_all.py — 串联全部 6 项 verify_xxx，按顺序运行并汇总。

任一 exit != 0 阻断 M1；运行完后输出 m0_report.json 与 m0_report.md。
"""
import importlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import REPO_ROOT, EXIT_PASS

VERIFIERS = [
    ("verify_llm", "Qwen3-14B-Instruct Q4_K_M"),
    ("verify_asr", "Faster-Whisper large-v3-turbo"),
    ("verify_tts", "Qwen3-TTS-12Hz-1.7B-Base"),
    ("verify_vad", "Silero VAD v5"),
    ("verify_embedding", "BAAI/bge-small-zh-v1.5"),
    ("verify_avatar", "Wav2Lip256 + LiveTalking"),
]


def main() -> int:
    t0 = time.time()
    results: list[dict] = []
    overall = EXIT_PASS

    for mod_name, label in VERIFIERS:
        print(f"\n========== {mod_name}: {label} ==========")
        mod = importlib.import_module(f"tests.m0.{mod_name}")
        rc = mod.verify()
        rec = {
            "module": mod_name,
            "label": label,
            "exit_code": rc,
            "ts": datetime.now(timezone.utc).isoformat(),
        }
        results.append(rec)
        if rc != EXIT_PASS:
            overall = rc

    elapsed = int((time.time() - t0) * 1000)
    summary = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "total_elapsed_ms": elapsed,
        "verifiers": results,
        "overall_exit": overall,
        "next_step": "M1" if overall == EXIT_PASS else "BLOCKED",
    }

    report_json = REPO_ROOT / "tests" / "m0" / "m0_report.json"
    report_json.write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"\n========== M0 Summary ==========")
    print(f"exit={overall}  elapsed={elapsed}ms")
    for r in results:
        flag = "PASS" if r["exit_code"] == 0 else "FAIL"
        print(f"  [{flag}] {r['module']}: {r['label']}")
    print(f"report → {report_json}")
    return overall


if __name__ == "__main__":
    sys.exit(main())