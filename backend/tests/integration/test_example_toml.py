"""M1-10 config: default.example.toml 含 §17 全部 10 段字段。"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLE_TOML = REPO_ROOT / "config" / "default.example.toml"


def test_example_toml_exists():
    assert EXAMPLE_TOML.exists()


def test_example_toml_loads():
    import tomllib
    with EXAMPLE_TOML.open("rb") as f:
        doc = tomllib.load(f)
    # §17 必须含 10 个段
    expected_sections = {
        "server", "paths", "db", "models", "device", "prompt",
        "cancel", "retention", "logging", "browser",
    }
    actual = set(doc.keys())
    missing = expected_sections - actual
    assert not missing, f"missing sections: {missing}"


def test_example_toml_required_keys_per_section():
    """每段关键字段存在。"""
    import tomllib
    with EXAMPLE_TOML.open("rb") as f:
        doc = tomllib.load(f)

    # 各段必填关键字段
    checks = {
        "server": ["bind", "gateway_port", "llama_port"],
        "paths": ["workspace", "data_root", "salt_file"],
        "db": ["path", "wal", "cache_size_kb"],
        "models": ["llm", "asr", "tts", "avatar", "embedding", "vad"],
        "device": ["llm_gpu_layers", "avatar_fps"],
        "prompt": ["max_context_tokens", "vector_top_k", "vector_score_min"],
        "cancel": ["audio_silence_p95_ms", "llm_cancel_deadline_ms"],
        "retention": ["session_ttl_days", "scan_cron_local"],
        "logging": ["level", "fields_blacklist"],
        "browser": ["audio_sample_rate", "webrtc_ice_servers"],
    }
    for section, keys in checks.items():
        assert section in doc, f"missing section {section}"
        for k in keys:
            assert k in doc[section], f"missing key {section}.{k}"


def test_example_toml_ports_match_registry():
    """example.toml 端口与 implementation-contracts §17 一致。"""
    import tomllib
    with EXAMPLE_TOML.open("rb") as f:
        doc = tomllib.load(f)
    assert doc["server"]["gateway_port"] == 7860
    assert doc["server"]["llama_port"] == 8090
    assert doc["server"]["speech_port"] == 8091
    assert doc["server"]["avatar_port"] == 8010


def test_example_toml_no_secrets():
    """M1 阶段：不允许出现 API key/token/password 字面值。"""
    content = EXAMPLE_TOML.read_text()
    forbidden = ["api_key", "apikey", "token", "password", "secret"]
    for word in forbidden:
        # 仅检查"="右侧含值的情况（避免命中注释）
        import re
        matches = re.findall(rf"^\s*{word}\s*=", content, re.MULTILINE | re.IGNORECASE)
        assert not matches, f"forbidden secret key found: {word}"
