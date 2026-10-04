###############################################################################
#  服务器路由 — 统一异常处理的 API 路由
###############################################################################

import json
import asyncio
import ipaddress
from threading import Event, Thread
from aiohttp import web
import numpy as np
import time
from urllib.parse import urlparse

from utils.logger import logger


AVATAR_HEARTBEAT_INTERVAL_SECONDS = 0.5


def avatar_heartbeat(session_id: str, monotonic_ms: int | None = None) -> dict:
    """Return the versioned application heartbeat sent during video gaps."""
    return {
        "type": "avatar.heartbeat",
        "version": 1,
        "session_id": session_id,
        "monotonic_ms": int(time.monotonic() * 1000) if monotonic_ms is None else monotonic_ms,
    }


# ─── 路由工具函数 ──────────────────────────────────────────────────────────

def json_ok(data=None):
    """返回成功 JSON 响应"""
    body = {"code": 0, "msg": "ok"}
    if data is not None:
        body["data"] = data
    return web.Response(
        content_type="application/json",
        text=json.dumps(body),
    )


def json_error(msg: str, code: int = -1):
    """返回错误 JSON 响应"""
    return web.Response(
        content_type="application/json",
        text=json.dumps({"code": code, "msg": str(msg)}),
    )


from server.session_manager import session_manager
from server.avatar_routes import setup_avatar_routes

def get_session(request, sessionid: str):
    """从 app 中获取 session 实例"""
    return session_manager.get_session(sessionid)


# ─── 路由处理函数 ──────────────────────────────────────────────────────────

async def human(request):
    """文本输入（echo/chat 模式），支持 voice/emotion 参数"""
    try:
        params: dict = await request.json()

        sessionid: str = params.get('sessionid', '')
        avatar_session = get_session(request, sessionid)
        if avatar_session is None:
            return json_error("session not found")

        if params.get('interrupt'):
            avatar_session.flush_talk()

        datainfo = {}
        if params.get('tts'):  # tts 参数透传（voice, emotion 等）
            datainfo['tts'] = params.get('tts')

        if params['type'] == 'echo':
            avatar_session.put_msg_txt(params['text'], datainfo)
        elif params['type'] == 'chat':
            llm_response = request.app.get("llm_response")
            if llm_response:
                asyncio.get_event_loop().run_in_executor(
                    None, llm_response, params['text'], avatar_session, datainfo
                )

        return json_ok()
    except Exception as e:
        logger.exception('human route exception:')
        return json_error(str(e))


async def interrupt_talk(request):
    """打断当前说话"""
    try:
        params = await request.json()
        sessionid = params.get('sessionid', '')
        avatar_session = get_session(request, sessionid)
        if avatar_session is None:
            return json_error("session not found")
        avatar_session.flush_talk()
        return json_ok()
    except Exception as e:
        logger.exception('interrupt_talk exception:')
        return json_error(str(e))


async def humanaudio(request):
    """上传音频文件"""
    try:
        form = await request.post()
        sessionid = str(form.get('sessionid', ''))
        fileobj = form["file"]
        filebytes = fileobj.file.read()

        datainfo = {}

        avatar_session = get_session(request, sessionid)
        if avatar_session is None:
            return json_error("session not found")
        avatar_session.put_audio_file(filebytes, datainfo)
        return json_ok()
    except Exception as e:
        logger.exception('humanaudio exception:')
        return json_error(str(e))


async def set_audiotype(request):
    """设置自定义状态（动作编排）"""
    try:
        params = await request.json()
        sessionid = params.get('sessionid', '')
        avatar_session = get_session(request, sessionid)
        if avatar_session is None:
            return json_error("session not found")
        avatar_session.set_custom_state(params['audiotype'])
        return json_ok()
    except Exception as e:
        logger.exception('set_audiotype exception:')
        return json_error(str(e))


async def record(request):
    """录制控制"""
    try:
        params = await request.json()
        sessionid = params.get('sessionid', '')
        avatar_session = get_session(request, sessionid)
        if avatar_session is None:
            return json_error("session not found")
        if params['type'] == 'start_record':
            avatar_session.start_recording()
        elif params['type'] == 'end_record':
            avatar_session.stop_recording()
        return json_ok()
    except Exception as e:
        logger.exception('record exception:')
        return json_error(str(e))


