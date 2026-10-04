"""Run the real WebSocket PCM -> VAD -> ASR -> LLM text-chain acceptance."""
from __future__ import annotations

import argparse
import asyncio
import json
import re
import statistics
import struct
import time
import wave
from pathlib import Path

import httpx
import websockets


def _normalize(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)


def _read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as wav:
        actual = (wav.getframerate(), wav.getnchannels(), wav.getsampwidth())
        if actual != (16000, 1, 2):
            raise ValueError(f"expected PCM16/16kHz/mono, got {actual}")
        pcm = wav.readframes(wav.getnframes())
    return pcm + b"\0" * ((-len(pcm)) % 640)


async def run(args) -> dict:
    pcm = _read_pcm(args.audio)
    client = httpx.Client(timeout=10, trust_env=False)
    created = client.post(
        f"{args.http_base}/api/v1/sessions",
        json={"recording_policy": "standard"},
    )
    created.raise_for_status()
    session_id = int(created.json()["id"])
    results: list[dict] = []
    event_sequences: list[int] = []
    try:
        async with websockets.connect(
            f"{args.ws_base}/ws/v1/sessions/{session_id}", max_size=2**20
        ) as socket:
            initial = json.loads(await socket.recv())
            event_sequences.append(initial["event_seq"])
            for turn_id in range(1, args.turns + 1):
                started = time.perf_counter()
                for chunk_seq, offset in enumerate(range(0, len(pcm), 640)):
                    await socket.send(
                        struct.pack("<IH", turn_id, chunk_seq) + pcm[offset:offset + 640]
                    )
                await socket.send(json.dumps({
                    "type": "audio.silence",
                    "turn_id": turn_id,
                    "event_seq": turn_id,
                }))
                events = []
                while True:
                    event = json.loads(await asyncio.wait_for(socket.recv(), args.timeout))
                    events.append(event)
                    event_sequences.append(event["event_seq"])
                    if event["type"] == "reply.audio.complete":
                        await socket.send(json.dumps({
                            "type": "audio.playback.ended",
                            "turn_id": turn_id,
                            "generation": event["payload"]["generation"],
                        }))
                    if event["type"] == "error" or (
                        event["type"] == "state.changed"
                        and event["payload"].get("reason") == "text_complete"
                    ):
                        break
                transcript = next(
                    (e["payload"]["text"] for e in events if e["type"] == "transcript.final"), ""
                )
                reply = next(
                    (e["payload"]["text_final"] for e in events if e["type"] == "reply.text.final"), ""
                )
                traces = {
                    e["payload"].get("trace_id")
                    for e in events
                    if e.get("turn_id") == turn_id and e["payload"].get("trace_id")
                }
                metrics = client.get(f"{args.http_base}/api/v1/runtime/metrics").json()
                passed = (
                    _normalize(transcript) == _normalize(args.expected)
                    and bool(reply)
                    and not any(tag in reply.lower() for tag in ("<think>", "<analysis>"))
                    and not any(e["type"] == "error" for e in events)
                    and all(e.get("turn_id") in {turn_id, None} for e in events)
                    and len(traces) == 1
                    and metrics["active_turns"] == 0
                    and metrics["llm_queue_depth"] == 0
                )
                result = {
                    "turn": turn_id,
                    "passed": passed,
                    "latency_ms": round((time.perf_counter() - started) * 1000),
                    "transcript": transcript,
                    "reply_chars": len(reply),
                    "delta_count": sum(e["type"] == "reply.text.delta" for e in events),
                }
                results.append(result)
                print(json.dumps(result, ensure_ascii=False), flush=True)
    finally:
        client.delete(f"{args.http_base}/api/v1/sessions/{session_id}")
        client.close()
    latencies = [result["latency_ms"] for result in results]
    return {
        "passed": sum(result["passed"] for result in results),
        "total": len(results),
        "event_seq_strict": all(b > a for a, b in zip(event_sequences, event_sequences[1:])),
        "latency_p50_ms": round(statistics.median(latencies)),
        "latency_p95_ms": sorted(latencies)[max(0, round(len(latencies) * 0.95) - 1)],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", type=Path, default=Path("audit/tts_nonstreaming.wav"))
    parser.add_argument("--expected", default="今天天气不错，我想和你聊聊天")
    parser.add_argument("--turns", type=int, default=20)
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:7860")
    parser.add_argument("--timeout", type=float, default=120.0)
    args = parser.parse_args()
    summary = asyncio.run(run(args))
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    if summary["passed"] < max(1, args.turns * 19 // 20) or not summary["event_seq_strict"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
