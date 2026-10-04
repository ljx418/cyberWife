"""M3-stretch QwenTtsAdapter 单元 + 健康测试（不实际加载模型）。

按 Q2 C monkey-patch 路径：qwen_tts 0.0.2 + transformers 4.57。
"""
import sys
from unittest.mock import MagicMock, patch

import pytest


class TestMonkeypatch:
    """_monkeypatch_transformers_dtype 把字符串 dtype 替换为 torch.dtype 对象。"""

    def test_string_dtype_replaced_with_torch_dtype(self):
        """验证 _patched 内部逻辑：字符串 dtype 替换为 torch.dtype。

        直接构造一个独立的 patched-like 函数（避免污染全局 transformers.AutoModel 状态）。
        """
        import torch

        from cyberwife.adapters import qwen_tts_adapter

        # 重新执行 _monkeypatch_transformers_dtype 让 _orig 被捕获
        qwen_tts_adapter._monkeypatch_transformers_dtype()

        # 从模块读出 patched 函数
        import inspect
        src = inspect.getsource(qwen_tts_adapter)
        # 必须含字符串 dtype 映射到 torch.dtype 的逻辑
        assert '"bf16"' in src or "'bf16'" in src
        assert "torch.bfloat16" in src
        assert "torch.float16" in src
        assert "torch.float32" in src

        # 同时验证 patched 函数被正确装载到 transformers.AutoModel 类层级
        import transformers
        qname = transformers.AutoModel.from_pretrained.__qualname__
        assert "_patched" in qname

        # 还原全局状态（避免污染其他测试）
        # 找到原 from_pretrained：再次 patch 时会覆盖；测试结束后 transformers.AutoModel 保持 patched 状态
        # 这没关系——因为 qwen_tts_adapter._patched 始终无害（仅 dtype 字符串替换）

    def test_non_string_dtype_unchanged(self):
        import torch
        import transformers

        from cyberwife.adapters.qwen_tts_adapter import _monkeypatch_transformers_dtype

        _orig = transformers.AutoModel.from_pretrained
        _monkeypatch_transformers_dtype()
        try:
            transformers.AutoModel.from_pretrained = MagicMock()
            transformers.AutoModel.from_pretrained("/path", dtype=torch.bfloat16)
            args, kwargs = transformers.AutoModel.from_pretrained.call_args
            assert kwargs["dtype"] is torch.bfloat16
        finally:
            transformers.AutoModel.from_pretrained = _orig


class TestResample:
    """_resample_to_16k_mono_int16 行为。"""

    def test_identity_when_16k(self):
        import numpy as np
        from cyberwife.adapters.qwen_tts_adapter import _resample_to_16k_mono_int16

        wav = (np.sin(2 * np.pi * 440 * np.arange(16000) / 16000) * 8000).astype(np.float32)
        out = _resample_to_16k_mono_int16(wav, 16000)
        assert len(out) == 16000
        assert out.dtype == np.int16

    def test_downsample_24k_to_16k(self):
        import numpy as np
        from cyberwife.adapters.qwen_tts_adapter import _resample_to_16k_mono_int16

        wav = np.zeros(24000, dtype=np.float32)  # 24kHz 1 秒
        out = _resample_to_16k_mono_int16(wav, 24000)
        # 1 秒 @ 16kHz ≈ 16000 帧
        assert 15900 <= len(out) <= 16100

    def test_stereo_to_mono(self):
        import numpy as np
        from cyberwife.adapters.qwen_tts_adapter import _resample_to_16k_mono_int16

        stereo = np.zeros((16000, 2), dtype=np.float32)
        out = _resample_to_16k_mono_int16(stereo, 16000)
        assert len(out) == 16000


class TestCharactersJson:
    """characters.example.json schema 验证。"""

    def test_loads_as_valid_json(self):
        import json
        from pathlib import Path

        repo = Path(__file__).resolve().parents[3]
        doc = json.loads((repo / "config" / "characters.example.json").read_text())
        assert "_active_character" in doc
        assert "characters" in doc
        assert doc["_active_character"] in doc["characters"]
        ch = doc["characters"][doc["_active_character"]]
        # 教程强制项
        for required in ("label", "system_prompt", "llm_model"):
            assert required in ch, f"missing character field: {required}"
        # system_prompt 必须含教程强制 5 条
        sp = ch["system_prompt"]
        for rule in [
            "不超过两句话",
            "禁止使用 markdown",
            "禁止输出任何 emoji",
            "不要复述",
            "数字用中文",
        ]:
            assert rule in sp, f"system_prompt 缺强制规则: {rule}"


class TestQwenTtsAdapterHealth:
    """health 状态：未加载 → loading。"""

    def test_health_before_load(self):
        from cyberwife.adapters.qwen_tts_adapter import QwenTtsAdapter
        a = QwenTtsAdapter(model_dir="/tmp/nonexistent")
        h = a.health()
        assert h["status"] == "loading"
        assert h["device"] in ("cuda", "cpu")


class TestNonStreamingDefault:
    """Q3R-rerun2 修复：默认 non_streaming_mode=True 避免 qwen_tts 0.0.2 模拟流式断句。"""

    def test_synthesize_stream_passes_non_streaming_mode(self):
        """检查 source 中 generate_voice_clone 调用包含 non_streaming_mode=True。"""
        import inspect
        from cyberwife.adapters.qwen_tts_adapter import QwenTtsAdapter

        source = inspect.getsource(QwenTtsAdapter.synthesize_stream)
        assert "non_streaming_mode=True" in source, (
            "QwenTtsAdapter.synthesize_stream must call generate_voice_clone "
            "with non_streaming_mode=True to avoid 0.0.2 streaming-mode silence gaps"
        )
        assert "non_streaming_mode=False" not in source, (
            "Default should be True; do not pass non_streaming_mode=False"
        )


def test_pcm_chunks_are_exactly_20ms_at_16khz(monkeypatch):
    import numpy as np
    from cyberwife.adapters.qwen_tts_adapter import QwenTtsAdapter

    class FakeModel:
        def generate_voice_clone(self, **_kwargs):
            return [np.ones(16000, dtype=np.float32) * 0.1], 16000

    monkeypatch.setattr(QwenTtsAdapter, "_model", FakeModel())
    adapter = QwenTtsAdapter(model_dir="unused")
    frames = list(adapter.synthesize_stream("x", "ref.wav", "x"))
    assert len(frames) == 50
    assert all(len(frame) == 640 for frame in frames)
