"""Contract tests for the CosyVoice2 adapter without loading model weights."""
from pathlib import Path

import numpy as np
import pytest
from unittest.mock import patch

from cyberwife.adapters.cosyvoice_tts_adapter import (
    CosyVoiceTtsAdapter,
    CosyVoiceTensorRtProfile,
    _load_wav_tensor,
    _resample_to_16k_mono_int16,
)


def test_resample_24k_tensor_shape_to_16k_pcm():
    source = np.sin(2 * np.pi * 440 * np.arange(24000) / 24000)[None, :]
    actual = _resample_to_16k_mono_int16(source, 24000)
    assert actual.dtype == np.int16
    assert len(actual) == 16000
    assert 32000 <= int(actual.max()) <= 32767


def test_health_does_not_expose_private_absolute_path(tmp_path: Path):
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    adapter = CosyVoiceTtsAdapter(str(model_dir), source_dir=str(tmp_path))
    health = adapter.health()
    assert health["status"] == "error"
    assert "model_dir" not in health
    assert health["logical_id"] == "cosyvoice2-0.5b"


def test_zero_shot_requires_reference_transcript(tmp_path: Path):
    reference = tmp_path / "reference.wav"
    reference.write_bytes(b"RIFF")
    adapter = CosyVoiceTtsAdapter(str(tmp_path), source_dir=str(tmp_path))
    with pytest.raises(ValueError, match="reference_transcript"):
        next(adapter.synthesize_stream("测试", str(reference), ""))


def test_cancel_is_available_for_single_worker(tmp_path: Path):
    adapter = CosyVoiceTtsAdapter(str(tmp_path), source_dir=str(tmp_path))
    assert adapter.cancel("turn-1") is True


def test_private_voice_cache_clear_is_safe_before_model_load(tmp_path: Path):
    adapter = CosyVoiceTtsAdapter(str(tmp_path), source_dir=str(tmp_path))
    adapter.clear_private_cache()


def test_runtime_inference_is_explicitly_offline():
    import inspect

    source = inspect.getsource(CosyVoiceTtsAdapter.synthesize_stream)
    assert "text_frontend=True" in source
    assert "zero_shot_spk_id=speaker_key" in source
    assert "spoken_chars <= 7" in source
    assert "set_all_random_seed(inference_seed)" in source


def test_soundfile_compat_loader_preserves_tensor_contract(tmp_path: Path):
    import soundfile as sf

    path = tmp_path / "reference.wav"
    sf.write(path, np.zeros(24000, dtype=np.float32), 24000)
    actual = _load_wav_tensor(path, 16000)
    assert tuple(actual.shape) == (1, 16000)
    assert str(actual.dtype) == "torch.float32"


def test_trt_profile_fails_closed_without_engine(tmp_path: Path):
    profile = CosyVoiceTensorRtProfile(
        tmp_path,
        model_revision="model-rev",
        source_revision="source-rev",
        runtime_identity=lambda: {"tensorrt_version": "10.13.3.9", "gpu_name": "RTX 4090"},
    )
    status = profile.validate()
    assert status["status"] == "missing"
    assert "absolute_path" not in status


def test_trt_profile_manifest_binds_engine_onnx_and_runtime(tmp_path: Path):
    (tmp_path / "flow.decoder.estimator.fp32.onnx").write_bytes(b"onnx")
    (tmp_path / "flow.decoder.estimator.fp16.mygpu.plan").write_bytes(b"engine")
    profile = CosyVoiceTensorRtProfile(
        tmp_path,
        model_revision="model-rev",
        source_revision="source-rev",
        runtime_identity=lambda: {"tensorrt_version": "10.13.3.9", "gpu_name": "RTX 4090"},
    )
    profile.record_built_engine()
    assert profile.validate()["status"] == "ready"
    (tmp_path / "flow.decoder.estimator.fp32.onnx").write_bytes(b"changed")
    invalid = profile.validate()
    assert invalid["status"] == "invalid"
    assert invalid["reason"] == "manifest_mismatch"


