"""Compare a baseline/candidate capture without pretending to score naturalness."""
from __future__ import annotations

import argparse
import json
from pathlib import Path


def compare(baseline: dict, candidate: dict) -> dict:
    base_visual = baseline["visual"]
    next_visual = candidate["visual"]
    boundary_key = "cheek_boundary_excess_over_codec_floor"
    base_boundary = float(base_visual[boundary_key]["p95"])
    next_boundary = float(next_visual[boundary_key]["p95"])
    base_jerk = float(base_visual["face_second_order_motion"]["p95"])
    next_jerk = float(next_visual["face_second_order_motion"]["p95"])
    base_sharpness = float(base_visual["face_sharpness"]["mean"])
    next_sharpness = float(next_visual["face_sharpness"]["mean"])
    gates = {
        "runtime_rate_is_realtime": abs(float(candidate["dataset_timing"]["effective_source_playback_rate"]) - 1.0) <= 0.02,
        "boundary_delta_improves_20_percent": next_boundary <= base_boundary * 0.80,
        "second_order_motion_not_worse": next_jerk <= base_jerk,
        "sharpness_not_traded_away": next_sharpness >= base_sharpness * 0.90,
        "mouth_response_preserved": bool(candidate["gates"]["mouth_responds_during_voice"]),
        "no_black_or_sustained_freeze": bool(
            candidate["gates"]["no_black_frames"]
            and candidate["gates"]["no_sustained_freeze"]
        ),
    }
    return {
        "schema_version": 1,
        "baseline": {
            "boundary_p95": base_boundary,
            "second_order_motion_p95": base_jerk,
            "sharpness_mean": base_sharpness,
            "playback_rate": baseline["dataset_timing"]["effective_source_playback_rate"],
        },
        "candidate": {
            "boundary_p95": next_boundary,
            "second_order_motion_p95": next_jerk,
            "sharpness_mean": next_sharpness,
            "playback_rate": candidate["dataset_timing"]["effective_source_playback_rate"],
        },
        "improvement": {
            "boundary_percent": round((1.0 - next_boundary / base_boundary) * 100, 3) if base_boundary else 0.0,
            "second_order_motion_percent": round((1.0 - next_jerk / base_jerk) * 100, 3) if base_jerk else 0.0,
            "sharpness_percent": round((next_sharpness / base_sharpness - 1.0) * 100, 3) if base_sharpness else 0.0,
        },
        "gates": gates,
        "automated_pass": all(gates.values()),
        "human_review_required": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--require-pass", action="store_true")
    args = parser.parse_args()
    result = compare(
        json.loads(args.baseline.read_text(encoding="utf-8")),
        json.loads(args.candidate.read_text(encoding="utf-8")),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["automated_pass"] or not args.require_pass else 2


if __name__ == "__main__":
    raise SystemExit(main())
