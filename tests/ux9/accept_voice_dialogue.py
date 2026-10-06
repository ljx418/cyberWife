"""Real-model voice dialogue round-trip acceptance.

The runner generates synthetic user speech with the project's active
CosyVoice profile, sends the PCM through the real WebSocket conversation
pipeline, then transcribes the emitted reply PCM with the independent speech
worker.  Audio stays in memory; the report contains only text, metrics and
SHA-256 digests.
"""
from __future__ import annotations

import argparse
import asyncio
import base64
import hashlib
import io
import json
import re
import struct
import time
import wave
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx
import websockets


_TEXT_NOISE = re.compile(r"[^0-9a-zA-Z\u4e00-\u9fff]+")
_BAD_MARKERS = ("<|", "|>", "think", "analysis", "###", "```", "乱码")
_ARABIC_TO_CHINESE_DIGIT = str.maketrans("0123456789", "零一二三四五六七八九")


def normalize_text(text: str) -> str:
    # ASR may render spoken Chinese numerals as Arabic digits. That is a
    # notation difference rather than an intelligibility error.
    return _TEXT_NOISE.sub("", text).lower().translate(_ARABIC_TO_CHINESE_DIGIT)


def edit_distance(left: str, right: str) -> int:
    if len(left) < len(right):
        left, right = right, left
    previous = list(range(len(right) + 1))
    for row, lchar in enumerate(left, 1):
        current = [row]
        for column, rchar in enumerate(right, 1):
            current.append(
                min(
                    current[-1] + 1,
                    previous[column] + 1,
                    previous[column - 1] + (lchar != rchar),
                )
            )
        previous = current
    return previous[-1]


def character_error_rate(reference: str, hypothesis: str) -> float:
    expected = normalize_text(reference)
    actual = normalize_text(hypothesis)
    if not expected:
        return 0.0 if not actual else 1.0
    return edit_distance(expected, actual) / len(expected)


@dataclass(frozen=True)
class Scenario:
    id: str
    prompt: str
    must_any: tuple[str, ...]
    must_all: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()


SCENARIOS = (
    Scenario("greeting", "你好。", ("你好", "嗨", "在呢")),
    Scenario("fact", "请问二加三等于多少？", ("五", "5"), forbidden=("四", "六")),
    Scenario("empathy", "我今天有点累，请安慰我。", ("休息", "抱抱", "陪", "辛苦", "歇")),
    Scenario("advice", "我晚饭想吃清淡一点，请给一个具体建议。", ("粥", "汤", "面", "蔬菜", "蒸", "豆腐", "鱼")),
    Scenario("context_seed", "请记住，我明天上午九点开会。", ("记住", "九点", "好", "知道")),
    Scenario(
        "context_query",
        "我明天几点开会？",
        ("九点", "九点钟", "9点"),
        must_all=("点",),
        forbidden=("不知道", "不清楚", "没说"),
    ),
)


def semantic_checks(scenario: Scenario, reply: str) -> dict[str, bool]:
    normalized = normalize_text(reply)
    terminates = reply.rstrip().endswith(("。", "！", "？", "!", "?"))
    return {
        "non_empty": bool(normalized),
        "must_any": any(normalize_text(term) in normalized for term in scenario.must_any),
        "must_all": all(normalize_text(term) in normalized for term in scenario.must_all),
        "forbidden_absent": not any(normalize_text(term) in normalized for term in scenario.forbidden),
        "bounded_length": 2 <= len(normalized) <= 40,
        "complete_ending": terminates,
        "clean_markers": not any(marker.lower() in reply.lower() for marker in _BAD_MARKERS),
        "no_abnormal_repeat": not bool(re.search(r"(.{2,8})\1\1", normalized)),
    }