def test_adapter_health_reports_trt_without_private_path(tmp_path: Path):
    adapter = CosyVoiceTtsAdapter(
        str(tmp_path), source_dir=str(tmp_path), load_trt=True,
        model_revision="model-rev", source_revision="source-rev",
    )
    health = adapter.health()
    assert health["trt_requested"] is True
    assert health["trt_engine_status"] == "missing"
    assert "absolute_path" not in health


def test_gateway_has_explicit_cosy_trt_runtime_switch():
    source = (Path(__file__).resolve().parents[2] / "cyberwife" / "api" / "server.py").read_text()
    assert '"CW_TTS_MODEL",' in source
    assert 'os.environ.get("CW_COSYVOICE_LOAD_TRT", "0") == "1"' in source
    assert "load_trt=cosyvoice_load_trt" in source


def test_transient_cleanup_keeps_allocator_warm_when_memory_is_healthy(tmp_path: Path):
    adapter = CosyVoiceTtsAdapter(str(tmp_path), source_dir=str(tmp_path))
    with patch(
        "cyberwife.adapters.cosyvoice_tts_adapter._linux_mem_available_mib",
        return_value=8192,
    ), patch(
        "cyberwife.adapters.cosyvoice_tts_adapter._linux_process_rss_mib",
        return_value=2048,
    ), patch("ctypes.CDLL") as cdll:
        adapter.release_transient_memory()
    cdll.assert_not_called()
    assert adapter.last_metrics["cleanup"] == "warm"


@pytest.mark.parametrize("available_mib", [1024, None])
def test_transient_cleanup_trims_under_pressure_or_unknown(tmp_path: Path, available_mib):
    adapter = CosyVoiceTtsAdapter(str(tmp_path), source_dir=str(tmp_path))
    with patch(
        "cyberwife.adapters.cosyvoice_tts_adapter._linux_mem_available_mib",
        return_value=available_mib,
    ), patch(
        "cyberwife.adapters.cosyvoice_tts_adapter._linux_process_rss_mib",
        return_value=2048,
    ), patch("ctypes.CDLL") as cdll:
        adapter.release_transient_memory()
    cdll.return_value.malloc_trim.assert_called_once_with(0)
    assert adapter.last_metrics["cleanup"] == "trim"


def test_transient_cleanup_trims_when_worker_exceeds_project_rss_budget(tmp_path: Path):
    adapter = CosyVoiceTtsAdapter(str(tmp_path), source_dir=str(tmp_path))
    with patch(
        "cyberwife.adapters.cosyvoice_tts_adapter._linux_mem_available_mib",
        return_value=8192,
    ), patch(
        "cyberwife.adapters.cosyvoice_tts_adapter._linux_process_rss_mib",
        return_value=5120,
    ), patch("ctypes.CDLL") as cdll:
        adapter.release_transient_memory()
    cdll.return_value.malloc_trim.assert_called_once_with(0)
    assert adapter.last_metrics["cleanup_reason"] == "process_rss"


def test_stream_hop_window_is_reset_for_every_request():
    class RuntimeModel:
        token_hop_len = 100

    class Model:
        model = RuntimeModel()

    previous = CosyVoiceTtsAdapter._stream_initial_hop_len
    try:
        CosyVoiceTtsAdapter._stream_initial_hop_len = 25
        CosyVoiceTtsAdapter._reset_stream_hop_window(Model())
        assert Model.model.token_hop_len == 25
        Model.model.token_hop_len = 100
        CosyVoiceTtsAdapter._reset_stream_hop_window(Model())
        assert Model.model.token_hop_len == 25
    finally:
        CosyVoiceTtsAdapter._stream_initial_hop_len = previous


def test_stream_hop_window_reset_is_compatible_when_upstream_field_is_absent():
    class Model:
        model = object()

    previous = CosyVoiceTtsAdapter._stream_initial_hop_len
    try:
        CosyVoiceTtsAdapter._stream_initial_hop_len = 25
        CosyVoiceTtsAdapter._reset_stream_hop_window(Model())
    finally:
        CosyVoiceTtsAdapter._stream_initial_hop_len = previous
