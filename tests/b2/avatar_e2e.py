"""Real WebRTC + raw PCM Avatar FPS acceptance probe."""
from __future__ import annotations

import asyncio
import json
import time
import urllib.request
import wave

import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription


async def main() -> int:
    pc = RTCPeerConnection()
    pc.addTransceiver("audio", direction="recvonly")
    pc.addTransceiver("video", direction="recvonly")
    received = {"audio": 0, "video": 0, "video_first": None, "video_last": None}
    tasks = []

    @pc.on("track")
    def on_track(track):
        async def consume():
            while True:
                try:
                    await track.recv()
                except Exception:
                    return
                received[track.kind] += 1
                if track.kind == "video":
                    now = time.perf_counter()
                    received["video_first"] = received["video_first"] or now
                    received["video_last"] = now
        tasks.append(asyncio.create_task(consume()))

    await pc.setLocalDescription(await pc.createOffer())
    async with aiohttp.ClientSession() as session:
        async with session.post("http://127.0.0.1:8010/offer", json={
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type,
        }) as response:
            answer = await response.json()
        session_id = answer["sessionid"]
        await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))
        async with session.post("http://127.0.0.1:8010/api/v1/media/open", json={"session_id": session_id}) as response:
            opened = await response.json()
            assert opened["code"] == 0
        with wave.open("audit/v1/B2/tts/cosyvoice/01.wav", "rb") as stream:
            payload = stream.readframes(stream.getnframes())
        frames = [payload[i:i + 640] for i in range(0, len(payload), 640) if len(payload[i:i + 640]) == 640]
        started = time.perf_counter()
        for index, frame in enumerate(frames):
            async with session.post(
                f"http://127.0.0.1:8010/api/v1/media/{session_id}/audio?clock_ms={index * 20}",
                data=frame,
                headers={"content-type": "application/octet-stream"},
            ) as response:
                assert (await response.json())["code"] == 0
            target = started + (index + 1) * 0.02
            await asyncio.sleep(max(0, target - time.perf_counter()))
        await asyncio.sleep(3)
        async with session.get(f"http://127.0.0.1:8010/api/v1/media/{session_id}/metrics") as response:
            server_metrics = (await response.json())["data"]

    video_elapsed = (received["video_last"] - received["video_first"]) if received["video_first"] and received["video_last"] else 0
    result = {
        "session_id_redacted": True,
        "input_audio_frames": len(frames),
        "received_audio_frames": received["audio"],
        "received_video_frames": received["video"],
        "client_finalfps": round((received["video"] - 1) / video_elapsed, 3) if video_elapsed else 0,
        "server": server_metrics,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    for task in tasks:
        task.cancel()
    await pc.close()
    return 0 if server_metrics["inferfps"] >= 25 and result["client_finalfps"] >= 25 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
