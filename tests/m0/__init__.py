# M0 smoke test 共享工具
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_REGISTRY = REPO_ROOT / "config" / "model-registry.local.yaml"
EXAMPLE_REGISTRY = REPO_ROOT / "config" / "model-registry.example.yaml"
ENV_OVERRIDE_PREFIX = "CW_MODEL_"


def _normalize_path(p: str) -> str:
    """跨平台路径兼容：把 Windows 路径在 WSL 下转 /mnt/c/...；WSL 原生路径不动。"""
    if not p:
        return p
    if os.name == "posix" and len(p) >= 2 and p[1] == ":":
        # C:\\foo\\bar -> /mnt/c/foo/bar
        drive = p[0].lower()
        rest = p[2:].replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{rest}"
    return p


def load_registry() -> dict:
    """从 model-registry.local.yaml 加载本机路径；缺失时退回 example。
    返回 {logical_id: entry} dict（不是 yaml 顶层结构）。
    支持 CW_MODEL_<logical_id> 环境变量覆盖绝对路径。"""
    if LOCAL_REGISTRY.exists():
        reg = yaml.safe_load(LOCAL_REGISTRY.read_text(encoding="utf-8"))
    elif EXAMPLE_REGISTRY.exists():
        reg = yaml.safe_load(EXAMPLE_REGISTRY.read_text(encoding="utf-8"))
    else:
        reg = {"models": []}
    models_list = reg.get("models", [])
    out = {}
    for entry in models_list:
        logical_id = entry.get("logical_id")
        if not logical_id:
            continue
        env_key = f"{ENV_OVERRIDE_PREFIX}{logical_id.upper().replace('-', '_').replace('/', '_')}"
        if env_key in os.environ:
            entry["absolute_path"] = os.environ[env_key]
        else:
            entry["absolute_path"] = _normalize_path(entry.get("absolute_path", ""))
        out[logical_id] = entry
    return out


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    """流式计算 SHA256 hex（大文件内存安全）。"""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def record_status(logical_id: str, status: str, **fields) -> dict:
    """构造一条 M0 核验记录（status: discovered|hashed|licensed|loadable|verified|blocked）。"""
    record = {
        "logical_id": logical_id,
        "status": status,
        "verified_at": datetime.now(timezone.utc).isoformat(),
    }
    record.update(fields)
    return record


def check_exists(path: Path) -> tuple[bool, int | None]:
    """检查文件存在并返回 size_bytes；不存在返回 (False, None)。"""
    if not path.exists():
        return False, None
    return True, path.stat().st_size


def elapsed_ms(start: float) -> int:
    return int((time.time() - start) * 1000)


def print_record(rec: dict) -> None:
    print(json.dumps(rec, ensure_ascii=False, indent=2))


# 统一退出码
EXIT_PASS = 0
EXIT_FAIL = 1