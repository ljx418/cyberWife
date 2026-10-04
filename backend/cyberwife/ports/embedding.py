"""Embedding Port — 中文向量抽象接口（FR-12 长期记忆语义召回）。"""
from __future__ import annotations

from abc import ABC, abstractmethod


class EmbeddingPort(ABC):
    """BGE 中文向量接口；输出维度固化 512（target-architecture §7 vec_f32(512)）。"""

    EMBEDDING_DIM = 512

    @abstractmethod
    def embed(self, text: str) -> list[float]:
        """单句嵌入；返回 512 维向量。"""
        ...

    @abstractmethod
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """批量嵌入；空输入返回空列表。"""
        ...

    @abstractmethod
    def health(self) -> dict:
        ...
