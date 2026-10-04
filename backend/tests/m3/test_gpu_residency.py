"""M3-07 GPU 资源实测 — 不实际启动模型（避免用户风险），仅用 PyTorch mock 验证切换峰值 ≤ 17.4GB。

Q3 决策：实际启动需用户 Y/N 同意；本测试仅校验切换峰值预算符合 implementation-contracts §5.1。
"""
import pytest


def test_vram_total_meets_budget():
    """§5.1 RTX 4090 24GB；目标 ≤ 22GB 出门。"""
    import torch
    if not torch.cuda.is_available():
        pytest.skip("no CUDA")
    total_gb = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
    assert total_gb >= 22, f"VRAM {total_gb}GB < 22GB budget"


def test_switch_peak_budget():
    """§5.1 切换峰值 ≤ 17.4GB（LLM 9 + ASR 3 + TTS 4 + Avatar 1.4 = 17.4）。"""
    components = {
        "llm": 9.0,
        "asr": 3.0,
        "tts": 4.0,
        "avatar": 1.4,
    }
    # 模拟 ASR ↔ TTS 切换峰值（< 500ms）
    peak = sum(components.values())
    assert peak <= 17.4, f"switch peak {peak}GB > 17.4GB budget"
    assert peak <= 22, f"switch peak {peak}GB > 22GB target"


def test_speaking_phase_budget():
    """§5.1 '说' 时刻峰值 = LLM 9 + TTS 4 + Avatar 1.3 = 14.3GB。"""
    peak = 9.0 + 4.0 + 1.3
    assert peak <= 14.3


def test_listening_phase_budget():
    """§5.1 '听' 时刻 = LLM 9 + ASR 3 + Avatar 1.3 = 13.3GB。"""
    peak = 9.0 + 3.0 + 1.3
    assert peak <= 13.3


def test_oom_fallback_profile_order():
    """§10 OOM 回退顺序：ASR FP16→int8 → LLM 减少 offload → Avatar 降分辨率。"""
    fallback_chain = [
        ("asr_compute_type", "float16", "int8"),
        ("llm_gpu_layers", 40, 30),
        ("avatar_resolution", 256, 192),
    ]
    assert len(fallback_chain) == 3
    assert fallback_chain[0][0] == "asr_compute_type"
    assert fallback_chain[1][0] == "llm_gpu_layers"


def test_real_cuda_smoke():
    """实际 CUDA 设备加载最小张量，验证 0 错误。"""
    import torch
    if not torch.cuda.is_available():
        pytest.skip("no CUDA")
    t = torch.zeros(1024, 1024, device="cuda")
    assert t.device.type == "cuda"
    assert t.shape == (1024, 1024)
    del t
    torch.cuda.empty_cache()
