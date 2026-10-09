###############################################################################
#  Copyright (C) 2024 LiveTalking@lipku https://github.com/lipku/LiveTalking
#  email: lipku@foxmail.com
# 
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  
#       http://www.apache.org/licenses/LICENSE-2.0
# 
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
###############################################################################

# server.py
from flask import Flask, render_template,send_from_directory,request, jsonify
#from flask_sockets import Sockets
import base64
import json
#import gevent
#from gevent import pywsgi
#from geventwebsocket.handler import WebSocketHandler
import re
import os
import numpy as np
from threading import Thread,Event
#import multiprocessing
import torch.multiprocessing as mp

from aiohttp import web
import aiohttp
import aiohttp_cors
from aiortc import RTCPeerConnection, RTCSessionDescription,RTCIceServer,RTCConfiguration
from aiortc.rtcrtpsender import RTCRtpSender
from server.webrtc import HumanPlayer
from avatars.base_avatar import BaseAvatar
import registry
from server.routes import setup_routes
from server.rtc_manager import RTCManager
from server.session_manager import session_manager
from control_server import AvatarControlServer

import argparse
import random
import shutil
from collections import OrderedDict
import asyncio
import torch
from io import BytesIO
from typing import Dict
from utils.logger import logger
import copy
import gc
from dotenv import load_dotenv


app = Flask(__name__)
#sockets = Sockets(app)
opt = None
model = None
global_avatars = OrderedDict() # bounded avatar_id: payload
        

#####webrtc###############################
# rtc_manager replaces the old pcs set and duplicate offer handlers.
rtc_manager = None

def randN(N)->int:
    '''生成长度为 N的随机数 '''
    min = pow(10, N - 1)
    max = pow(10, N)
    return random.randint(min, max - 1)

def build_avatar_session(sessionid:str, params:dict)->BaseAvatar:
    opt_this = copy.deepcopy(opt)
    opt_this.sessionid = sessionid

    avatar_id = params.get('avatar',opt.avatar_id) 
    opt_this.avatar_id = avatar_id
    ref_audio = params.get('refaudio','') #音色
    ref_text = params.get('reftext','')
    if (avatar_id and avatar_id != opt.avatar_id):
        # Avoid reloading if already cached globally
        if avatar_id not in global_avatars:
            # max_session=1 means no other live session reaches this branch.
            # Keep the startup fallback plus at most one content-addressed
            # portrait so repeated uploads cannot grow host RAM forever.
            for cached_id in list(global_avatars):
                if cached_id != opt.avatar_id:
                    global_avatars.pop(cached_id, None)
            global_avatars[avatar_id] = load_avatar(avatar_id)
        else:
            global_avatars.move_to_end(avatar_id)
        avatar_this = global_avatars[avatar_id]
    else:
        # Default avatar loaded at startup
        avatar_this = global_avatars.get(opt.avatar_id)
    if ref_audio: #请求参数配置了参考音频
        opt_this.REF_FILE = ref_audio
        opt_this.REF_TEXT = ref_text
    custom_config=params.get('custom_config','') #动作编排配置
    if custom_config:
        opt_this.customopt = json.loads(custom_config)

    avatar_session = registry.create("avatar", opt.model, opt=opt_this, model=model, avatar=avatar_this)
    return avatar_session

async def offer(request):
    return await rtc_manager.handle_offer(request)

async def whep(request):
    return await rtc_manager.handle_whep(request)

async def on_shutdown(app):
    await rtc_manager.shutdown()

async def download_record(request):
    sessionid = request.match_info.get('sessionid')
    if not sessionid:
        return web.Response(status=400, text="sessionid is required")
    
    record_file = os.path.join('data', 'record', f"{sessionid}.mp4")
    
    if os.path.exists(record_file):
        return web.FileResponse(record_file)
    else:
        return web.Response(status=404, text="Record not found")


