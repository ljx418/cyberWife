"""Real voice turn → pending memory → explicit confirmation acceptance."""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
import struct
import time
import wave
from pathlib import Path

import httpx
import websockets


def pcm16(payload: bytes) -> bytes:
    with wave.open(io.BytesIO(payload), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
            raise ValueError("preview is not PCM16 mono 16kHz")
        pcm = source.readframes(source.getnframes())
    return pcm + b"\0" * ((-len(pcm)) % 640)


async def run(args: argparse.Namespace) -> dict:
    phrase = "今天想早点休息。"
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        created = (await client.post(
            f"{args.http_base}/api/v1/sessions", json={"recording_policy": "standard"}
        )).json()
        session_id = int(created["id"])
        turn_id = int(created["next_turn_id"])
        preview = await client.post(f"{args.http_base}/api/v1/tts/preview", json={"text": phrase})
        preview.raise_for_status()
        pcm = pcm16(preview.content)
        transcript = ""
        reply = ""
        event_types: list[str] = []
        client_sequence = 0
        playback_started = False
        try:
            async with websockets.connect(
                f"{args.ws_base}/ws/v1/sessions/{created['session_ref']}", max_size=8 * 1024 * 1024
            ) as socket:
                await asyncio.wait_for(socket.recv(), args.timeout)
                for chunk_sequence, offset in enumerate(range(0, len(pcm), 640)):
                    await socket.send(
                        struct.pack("<IH", turn_id, chunk_sequence) + pcm[offset:offset + 640]
                    )
                client_sequence += 1
                await socket.send(json.dumps({
                    "type": "audio.silence", "turn_id": turn_id,
                    "event_seq": client_sequence,
                }))
                deadline = time.monotonic() + args.timeout
                terminal = False
                while not terminal:
                    event = json.loads(await asyncio.wait_for(socket.recv(), deadline - time.monotonic()))
                    event_types.append(event["type"])
                    if event["type"] == "transcript.final":
                        transcript = str(event["payload"].get("text", ""))
                    elif event["type"] == "reply.text.final":
                        reply = str(event["payload"].get("text_final", ""))
                    elif event["type"] == "reply.audio.chunk":
                        # Decode to prove the payload is real, but persist only a digest.
                        audio = base64.b64decode(event["payload"]["audio_chunk_b64"])
                        if audio and not playback_started:
                            client_sequence += 1
                            await socket.send(json.dumps({
                                "type": "audio.playback.started", "turn_id": turn_id,
                                "trace_id": event["payload"]["trace_id"],
                                "generation": event["payload"]["generation"],
                                "asr_to_playback_ms": event["payload"]["server_elapsed_ms"],
                                "browser_first_non_silent_wall_ms": time.time() * 1000,
                                "event_seq": client_sequence,
                            }))
                            playback_started = True
                    elif event["type"] == "reply.audio.complete":
                        client_sequence += 1
                        await socket.send(json.dumps({
                            "type": "audio.playback.ended", "turn_id": turn_id,
                            "generation": event["payload"]["generation"],
                            "event_seq": client_sequence,
                        }))
                    elif event["type"] == "state.changed" and event.get("turn_id") == turn_id:
                        terminal = event["payload"].get("reason") in {"playback_complete", "text_complete"}
                    elif event["type"] == "error":
                        raise RuntimeError(str(event.get("payload", {})))
        finally:
            closed = await client.delete(f"{args.http_base}/api/v1/sessions/{created['session_ref']}")
            closed.raise_for_status()

        pending = (await client.get(f"{args.http_base}/api/v1/memory-candidates")).json()["items"]
        candidate = next(
            item for item in pending
            if int(item["source_session_id"]) == session_id
        )
        persisted_turn_id = int(candidate["source_turn_id"])
        before = (await client.get(f"{args.http_base}/api/v1/memories", params={"q": candidate["content"]})).json()["items"]
        confirmed_response = await client.post(
            f"{args.http_base}/api/v1/memory-candidates/confirm",
            json={"session_id": session_id, "turn_id": persisted_turn_id, "content": candidate["content"]},
        )
        confirmed_response.raise_for_status()
        confirmed = confirmed_response.json()
        after = (await client.get(f"{args.http_base}/api/v1/memories", params={"q": candidate["content"]})).json()["items"]
        duplicate = (await client.post(
            f"{args.http_base}/api/v1/memory-candidates/confirm",
            json={"session_id": session_id, "turn_id": persisted_turn_id, "content": candidate["content"]},
        )).json()
        deleted = (await client.delete(
            f"{args.http_base}/api/v1/memories/{confirmed['id']}"
        )).json()
        final = (await client.get(f"{args.http_base}/api/v1/memories", params={"q": candidate["content"]})).json()["items"]

    checks = {
        "real_transcript": bool(transcript.strip()),
        "real_reply": bool(reply.strip()),
        "candidate_pending": candidate["confidence"] < 0.8,
        "pending_not_recalled": before == [],
        "confirmed_recalled": any(item["id"] == confirmed["id"] for item in after),
        "confirmation_idempotent": duplicate.get("id") == confirmed["id"],
        "deleted_from_recall": deleted.get("deleted") is True and final == [],
    }
    report = {
        "schema_version": 1,
        "gate": "UX10-real-memory-candidate",
        "audio_persisted": False,
        "input_audio_sha256": hashlib.sha256(pcm).hexdigest(),
        "session_id": session_id,
        "client_turn_id": turn_id,
        "persisted_turn_id": persisted_turn_id,
        "input_transcript": transcript,
        "reply_text": reply,
        "candidate": candidate,
        "event_types": sorted(set(event_types)),
        "checks": checks,
        "result": "PASS" if all(checks.values()) else "FAIL",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:7860")
    parser.add_argument("--timeout", type=float, default=120)
    parser.add_argument("--output", type=Path, default=Path("audit/v1/UX10/real-memory-candidate.json"))
    args = parser.parse_args()
    result = asyncio.run(run(args))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