async def is_speaking(request):
    """查询是否正在说话"""
    params = await request.json()
    sessionid = params.get('sessionid', '')
    avatar_session = get_session(request, sessionid)
    if avatar_session is None:
        return json_error("session not found")
    return json_ok(data=avatar_session.is_speaking())


async def media_open(request):
    """Open an already configured local session without accepting file paths."""
    params = await request.json()
    sessionid = str(params.get("session_id", "0"))
    avatar_session = get_session(request, sessionid)
    if avatar_session is None and sessionid == "0":
        # WebRTC assigns a random session id.  V1 is single-user/max_session=1,
        # so the backend may safely bind to the sole browser-owned session.
        live = [(sid, value) for sid, value in session_manager.sessions.items() if value is not None]
        if len(live) == 1:
            sessionid, avatar_session = live[0]
    if avatar_session is None:
        return json_error("session not found")
    metrics = getattr(avatar_session, "media_metrics", None)
    if metrics is not None:
        metrics.update({
            "audio_frames_received": 0,
            "audio_clock_ms": 0,
            "inference_frames": 0,
            "inference_seconds": 0.0,
            "video_frames": 0,
            "video_started_at": None,
            "late_video_frames_dropped": 0,
        })
    return json_ok(data={"session_id": sessionid, "mode": "audio_master"})


async def media_audio(request):
    """Inject exactly one 20 ms, 16 kHz, mono signed-16 PCM frame in memory."""
    sessionid = request.match_info["sessionid"]
    avatar_session = get_session(request, sessionid)
    if avatar_session is None:
        return json_error("session not found")
    if request.content_type != "application/octet-stream":
        return web.json_response({"code": -1, "msg": "octet-stream required"}, status=415)
    pcm = await request.read()
    if len(pcm) != 640:
        return web.json_response({"code": -1, "msg": "PCM frame must be 640 bytes"}, status=422)
    clock_ms = int(request.query.get("clock_ms", "0"))
    generation = int(request.query.get("generation", "0"))
    samples = np.frombuffer(pcm, dtype="<i2").astype(np.float32) / 32768.0
    avatar_session.put_audio_frame(samples, {"clock_ms": clock_ms, "generation": generation})
    return json_ok(data={"accepted": True, "clock_ms": clock_ms, "generation": generation})


async def media_cancel(request):
    sessionid = request.match_info["sessionid"]
    avatar_session = get_session(request, sessionid)
    if avatar_session is None:
        return json_error("session not found")
    avatar_session.flush_talk()
    return json_ok(data={"cancelled": True})


async def media_metrics(request):
    sessionid = request.match_info["sessionid"]
    avatar_session = get_session(request, sessionid)
    if avatar_session is None:
        return json_error("session not found")
    values = dict(getattr(avatar_session, "media_metrics", {}))
    inference_seconds = float(values.pop("inference_seconds", 0.0))
    inference_frames = int(values.get("inference_frames", 0))
    video_started = values.pop("video_started_at", None)
    video_elapsed = max(0.0, time.perf_counter() - video_started) if video_started else 0.0
    values["inferfps"] = round(inference_frames / inference_seconds, 3) if inference_seconds else 0.0
    values["finalfps"] = round(int(values.get("video_frames", 0)) / video_elapsed, 3) if video_elapsed else 0.0
    return json_ok(data=values)


async def media_close(request):
    # Session 0 is the launcher-owned preloaded session.  Closing the adapter
    # flushes its queue but deliberately does not unload the shared Avatar.
    return await media_cancel(request)


def _is_loopback_host(value: str) -> bool:
    if value in {"localhost", "localhost."}:
        return True
    try:
        return ipaddress.ip_address(value).is_loopback
    except ValueError:
        return False


