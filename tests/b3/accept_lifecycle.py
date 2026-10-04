"""B3-AC07: repeated conversation lifecycle and zero-residue checks."""
from __future__ import annotations

import argparse
import asyncio
import json
import socket
import time
from pathlib import Path

import httpx
import websockets


def port_open(port: int) -> bool:
    with socket.socket() as probe:
        probe.settimeout(1)
        return probe.connect_ex(("127.0.0.1", port)) == 0


def audio_files(roots: list[Path]) -> set[str]:
    values = set()
    for root in roots:
        if root.exists():
            for pattern in ("*.wav", "*.pcm", "*.mp3", "*.flac", "*.ogg"):
                values.update(str(path.resolve()) for path in root.rglob(pattern) if path.is_file())
    return values


async def run(args) -> tuple[dict, list[dict]]:
    client = httpx.Client(timeout=10, trust_env=False)
    roots = [Path("/home/administrator/.cyberWife/logs"), Path("/home/administrator/.cyberWife/audit")]
    before = audio_files(roots)
    rows = []
    try:
        for cycle in range(1, args.cycles + 1):
            started = time.perf_counter()
            created = client.post(f"{args.http_base}/api/v1/sessions", json={"recording_policy": "standard"})
            created.raise_for_status()
            session_id = int(created.json()["id"])
            async with websockets.connect(f"{args.ws_base}/ws/v1/sessions/{session_id}") as socket:
                initial = json.loads(await asyncio.wait_for(socket.recv(), 5))
                await socket.send(json.dumps({"type": "conversation.stop", "event_seq": 1}))
                await socket.wait_closed()
            ended = client.delete(f"{args.http_base}/api/v1/sessions/{session_id}")
            # conversation.stop already closes the in-memory session; DELETE
            # persists ended_at and is deliberately idempotent at the data layer.
            if ended.status_code not in {200, 404}:
                ended.raise_for_status()
            deadline = time.perf_counter() + 1
            metrics = {}
            while time.perf_counter() < deadline:
                metrics = client.get(f"{args.http_base}/api/v1/runtime/metrics").json()
                if str(session_id) not in metrics.get("session_runtimes", {}) and metrics.get("active_turns") == 0 and metrics.get("outbound_queue_depth", 0) == 0:
                    break
                await asyncio.sleep(0.02)
            passed = initial["type"] == "state.changed" and str(session_id) not in metrics.get("session_runtimes", {}) and metrics.get("active_turns") == 0 and metrics.get("outbound_queue_depth", 0) == 0
            rows.append({
                "cycle": cycle, "session_id": session_id,
                "cleanup_ms": round((time.perf_counter() - started) * 1000, 3),
                "active_turns_after": metrics.get("active_turns"),
                "outbound_queue_after": metrics.get("outbound_queue_depth"),
                "runtime_present_after": str(session_id) in metrics.get("session_runtimes", {}),
                "result": "PASS" if passed else "FAIL",
            })
    finally:
        client.close()
    after = audio_files(roots)
    new_audio = sorted(after - before)
    ports = {str(port): port_open(port) for port in (7860, 8010, 8090, 8091)}
    passed = all(row["result"] == "PASS" for row in rows) and not new_audio and all(ports.values())
    summary = {
        "cycles": len(rows), "passed": sum(row["result"] == "PASS" for row in rows),
        "new_temporary_audio_files": new_audio, "ports": ports,
        "result": "PASS" if passed else "FAIL",
    }
    return summary, rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:7860")
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B3/AC07"))
    args = parser.parse_args()
    summary, rows = asyncio.run(run(args))
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "lifecycle.json").write_text(json.dumps({"summary": summary, "cycles": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.evidence / "manifest.json").write_text(json.dumps({"schema_version": 1, "command": f"python -m tests.b3.accept_lifecycle --cycles {args.cycles}", "summary": summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    raise SystemExit(0 if summary["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
