"""B4-AC06/07: real no-record and irreversible mid-session privacy acceptance."""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import re
import sqlite3
import struct
import time
import wave
from pathlib import Path

import httpx
import websockets


def read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as source:
        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
            raise ValueError("audio must be PCM16 mono 16kHz")
        pcm = source.readframes(source.getnframes())
    return pcm + b"\0" * ((-len(pcm)) % 640)


def business_counts(db: Path) -> dict[str, int]:
    conn = sqlite3.connect(str(db))
    try:
        result = {
            table: int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
            for table in ("sessions", "turns", "session_transcripts", "session_summaries", "memories", "memory_vectors_meta")
        }
        result["no_record_audit"] = int(conn.execute(
            "SELECT COUNT(*) FROM audit_events WHERE action='session.no_record'"
        ).fetchone()[0])
        return result
    finally:
        conn.close()


def audio_files(data_root: Path) -> dict[str, int]:
    return {
        str(path.relative_to(data_root)): path.stat().st_size
        for path in data_root.rglob("*")
        if path.is_file() and path.suffix.lower() in {".wav", ".pcm", ".mp3", ".flac"}
    }


async def send_turn(socket, turn_id: int, pcm: bytes, client_seq: int, timeout: float):
    for chunk_seq, offset in enumerate(range(0, len(pcm), 640)):
        await socket.send(struct.pack("<IH", turn_id, chunk_seq) + pcm[offset:offset + 640])
    client_seq += 1
    await socket.send(json.dumps({"type": "audio.silence", "turn_id": turn_id, "event_seq": client_seq}))
    events = []
    playback_started = False
    while True:
        event = json.loads(await asyncio.wait_for(socket.recv(), timeout))
        events.append(event)
        if event["type"] == "reply.audio.chunk" and not playback_started:
            client_seq += 1
            await socket.send(json.dumps({
                "type": "audio.playback.started", "turn_id": turn_id,
                "trace_id": event["payload"]["trace_id"],
                "generation": event["payload"]["generation"],
                "asr_to_playback_ms": event["payload"]["server_elapsed_ms"],
                "browser_first_non_silent_wall_ms": time.time() * 1000,
                "event_seq": client_seq,
            }))
            playback_started = True
        if event["type"] == "reply.audio.complete":
            client_seq += 1
            await socket.send(json.dumps({
                "type": "audio.playback.ended", "turn_id": turn_id,
                "generation": event["payload"]["generation"], "event_seq": client_seq,
            }))
        if event["type"] == "state.changed" and event.get("turn_id") == turn_id and event["payload"].get("current") == "listening":
            break
        if event["type"] == "error":
            break
    return events, client_seq


async def five_turns(ws_url: str, pcm: bytes, timeout: float, *, switch=None):
    rows, all_events, client_seq = [], [], 0
    async with websockets.connect(ws_url, max_size=2**20) as socket:
        initial = json.loads(await asyncio.wait_for(socket.recv(), timeout))
        all_events.append(initial)
        for turn_id in range(1, 6):
            events, client_seq = await send_turn(socket, turn_id, pcm, client_seq, timeout)
            all_events.extend(events)
            rows.append({
                "turn": turn_id,
                "transcript": next((e["payload"].get("text", "") for e in events if e["type"] == "transcript.final"), ""),
                "reply_chars": len(next((e["payload"].get("text_final", "") for e in events if e["type"] == "reply.text.final"), "")),
                "errors": [e["payload"].get("code") for e in events if e["type"] == "error"],
            })
            if turn_id == 1 and switch is not None:
                switch()
        client_seq += 1
        await socket.send(json.dumps({"type": "conversation.stop", "event_seq": client_seq}))
    return rows, all_events