def wav_pcm16_mono_16k(payload: bytes) -> bytes:
    with wave.open(io.BytesIO(payload), "rb") as source:
        if (source.getnchannels(), source.getsampwidth(), source.getframerate()) != (1, 2, 16000):
            raise ValueError("generated input must be PCM16/16kHz/mono WAV")
        pcm = source.readframes(source.getnframes())
    padding = (-len(pcm)) % 640
    return pcm + (b"\0" * padding)


async def transcribe(client: httpx.AsyncClient, speech_base: str, pcm: bytes) -> dict[str, Any]:
    response = await client.post(
        f"{speech_base}/api/v1/utterances/transcribe",
        content=pcm,
        headers={
            "content-type": "application/octet-stream",
            "x-sample-rate": "16000",
            "x-audio-channels": "1",
        },
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


async def run(args: argparse.Namespace) -> dict[str, Any]:
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=120, trust_env=False) as client:
        health = (await client.get(f"{args.http_base}/api/v1/health")).json()
        if health.get("status") not in {"ready", "degraded"}:
            raise RuntimeError(f"gateway is not ready: {health.get('status')}")
        created_response = await client.post(
            f"{args.http_base}/api/v1/sessions",
            json={"recording_policy": "none"},
        )
        created_response.raise_for_status()
        created = created_response.json()
        session_ref = str(created["session_ref"])
        turn_id = int(created["next_turn_id"])
        client_sequence = 0
        try:
            async with websockets.connect(
                f"{args.ws_base}/ws/v1/sessions/{session_ref}", max_size=8 * 1024 * 1024
            ) as socket:
                await asyncio.wait_for(socket.recv(), args.timeout)
                for scenario in SCENARIOS:
                    preview = await client.post(
                        f"{args.http_base}/api/v1/tts/preview",
                        json={"text": scenario.prompt},
                    )
                    preview.raise_for_status()
                    input_pcm = wav_pcm16_mono_16k(preview.content)
                    for chunk_sequence, offset in enumerate(range(0, len(input_pcm), 640)):
                        frame = struct.pack("<IH", turn_id, chunk_sequence) + input_pcm[offset : offset + 640]
                        await socket.send(frame)
                    client_sequence += 1
                    await socket.send(
                        json.dumps(
                            {"type": "audio.silence", "turn_id": turn_id, "event_seq": client_sequence}
                        )
                    )

                    events: list[dict[str, Any]] = []
                    reply_pcm = bytearray()
                    playback_started = False
                    terminal = False
                    deadline = time.monotonic() + args.timeout
                    while not terminal:
                        remaining = deadline - time.monotonic()
                        if remaining <= 0:
                            raise TimeoutError(f"turn timeout: {scenario.id}")
                        event = json.loads(await asyncio.wait_for(socket.recv(), remaining))
                        events.append(event)
                        if event["type"] == "reply.audio.chunk":
                            reply_pcm.extend(base64.b64decode(event["payload"]["audio_chunk_b64"]))
                            if not playback_started:
                                client_sequence += 1
                                await socket.send(
                                    json.dumps(
                                        {
                                            "type": "audio.playback.started",
                                            "turn_id": turn_id,
                                            "trace_id": event["payload"]["trace_id"],
                                            "generation": event["payload"]["generation"],
                                            "asr_to_playback_ms": event["payload"]["server_elapsed_ms"],
                                            "browser_first_non_silent_wall_ms": time.time() * 1000,
                                            "event_seq": client_sequence,
                                        }
                                    )
                                )
                                playback_started = True
                        elif event["type"] == "reply.audio.complete":
                            client_sequence += 1
                            await socket.send(
                                json.dumps(
                                    {
                                        "type": "audio.playback.ended",
                                        "turn_id": turn_id,
                                        "generation": event["payload"]["generation"],
                                        "event_seq": client_sequence,
                                    }
                                )
                            )
                        elif event["type"] == "state.changed" and event.get("turn_id") == turn_id:
                            if event["payload"].get("reason") in {"playback_complete", "text_complete"}:
                                terminal = True
                        elif event["type"] == "error":
                            terminal = True

                    input_transcript = next(
                        (e["payload"].get("text", "") for e in events if e["type"] == "transcript.final"),
                        "",
                    )
                    reply_text = next(
                        (e["payload"].get("text_final", "") for e in events if e["type"] == "reply.text.final"),
                        "",
                    )
                    output_asr = await transcribe(client, args.speech_base, bytes(reply_pcm)) if reply_pcm else {}
                    output_transcript = str(output_asr.get("text", ""))
                    first_audio_event = next(
                        (e for e in events if e["type"] == "reply.audio.chunk"),
                        None,
                    )
                    first_audio_server_ms = (
                        float(first_audio_event["payload"]["server_elapsed_ms"])
                        if first_audio_event is not None
                        else None
                    )
                    input_cer = character_error_rate(scenario.prompt, input_transcript)
                    output_cer = character_error_rate(reply_text, output_transcript)
                    checks = semantic_checks(scenario, reply_text)
                    row_pass = (
                        input_cer <= args.max_input_cer
                        and output_cer <= args.max_output_cer
                        and bool(output_transcript.strip())
                        and first_audio_server_ms is not None
                        and first_audio_server_ms <= args.max_first_audio_ms
                        and all(checks.values())
                        and not any(e["type"] == "error" for e in events)
                    )
                    row = {
                        "scenario": scenario.id,
                        "prompt": scenario.prompt,
                        "input_transcript": input_transcript,
                        "reply_text": reply_text,
                        "output_transcript": output_transcript,
                        "input_cer": round(input_cer, 4),
                        "output_cer": round(output_cer, 4),
                        "semantic_checks": checks,
                        "input_audio_sha256": hashlib.sha256(input_pcm).hexdigest(),
                        "output_audio_sha256": hashlib.sha256(reply_pcm).hexdigest(),
                        "output_audio_ms": round(len(reply_pcm) / 32, 1),
                        "first_audio_server_ms": (
                            round(first_audio_server_ms, 1)
                            if first_audio_server_ms is not None
                            else None
                        ),
                        "error_codes": [
                            e.get("payload", {}).get("code") for e in events if e["type"] == "error"
                        ],
                        "pass": row_pass,
                    }
                    rows.append(row)
                    print(json.dumps(row, ensure_ascii=False), flush=True)
                    turn_id += 1
        finally:
            await client.delete(f"{args.http_base}/api/v1/sessions/{session_ref}")

    result = "PASS" if len(rows) == len(SCENARIOS) and all(row["pass"] for row in rows) else "FAIL"
    report = {
        "schema_version": 1,
        "gate": "UX9-real-voice-dialogue-roundtrip",
        "evidence_level": "real-local-cosyvoice-faster-whisper-llama",
        "audio_persisted": False,
        "scenario_count": len(rows),
        "passed_scenarios": sum(row["pass"] for row in rows),
        "max_input_cer": args.max_input_cer,
        "max_output_cer": args.max_output_cer,
        "max_first_audio_ms": args.max_first_audio_ms,
        "duration_s": round(time.perf_counter() - started, 3),
        "rows": rows,
        "result": result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:7860")
    parser.add_argument("--speech-base", default="http://127.0.0.1:8091")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--max-input-cer", type=float, default=0.10)
    parser.add_argument("--max-output-cer", type=float, default=0.15)
    parser.add_argument("--max-first-audio-ms", type=float, default=7000.0)
    parser.add_argument("--output", type=Path, default=Path("audit/v1/UX9/voice-dialogue-roundtrip.json"))
    args = parser.parse_args()
    report = asyncio.run(run(args))
    print("SUMMARY " + json.dumps({key: report[key] for key in ("result", "scenario_count", "passed_scenarios", "duration_s")}, ensure_ascii=False))
    raise SystemExit(0 if report["result"] == "PASS" else 2)


if __name__ == "__main__":
    main()
