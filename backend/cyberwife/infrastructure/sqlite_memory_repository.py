"""Transactional memory repository for source, FTS5, sqlite-vec and audit rows."""
from __future__ import annotations

import hashlib
import secrets
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable, Iterator

from cyberwife.domain.memory import MemoryRecord
from cyberwife.infrastructure.vector_index import VectorIndex


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SqliteMemoryRepository:
    """Owns the only transaction boundary for all persistent memory layers."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        lock: threading.RLock | None = None,
        *,
        vector_index: VectorIndex | None = None,
        revision: str = "BAAI/bge-small-zh-v1.5",
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        self._conn = conn
        self._lock = lock or threading.RLock()
        self._vector = vector_index or VectorIndex(conn)
        self._revision = revision
        self._fault_injector = fault_injector
        with self._lock:
            self._vector.ensure_schema()
            self._vector.probe()

    @property
    def vector_index(self) -> VectorIndex:
        return self._vector

    def _fault(self, point: str) -> None:
        if self._fault_injector is not None:
            self._fault_injector(point)

    @contextmanager
    def _transaction(self) -> Iterator[None]:
        with self._lock:
            self._conn.execute("BEGIN IMMEDIATE")
            try:
                yield
                self._fault("before_commit")
                self._conn.execute("COMMIT")
            except BaseException:
                self._conn.execute("ROLLBACK")
                raise

    @staticmethod
    def _entity_hash(entity_id: int | str) -> str:
        return hashlib.sha256(f"memory:{entity_id}".encode()).hexdigest()[:16]

    def _audit(
        self,
        action: str,
        entity_id: int | str,
        *,
        deleted: int | None = None,
        fts_before: int | None = None,
        fts_after: int | None = None,
        vector_before: int | None = None,
        vector_after: int | None = None,
    ) -> None:
        self._conn.execute(
            "INSERT INTO audit_events(action, entity_type, entity_id_hash, result, "
            "deleted_row_count, fts_count_before, fts_count_after, vector_count_before, "
            "vector_count_after, created_at) VALUES (?, 'memory', ?, 'success', ?, ?, ?, ?, ?, ?)",
            (
                action,
                self._entity_hash(entity_id),
                deleted,
                fts_before,
                fts_after,
                vector_before,
                vector_after,
                _now(),
            ),
        )

    def upsert(self, record: MemoryRecord, embedding: list[float]) -> int:
        with self._transaction():
            if record.id > 0:
                old = self._conn.execute(
                    "SELECT content FROM memories WHERE id=?", (record.id,)
                ).fetchone()
            else:
                old = None
            if old is None:
                cursor = self._conn.execute(
                    "INSERT INTO memories(source_session_id, content, confidence, edited, created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        record.source_session_id,
                        record.content,
                        record.confidence,
                        int(record.edited),
                        record.created_at.isoformat(),
                        record.updated_at.isoformat(),
                    ),
                )
                memory_id = int(cursor.lastrowid)
            else:
                memory_id = record.id
                self._conn.execute(
                    "UPDATE memories SET content=?, confidence=?, edited=?, updated_at=? WHERE id=?",
                    (
                        record.content,
                        record.confidence,
                        int(record.edited),
                        record.updated_at.isoformat(),
                        memory_id,
                    ),
                )
                self._conn.execute(
                    "INSERT INTO memory_fts(memory_fts, rowid, content) VALUES ('delete', ?, ?)",
                    (memory_id, str(old["content"])),
                )
            self._fault("after_source")
            self._conn.execute(
                "INSERT INTO memory_fts(rowid, content) VALUES (?, ?)",
                (memory_id, record.content),
            )
            self._fault("after_fts")
            self._vector.insert(memory_id, embedding)
            self._fault("after_vector")
            self._conn.execute(
                "INSERT INTO memory_vectors_meta(memory_id, model_id, revision, created_at) "
                "VALUES (?, 'bge-small-zh-v1.5', ?, ?) "
                "ON CONFLICT(memory_id) DO UPDATE SET revision=excluded.revision, created_at=excluded.created_at",
                (memory_id, self._revision, _now()),
            )
            self._fault("after_meta")
            self._audit("memory.updated" if old is not None else "memory.committed", memory_id)
            self._fault("after_audit")
        return memory_id

    def get(self, memory_id: int) -> MemoryRecord | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
        return self._record(row) if row else None

    def list_all(self) -> list[MemoryRecord]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM memories ORDER BY updated_at DESC, id DESC").fetchall()
        return [self._record(row) for row in rows]

    def delete(self, memory_id: int) -> bool:
        with self._transaction():
            row = self._conn.execute("SELECT content FROM memories WHERE id=?", (memory_id,)).fetchone()
            if row is None:
                return False
            fts_before = self.fts_count()
            vector_before = self._vector.count()
            self._conn.execute(
                "INSERT INTO memory_fts(memory_fts, rowid, content) VALUES ('delete', ?, ?)",
                (memory_id, str(row["content"])),
            )
            self._fault("after_fts")
            self._vector.delete(memory_id)
            self._fault("after_vector")
            self._conn.execute("DELETE FROM memory_vectors_meta WHERE memory_id=?", (memory_id,))
            self._conn.execute("DELETE FROM memories WHERE id=?", (memory_id,))
            self._fault("after_source")
            self._audit(
                "memory.deleted",
                memory_id,
                deleted=1,
                fts_before=fts_before,
                fts_after=self.fts_count(),
                vector_before=vector_before,
                vector_after=self._vector.count(),
            )
        return True

    def purge_all(self) -> int:
        with self._transaction():
            rows = self._conn.execute("SELECT id, content FROM memories ORDER BY id").fetchall()
            fts_before = self.fts_count()
            vector_before = self._vector.count()
            for row in rows:
                self._conn.execute(
                    "INSERT INTO memory_fts(memory_fts, rowid, content) VALUES ('delete', ?, ?)",
                    (int(row["id"]), str(row["content"])),
                )
                self._vector.delete(int(row["id"]))
            self._fault("after_indexes")
            self._conn.execute("DELETE FROM memory_vectors_meta")
            self._conn.execute("DELETE FROM memories")
            self._fault("after_source")
            self._audit(
                "memory.purge_all",
                "all",
                deleted=len(rows),
                fts_before=fts_before,
                fts_after=self.fts_count(),
                vector_before=vector_before,
                vector_after=self._vector.count(),
            )
        return len(rows)

    def purge_session_business_data(self, session_id: int) -> dict[str, int]:
        """Atomically erase a session and every memory/index row derived from it."""
        with self._transaction():
            rows = self._conn.execute(
                "SELECT id, content FROM memories WHERE source_session_id=? ORDER BY id",
                (session_id,),
            ).fetchall()
            for row in rows:
                memory_id = int(row["id"])
                self._conn.execute(
                    "INSERT INTO memory_fts(memory_fts, rowid, content) VALUES ('delete', ?, ?)",
                    (memory_id, str(row["content"])),
                )
                self._vector.delete(memory_id)
            self._fault("after_indexes")
            self._conn.execute(
                "DELETE FROM memory_vectors_meta WHERE memory_id IN "
                "(SELECT id FROM memories WHERE source_session_id=?)",
                (session_id,),
            )
            self._conn.execute("DELETE FROM memories WHERE source_session_id=?", (session_id,))
            turns = self._conn.execute("SELECT COUNT(*) FROM turns WHERE session_id=?", (session_id,)).fetchone()[0]
            transcripts = self._conn.execute("SELECT COUNT(*) FROM session_transcripts WHERE session_id=?", (session_id,)).fetchone()[0]
            summaries = self._conn.execute("SELECT COUNT(*) FROM session_summaries WHERE session_id=?", (session_id,)).fetchone()[0]
            sessions = self._conn.execute("DELETE FROM sessions WHERE id=?", (session_id,)).rowcount
            self._fault("after_source")
            self._conn.execute(
                "INSERT INTO audit_events(action, entity_type, entity_id_hash, result, deleted_row_count, "
                "fts_count_after, vector_count_after, created_at) VALUES "
                "('session.no_record', 'session', ?, 'success', ?, ?, ?, ?)",
                (
                    hashlib.sha256(secrets.token_bytes(32)).hexdigest()[:16],
                    int(sessions) + int(turns) + int(transcripts) + int(summaries) + len(rows),
                    self.fts_count(),
                    self._vector.count(),
                    _now(),
                ),
            )
        result = {
            "sessions": int(sessions),
            "turns": int(turns),
            "transcripts": int(transcripts),
            "summaries": int(summaries),
            "memories": len(rows),
        }
        # Deleted page images may otherwise remain in the WAL.  TRUNCATE is
        # deliberately outside the transaction; failure to obtain the
        # checkpoint is surfaced instead of claiming privacy erasure.
        with self._lock:
            checkpoint = self._conn.execute("PRAGMA wal_checkpoint(TRUNCATE)").fetchone()
        result["wal_checkpoint_busy"] = int(checkpoint[0]) if checkpoint is not None else 0
        return result

    def search(
        self,
        query: str,
        query_embedding: list[float],
        top_k_vector: int = 4,
        top_k_fts: int = 6,
        min_score: float = 0.55,
    ) -> list[tuple[MemoryRecord, float]]:
        phrase = '"' + query.replace('"', '""').strip() + '"'
        with self._lock:
            fts_rows = []
            if query.strip():
                fts_rows = self._conn.execute(
                    "SELECT rowid FROM memory_fts WHERE memory_fts MATCH ? ORDER BY bm25(memory_fts) LIMIT ?",
                    (phrase, top_k_fts),
                ).fetchall()
            vector_rows = self._vector.search(query_embedding, top_k_vector, min_score)
            scores: dict[int, float] = {}
            for rank, row in enumerate(fts_rows, 1):
                memory_id = int(row["rowid"])
                scores[memory_id] = max(scores.get(memory_id, 0.0), 1.0 - (rank - 1) * 0.02)
            for rank, (memory_id, similarity) in enumerate(vector_rows, 1):
                rank_bonus = max(0.0, 0.02 - (rank - 1) * 0.005)
                scores[memory_id] = max(scores.get(memory_id, 0.0), min(1.0, similarity + rank_bonus))
            ordered = sorted(scores, key=lambda mid: (-scores[mid], mid))[: max(top_k_vector, 4)]
            records = []
            for memory_id in ordered:
                row = self._conn.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone()
                if row is not None:
                    records.append((self._record(row), scores[memory_id]))
            return records

    def fts_count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM memory_fts").fetchone()[0])

    def layer_counts(self) -> dict[str, int]:
        with self._lock:
            return {
                "source": int(self._conn.execute("SELECT COUNT(*) FROM memories").fetchone()[0]),
                "fts": self.fts_count(),
                "vector": self._vector.count(),
                "meta": int(self._conn.execute("SELECT COUNT(*) FROM memory_vectors_meta").fetchone()[0]),
            }

    @staticmethod
    def _record(row: sqlite3.Row) -> MemoryRecord:
        return MemoryRecord(
            id=int(row["id"]),
            source_session_id=row["source_session_id"],
            content=str(row["content"]),
            confidence=float(row["confidence"]),
            edited=bool(row["edited"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