async def run(args) -> dict:
    pcm = read_pcm(args.audio)
    http = httpx.Client(timeout=180, trust_env=False)
    before = business_counts(args.db)
    files_before = audio_files(args.data_root)

    created = http.post(f"{args.http_base}/api/v1/sessions", json={"recording_policy": "none"})
    created.raise_for_status()
    private = created.json()
    rows_none, events_none = await five_turns(
        args.ws_base + private["ws_url"].removeprefix("/ws/v1"), pcm, args.timeout
    )
    after_none = business_counts(args.db)
    search_after_none = http.get(f"{args.http_base}/api/v1/memories", params={"q": args.search}).json()

    standard = http.post(f"{args.http_base}/api/v1/sessions", json={"recording_policy": "standard"})
    standard.raise_for_status()
    standard_body = standard.json()
    switch_result = {}

    def switch():
        response = http.patch(f"{args.http_base}/api/v1/sessions/{standard_body['session_ref']}/no_record")
        response.raise_for_status()
        switch_result.update(response.json())

    rows_switch, events_switch = await five_turns(
        args.ws_base + standard_body["ws_url"].removeprefix("/ws/v1"), pcm, args.timeout, switch=switch
    )
    after_switch = business_counts(args.db)
    search_after_switch = http.get(f"{args.http_base}/api/v1/memories", params={"q": args.search}).json()
    files_after = audio_files(args.data_root)
    serialized_public = json.dumps(
        {"create_none": private, "events_none": events_none, "switch": switch_result, "events_switch": events_switch},
        ensure_ascii=False,
    )
    internal_pattern = re.compile(r"46[0-9]{17}")
    none_delta = {key: after_none[key] - before[key] for key in before if key != "no_record_audit"}
    # The standard session created for the switch is erased; no business row
    # from either scenario may survive relative to the original baseline.
    final_delta = {key: after_switch[key] - before[key] for key in before if key != "no_record_audit"}
    result = {
        "schema_version": 1,
        "evidence_level": "real_audio_real_asr_llm_tts_sqlite_wal",
        "audio_sha256": hashlib.sha256(pcm).hexdigest(),
        "create_none": {"id": private["id"], "opaque_ref": len(private["session_ref"]) == 32},
        "none_turns": rows_none,
        "switch_turns": rows_switch,
        "switch_result": switch_result,
        "counts": {"before": before, "after_none": after_none, "after_switch": after_switch, "none_delta": none_delta, "final_delta": final_delta},
        "search_counts": {"after_none": len(search_after_none.get("items", [])), "after_switch": len(search_after_switch.get("items", []))},
        "audio_file_delta": sorted(set(files_after) - set(files_before)),
        "internal_id_match_count": len(internal_pattern.findall(serialized_public)),
        "all_event_session_ids_public": all(e.get("session_id") == "0" for e in events_none)
        and all(
            e.get("session_id") == "0"
            for e in events_switch
            if isinstance(e.get("turn_id"), int) and e["turn_id"] >= 2
        ),
        "wal_bytes": args.db.with_name(args.db.name + "-wal").stat().st_size if args.db.with_name(args.db.name + "-wal").exists() else 0,
    }
    result["pass"] = all((
        private["id"] == "0", result["create_none"]["opaque_ref"],
        len(rows_none) == 5, len(rows_switch) == 5,
        all(row["transcript"] and row["reply_chars"] and not row["errors"] for row in rows_none + rows_switch),
        all(value == 0 for value in none_delta.values()),
        all(value == 0 for value in final_delta.values()),
        result["search_counts"]["after_none"] == 0,
        result["search_counts"]["after_switch"] == 0,
        not result["audio_file_delta"], result["internal_id_match_count"] == 0,
        result["all_event_session_ids_public"],
        switch_result.get("id") == "0",
        switch_result.get("deleted", {}).get("sessions") == 1,
        switch_result.get("deleted", {}).get("wal_checkpoint_busy") == 0,
    ))
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    http.close()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-models", action="store_true")
    parser.add_argument("--audio", type=Path, required=True)
    parser.add_argument("--search", default="紫色风筝")
    parser.add_argument("--db", type=Path, default=Path("/home/administrator/.cyberWife/cyberwife.db"))
    parser.add_argument("--data-root", type=Path, default=Path("/home/administrator/.cyberWife"))
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:7860/ws/v1")
    parser.add_argument("--timeout", type=float, default=180)
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B4/B4.4"))
    args = parser.parse_args()
    if not args.real_models:
        raise SystemExit(3)
    result = asyncio.run(run(args))
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
