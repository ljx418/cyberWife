"""B5 AC-04A: real-browser warm response cache acceptance.

The positive path is deliberately delegated to the same Windows Chrome runner
used for ordinary first-response measurements.  Policy, version and memory
assertions instantiate the production classes rather than duplicating their
matching rules in this verifier.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from cyberwife.application.warm_response_cache import WarmResponseCache  # noqa: E402
from cyberwife.domain.warm_response import WarmResponseContext, WarmResponsePolicy  # noqa: E402


NEGATIVES = (
    "今天天气怎么样", "你好今天天气怎么样", "你好，请告诉我天气", "你还记得我吗",
    "你好你记得我吗", "继续说", "你好继续说", "再说一点", "早上好今天天气如何",
    "晚上好帮我查天气", "嗨你是谁", "嗨说个故事", "你在吗告诉我时间",
    "能听见吗继续", "谢谢你告诉我天气", "再见之前回答我", "你好呀", "你好啊",
    "你好宝贝", "宝贝你好", "天气", "记忆", "继续", "在吗今天天气如何",
)
VERSION_FIELDS = ("persona_version", "voice_version", "llm_revision", "tts_revision", "policy_version")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _context(**changes: str) -> WarmResponseContext:
    values = {
        "persona_version": "profile-v1",
        "voice_version": "voice-v1",
        "llm_revision": "llm-v1",
        "tts_revision": "tts-v1",
        "policy_version": "policy-v1",
    }
    values.update(changes)
    return WarmResponseContext(**values)


def _cache_feature_files(runtime_dir: Path) -> set[str]:
    if not runtime_dir.exists():
        return set()
    found: set[str] = set()
    for path in runtime_dir.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(runtime_dir).as_posix()
        lowered = relative.lower()
        if "warm_response" in lowered or "cache-hit" in lowered or path.suffix.lower() == ".cache":
            found.add(relative)
    return found


def _cache_tables(db_path: Path) -> list[str]:
    if not db_path.exists():
        return []
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    return [str(row[0]) for row in rows if "cache" in str(row[0]).lower() or "warm" in str(row[0]).lower()]


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--positive-rounds", type=int, default=3)
    parser.add_argument("--negative-min", type=int, default=24)
    parser.add_argument("--chrome-cdp", default=os.environ.get("CW_CHROME_CDP", "http://127.0.0.1:9222"))
    parser.add_argument("--web-url", default=os.environ.get("CW_TEST_WEB_URL", "http://127.0.0.1:4173/?preview=1"))
    parser.add_argument("--audio", type=Path, default=ROOT / "audit/v1/B2.5/O5/audio/hello-0.75.wav")
    parser.add_argument("--normal-evidence", type=Path, default=ROOT / "audit/v1/B5/B5.4C-AC04-normal30")
    parser.add_argument("--evidence", type=Path, default=ROOT / "audit/v1/B5/B5.4C-AC04A")
    parser.add_argument("--runtime-dir", type=Path, default=Path("/home/administrator/.cyberWife"))
    parser.add_argument("--database", type=Path, default=Path("/home/administrator/.cyberWife/cyberwife.db"))
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    positive_dir = args.evidence / "positive"

    result: dict[str, Any] = {
        "schema_version": 1,
        "evidence_level": "real_windows_chrome_models_plus_product_class_contracts",
        "command": "python -m tests.b25.accept_warm_cache --positive-rounds 3 --negative-min 24",
        "pass": False,
    }
    exit_code = 1
    try:
        if args.positive_rounds < 3:
            raise AssertionError("positive-rounds must be at least 3")
        if args.negative_min < 24 or len(NEGATIVES) < args.negative_min:
            raise AssertionError("negative-min must be 24 and the corpus must cover it")
        if not args.audio.is_file():
            raise FileNotFoundError(args.audio)

        files_before = _cache_feature_files(args.runtime_dir)
        tables_before = _cache_tables(args.database)
        env = os.environ.copy()
        env.update({
            "CW_CHROME_CDP": args.chrome_cdp,
            "CW_TEST_WEB_URL": args.web_url,
            "CW_TEST_AUDIO_FILE": str(args.audio),
        })
        subprocess.run(
            ["node", "tests/b25/run_o1_browser_chain.mjs", str(args.positive_rounds), str(positive_dir)],
            cwd=ROOT,
            env=env,
            check=True,
        )
        positive_metrics = _load_json(positive_dir / "metrics.json")
        positive_samples = _load_json(positive_dir / "samples.json")

        policy = WarmResponsePolicy(("你好",), version="policy-v1")
        context = _context()
        frame = b"\x01\x00" * 320
        cache = WarmResponseCache(policy)
        assert cache.put("你好", context, reply_text="你好。", pcm_frames=(frame,))

        negative_rows = []
        for text in NEGATIVES[: args.negative_min]:
            entry, bucket = cache.resolve(text, context)
            negative_rows.append({"text_sha256": _digest(text), "bucket": bucket, "hit": entry is not None})

        version_rows = []
        for field in VERSION_FIELDS:
            entry, bucket = cache.resolve("你好", _context(**{field: "changed"}))
            version_rows.append({"field": field, "bucket": bucket, "hit": entry is not None})

        bounded = WarmResponseCache(policy, max_bytes=650)
        first_write = bounded.put("你好", context, reply_text="你好。", pcm_frames=(frame,))
        overflow_write = bounded.put("你好", context, reply_text="超限", pcm_frames=(frame, frame))

        normal_metrics = _load_json(args.normal_evidence / "metrics.json")
        files_after = _cache_feature_files(args.runtime_dir)
        tables_after = _cache_tables(args.database)
        cache_source = (BACKEND / "cyberwife/application/warm_response_cache.py").read_text(encoding="utf-8")
        persistence_tokens = [token for token in ("sqlite", "open(", "write_text", "write_bytes") if token in cache_source.lower()]

        positive_ok = (
            positive_metrics.get("sample_count") == args.positive_rounds
            and positive_metrics.get("complete_count") == args.positive_rounds
            and positive_metrics.get("cache_hit_count") == args.positive_rounds
            and positive_metrics.get("bucket") == "cache-hit"
            and float(positive_metrics.get("p95_ms", 1e12)) <= 800.0
            and all(int(row.get("confirmations_sent", 0)) == 1 for row in positive_samples)
            and all(int(row.get("non_silent_chunks", 0)) > 0 for row in positive_samples)
        )
        negatives_ok = len(negative_rows) >= 24 and all(not row["hit"] and row["bucket"] == "normal" for row in negative_rows)
        versions_ok = len(version_rows) == 5 and all(not row["hit"] and row["bucket"] == "config-invalid" for row in version_rows)
        memory_ok = (
            first_write
            and not overflow_write
            and bounded.size_bytes <= bounded.max_bytes == 650
            and cache.size_bytes <= cache.max_bytes == 64 * 1024 * 1024
        )
        persistence_ok = (
            tables_before == tables_after == []
            and files_after - files_before == set()
            and persistence_tokens == []
        )
        normal_ok = (
            normal_metrics.get("sample_count") == 30
            and normal_metrics.get("complete_count") == 30
            and normal_metrics.get("cache_hit_count") == 0
            and normal_metrics.get("bucket") == "normal"
            and float(normal_metrics.get("p95_ms", 1e12)) <= 7000.0
        )

        result.update({
            "positive": {"metrics": positive_metrics, "checks_pass": positive_ok},
            "negative": {"count": len(negative_rows), "false_hits": sum(row["hit"] for row in negative_rows), "rows": negative_rows, "checks_pass": negatives_ok},
            "version_invalidation": {"rows": version_rows, "checks_pass": versions_ok},
            "memory": {"configured_limit_bytes": cache.max_bytes, "bounded_test_limit_bytes": bounded.max_bytes, "bounded_size_bytes": bounded.size_bytes, "overflow_rejected": not overflow_write, "checks_pass": memory_ok},
            "persistence": {"cache_tables_before": tables_before, "cache_tables_after": tables_after, "new_cache_feature_files": sorted(files_after - files_before), "source_persistence_tokens": persistence_tokens, "checks_pass": persistence_ok},
            "normal_regression": {"metrics": normal_metrics, "checks_pass": normal_ok},
        })
        result["pass"] = all((positive_ok, negatives_ok, versions_ok, memory_ok, persistence_ok, normal_ok))
        exit_code = 0 if result["pass"] else 1
    except Exception as exc:  # evidence must survive a failed acceptance run
        result["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        (args.evidence / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
