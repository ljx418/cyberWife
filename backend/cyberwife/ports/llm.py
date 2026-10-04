"""LLM Port — 文本对话模型抽象接口（FR-08 / §5 第 4-5 步）。"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator


class LlmPort(ABC):
    """对话 LLM 接口；流式生成；可取消。"""

    @abstractmethod
    def generate_stream(
        self,
        prompt: str,
        max_tokens: int = 1024,
        temperature: float = 0.7,
        stop: list[str] | None = None,
    ) -> Iterator[str]:
        """流式 yield 增量文本。生成失败抛 RuntimeError。"""
        ...

    @abstractmethod
    def cancel(self, request_id: str) -> bool:
        """取消一个正在进行的 generate_stream 请求（按 request_id 标识）。返回是否成功取消。"""
        ...

    @abstractmethod
    def health(self) -> dict:
        ...
