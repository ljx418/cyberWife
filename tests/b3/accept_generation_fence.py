"""B3-AC02/03: real-model cancellation fence, persistence, and next-turn pairing."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import struct
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

import httpx
import websockets


def read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as source:
        actual = source.getframerate(), source.getnchannels(), source.getsampwidth()
        if actual != (16000, 1, 2):
            raise ValueError(f"expected PCM16/16kHz/mono, got {actual}")
        pcm = source.readframes(source.getnframes())
    return pcm + b"\0" * ((-len(pcm)) % 640)


async def send_audio(socket, turn_id: int, pcm: bytes, *, event_seq: int) -> None:
    for sequence, offset in enumerate(range(0, len(pcm), 640)):
        await socket.send(struct.pack("<IH", turn_id, sequence) + pcm[offset:offset + 640])
    await socket.send(json.dumps({"type": "audio.silence", "turn_id": turn_id, "event_seq": event_seq}))


def compact(event: dict) -> dict:
    result = json.loads(json.dumps(event, ensure_ascii=False))
    payload = result.get("payload", {})
    audio = payload.pop("audio_chunk_b64", None)
    if audio is not None:
        payload["audio_chunk_base64_length"] = len(audio)
        payload["audio_chunk_sha256"] = hashlib.sha256(audio.encode("ascii")).hexdigest()
    result["observed_at"] = datetime.now(timezone.utc).isoformat()
    return result


def turn_rows(db: Path, session_id: int) -> list[dict]:
    with sqlite3.connect(db) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT ordinal,user_text,assistant_text,status FROM turns WHERE session_id=? ORDER BY ordinal",
            (session_id,),
        ).fetchall()
    return [dict(row) for row in rows]


async def run(args) -> tuple[dict, list[dict], dict, dict]:
    pcm1, pcm2 = read_pcm(args.audio1), read_pcm(args.audio2)
    client = httpx.Client(timeout=10, trust_env=False)
    response = client.post(f"{args.http_base}/api/v1/sessions", json={"recording_policy": "standard"})
    response.raise_for_status()
    session_id = int(response.json()["id"])
    events: list[dict] = []
    at_cancel: list[dict] = []
    cancelled_seen = False
    interrupt_sent = False
    try:
        async with websockets.connect(f"{args.ws_base}/ws/v1/sessions/{session_id}", max_size=2**20) as socket:
            events.append(compact(json.loads(await asyncio.wait_for(socket.recv(), args.timeout))))
            await send_audio(socket, 1, pcm1, event_seq=1)
            while not cancelled_seen:
                event = json.loads(await asyncio.wait_for(socket.recv(), args.timeout))
                events.append(compact(event))
                if event["type"] == "reply.audio.chunk" and not interrupt_sent:
                    await socket.send(json.dumps({"type": "barge_in.detected", "turn_id": 1, "event_seq": 2}))
                    interrupt_sent = True
                if event["type"] == "turn.cancelled":
                    cancelled_seen = True
            at_cancel = turn_rows(args.db, session_id)

            await send_audio(socket, 2, pcm2, event_seq=3)
            turn2_complete = False
            while not turn2_complete:
                event = json.loads(await asyncio.wait_for(socket.recv(), args.timeout))
                events.append(compact(event))
                if event["type"] == "reply.audio.complete" and event.get("turn_id") == 2:
                    await socket.send(json.dumps({
                        "type": "audio.playback.ended",
                        "turn_id": 2,
                        "generation": event["payload"]["generation"],
                    }))
                if event["type"] == "state.changed" and event.get("turn_id") == 2 and event["payload"].get("reason") in {"playback_complete", "text_complete"}:
                    turn2_complete = True

            late_deadline = time.monotonic() + args.late_window
            while time.monotonic() < late_deadline:
                try:
                    event = json.loads(await asyncio.wait_for(socket.recv(), 0.2))
                except asyncio.TimeoutError:
                    continue
                events.append(compact(event))
        final_rows = turn_rows(args.db, session_id)
        metrics = client.get(f"{args.http_base}/api/v1/runtime/metrics").json()
    finally:
        client.delete(f"{args.http_base}/api/v1/sessions/{session_id}")
        client.close()

    cancel_index = next(i for i, event in enumerate(events) if event["type"] == "turn.cancelled")
    post_cancel = events[cancel_index + 1:]
    old_leaks = [
        event for event in post_cancel
        if event["type"] in {"reply.text.delta", "reply.text.final", "reply.audio.chunk", "reply.audio.complete"}
        and event.get("payload", {}).get("generation") == 1
    ]
    turn2_events = [event for event in events if event.get("turn_id") == 2]
    turn2_transcript = next((event["payload"].get("text", "") for event in turn2_events if event["type"] == "transcript.final"), "")
    turn2_reply = next((event["payload"].get("text_final", "") for event in turn2_events if event["type"] == "reply.text.final"), "")
    at_cancel_turn1 = next((row for row in at_cancel if row["ordinal"] == 1), None)
    final_turn1 = next((row for row in final_rows if row["ordinal"] == 1), None)
    final_turn2 = next((row for row in final_rows if row["ordinal"] == 2), None)
    sequences = [int(event["event_seq"]) for event in events]
    counts = {
        "events_total": len(events),
        "old_generation_after_cancel": len(old_leaks),
        "generation_1": sum(event.get("payload", {}).get("generation") == 1 for event in events),
        "generation_3": sum(event.get("payload", {}).get("generation") == 3 for event in events),
        "turn2_events": len(turn2_events),
    }
    db_diff = {
        "at_cancel": at_cancel,
        "final": final_rows,
        "cancelled_turn_changed_after_cancel": at_cancel_turn1 != final_turn1,
    }
    passed = all((
        counts["old_generation_after_cancel"] == 0,
        at_cancel_turn1 is not None and at_cancel_turn1["status"] == "cancelled",
        at_cancel_turn1 == final_turn1,
        final_turn2 is not None and final_turn2["status"] == "completed",
        bool(turn2_transcript),
        bool(turn2_reply),
        all(event.get("payload", {}).get("generation") in {None, 3} for event in turn2_events),
        all(right > left for left, right in zip(sequences, sequences[1:])),
        metrics.get("active_turns") == 0,
        metrics.get("llm_queue_depth") == 0,
    ))
    summary = {
        "evidence_level": "e2e_real_models",
        "session_id": session_id,
        "turn2_transcript": turn2_transcript,
        "turn2_reply_chars": len(turn2_reply),
        "audio_sha256": [hashlib.sha256(pcm1).hexdigest(), hashlib.sha256(pcm2).hexdigest()],
        "result": "PASS" if passed else "FAIL",
    }
    return summary, events, counts, db_diff


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio1", type=Path, default=Path("audit/tts_nonstream_long_t1.wav"))
    parser.add_argument("--audio2", type=Path, default=Path("audit/tts_nonstreaming.wav"))
    parser.add_argument("--db", type=Path, default=Path("/home/administrator/.cyberWife/cyberwife.db"))
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:7860")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--late-window", type=float, default=2.0)
    parser.add_argument("--inject-late", default="all")
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B3/AC02-03"))
    args = parser.parse_args()
    summary, events, counts, db_diff = asyncio.run(run(args))
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "events.jsonl").write_text("".join(json.dumps(event, ensure_ascii=False) + "\n" for event in events), encoding="utf-8")
    (args.evidence / "generation-counts.json").write_text(json.dumps(counts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.evidence / "db-diff.json").write_text(json.dumps(db_diff, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.evidence / "manifest.json").write_text(json.dumps({"schema_version": 1, "command": "python -m tests.b3.accept_generation_fence --inject-late all", "summary": summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    raise SystemExit(0 if summary["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
