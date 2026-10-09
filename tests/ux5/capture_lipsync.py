"""Capture the real loopback Wav2Lip H.264 path with its exact PCM input."""

from __future__ import annotations

import argparse
import asyncio
import csv
import hashlib
import json
import math
import statistics
import struct
import subprocess
import time
import wave
from pathlib import Path

import aiohttp
import websockets


HEADER = struct.Struct("<BBHHIII")
PCM_BYTES = 640


def wav_frames(path: Path) -> tuple[list[bytes], dict[str, int | float | str]]:
    with wave.open(str(path), "rb") as stream:
        meta = {
            "channels": stream.getnchannels(),
            "sample_rate": stream.getframerate(),
            "sample_width": stream.getsampwidth(),
            "sample_frames": stream.getnframes(),
        }
        if (meta["channels"], meta["sample_rate"], meta["sample_width"]) != (1, 16000, 2):
            raise ValueError("input must be 16 kHz mono signed-16 PCM WAV")
        payload = stream.readframes(stream.getnframes())
    frames = [payload[pos : pos + PCM_BYTES] for pos in range(0, len(payload), PCM_BYTES)]
    if frames and len(frames[-1]) < PCM_BYTES:
        frames[-1] = frames[-1] + bytes(PCM_BYTES - len(frames[-1]))
    meta["duration_seconds"] = round(len(payload) / 2 / 16000, 6)
    meta["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    return frames, meta


async def capture(args: argparse.Namespace) -> dict:
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    pcm_frames, wav_meta = wav_frames(args.wav)
    generation = args.generation or (int(time.time() * 1000) & 0x7FFFFFFF)
    ws_url = f"{args.ws_base}/ws/v1/avatar?avatar_id={args.avatar_id}"
    packet_rows: list[dict] = []
    audio_rows: list[dict] = []
    # Keep a decodable pre-roll from the first keyframe.  A generation change
    # reaches the NVENC output a couple of packets before its forced IDR, so
    # dropping generation-0 decoder state would make those valid product
    # frames look corrupt in an isolated acceptance capture.
    encoded: list[bytes] = []
    target_start_index: int | None = None
    have_decoder_keyframe = False
    config: dict = {}
    first_send = 0.0
    completion_ack = False

    async with websockets.connect(
        ws_url,
        origin="http://127.0.0.1:7860",
        max_size=8 * 1024 * 1024,
        ping_interval=10,
    ) as socket:
        initial = await asyncio.wait_for(socket.recv(), timeout=30)
        if not isinstance(initial, str):
            raise RuntimeError("avatar did not send video.config first")
        config = json.loads(initial)
        if config.get("type") != "video.config" or config.get("version") != 2:
            raise RuntimeError(f"unsupported avatar protocol: {config}")
        session_id = config["session_id"]
        done = asyncio.Event()

        async def receive() -> None:
            nonlocal have_decoder_keyframe, target_start_index
            while not done.is_set():
                try:
                    message = await asyncio.wait_for(socket.recv(), timeout=0.5)
                except asyncio.TimeoutError:
                    continue
                except websockets.ConnectionClosed:
                    return
                if not isinstance(message, bytes) or len(message) < HEADER.size:
                    continue
                version, flags, width, height, stamp_ms, sequence, frame_generation = HEADER.unpack_from(message)
                if version != 2:
                    continue
                is_keyframe = bool(flags & 1)
                if not have_decoder_keyframe:
                    if not is_keyframe:
                        continue
                    have_decoder_keyframe = True
                if frame_generation == generation and target_start_index is None:
                    target_start_index = len(encoded)
                encoded.append(message[HEADER.size :])
                if frame_generation != generation:
                    continue
                received = time.perf_counter()
                if not packet_rows:
                    relative_stamp = 0
                    relative_receive = 0.0
                else:
                    relative_stamp = stamp_ms - packet_rows[0]["timestamp_ms"]
                    relative_receive = (received - packet_rows[0]["received_monotonic"]) * 1000
                packet_rows.append({
                    "sequence": sequence,
                    "timestamp_ms": stamp_ms,
                    "relative_timestamp_ms": relative_stamp,
                    "received_monotonic": received,
                    "relative_receive_ms": round(relative_receive, 3),
                    "generation": frame_generation,
                    "keyframe": int(is_keyframe),
                    "width": width,
                    "height": height,
                    "payload_bytes": len(message) - HEADER.size,
                })

        receiver = asyncio.create_task(receive())
        try:
            async with aiohttp.ClientSession() as client:
                endpoint = f"{args.http_base}/api/v1/media/{session_id}/audio"
                first_send = time.perf_counter()
                for index, frame in enumerate(pcm_frames):
                    if args.send_mode == "realtime":
                        scheduled = first_send + index * 0.020
                        await asyncio.sleep(max(0.0, scheduled - time.perf_counter()))
                    sent = time.perf_counter()
                    async with client.post(
                        endpoint,
                        params={"clock_ms": index * 20, "generation": generation},
                        data=frame,
                        headers={"content-type": "application/octet-stream"},
                    ) as response:
                        body = await response.json()
                        if (
                            response.status != 200
                            or body.get("code") != 0
                            or not body.get("data", {}).get("accepted")
                        ):
                            raise RuntimeError(f"PCM rejected at frame {index}: {body}")
                    audio_rows.append({
                        "index": index,
                        "clock_ms": index * 20,
                        "sent_relative_ms": round((sent - first_send) * 1000, 3),
                        "bytes": len(frame),
                    })
                async with client.post(
                    f"{args.http_base}/api/v1/media/{session_id}/complete",
                    params={"generation": generation},
                    json={},
                ) as response:
                    body = await response.json()
                    completion_ack = bool(
                        response.status == 200
                        and body.get("code") == 0
                        and body.get("data", {}).get("completed")
                    )
                    if not completion_ack:
                        raise RuntimeError(f"PCM completion rejected: {body}")
                drain_seconds = args.tail_seconds
                if args.send_mode == "burst":
                    drain_seconds += float(wav_meta["duration_seconds"])
                await asyncio.sleep(drain_seconds)
                async with client.get(f"{args.http_base}/api/v1/media/{session_id}/metrics") as response:
                    metrics = (await response.json()).get("data", {})
        finally:
            done.set()
            await asyncio.gather(receiver, return_exceptions=True)

    if not encoded or not packet_rows or target_start_index is None:
        raise RuntimeError("no matching Wav2Lip H.264 frames captured")
    h264 = output / "lipsync.h264"
    h264.write_bytes(b"".join(encoded))
    with (output / "video-timeline.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=packet_rows[0].keys())
        writer.writeheader()
        writer.writerows(packet_rows)
    with (output / "audio-timeline.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=audio_rows[0].keys())
        writer.writeheader()
        writer.writerows(audio_rows)

    mp4 = output / "lipsync-review.mp4"
    review_frames = math.ceil(float(wav_meta["duration_seconds"]) * int(config["fps"]))
    command = [
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
        "-r", str(config["fps"]), "-i", str(h264), "-i", str(args.wav),
        "-filter_complex",
        f"[0:v]trim=start_frame={target_start_index}:"
        f"end_frame={target_start_index + review_frames},setpts=PTS-STARTPTS[v]",
        "-map", "[v]", "-map", "1:a", "-c:v", "libx264", "-preset", "veryfast",
        "-crf", "18", "-c:a", "aac", "-shortest",
        "-movflags", "+faststart", str(mp4),
    ]
    subprocess.run(command, check=True)

    cadence_errors = [
        abs((row["relative_timestamp_ms"] - index * 40.0))
        for index, row in enumerate(packet_rows)
    ]
    sequences = [row["sequence"] for row in packet_rows]
    result = {
        "schema_version": 1,
        "privacy": {"session_id_redacted": True, "transcript_recorded": False, "loopback_only": True},
        "avatar_id": args.avatar_id,
        "generation": generation,
        "input": wav_meta,
        "protocol": {key: config.get(key) for key in ("version", "codec", "format", "fps", "audio")},
        "audio_packets": len(audio_rows),
        "audio_completion_ack": completion_ack,
        "send_mode": args.send_mode,
        "video_packets": len(packet_rows),
        "review_video_frames": review_frames,
        "keyframes": sum(row["keyframe"] for row in packet_rows),
        "decoder_preroll_frames": target_start_index,
        "first_video_after_first_audio_ms": round(
            (packet_rows[0]["received_monotonic"] - first_send) * 1000, 3
        ),
        "sequence_monotonic": all(b > a for a, b in zip(sequences, sequences[1:])),
        "sequence_gaps": sum(max(0, b - a - 1) for a, b in zip(sequences, sequences[1:])),
        "cadence_error_ms": {
            "median": round(statistics.median(cadence_errors), 3),
            "p95": round(sorted(cadence_errors)[max(0, int(len(cadence_errors) * 0.95) - 1)], 3),
        },
        "server_metrics": metrics,
        "artifacts": {
            "review_video": mp4.name,
            "video_timeline": "video-timeline.csv",
            "audio_timeline": "audio-timeline.csv",
        },
    }
    (output / "capture-result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wav", type=Path, required=True)
    parser.add_argument("--avatar-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--http-base", default="http://127.0.0.1:8010")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:8010")
    parser.add_argument("--generation", type=int, default=0)
    parser.add_argument("--tail-seconds", type=float, default=1.2)
    parser.add_argument("--send-mode", choices=("burst", "realtime"), default="burst")
    return parser.parse_args()


if __name__ == "__main__":
    report = asyncio.run(capture(parse_args()))
    print(json.dumps(report, ensure_ascii=False, indent=2))
