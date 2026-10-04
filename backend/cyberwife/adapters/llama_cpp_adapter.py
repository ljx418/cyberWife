"""LlamaCppAdapter — M3-04 LLM 适配器（实现 ports.llm.LlmPort）。

按 model-manifest §1 LLM 行（Qwen3-14B-Instruct Q4_K_M GGUF）。
按 implementation-contracts §18 cancel deadline（400ms / 1s）。

M3 阶段：通过 llama-server.exe HTTP /completion 端点流式生成；不支持取消时降级为 timeout。
"""
from __future__ import annotations

import json
import ipaddress
import time
import uuid
from collections.abc import Iterator
from typing import Optional

import httpx

from cyberwife.infrastructure.structured_logger import StructuredLogger


class LlamaCppAdapter:
    """llama.cpp 后端 LLM。"""

    def __init__(
        self,
        *,
        host: str = "127.0.0.1",
        port: int = 8090,
        timeout_s: float = 60.0,
    ) -> None:
        try:
            loopback = host in {"localhost", "localhost."} or ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
        if not loopback:
            raise ValueError("llama.cpp endpoint must be loopback")
        self._base = f"http://{host}:{port}"
        self._timeout_s = timeout_s
        self._logger = StructuredLogger(name="cyberwife.llm")
        self._inflight: dict[str, httpx.Response] = {}

    def health(self) -> dict:
        try:
            r = httpx.get(f"{self._base}/health", timeout=2.0, trust_env=False)
            if r.status_code == 200:
                return {"status": "ready", "endpoint": f"{self._base}/health"}
            return {"status": "degraded", "status_code": r.status_code}
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def generate_stream(
        self,
        prompt: str,
        *,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop: Optional[list[str]] = None,
        request_id: str | None = None,
    ) -> Iterator[str]:
        """流式 yield 增量文本；M3 阶段通过 llama-server /completion SSE。"""
        request_id = request_id or uuid.uuid4().hex
        stop_seq = stop or ["<|im_end|>"]
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": stop_seq,
            "stream": True,
        }
        t0 = time.time()
        with httpx.Client(timeout=self._timeout_s, trust_env=False) as client:
            with client.stream("POST", f"{self._base}/completion", json=payload) as resp:
                self._inflight[request_id] = resp
                try:
                    for line in resp.iter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            content = data.get("content", "")
                            if content:
                                yield content
                            if data.get("stop"):
                                break
                        except json.JSONDecodeError:
                            continue
                finally:
                    self._inflight.pop(request_id, None)
                    duration_ms = int((time.time() - t0) * 1000)
                    self._logger.emit(
                        "llm.generate",
                        "llm",
                        request_id=request_id,
                        duration_ms=duration_ms,
                        prompt_tokens=len(prompt),
                    )

    def cancel(self, request_id: str) -> bool:
        """取消一个正在进行的 generate_stream（按 request_id 标识）。

        llama-server 当前没有内置 cancel 端点；M3 通过 close httpx.Response 触发
        连接断开，llama-server 端会因 stream 断开停止生成。
        """
        resp = self._inflight.pop(request_id, None)
        if resp is None:
            return False
        try:
            resp.close()
            return True
        except Exception:
            return False

    def generate_blocking(
        self,
        prompt: str,
        *,
        max_tokens: int = 256,
        temperature: float = 0.7,
        stop: Optional[list[str]] = None,
    ) -> str:
        """M3 测试用：阻塞式生成（不走 SSE）。"""
        stop_seq = stop or ["<|im_end|>"]
        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": stop_seq,
            "stream": False,
        }
        r = httpx.post(f"{self._base}/completion", json=payload, timeout=self._timeout_s, trust_env=False)
        r.raise_for_status()
        return r.json().get("content", "")
