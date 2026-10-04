#!/usr/bin/env python3
"""Create reproducible, standardized frontal portraits with Qwen-Image edit."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import time
import urllib.request
from pathlib import Path


def request_json(url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_outputs(history: dict) -> list[dict]:
    outputs: list[dict] = []
    for node in history.get("outputs", {}).values():
        for kind in ("images", "videos", "gifs"):
            for item in node.get(kind, []):
                outputs.append({"kind": kind, **item})
    return outputs


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workflow", type=Path, required=True)
    parser.add_argument("--server", default="http://127.0.0.1:8188")
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--timeout", type=int, default=1200)
    parser.add_argument(
        "--job",
        action="append",
        nargs=3,
        metavar=("SLUG", "COMFY_INPUT_NAME", "SOURCE_PATH"),
        required=True,
    )
    args = parser.parse_args()
    base = json.loads(args.workflow.read_text(encoding="utf-8"))
    records: list[dict] = []

    for slug, comfy_input, source_raw in args.job:
        source = Path(source_raw)
        graph = copy.deepcopy(base)
        graph["1"]["inputs"]["image"] = comfy_input
        graph["10"]["inputs"]["filename_prefix"] = (
            f"cyberWife/frontal/{slug}_frontal"
        )
        started = time.monotonic()
        queued = request_json(f"{args.server}/prompt", {"prompt": graph})
        prompt_id = queued["prompt_id"]
        print(f"QUEUED {slug} {prompt_id}", flush=True)
        deadline = started + args.timeout
        while time.monotonic() < deadline:
            history_map = request_json(f"{args.server}/history/{prompt_id}")
            history = history_map.get(prompt_id)
            if history:
                status = history.get("status", {})
                if status.get("completed"):
                    record = {
                        "slug": slug,
                        "source_name": source.name,
                        "source_sha256": sha256(source),
                        "prompt_id": prompt_id,
                        "elapsed_seconds": round(time.monotonic() - started, 3),
                        "outputs": find_outputs(history),
                        "status": "completed",
                    }
                    records.append(record)
                    print(json.dumps(record, ensure_ascii=False), flush=True)
                    break
                messages = status.get("messages", [])
                if any(
                    message and message[0] == "execution_error"
                    for message in messages
                ):
                    raise RuntimeError(f"ComfyUI execution failed for {slug}: {messages}")
            time.sleep(2)
        else:
            raise TimeoutError(f"ComfyUI job timed out: {slug}")

    result = {
        "workflow": str(args.workflow),
        "server": args.server,
        "generated_at_epoch": int(time.time()),
        "fixed_parameters": {
            "seed": 314159,
            "size": [768, 1152],
            "steps": 25,
            "background": "uniform warm light-gray matte #D8D3CC",
        },
        "records": records,
    }
    args.result.parent.mkdir(parents=True, exist_ok=True)
    args.result.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"RESULT {args.result}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
