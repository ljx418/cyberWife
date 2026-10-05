"""B3-AC05: 100 sequential real-audio/model turns with live Avatar transport."""
from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import re
import statistics
import struct
import time
import wave
from pathlib import Path
from urllib.parse import quote

import httpx
import websockets


def normalize(text: str) -> str:
    return re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", text)


def read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as source:
        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
            raise ValueError("acceptance audio must be PCM16/16kHz/mono")
        value = source.readframes(source.getnframes())
    return value + b"\0" * ((-len(value)) % 640)


async def avatar_transport(
    stats: dict, ready: asyncio.Event, stop: asyncio.Event, avatar_id: str
) -> None:
    async with websockets.connect(
        f"ws://127.0.0.1:8010/ws/v1/avatar?avatar_id={quote(avatar_id, safe='')}",
        origin="http://127.0.0.1:4173",
        max_size=8 * 1024 * 1024,
    ) as socket:
        while not stop.is_set():
            try:
                message = await asyncio.wait_for(socket.recv(), 0.5)
            except asyncio.TimeoutError:
                continue
            if isinstance(message, str):
                config = json.loads(message)
                if config.get("type") == "video.config":
                    stats["session_id"] = config.get("session_id")
                    stats["protocol_version"] = config.get("version")
            else:
                stats["frames"] += 1
                if len(message) >= 18:
                    stats["generations"].add(struct.unpack_from("<I", message, 14)[0])
                ready.set()


