import numpy as np
import pytest
import threading

from cyberwife.application.media_pipeline import MediaPipeline
from cyberwife.application.sentence_scheduler import playable_prefix, semantic_sentences
from cyberwife.adapters.live_talking_adapter import LiveTalkingAdapter
from cyberwife.adapters.cosyvoice_tts_adapter import _install_cancellable_llm_inference


def test_semantic_scheduler_keeps_punctuation_and_bounds_long_text():
    parts = semantic_sentences("你好呀！今天想和你聊聊天，我们慢慢说，不着急。" + "很长" * 30)
    assert parts[0] == "你好呀！"
    assert all(part.strip() == part and len(part) <= 48 for part in parts)
    assert "".join(parts).replace(" ", "") == "你好呀！今天想和你聊聊天，我们慢慢说，不着急。" + "很长" * 30


def test_playable_prefix_is_configurable_and_lossless():
    assert playable_prefix("只有七个字呀", min_chars=8) is None
    punctuated = "今天真的很好呀！我们慢慢聊。"
    prefix = playable_prefix(punctuated, min_chars=8)
    assert prefix == "今天真的很好呀！"
    assert prefix + punctuated[len(prefix):] == punctuated
    unpunctuated = "我想认真听你慢慢说下去"
    assert playable_prefix(unpunctuated, min_chars=8) is None
    long_unpunctuated = "我想认真听你慢慢说下去也不会突然打断你"
    assert playable_prefix(long_unpunctuated, min_chars=8, hard_limit=18) == long_unpunctuated[:18]


def test_playable_prefix_rejects_unsafe_threshold():
    with pytest.raises(ValueError, match="min_chars"):
        playable_prefix("测试文本", min_chars=3)
    with pytest.raises(ValueError, match="min_chars"):
        playable_prefix("测试文本" * 10, min_chars=19)


def test_livetalking_rejects_non_loopback_and_bad_pcm():
    with pytest.raises(ValueError, match="loopback"):
        LiveTalkingAdapter("http://192.168.1.10:8010")
    adapter = LiveTalkingAdapter()
    adapter._session_id = "0"
    with pytest.raises(ValueError, match="640"):
        adapter.push_audio(b"x", clock_ms=0)


@pytest.mark.asyncio
async def test_media_pipeline_tolerates_one_transient_avatar_frame_failure():
    class Tts:
        last_metrics = {"rtf": 0.1}
        def synthesize_stream(self, text, *_args):
            assert text
            yield (np.ones(320, dtype=np.int16) * 100).tobytes()
            yield (np.ones(320, dtype=np.int16) * 100).tobytes()

    class Avatar:
        def open(self): return "0"
        def push_audio(self, frame, *, clock_ms):
            if clock_ms == 20:
                raise ConnectionError("avatar stopped")

    pipeline = MediaPipeline(Tts(), Avatar(), queue_size=2)
    events = [event async for event in pipeline.stream("你好。", "ref.wav", "参考")]
    audio = [event for event in events if event["type"] == "reply.audio.chunk"]
    assert [event["clock_ms"] for event in audio] == [0, 20]
    assert all(len(event["pcm"]) == 640 for event in audio)
    assert not any(event.get("mode") == "static_fallback" for event in events)
    assert pipeline.metrics()["avatar_frame_errors"] == 1
    assert pipeline.metrics()["tts_queue_depth"] == 0


@pytest.mark.asyncio
async def test_media_pipeline_synthesizes_a_multi_sentence_reply_once():
    class Tts:
        last_metrics = {"rtf": 0.1}

        def __init__(self):
            self.calls = []

        def synthesize_stream(self, text, *_args):
            self.calls.append(text)
            yield (np.ones(320, dtype=np.int16) * 100).tobytes()

    tts = Tts()
    pipeline = MediaPipeline(tts)
    try:
        events = [
            event
            async for event in pipeline.stream(
                "我在认真听你说。你可以慢慢讲。", "ref.wav", "参考"
            )
        ]
        assert tts.calls == ["我在认真听你说。你可以慢慢讲。"]
        assert sum(event["type"] == "reply.audio.chunk" for event in events) == 1
    finally:
        pipeline.close()


@pytest.mark.asyncio
async def test_media_pipeline_degrades_after_three_consecutive_avatar_failures():
    class Tts:
        last_metrics = {"rtf": 0.1}
        def synthesize_stream(self, text, *_args):
            for _ in range(4):
                yield (np.ones(320, dtype=np.int16) * 100).tobytes()

    class Avatar:
        def open(self): return "0"
        def push_audio(self, frame, *, clock_ms):
            raise TimeoutError(clock_ms)

    pipeline = MediaPipeline(Tts(), Avatar(), queue_size=4)
    events = [event async for event in pipeline.stream("你好。", "ref.wav", "参考")]

    assert sum(event.get("mode") == "static_fallback" for event in events) == 1
    assert pipeline.metrics()["avatar_frame_errors"] == 3


def test_media_pipeline_delegates_transient_memory_release():
    class Tts:
        released = 0

        def release_transient_memory(self):
            self.released += 1

    tts = Tts()
    pipeline = MediaPipeline(tts)
    pipeline.release_transient_memory()
    assert tts.released == 1


@pytest.mark.asyncio
async def test_media_pipeline_reuses_one_owned_tts_thread_and_closes_idempotently():
    class Tts:
        def __init__(self):
            self.thread_ids = []

        def synthesize_stream(self, text, *_args):
            self.thread_ids.append(threading.get_ident())
            yield (np.ones(320, dtype=np.int16) * 100).tobytes()

    tts = Tts()
    pipeline = MediaPipeline(tts)
    try:
        for text in ("第一轮。", "第二轮。", "第三轮。"):
            events = [event async for event in pipeline.stream(text, "ref.wav", "参考")]
            assert any(event["type"] == "reply.audio.chunk" for event in events)
        assert len(set(tts.thread_ids)) == 1
        assert tts.thread_ids[0] != threading.get_ident()
    finally:
        pipeline.close()
        pipeline.close()

    with pytest.raises(RuntimeError, match="closed"):
        _ = [event async for event in pipeline.stream("关闭后。", "ref.wav", "参考")]


def test_cosyvoice_llm_wrapper_stops_tokens_cooperatively_and_is_idempotent():
    cancel_event = threading.Event()

    class Llm:
        def inference(self):
            yield 1
            yield 2
            yield 3

    class Inner:
        llm = Llm()

    class Model:
        model = Inner()

    model = Model()
    _install_cancellable_llm_inference(model, cancel_event)
    stream = model.model.llm.inference()
    assert next(stream) == 1
    cancel_event.set()
    assert list(stream) == []

    replacement = threading.Event()
    _install_cancellable_llm_inference(model, replacement)
    assert list(model.model.llm.inference()) == [1, 2, 3]
