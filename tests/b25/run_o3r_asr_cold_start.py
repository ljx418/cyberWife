"""Run three real Speech Worker cold-start and ASR inference cycles for O3R."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import wave
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _wait_http(url: str, timeout_s: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.0) as response:
                if response.status == 200:
                    return
        except (OSError, urllib.error.URLError):
            time.sleep(0.2)
    raise TimeoutError(f"endpoint did not become reachable: {url}")


def _pcm_from_wav(path: Path) -> bytes:
    with wave.open(str(path), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
            raise ValueError(f"expected PCM16 mono 16kHz: {path}")
        return source.readframes(source.getnframes())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--port", type=int, default=8091)
    parser.add_argument(
        "--audio",
        type=Path,
        default=ROOT / "audit/v1/B2/tts/cosyvoice/01.wav",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "audit/v1/B2.5/O3R/cold-start",
    )
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    pcm = _pcm_from_wav(args.audio)
    rows: list[dict] = []

    for cycle in range(1, args.cycles + 1):
        stdout_path = args.output / f"cycle-{cycle}.stdout.log"
        stderr_path = args.output / f"cycle-{cycle}.stderr.log"
        env = os.environ.copy()
        env.update({"PYTHONPATH": "backend:.", "HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"})
        started = time.perf_counter()
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "workers.speech_worker.server",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(args.port),
                    "--probe-timeout",
                    "120",
                    "--asr-device",
                    "cuda",
                    "--asr-compute-type",
                    "float16",
                ],
                cwd=ROOT,
                env=env,
                stdout=stdout,
                stderr=stderr,
            )
            try:
                _wait_http(f"http://127.0.0.1:{args.port}/health")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{args.port}/api/v1/utterances/transcribe",
                    data=pcm,
                    method="POST",
                    headers={"content-type": "application/octet-stream", "x-sample-rate": "16000"},
                )
                with urllib.request.urlopen(request, timeout=180.0) as response:
                    payload = json.loads(response.read())
                row = {
                    "cycle": cycle,
                    "process_id": process.pid,
                    "wall_ms": round((time.perf_counter() - started) * 1000, 3),
                    "speech_detected": payload.get("speech_detected"),
                    "text_non_empty": bool(str(payload.get("text", "")).strip()),
                    "segment_count": len(payload.get("segments", [])),
                    "asr_latency_ms": payload.get("latency_ms"),
                }
                rows.append(row)
                print(json.dumps(row, ensure_ascii=False), flush=True)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

    passed = len(rows) == args.cycles and all(row["text_non_empty"] for row in rows)
    result = {"schema_version": 1, "cycles": rows, "passed": passed}
    (args.output / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
