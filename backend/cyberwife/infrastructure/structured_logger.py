"""StructuredLogger — JSONL 日志（implementation-contracts §4）。

字段：timestamp, level, component, session_id_hash, turn_id, trace_id, event,
duration_ms, error_code。
敏感字段黑名单：audio_bytes / raw_text / raw_prompt / voiceprint / absolute_path。
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

# §17 [logging].fields_blacklist.  The historical browser-storage waiver does
# not weaken the backend privacy boundary (implementation-contracts §34).
DEFAULT_BLACKLIST = {
    "audio_bytes",
    "raw_audio",
    "raw_text",
    "transcript",
    "raw_prompt",
    "prompt",
    "response_text",
    "voiceprint",
    "absolute_path",
}

# §4 哈希算法
def hash_id(value: str, salt: Optional[str] = None) -> str:
    """SHA256(value || salt)[:16] hex lower case。"""
    s = (salt or _default_salt()).encode("utf-8")
    h = hashlib.sha256(value.encode("utf-8") + s).hexdigest()
    return h[:16]


def _default_salt() -> str:
    """读取 config/.salt；不存在则生成一次性 salt 写到磁盘，仅本机使用。"""
    salt_path = Path(__file__).resolve().parents[3] / "config" / ".salt"
    if salt_path.exists():
        return salt_path.read_text().strip()
    salt = os.urandom(32).hex()
    salt_path.parent.mkdir(parents=True, exist_ok=True)
    salt_path.write_text(salt)
    salt_path.chmod(0o600)
    return salt


class StructuredLogger:
    """JSONL 日志记录器；每行一个 JSON 事件。"""

    def __init__(
        self,
        name: str = "cyberwife",
        path: Optional[Path] = None,
        blacklist: set[str] | None = None,
    ) -> None:
        self._name = name
        self._path = path
        self._blacklist = DEFAULT_BLACKLIST if blacklist is None else blacklist
        self._logger = logging.getLogger(name)
        self._logger.setLevel(logging.INFO)
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
            self._logger.propagate = False

    def _redact(self, payload: dict) -> dict:
        """删除敏感字段；保留 key 但替换值为 null。"""
        out = {}
        for k, v in payload.items():
            if k in self._blacklist:
                out[k] = None
            elif isinstance(v, dict):
                out[k] = self._redact(v)
            else:
                out[k] = v
        return out

    def emit(
        self,
        event: str,
        component: str,
        *,
        level: str = "INFO",
        session_id: Optional[str] = None,
        turn_id: Optional[int] = None,
        trace_id: Optional[str] = None,
        duration_ms: Optional[int] = None,
        error_code: Optional[str] = None,
        **fields: Any,
    ) -> dict:
        rec: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": level,
            "component": component,
            "event": event,
        }
        if session_id is not None:
            rec["session_id_hash"] = hash_id(session_id)
        if turn_id is not None:
            rec["turn_id"] = turn_id
        if trace_id is not None:
            rec["trace_id"] = trace_id
        if duration_ms is not None:
            rec["duration_ms"] = duration_ms
        if error_code is not None:
            rec["error_code"] = error_code
        rec.update(self._redact(fields))
        line = json.dumps(rec, ensure_ascii=False)
        self._logger.info(line)
        if self._path:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        return rec
