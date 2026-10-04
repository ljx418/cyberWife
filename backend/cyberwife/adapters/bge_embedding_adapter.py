"""Local BAAI/bge-small-zh-v1.5 embedding adapter."""
from __future__ import annotations

from pathlib import Path
from threading import RLock

from cyberwife.ports.embedding import EmbeddingPort


class BgeEmbeddingAdapter(EmbeddingPort):
    def __init__(self, model_path: str | Path, *, device: str = "cpu") -> None:
        self._model_path = Path(model_path)
        self._device = device
        self._model = None
        self._lock = RLock()

    def _ensure_model(self):
        with self._lock:
            if self._model is None:
                if not (self._model_path / "model.safetensors").is_file():
                    raise RuntimeError("embedding_model_missing")
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(
                    str(self._model_path), device=self._device, local_files_only=True
                )
            return self._model

    def embed(self, text: str) -> list[float]:
        if not text.strip():
            raise ValueError("embedding text must not be empty")
        vector = self._ensure_model().encode(text, normalize_embeddings=True)
        result = [float(value) for value in vector.tolist()]
        if len(result) != self.EMBEDDING_DIM:
            raise RuntimeError(
                f"embedding_dim_mismatch: expected {self.EMBEDDING_DIM}, got {len(result)}"
            )
        return result

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not text.strip() for text in texts):
            raise ValueError("embedding text must not be empty")
        vectors = self._ensure_model().encode(texts, normalize_embeddings=True)
        result = [[float(value) for value in vector.tolist()] for vector in vectors]
        if any(len(vector) != self.EMBEDDING_DIM for vector in result):
            raise RuntimeError("embedding_dim_mismatch")
        return result

    def health(self) -> dict:
        try:
            vector = self.embed("本地记忆健康检查")
            return {
                "status": "ready",
                "logical_id": "bge-small-zh-v1.5",
                "device": self._device,
                "dtype": "float32",
                "embedding_dim": len(vector),
            }
        except Exception as exc:
            return {
                "status": "error",
                "logical_id": "bge-small-zh-v1.5",
                "device": self._device,
                "error": f"{type(exc).__name__}: {exc}",
            }