async def avatar_websocket(request):
    """Create one local Avatar render session and stream bounded H.264 access units."""
    opt = request.app.get("opt")
    if opt is None or getattr(opt, "transport", "") != "ws_h264":
        return web.json_response({"code": -1, "msg": "ws_h264 transport is not enabled"}, status=409)
    if not _is_loopback_host(request.remote or ""):
        return web.json_response({"code": -1, "msg": "loopback peer required"}, status=403)
    origin = request.headers.get("Origin", "")
    origin_host = urlparse(origin).hostname if origin else None
    if not origin_host or not _is_loopback_host(origin_host):
        return web.json_response({"code": -1, "msg": "loopback Origin required"}, status=403)

    try:
        sessionid = await session_manager.create_session({})
    except Exception as error:
        logger.warning("H.264 WebSocket session rejected: %s", error)
        return web.json_response({"code": -1, "msg": str(error)}, status=503)
    avatar_session = session_manager.get_session(sessionid)
    output = getattr(avatar_session, "output", None)
    if output is None or not hasattr(output, "subscribe"):
        session_manager.remove_session(sessionid)
        return web.json_response({"code": -1, "msg": "H.264 output unavailable"}, status=500)

    ws = web.WebSocketResponse(heartbeat=10, autoping=True, max_msg_size=1024**2 * 8)
    await ws.prepare(request)
    loop = asyncio.get_running_loop()
    token, frame_queue = output.subscribe(loop)
    quit_event = Event()
    render_thread = Thread(
        name=f"avatar-ws-{sessionid[:8]}",
        target=avatar_session.render,
        args=(quit_event,),
    )
    render_thread.start()
    await ws.send_json({
        "type": "video.config",
        "version": 2,
        "session_id": sessionid,
        "codec": "avc1.42E01F",
        "format": "annexb",
        "fps": int(opt.fps),
        "queue_limit": 2,
        "audio": "gateway-pcm",
    })

    async def send_frames():
        while not ws.closed:
            try:
                payload = await asyncio.wait_for(
                    frame_queue.get(),
                    timeout=AVATAR_HEARTBEAT_INTERVAL_SECONDS,
                )
            except asyncio.TimeoutError:
                await ws.send_json(avatar_heartbeat(sessionid))
            else:
                await ws.send_bytes(payload)

    sender = asyncio.create_task(send_frames())
    try:
        async for message in ws:
            if message.type in {web.WSMsgType.CLOSE, web.WSMsgType.CLOSED, web.WSMsgType.ERROR}:
                break
    finally:
        sender.cancel()
        await asyncio.gather(sender, return_exceptions=True)
        output.unsubscribe(token)
        quit_event.set()
        await asyncio.to_thread(render_thread.join, 10)
        session_manager.remove_session(sessionid)
        logger.info("H.264 WebSocket session closed: %s", sessionid)
    return ws

async def sse_handler(request):
    """SSE 事件流，推送服务器状态更新到客户端"""
    sessionid = request.query.get('sessionid', '')
    avatar_session = session_manager.get_session(sessionid)
    if avatar_session is None:
        return json_error("session not found")

    response = web.StreamResponse(
        status=200,
        reason='OK',
        headers={
            'Content-Type': 'text/event-stream',
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'Access-Control-Allow-Origin': '*',
        }
    )
    await response.prepare(request)

    import queue
    msgqueue = queue.Queue()
    avatar_session.add_msgqueue(msgqueue)

    try:
        while True:
            try:
                msg = msgqueue.get_nowait()
                await response.write(f"data: {msg}\n\n".encode('utf-8'))
            except queue.Empty:
                await asyncio.sleep(0.01)
    except (asyncio.CancelledError, ConnectionResetError):
        logger.info('SSE connection closed for session: %s', sessionid)
    finally:
        if msgqueue in avatar_session.msgqueues:
            avatar_session.msgqueues.remove(msgqueue)

    return response


async def admin_config(request):
    """Admin: 获取全局配置参数"""
    try:
        opt = request.app.get("opt")
        if opt:
            return json_ok(data={"config": vars(opt)})
        return json_error("Config not found")
    except Exception as e:
        logger.exception('admin_config exception:')
        return json_error(str(e))


