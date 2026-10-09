#!/usr/bin/env python3
"""Real six-combination activation and PCM response acceptance for V2-X3.5."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from pathlib import Path


def request(base: str, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base + path,
        data=data,
        headers={"Content-Type": "application/json"},
        method="GET" if data is None else "POST",
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def run(args: argparse.Namespace) -> dict:
    args.output.mkdir(parents=True, exist_ok=True)
    initial = request(args.gateway, "/api/v1/scene-presets")
    initial_pair = (initial.get("active_appearance_id"), initial.get("active_scene_id"))
    by_appearance: dict[str, list[dict]] = {}
    for item in initial.get("combinations", []):
        by_appearance.setdefault(item["appearance_id"], []).append(item)
    common_scenes = set.intersection(*(
        {item["scene_id"] for item in records} for records in by_appearance.values()
    ))
    combinations = sorted(
        (item for item in initial.get("combinations", []) if item["scene_id"] in common_scenes),
        key=lambda item: (item["appearance_id"], item["scene_id"]),
    )
    if len(by_appearance) != 2 or len(common_scenes) < 3 or len(combinations) < 6:
        raise RuntimeError("combination.catalog_incomplete")
    revision = int(initial["revision"])
    records: list[dict] = []
    try:
        for index, combination in enumerate(combinations[:6]):
            activated = request(
                args.gateway,
                f"/api/v1/scene-presets/{combination['scene_id']}/activate",
                {"expected_revision": revision, "appearance_id": combination["appearance_id"]},
            )
            revision = int(activated["revision"])
            if (
                activated.get("active_scene_id") != combination["scene_id"]
                or activated.get("active_appearance_id") != combination["appearance_id"]
            ):
                raise RuntimeError("combination.activation_mismatch")
            active = request(args.gateway, "/api/v1/avatar/active")
            if active.get("avatar_id") != combination["speaking_avatar_id"]:
                raise RuntimeError("combination.avatar_mismatch")
            target = args.output / f"{index + 1:02d}-{combination['appearance_id'][:8]}-{combination['scene_id'][:8]}"
            subprocess.run([
                sys.executable,
                str(args.workspace / "tests/ux5/capture_lipsync.py"),
                "--wav", str(args.wav),
                "--avatar-id", combination["speaking_avatar_id"],
                "--output", str(target),
                "--send-mode", "realtime",
                "--tail-seconds", "0.8",
            ], cwd=args.workspace, check=True, timeout=180)
            capture = json.loads((target / "capture-result.json").read_text(encoding="utf-8"))
            metrics = capture.get("server_metrics", {})
            passed = all((
                capture.get("audio_completion_ack") is True,
                capture.get("sequence_monotonic") is True,
                capture.get("sequence_gaps") == 0,
                capture.get("video_packets", 0) > 0,
                metrics.get("inference_frames", 0) > 0,
                metrics.get("audio_completions") == 1,
                float(capture.get("first_video_after_first_audio_ms", 99999)) <= 7000,
            ))
            records.append({
                **combination,
                "result": "PASS" if passed else "FAIL",
                "capture": str(target / "capture-result.json"),
                "first_video_after_first_audio_ms": capture.get("first_video_after_first_audio_ms"),
                "inference_frames": metrics.get("inference_frames"),
                "finalfps": metrics.get("finalfps"),
            })
            if not passed:
                raise RuntimeError("combination.capture_failed")
    finally:
        if initial_pair[0] and initial_pair[1]:
            current = request(args.gateway, "/api/v1/scene-presets")
            request(
                args.gateway,
                f"/api/v1/scene-presets/{initial_pair[1]}/activate",
                {"expected_revision": current["revision"], "appearance_id": initial_pair[0]},
            )
    result = {
        "schema_version": 1,
        "result": "PASS" if len(records) == 6 and all(item["result"] == "PASS" for item in records) else "FAIL",
        "privacy": {"loopback_only": True, "transcript_recorded": False},
        "common_scene_count": len(common_scenes),
        "combination_count": len(records),
        "restored_pair": {"appearance_id": initial_pair[0], "scene_id": initial_pair[1]},
        "records": records,
    }
    (args.output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--gateway", default="http://127.0.0.1:7860")
    result = run(parser.parse_args())
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