def main():
    global rtc_manager, opt, model,load_avatar
    # 解析命令行参数
    from config import parse_args
    opt = parse_args()

    # ─── 加载 avatar 插件（触发 @register 注册）──────────────────────
    _avatar_modules = {
        'musetalk':   'avatars.musetalk_avatar',
        'wav2lip':    'avatars.wav2lip_avatar',
        'ultralight': 'avatars.ultralight_avatar',
    }
    import importlib
    avatar_mod = importlib.import_module(_avatar_modules[opt.model])
    load_model = avatar_mod.load_model
    load_avatar = avatar_mod.load_avatar
    warm_up = avatar_mod.warm_up
    logger.info(opt)

    if opt.model == 'musetalk':
        model = load_model()
        global_avatars[opt.avatar_id] = load_avatar(opt.avatar_id) 
        warm_up(opt.batch_size,model)      
    elif opt.model == 'wav2lip':
        model = load_model(opt.modelfile or "./models/wav2lip.pth")
        global_avatars[opt.avatar_id] = load_avatar(opt.avatar_id)
        warm_up(opt.batch_size,model,256)
    elif opt.model == 'ultralight':
        model = load_model(opt)
        global_avatars[opt.avatar_id] = load_avatar(opt.avatar_id)
        warm_up(opt.batch_size,global_avatars[opt.avatar_id],160)

    # init rtc manager
    session_manager.set_max_session(opt.max_session)
    session_manager.init_builder(build_avatar_session)
    rtc_manager = RTCManager(opt)
    # share avatar_sessions (RTCManager handles it but routes.py expects it)

    # 虚拟摄像头或 RTMP 模式：启动后台渲染线程
    if opt.transport == 'virtualcam' or opt.transport == 'rtmp':
        thread_quit = Event()
        params = {}
        # session 0 for virtualcam
        session_manager.add_session('0', build_avatar_session('0', params))
        rendthrd = Thread(target=session_manager.get_session('0').render, args=(thread_quit,))
        rendthrd.start()
        if opt.transport == 'virtualcam':
            logger.info("[VirtualCam] Virtual camera output enabled - digital human will be rendered to virtual camera")

    #############################################################################
    appasync = web.Application(client_max_size=1024**2*100)
    if opt.allow_external_services:
        from llm import llm_response as configured_llm_response
        appasync["llm_response"] = configured_llm_response
    else:
        appasync["llm_response"] = None
    appasync["opt"] = opt
    appasync["rtc_manager"] = rtc_manager

    async def health(_request):
        logical_ids = {
            "wav2lip": "livetalking-wav2lip256",
            "musetalk": "livetalking-musetalk15",
            "ultralight": "livetalking-ultralight",
        }
        return web.json_response({
            "status": "ready",
            "logical_id": logical_ids.get(opt.model, f"livetalking-{opt.model}"),
            "engine": opt.model,
            "device": "cuda" if torch.cuda.is_available() else "cpu",
            "dtype": "fp16" if opt.model == "musetalk" else "fp32",
            "avatar_id": opt.avatar_id,
        })

    appasync.on_shutdown.append(on_shutdown)
    if opt.allow_external_services or opt.transport != "ws_h264":
        appasync.router.add_post("/offer", offer)
        appasync.router.add_get("/record/{sessionid}", download_record)
    appasync.router.add_get("/health", health)

    # 注册 server/routes.py 中的通用 API 路由
    setup_routes(appasync)

    # Configure default CORS settings.
    cors = aiohttp_cors.setup(appasync, defaults={
            origin: aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
            )
            for origin in (
                "http://127.0.0.1:4173", "http://localhost:4173",
                "http://127.0.0.1:7860", "http://localhost:7860",
            )
        })
    # Configure CORS on all routes.
    for route in list(appasync.router.routes()):
        cors.add(route)

    # /whep 注册在 CORS 之后：自行管理 OPTIONS，避免与 aiohttp_cors 冲突
    if opt.allow_external_services or opt.transport != "ws_h264":
        whep_resource = appasync.router.add_resource('/whep')
        whep_resource.add_route('POST', whep)
        whep_resource.add_route('OPTIONS', lambda _: web.Response(status=200))

    logger.info('start local avatar server on configured loopback port %s', opt.listenport)
    # logger.info('如果使用webrtc，推荐访问webrtc集成前端: http://<serverip>:'+str(opt.listenport)+'/dashboard.html')
    def run_server(runner):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(runner.setup())
        if opt.bind not in {'127.0.0.1', '::1', 'localhost'}:
            raise RuntimeError('cyberWife V1 avatar server must bind loopback')
        site = web.TCPSite(runner, opt.bind, opt.listenport)
        loop.run_until_complete(site.start())
        if opt.transport=='rtcpush':
            for k in range(opt.max_session):
                push_url = opt.push_url
                if k!=0:
                    push_url = opt.push_url+str(k)
                loop.run_until_complete(rtc_manager.handle_rtcpush(push_url, str(k)))
        loop.run_forever()    
    # The liveness endpoint deliberately runs outside the inference/aiohttp
    # event loop.  A bind failure is fatal so the launcher never reports a
    # candidate that cannot satisfy the two-second recovery contract.
    control_server = AvatarControlServer(opt.bind, opt.control_port)
    control_server.start()
    logger.info('start independent avatar control server on %s:%s', opt.bind, control_server.port)
    try:
        run_server(web.AppRunner(appasync))
    finally:
        control_server.stop()

    #app.on_shutdown.append(on_shutdown)
    #app.router.add_post("/offer", offer)

    # print('start websocket server')
    # server = pywsgi.WSGIServer(('0.0.0.0', 8000), app, handler_class=WebSocketHandler)
    # server.serve_forever()


# os.environ['MKL_SERVICE_FORCE_INTEL'] = '1'
# os.environ['MULTIPROCESSING_METHOD'] = 'forkserver'                                                    
if __name__ == '__main__':
    mp.set_start_method('spawn')
    load_dotenv()  # Load environment variables from .env file, if it exists
    main()
    
    
    
