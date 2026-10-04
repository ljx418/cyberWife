import pytest

from cyberwife.application.conversation_orchestrator import ConversationOrchestrator
from cyberwife.application.media_pipeline import MediaPipeline
from cyberwife.application.output_sanitizer import OutputSanitizer
from cyberwife.application.prompt_compiler import PromptCompiler
from cyberwife.application.turn_pipeline import TurnPipeline
from cyberwife.application.warm_response_cache import WarmResponseCache
from cyberwife.domain.conversation import SessionState
from cyberwife.domain.warm_response import WarmResponseContext, WarmResponsePolicy


def _context(**changes):
    values = {
        "persona_version": "p1",
        "voice_version": "v1",
        "llm_revision": "l1",
        "tts_revision": "t1",
        "policy_version": "policy-1",
    }
    values.update(changes)
    return WarmResponseContext(**values)


def test_policy_is_exact_and_rejects_dynamic_or_augmented_text():
    policy = WarmResponsePolicy(("你好", "嗨", "早上好", "晚上好", "你在吗", "能听见吗"), version="policy-1")
    assert policy.match(" 你 好！ ") == "你好"
    negatives = (
        "今天天气怎么样", "你好今天天气怎么样", "你好，请告诉我天气", "你还记得我吗",
        "你好你记得我吗", "继续说", "你好继续说", "再说一点", "早上好今天天气如何",
        "晚上好帮我查天气", "嗨你是谁", "嗨说个故事", "你在吗告诉我时间",
        "能听见吗继续", "谢谢你告诉我天气", "再见之前回答我", "你好呀", "你好啊",
        "你好宝贝", "宝贝你好", "天气", "记忆", "继续", "在吗今天天气如何",
    )
    assert len(negatives) == 24
    assert all(policy.match(text) is None for text in negatives)


def test_cache_binds_all_versions_and_enforces_memory_limit():
    cache = WarmResponseCache(WarmResponsePolicy(("你好",), version="policy-1"), max_bytes=650)
    assert cache.max_bytes == 650
    ctx = _context()
    frame = b"\x01\x00" * 320
    assert cache.put("你好。", ctx, reply_text="你好。", pcm_frames=(frame,))
    assert cache.lookup("你 好！", ctx) is not None
    for field in ("persona_version", "voice_version", "llm_revision", "tts_revision", "policy_version"):
        assert cache.lookup("你好", _context(**{field: "changed"})) is None
        assert cache.resolve("你好", _context(**{field: "changed"}))[1] == "config-invalid"
    assert cache.resolve("今天天气怎么样", ctx)[1] == "normal"
    assert not cache.put("你好", ctx, reply_text="太大", pcm_frames=(frame, frame))
    assert cache.size_bytes <= 650


@pytest.mark.asyncio
async def test_turn_pipeline_cache_hit_bypasses_models_but_keeps_media_contract():
    class Speech:
        def transcribe(self, _pcm, _sample_rate):
            return {"speech_detected": True, "text": "你好！", "confidence": 1.0, "language": "zh", "segments": []}

    class ForbiddenLlm:
        def generate_stream(self, *_args, **_kwargs):
            raise AssertionError("LLM must not run on a cache hit")

    class Tts:
        last_metrics = {}

        def synthesize_stream(self, *_args, **_kwargs):
            raise AssertionError("TTS must not run on a cache hit")

    class Avatar:
        pushed = 0

        def open(self):
            return "0"

        def push_audio(self, frame, *, clock_ms):
            assert len(frame) == 640
            assert clock_ms == 0
            self.pushed += 1

    ctx = _context()
    cache = WarmResponseCache(WarmResponsePolicy(("你好",), version="policy-1"))
    assert cache.put("你好", ctx, reply_text="你好。", pcm_frames=(b"\x01\x00" * 320,))
    avatar = Avatar()
    orchestrator = ConversationOrchestrator()
    session = orchestrator.open_session()
    orchestrator.transition(session.id, SessionState.LISTENING)
    pipeline = TurnPipeline(
        orchestrator,
        Speech(),
        ForbiddenLlm(),
        PromptCompiler(),
        OutputSanitizer(),
        media_pipeline=MediaPipeline(Tts(), avatar),
        warm_response_cache=cache,
        warm_context_provider=lambda: ctx,
    )
    events = [event async for event in pipeline.run(session.id, 1, b"\x01\x00" * 320)]
    assert avatar.pushed == 1
    assert next(event for event in events if event.type == "reply.text.final").payload["text_final"] == "你好。"
    assert len([event for event in events if event.type == "reply.audio.chunk"]) == 1
    sample = pipeline.metrics()["latency"]["samples"][0]
    assert sample["bucket"] == "cache-hit"
    assert orchestrator.get(session.id).state == SessionState.SPEAKING
    assert pipeline.complete_playback(session.id, generation=1) is not None
    assert orchestrator.get(session.id).state == SessionState.LISTENING
