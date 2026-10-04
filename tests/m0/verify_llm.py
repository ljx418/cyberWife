"""M0-01 verify_llm.py — Qwen3-14B-Instruct Q4_K_M GGUF 加载 smoke。

按 model-manifest.md §3 七步：discovered → hashed → licensed → loadable → verified。
触发条件：
- 模型文件存在（来自 model-registry.local.yaml）
- 文件 magic = GGUF
- llama-cpp-python 已装上
- llama-server Windows 二进制就绪（来自 ops/windows/StartLlamaCpp.ps1 探测）
"""
import sys
import time
from pathlib import Path

from . import (
    EXIT_FAIL,
    EXIT_PASS,
    LOCAL_REGISTRY,
    REPO_ROOT,
    check_exists,
    elapsed_ms,
    load_registry,
    print_record,
    record_status,
    sha256_file,
)

LOGICAL_ID = "qwen3-14b-instruct-q4_k_m"


def verify() -> int:
    reg = load_registry()
    entry = reg.get(LOGICAL_ID, {})
    abs_path = Path(entry.get("absolute_path", ""))
    license_id = entry.get("license_id", "unknown")
    license_review = entry.get("license_review", "pending")

    # Step 1: discovered
    print(f"[1/5] discovered: {abs_path}")
    ok, size = check_exists(abs_path)
    if not ok:
        print_record(record_status(LOGICAL_ID, "blocked", reason="file_missing"))
        return EXIT_FAIL

    # Step 2: hashed
    print(f"[2/5] hashing ({(size or 0) / 1024 / 1024 / 1024:.1f} GB, 估计 30-60s)...")
    t0 = time.time()
    sha = sha256_file(abs_path)
    print(f"    sha256: {sha}  ({elapsed_ms(t0)} ms)")

    # Step 3: licensed
    print(f"[3/5] licensed: license_id={license_id}, review={license_review}")
    if license_review != "approved":
        print_record(record_status(LOGICAL_ID, "blocked", reason="license_not_approved"))
        return EXIT_FAIL

    # Step 4: loadable (GGUF magic + 可选 llama-cpp-python import probe)
    print(f"[4/5] loadable: magic byte check + optional import")
    with abs_path.open("rb") as f:
        magic = f.read(4)
    if magic != b"GGUF":
        print_record(
            record_status(LOGICAL_ID, "blocked", reason="not_gguf_magic", magic=magic.hex())
        )
        return EXIT_FAIL

    # optional: 真正尝试 llama-cpp-python 加载（仅当 import 可用）
    try:
        from llama_cpp import Llama  # type: ignore

        print("    llama_cpp available, attempting load (may take 30s)...")
        t0 = time.time()
        llm = Llama(model_path=str(abs_path), n_ctx=512, verbose=False)
        # smoke prompt: 输出 1 token
        out = llm("Q", max_tokens=1)
        llm.close()
        del llm
        load_ms = elapsed_ms(t0)
        print(f"    loaded + 1 token OK ({load_ms} ms)")
        load_status = "verified"
    except ImportError:
        print("    llama_cpp not installed, skipping in-process load (run install for verified)")
        load_status = "loadable"
    except Exception as e:
        print(f"    load failed: {e}")
        return EXIT_FAIL

    # Step 5: verified (write back)
    print(f"[5/5] verified: {sha[:16]}")
    print_record(
        record_status(
            LOGICAL_ID,
            load_status,
            sha256=sha,
            size_bytes=size,
            absolute_path=str(abs_path),
            license_id=license_id,
            runtime="llama-cpp-python" if load_status == "verified" else "pending_install",
        )
    )
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(verify())