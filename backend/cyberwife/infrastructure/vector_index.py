"""VectorIndex — sqlite-vec 包装。

M1 阶段实现：
- ensure_schema(vec_f32(512))
- insert(memory_id, embedding)
- delete(memory_id)
- search(query_embedding, top_k)

B4 起 sqlite-vec 不可用即 fail-closed；索引不拥有事务，也不得自行 commit。
"""
from __future__ import annotations

import sqlite3

from cyberwife.ports.embedding import EmbeddingPort


class VectorIndexUnavailable(RuntimeError):
    """Raised when sqlite-vec cannot satisfy the persistent index contract."""


class VectorIndex:
    """Fail-closed sqlite-vec index with caller-owned transactions."""

    def __init__(self, conn: sqlite3.Connection, dim: int = EmbeddingPort.EMBEDDING_DIM):
        self._conn = conn
        self._dim = dim
        try:
            import sqlite_vec  # type: ignore

            self._conn.enable_load_extension(True)
            sqlite_vec.load(self._conn)
        except Exception as exc:
            raise VectorIndexUnavailable(f"sqlite_vec_unavailable: {exc}") from exc
        finally:
            try:
                self._conn.enable_load_extension(False)
            except Exception:
                pass
        self._sqlite_vec_loaded = True

    @property
    def using_sqlite_vec(self) -> bool:
        return self._sqlite_vec_loaded

    def ensure_schema(self) -> None:
        self._conn.execute(
            f"CREATE VIRTUAL TABLE IF NOT EXISTS memory_vectors USING vec0("
            f"memory_id INTEGER PRIMARY KEY, embedding float[{self._dim}])"
        )

    def insert(self, memory_id: int, embedding: list[float]) -> None:
        if len(embedding) != self._dim:
            raise ValueError(f"embedding dim must be {self._dim}, got {len(embedding)}")
        blob = self._pack(embedding)
        self._conn.execute("DELETE FROM memory_vectors WHERE memory_id = ?", (memory_id,))
        self._conn.execute(
            "INSERT INTO memory_vectors(memory_id, embedding) VALUES (?, ?)",
            (memory_id, blob),
        )

    def delete(self, memory_id: int) -> None:
        self._conn.execute("DELETE FROM memory_vectors WHERE memory_id = ?", (memory_id,))

    def search(self, query: list[float], top_k: int = 4, min_score: float = 0.0) -> list[tuple[int, float]]:
        if len(query) != self._dim:
            raise ValueError(f"query dim must be {self._dim}, got {len(query)}")
        blob = self._pack(query)
        cur = self._conn.execute(
            "SELECT memory_id, vec_distance_cosine(embedding, ?) FROM memory_vectors",
            (blob,),
        )
        scored = [(int(mid), 1.0 - float(dist)) for mid, dist in cur.fetchall()]
        scored = [(mid, s) for mid, s in scored if s >= min_score]
        scored.sort(key=lambda x: -x[1])
        return scored[:top_k]

    def count(self) -> int:
        cur = self._conn.execute("SELECT COUNT(*) FROM memory_vectors")
        return int(cur.fetchone()[0])

    def probe(self) -> None:
        """Verify schema, dimension, insert/search/delete without persisting rows."""
        probe_id = -9223372036854775807
        self._conn.execute("SAVEPOINT vector_probe")
        try:
            vector = [0.0] * self._dim
            vector[0] = 1.0
            self.insert(probe_id, vector)
            found = self.search(vector, top_k=self.count(), min_score=0.99)
            if probe_id not in {memory_id for memory_id, _ in found}:
                raise VectorIndexUnavailable("sqlite_vec_roundtrip_failed")
            self.delete(probe_id)
            if self.count() < 0:
                raise VectorIndexUnavailable("sqlite_vec_count_failed")
        finally:
            self._conn.execute("ROLLBACK TO vector_probe")
            self._conn.execute("RELEASE vector_probe")

    def _pack(self, vec: list[float]) -> bytes:
        """list[float] → bytes（小端 float32 平铺）。sqlite-vec 默认 float32。"""
        import struct

        return struct.pack(f"<{len(vec)}f", *vec)
