"""Loopback client for the shared speech worker's local BGE runtime."""
from __future__ import annotations

import httpx

from cyberwife.ports.embedding import EmbeddingPort


class SpeechEmbeddingAdapter(EmbeddingPort):
    def __init__(self, base_url: str = "http://127.0.0.1:8091", *, timeout_s: float = 30.0) -> None:
        self._base = base_url.rstrip("/")
        self._timeout = timeout_s

    def embed(self, text: str) -> list[float]:
        return self.embed_batch([text])[0]

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = httpx.post(
            f"{self._base}/api/v1/embeddings",
            json={"texts": texts},
            timeout=self._timeout,
            trust_env=False,
        )
        response.raise_for_status()
        payload = response.json()
        vectors = payload.get("vectors", [])
        if len(vectors) != len(texts) or any(len(vector) != self.EMBEDDING_DIM for vector in vectors):
            raise RuntimeError("embedding_runtime_contract_invalid")
        return [[float(value) for value in vector] for vector in vectors]

    def health(self) -> dict:
        try:
            vector = self.embed("本地记忆健康检查")
            return {
                "status": "ready",
                "logical_id": "bge-small-zh-v1.5",
                "device": "cpu",
                "dtype": "float32",
                "embedding_dim": len(vector),
            }
        except Exception as exc:
            return {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
