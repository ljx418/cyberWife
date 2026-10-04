"""B4-AC01/02 real speech -> ASR -> session -> memory -> prompt acceptance."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sqlite3
import struct
import time
import wave
from pathlib import Path

import httpx
import websockets

from cyberwife.adapters.speech_embedding_adapter import SpeechEmbeddingAdapter
from cyberwife.application.memory_service import MemoryService
from cyberwife.application.prompt_compiler import PromptCompiler, estimate_tokens
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


ROOT = Path(__file__).resolve().parents[2]


def read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as source:
        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
            raise ValueError("audio must be PCM16 mono 16kHz")
        pcm = source.readframes(source.getnframes())
    return pcm + b"\0" * ((-len(pcm)) % 640)


async def send_turn(socket, turn_id: int, pcm: bytes, client_seq: int, timeout: float):
    for chunk_seq, offset in enumerate(range(0, len(pcm), 640)):
        await socket.send(struct.pack("<IH", turn_id, chunk_seq) + pcm[offset : offset + 640])
    client_seq += 1
    await socket.send(json.dumps({"type": "audio.silence", "turn_id": turn_id, "event_seq": client_seq}))
    transcript = ""
    reply = ""
    errors = []
    while True:
        event = json.loads(await asyncio.wait_for(socket.recv(), timeout))
        if event["type"] == "transcript.final":
            transcript = str(event["payload"].get("text", ""))
        elif event["type"] == "reply.text.final":
            reply = str(event["payload"].get("text_final", ""))
        elif event["type"] == "reply.audio.chunk" and not reply:
            client_seq += 1
            await socket.send(json.dumps({
                "type": "audio.playback.started",
                "turn_id": turn_id,
                "trace_id": event["payload"]["trace_id"],
                "generation": event["payload"]["generation"],
                "asr_to_playback_ms": event["payload"]["server_elapsed_ms"],
                "browser_first_non_silent_wall_ms": time.time() * 1000,
                "event_seq": client_seq,
            }))
        elif event["type"] == "reply.audio.complete":
            client_seq += 1
            await socket.send(json.dumps({
                "type": "audio.playback.ended",
                "turn_id": turn_id,
                "generation": event["payload"]["generation"],
                "event_seq": client_seq,
            }))
        elif event["type"] == "error":
            errors.append(event["payload"].get("code"))
        if (
            event["type"] == "state.changed"
            and event.get("turn_id") == turn_id
            and event["payload"].get("current") == "listening"
        ):
            break
    return {"turn_id": turn_id, "transcript": transcript, "reply": reply, "errors": errors}, client_seq


async def run(args) -> dict:
    upstream = json.loads((ROOT / "audit/v1/B3/AC05/manifest.json").read_text(encoding="utf-8"))
    if upstream["summary"].get("result") != "PASS":
        raise RuntimeError("B3 real-session gate is not PASS")
    stable_pcm = read_pcm(args.stable_audio)
    temporary_pcm = read_pcm(args.temporary_audio)
    client = httpx.Client(timeout=180, trust_env=False)
    created = client.post(f"{args.http_base}/api/v1/sessions", json={"recording_policy": "standard"})
    created.raise_for_status()
    session_id = int(created.json()["id"])
    rows = []
    client_seq = 0
    async with websockets.connect(f"{args.ws_base}/ws/v1/sessions/{session_id}", max_size=2**20) as socket:
        await asyncio.wait_for(socket.recv(), args.timeout)
        for turn_id, pcm in enumerate((stable_pcm, temporary_pcm), 1):
            row, client_seq = await send_turn(socket, turn_id, pcm, client_seq, args.timeout)
            rows.append(row)
    ended = client.delete(f"{args.http_base}/api/v1/sessions/{session_id}")
    ended.raise_for_status()
    extraction = ended.json().get("memory_extraction") or {}

    repo = SqliteRepository(args.db, schema_sql_path=ROOT / "migrations/0001_init.sql")
    memory_repo = SqliteMemoryRepository(repo.conn, repo.lock)
    embedding = SpeechEmbeddingAdapter(args.speech_base, timeout_s=120)
    service = MemoryService(repo, memory_repo, embedding)
    created_records = [item for item in memory_repo.list_all() if item.source_session_id == session_id]
    real_turns = repo.list_session_turns(session_id)
    temporary_candidates = []
    for turn in real_turns:
        temporary_candidates.extend(
            item for item in service.extract_text(session_id, turn.id, turn.user_text)
            if 0.60 <= item.confidence < 0.80
        )
    recalled = service.recall("我周末喜欢喝什么，住在哪里？")
    prompt_memories = [(item.content, score) for item, score in recalled]
    compiled = PromptCompiler().compile(
        profile={"name": "她", "persona": "温柔", "relationship_context": "伴侣"},
        memories=prompt_memories,
        user_input="我周末喜欢喝什么，住在哪里？",
    )
    expected_fragments = {"用户叫小林", "用户喜欢红茶", "用户住在杭州", "用户生日是5月6日", "用户对花生过敏"}
    observed = {item.content for item in created_records}
    result = {
        "schema_version": 1,
        "evidence_level": "real_audio_real_asr_llm_tts_bge_sqlite_vec",
        "upstream_b3_session_id": upstream["summary"]["session_id"],
        "session_id": session_id,
        "audio_sha256": {
            "stable": hashlib.sha256(stable_pcm).hexdigest(),
            "temporary": hashlib.sha256(temporary_pcm).hexdigest(),
        },
        "turns": rows,
        "extraction": extraction,
        "stable_records": [
            {"id": item.id, "content": item.content, "confidence": item.confidence, "source_session_id": item.source_session_id}
            for item in created_records
        ],
        "temporary_candidate_count": len(temporary_candidates),
        "temporary_persisted_count": sum(
            any(marker in item.content for marker in ("今天", "现在", "刚才", "待会", "也许"))
            for item in created_records
        ),
        "recalled": [{"id": item.id, "content": item.content, "score": score} for item, score in recalled],
        "prompt_memory_count": len(prompt_memories),
        "prompt_memory_tokens": sum(estimate_tokens(content) for content, _ in prompt_memories),
        "prompt_exposes_technical_details": any(
            token in compiled.memories.lower() for token in ("sqlite", "vector", "fts", "embedding")
        ),
    }
    result["pass"] = bool(
        all(not row["errors"] and row["transcript"] and row["reply"] for row in rows)
        and observed == expected_fragments
        and extraction.get("pending_count") == 5
        and len(temporary_candidates) == 5
        and result["temporary_persisted_count"] == 0
        and 1 <= len(recalled) <= 4
        and result["prompt_memory_tokens"] <= 800
        and not result["prompt_exposes_technical_details"]
    )
    path = args.evidence / "result.json"
    args.evidence.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    for item in created_records:
        memory_repo.delete(item.id)
    result["cleanup_counts"] = memory_repo.layer_counts()
    (args.evidence / "cleanup.json").write_text(
        json.dumps({"session_id": session_id, "deleted_ids": [item.id for item in created_records], "counts": result["cleanup_counts"]}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    repo.close()
    client.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stable-audio", type=Path, required=True)
    parser.add_argument("--temporary-audio", type=Path, required=True)
    parser.add_argument("--db", type=Path, default=Path("/home/administrator/.cyberWife/cyberwife.db"))
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:7860")
    parser.add_argument("--speech-base", default="http://127.0.0.1:8091")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B4/B4.2"))
    args = parser.parse_args()
    result = asyncio.run(run(args))
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
