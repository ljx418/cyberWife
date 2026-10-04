"""Hold a real local WebRTC receiver open while the gateway E2E runs."""
import asyncio
import json

import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription


async def main():
    pc = RTCPeerConnection()
    pc.addTransceiver("audio", direction="recvonly")
    pc.addTransceiver("video", direction="recvonly")

    @pc.on("track")
    def track_received(track):
        async def consume():
            while True:
                try:
                    await track.recv()
                except Exception:
                    return
        asyncio.create_task(consume())

    await pc.setLocalDescription(await pc.createOffer())
    async with aiohttp.ClientSession() as session:
        async with session.post("http://127.0.0.1:8010/offer", json={
            "sdp": pc.localDescription.sdp, "type": pc.localDescription.type,
        }) as response:
            answer = await response.json()
    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))
    print(json.dumps({"ready": True, "session_id_redacted": True}), flush=True)
    await asyncio.sleep(180)
    await pc.close()


if __name__ == "__main__":
    asyncio.run(main())
