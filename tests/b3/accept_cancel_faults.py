"""B3-AC04 real lifecycle faults plus deterministic cancel deadline injection."""
from __future__ import annotations

import argparse
import asyncio
import json
import struct
import time
import wave
from pathlib import Path

import httpx
import websockets

from cyberwife.application.conversation_orchestrator import ConversationOrchestrator
from cyberwife.application.interruption_controller import InterruptionController
from cyberwife.domain.conversation import SessionState


def read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as source:
        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
            raise ValueError("acceptance audio must be PCM16/16kHz/mono")
        value = source.readframes(source.getnframes())
    return value + b"\0" * ((-len(value)) % 640)


async def send_turn(socket, turn_id: int, pcm: bytes, event_seq: int) -> None:
    for sequence, offset in enumerate(range(0, len(pcm), 640)):
        await socket.send(struct.pack("<IH", turn_id, sequence) + pcm[offset:offset + 640])
    await socket.send(json.dumps({"type": "audio.silence", "turn_id": turn_id, "event_seq": event_seq}))


async def real_repeat_cancel(args, client: httpx.Client, pcm: bytes) -> dict:
    session_id = int(client.post(f"{args.http_base}/api/v1/sessions", json={}).json()["id"])
    cancel_events = []
    started = 0.0
    try:
        async with websockets.connect(f"{args.ws_base}/ws/v1/sessions/{session_id}") as socket:
            await socket.recv()
            await send_turn(socket, 1, pcm, 1)
            while True:
                event = json.loads(await asyncio.wait_for(socket.recv(), args.timeout))
                if event["type"] == "state.changed" and event["payload"].get("current") == "thinking":
                    break
            started = time.perf_counter()
            await socket.send(json.dumps({"type": "barge_in.detected", "turn_id": 1, "event_seq": 2}))
            while True:
                event = json.loads(await asyncio.wait_for(socket.recv(), 2.0))
                if event["type"] == "turn.cancelled":
                    cancel_events.append(event)
                    break
            first_ms = (time.perf_counter() - started) * 1000
            await socket.send(json.dumps({"type": "barge_in.detected", "turn_id": 1, "event_seq": 3}))
            try:
                while True:
                    event = json.loads(await asyncio.wait_for(socket.recv(), 0.5))
                    if event["type"] == "turn.cancelled":
                        cancel_events.append(event)
            except asyncio.TimeoutError:
                pass
            metrics = client.get(f"{args.http_base}/api/v1/runtime/metrics").json()
    finally:
        client.delete(f"{args.http_base}/api/v1/sessions/{session_id}")
    passed = len(cancel_events) == 1 and first_ms <= 1000 and metrics["active_turns"] == 0 and metrics["llm_queue_depth"] == 0
    return {
        "case": "repeat_cancel_real_models", "elapsed_ms": round(first_ms, 3),
        "cancel_events": len(cancel_events), "task_after": metrics["active_turns"],
        "queue_after": metrics["llm_queue_depth"], "result": "PASS" if passed else "FAIL",
    }


async def real_disconnect(args, client: httpx.Client, pcm: bytes) -> dict:
    session_id = int(client.post(f"{args.http_base}/api/v1/sessions", json={}).json()["id"])
    socket = await websockets.connect(f"{args.ws_base}/ws/v1/sessions/{session_id}")
    await socket.recv()
    await send_turn(socket, 1, pcm, 1)
    while True:
        event = json.loads(await asyncio.wait_for(socket.recv(), args.timeout))
        if event["type"] == "state.changed" and event["payload"].get("current") == "thinking":
            break
    started = time.perf_counter()
    await socket.close()
    metrics = {}
    while time.perf_counter() - started < 1.2:
        metrics = client.get(f"{args.http_base}/api/v1/runtime/metrics").json()
        if metrics.get("active_turns") == 0 and str(session_id) not in metrics.get("session_runtimes", {}):
            break
        await asyncio.sleep(0.02)
    elapsed_ms = (time.perf_counter() - started) * 1000
    client.delete(f"{args.http_base}/api/v1/sessions/{session_id}")
    passed = elapsed_ms <= 1000 and metrics.get("active_turns") == 0 and str(session_id) not in metrics.get("session_runtimes", {})
    return {
        "case": "disconnect_real_models", "elapsed_ms": round(elapsed_ms, 3),
        "task_after": metrics.get("active_turns"),
        "runtime_present_after": str(session_id) in metrics.get("session_runtimes", {}),
        "result": "PASS" if passed else "FAIL",
    }


async def injected_timeout() -> dict:
    orchestrator = ConversationOrchestrator()
    session = orchestrator.open_session()
    orchestrator.transition(session.id, SessionState.LISTENING)
    turn = orchestrator.begin_turn(session.id, 1)
    orchestrator.transition(session.id, SessionState.THINKING)
    controller = InterruptionController(orchestrator, component_timeout_s=0.05)
    controller.register(session.id, turn.id, orchestrator.generation(session.id))
    controller.add_hook("slow_component", lambda _token: time.sleep(0.5))
    started = time.perf_counter()
    result = await controller.cancel(session.id, reason="component_failure")
    elapsed_ms = (time.perf_counter() - started) * 1000
    passed = elapsed_ms <= 1000 and result.component_errors == ("slow_component:timeout",) and session.state == SessionState.LISTENING
    return {
        "case": "slow_component_fault_injection", "evidence_level": "deterministic_contract",
        "elapsed_ms": round(elapsed_ms, 3), "component_errors": list(result.component_errors),
        "state_after": session.state.value, "result": "PASS" if passed else "FAIL",
    }


async def run(args) -> list[dict]:
    pcm = read_pcm(args.audio)
    client = httpx.Client(timeout=10, trust_env=False)
    try:
        return [
            await real_repeat_cancel(args, client, pcm),
            await real_disconnect(args, client, pcm),
            await injected_timeout(),
        ]
    finally:
        client.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--matrix", default="all")
    parser.add_argument("--audio", type=Path, default=Path("audit/tts_nonstreaming.wav"))
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:7860")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B3/AC04"))
    args = parser.parse_args()
    matrix = asyncio.run(run(args))
    summary = {"cases": len(matrix), "passed": sum(row["result"] == "PASS" for row in matrix), "result": "PASS" if all(row["result"] == "PASS" for row in matrix) else "FAIL"}
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "fault-matrix.json").write_text(json.dumps({"summary": summary, "matrix": matrix}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.evidence / "manifest.json").write_text(json.dumps({"schema_version": 1, "command": "python -m tests.b3.accept_cancel_faults --matrix all", "summary": summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    raise SystemExit(0 if summary["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