async def run(args) -> tuple[dict, list[dict], dict]:
    pcm = read_pcm(args.audio)
    client = httpx.Client(timeout=10, trust_env=False)
    response = client.post(f"{args.http_base}/api/v1/sessions", json={"recording_policy": "standard"})
    response.raise_for_status()
    session_id = int(response.json()["id"])
    active_avatar = client.get(f"{args.http_base}/api/v1/avatar/active")
    active_avatar.raise_for_status()
    avatar_id = str(active_avatar.json()["avatar_id"])
    avatar_stats = {
        "frames": 0,
        "generations": set(),
        "session_id": None,
        "protocol_version": None,
        "avatar_id": avatar_id,
    }
    avatar_ready, avatar_stop = asyncio.Event(), asyncio.Event()
    avatar_task = asyncio.create_task(
        avatar_transport(avatar_stats, avatar_ready, avatar_stop, avatar_id)
    )
    rows: list[dict] = []
    all_sequences: list[int] = []
    client_seq = 0
    try:
        await asyncio.wait_for(avatar_ready.wait(), 15)
        async with websockets.connect(f"{args.ws_base}/ws/v1/sessions/{session_id}", max_size=2**20) as socket:
            initial = json.loads(await asyncio.wait_for(socket.recv(), args.timeout))
            all_sequences.append(int(initial["event_seq"]))
            for turn_id in range(1, args.turns + 1):
                started = time.perf_counter()
                for chunk_seq, offset in enumerate(range(0, len(pcm), 640)):
                    await socket.send(struct.pack("<IH", turn_id, chunk_seq) + pcm[offset:offset + 640])
                client_seq += 1
                await socket.send(json.dumps({"type": "audio.silence", "turn_id": turn_id, "event_seq": client_seq}))
                events = []
                terminal = False
                playback_confirmed = False
                while not terminal:
                    event = json.loads(await asyncio.wait_for(socket.recv(), args.timeout))
                    events.append(event)
                    all_sequences.append(int(event["event_seq"]))
                    if event["type"] == "reply.audio.chunk" and not playback_confirmed:
                        client_seq += 1
                        await socket.send(json.dumps({
                            "type": "audio.playback.started", "turn_id": turn_id,
                            "trace_id": event["payload"]["trace_id"],
                            "generation": event["payload"]["generation"],
                            "asr_to_playback_ms": event["payload"]["server_elapsed_ms"],
                            "browser_first_non_silent_wall_ms": time.time() * 1000,
                            "event_seq": client_seq,
                        }))
                        playback_confirmed = True
                    if event["type"] == "reply.audio.complete":
                        client_seq += 1
                        await socket.send(json.dumps({
                            "type": "audio.playback.ended", "turn_id": turn_id,
                            "generation": event["payload"]["generation"], "event_seq": client_seq,
                        }))
                    if event["type"] == "state.changed" and event.get("turn_id") == turn_id and event["payload"].get("reason") in {"playback_complete", "text_complete"}:
                        terminal = True
                    if event["type"] == "error":
                        terminal = True
                transcript = next((event["payload"].get("text", "") for event in events if event["type"] == "transcript.final"), "")
                reply = next((event["payload"].get("text_final", "") for event in events if event["type"] == "reply.text.final"), "")
                generations = {event.get("payload", {}).get("generation") for event in events if event.get("payload", {}).get("generation") is not None}
                metrics = client.get(f"{args.http_base}/api/v1/runtime/metrics").json()
                media_modes = [event["payload"].get("mode") for event in events if event["type"] == "media.state"]
                passed = all((
                    normalize(transcript) == normalize(args.expected), bool(reply),
                    not any(event["type"] == "error" for event in events),
                    generations == {turn_id}, metrics["active_turns"] == 0,
                    metrics["llm_queue_depth"] == 0,
                    "static_fallback" not in media_modes and "text_only" not in media_modes,
                ))
                row = {
                    "turn": turn_id, "passed": passed,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 3),
                    "transcript": transcript, "reply_chars": len(reply),
                    "generation": turn_id, "observed_generations": sorted(generations),
                    "event_count": len(events), "media_modes": media_modes,
                    "error_codes": [event.get("payload", {}).get("code") for event in events if event["type"] == "error"],
                    "avatar_frames_total": avatar_stats["frames"],
                    "active_turns_after": metrics["active_turns"],
                    "llm_queue_after": metrics["llm_queue_depth"],
                }
                rows.append(row)
                args.evidence.mkdir(parents=True, exist_ok=True)
                (args.evidence / "turns.partial.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                print(json.dumps(row, ensure_ascii=False), flush=True)
    finally:
        avatar_stop.set()
        await asyncio.gather(avatar_task, return_exceptions=True)
        client.delete(f"{args.http_base}/api/v1/sessions/{session_id}")
        client.close()
    latencies = sorted(row["latency_ms"] for row in rows)
    success_rate = sum(row["passed"] for row in rows) / max(1, len(rows))
    strict_sequences = all(right > left for left, right in zip(all_sequences, all_sequences[1:]))
    avatar = {**avatar_stats, "generations": sorted(avatar_stats["generations"])}
    passed = len(rows) == args.turns and success_rate >= 0.95 and strict_sequences and avatar["frames"] > 0 and avatar["protocol_version"] == 2
    summary = {
        "evidence_level": "e2e_real_models_authorized_audio_live_avatar",
        "session_id": session_id, "turns": len(rows), "passed_turns": sum(row["passed"] for row in rows),
        "success_rate": round(success_rate, 4), "event_seq_strict": strict_sequences,
        "latency_p50_ms": round(statistics.median(latencies), 3),
        "latency_p95_ms": latencies[max(0, int(len(latencies) * 0.95) - 1)],
        "audio_sha256": hashlib.sha256(pcm).hexdigest(), "result": "PASS" if passed else "FAIL",
    }
    return summary, rows, avatar


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--turns", type=int, default=100)
    parser.add_argument("--real-models", action="store_true")
    parser.add_argument("--audio", type=Path, default=Path("audit/tts_nonstreaming.wav"))
    parser.add_argument("--expected", default="今天天气不错，我想和你聊聊天")
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:7860")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B3/AC05"))
    args = parser.parse_args()
    if not args.real_models:
        raise SystemExit(3)
    summary, rows, avatar = asyncio.run(run(args))
    args.evidence.mkdir(parents=True, exist_ok=True)
    headers = list(rows[0]) if rows else []
    with (args.evidence / "turns.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers)
        writer.writeheader(); writer.writerows(rows)
    (args.evidence / "avatar.json").write_text(json.dumps(avatar, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.evidence / "manifest.json").write_text(json.dumps({"schema_version": 1, "command": f"python -m tests.b3.accept_turns --turns {args.turns} --real-models", "summary": summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    raise SystemExit(0 if summary["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