async def admin_sessions(request):
    """Admin: 获取活跃的会话及其配置"""
    try:
        sessions_info = []
        for sid, avatar_session in session_manager.sessions.items():
            if avatar_session:
                s_opt = getattr(avatar_session, 'opt', None)
                s_data = {
                    "sessionid": sid,
                    "speaking": avatar_session.is_speaking() if hasattr(avatar_session, 'is_speaking') else False,
                    "recording": getattr(avatar_session, 'recording', False),
                }
                if s_opt:
                    s_data.update({
                        "model": getattr(s_opt, "model", ""),
                        "avatar_id": getattr(s_opt, "avatar_id", ""),
                        "REF_FILE": getattr(s_opt, "REF_FILE", ""),
                        "transport": getattr(s_opt, "transport", ""),
                        "batch_size": getattr(s_opt, "batch_size", 0),
                        "customopt": getattr(s_opt, "customopt", []),
                    })
                sessions_info.append(s_data)
        return json_ok(data={"sessions": sessions_info})
    except Exception as e:
        logger.exception('admin_sessions exception:')
        return json_error(str(e))


# ─── 路由注册 ──────────────────────────────────────────────────────────────

async def index(request):
    """默认首页重定向"""
    opt = request.app.get("opt")
    pagename = 'index.html'
    if opt and opt.transport == 'rtmp':
        pagename = 'rtmpapi.html'
    elif opt and opt.transport == 'rtcpush':
        pagename = 'rtcpushapi.html'
    raise web.HTTPFound(f'/{pagename}')


def setup_routes(app):
    """注册所有路由到 aiohttp app"""
    opt = app.get("opt")
    local_only = opt is not None and not getattr(opt, "allow_external_services", False)
    if local_only:
        # V1 exposes only the Gateway-driven, in-memory PCM/H.264 contract.
        # Upstream chat, TTS, recording, callbacks, ASR and static admin/demo
        # routes are deliberately unreachable because several can call cloud
        # providers or write user media.
        app.router.add_post("/interrupt_talk", interrupt_talk)
        app.router.add_post("/is_speaking", is_speaking)
        app.router.add_post("/api/v1/media/open", media_open)
        app.router.add_post("/api/v1/media/{sessionid}/audio", media_audio)
        app.router.add_post("/api/v1/media/{sessionid}/cancel", media_cancel)
        app.router.add_get("/api/v1/media/{sessionid}/metrics", media_metrics)
        app.router.add_post("/api/v1/media/{sessionid}/close", media_close)
        app.router.add_get("/ws/v1/avatar", avatar_websocket)
        return
    app.router.add_get("/", index)
    app.router.add_post("/human", human)
    app.router.add_post("/humanaudio", humanaudio)
    app.router.add_post("/set_audiotype", set_audiotype)
    app.router.add_post("/record", record)
    app.router.add_post("/interrupt_talk", interrupt_talk)
    app.router.add_post("/is_speaking", is_speaking)
    app.router.add_post("/api/v1/media/open", media_open)
    app.router.add_post("/api/v1/media/{sessionid}/audio", media_audio)
    app.router.add_post("/api/v1/media/{sessionid}/cancel", media_cancel)
    app.router.add_get("/api/v1/media/{sessionid}/metrics", media_metrics)
    app.router.add_post("/api/v1/media/{sessionid}/close", media_close)
    app.router.add_get("/ws/v1/avatar", avatar_websocket)
    app.router.add_get("/api/admin/config", admin_config)
    app.router.add_get("/api/admin/sessions", admin_sessions)
    app.router.add_get('/sse', sse_handler)

    # ── Local ASR endpoint (SenseVoice/FunASR) ── Issue #604 ──
    try:
        from server.asr_server import asr_websocket_handler, is_funasr_available
        if is_funasr_available():
            app.router.add_get("/api/asr", asr_websocket_handler)
            logger.info("[ASR] Local SenseVoice ASR endpoint enabled at /api/asr")
        else:
            logger.info("[ASR] funasr not installed — local ASR endpoint disabled "
                        "(pip install funasr modelscope)")
    except Exception as e:
        logger.warning(f"[ASR] Failed to register ASR endpoint: {e}")

    # 注册 avatar 生成相关的路由
    setup_avatar_routes(app)

    app.router.add_static('/', path='web')
