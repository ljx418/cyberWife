"""Collect real one-way TTS fallback evidence after launcher fault injection."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import urlopen


def gateway_processes() -> list[dict]:
    found = []
    for item in Path("/proc").iterdir():
        if not item.name.isdigit():
            continue
        try:
            command = (item / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except (OSError, PermissionError):
            continue
        if "-m cyberwife.api.server" in command:
            found.append({"pid": int(item.name), "command_class": "local_gateway"})
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--url", default="http://127.0.0.1:7860/api/v1/health")
    args = parser.parse_args()
    with urlopen(args.url, timeout=5) as response:
        health = json.load(response)
    tts = health["components"]["tts"]
    processes = gateway_processes()
    result = {
        "schema_version": 1,
        "evidence_level": "real_launcher_fault_injection_qwen_functional_probe",
        "fault": "cosy_interpreter_exits_nonzero",
        "health_status": health["status"],
        "tts": tts,
        "resources": health["resources"],
        "gateway_processes": processes,
    }
    result["pass"] = bool(
        health["status"] == "degraded"
        and tts["status"] == "degraded"
        and tts["logical_id"] == "qwen3-tts-12hz-1.7b-base"
        and tts["fallback_active"] is True
        and len(processes) == 1
        and float(health["resources"].get("vram_used_gb", 99)) <= 22
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["pass"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
