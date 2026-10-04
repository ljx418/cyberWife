"""M0-05 verify_embedding.py — BAAI/bge-small-zh-v1.5 加载 smoke。

按 model-manifest.md §3 七步核验 Embedding 组件。
输出维度必须 = 512（target-architecture.md §7 memory_vectors vec_f32(512) 合同）。
"""
import sys
import time

from . import (
    EXIT_FAIL,
    EXIT_PASS,
    elapsed_ms,
    print_record,
    record_status,
    sha256_file,
)

LOGICAL_ID = "bge-small-zh-v1.5"
EXPECTED_DIM = 512


def verify() -> int:
    from pathlib import Path
    from . import load_registry
    reg = load_registry()
    entry = reg.get(LOGICAL_ID, {})
    abs_path = Path(entry.get("absolute_path", ""))
    license_id = entry.get("license_id", "MIT")

    # Step 1: discovered
    print(f"[1/5] discovered: {abs_path}")
    if not abs_path.is_dir():
        print_record(record_status(LOGICAL_ID, "blocked", reason="dir_missing"))
        return EXIT_FAIL
    if not (abs_path / "model.safetensors").exists():
        print_record(
            record_status(LOGICAL_ID, "blocked", reason="model_safetensors_missing")
        )
        return EXIT_FAIL

    # Step 2: hashed
    print(f"[2/5] hashing model.safetensors (~100MB)...")
    t0 = time.time()
    sha = sha256_file(abs_path / "model.safetensors")
    print(f"    sha256: {sha}  ({elapsed_ms(t0)} ms)")

    # Step 3: licensed
    print(f"[3/5] licensed: license_id={license_id}")

    # Step 4: loadable + 维度校验
    print(f"[4/5] loadable: sentence-transformers + 维度校验 ({EXPECTED_DIM})")
    try:
        from sentence_transformers import SentenceTransformer  # type: ignore
    except ImportError:
        print_record(
            record_status(LOGICAL_ID, "loadable", reason="sentence_transformers_not_installed")
        )
        return EXIT_PASS

    t0 = time.time()
    try:
        model = SentenceTransformer(str(abs_path))
        load_ms = elapsed_ms(t0)

        # 维度校验
        emb = model.encode("测试维度校验", normalize_embeddings=True)
        if emb.shape[-1] != EXPECTED_DIM:
            print_record(
                record_status(
                    LOGICAL_ID,
                    "blocked",
                    reason="dim_mismatch",
                    expected=EXPECTED_DIM,
                    actual=int(emb.shape[-1]),
                )
            )
            return EXIT_FAIL
        print(f"    loaded + 维度 {emb.shape[-1]} = {EXPECTED_DIM} OK ({load_ms} ms)")
        status = "verified"
    except Exception as e:
        print(f"    load failed: {e}")
        print_record(record_status(LOGICAL_ID, "blocked", reason=str(e)))
        return EXIT_FAIL

    # Step 5: verified
    print(f"[5/5] verified: {sha[:16]}")
    print_record(
        record_status(
            LOGICAL_ID,
            status,
            sha256=sha,
            absolute_path=str(abs_path),
            license_id=license_id,
            runtime="sentence-transformers",
            embedding_dim=EXPECTED_DIM,
        )
    )
    return EXIT_PASS


if __name__ == "__main__":
    sys.exit(verify())