import asyncio
import threading

import pytest
from fastapi.testclient import TestClient

from cyberwife.application.conversation_orchestrator import ConversationOrchestrator
from cyberwife.application.output_sanitizer import OutputSanitizer
from cyberwife.application.prompt_compiler import PromptCompiler
from cyberwife.application.turn_pipeline import TurnPipeline
from cyberwife.domain.conversation import SessionState
from cyberwife.infrastructure.runtime_metrics import RuntimeMetrics
from workers.speech_worker.server import SpeechRuntime, build_app


class _VadEvent:
    def to_dict(self):
        return {"start_ms": 0, "end_ms": 1000}


class _Vad:
    def speech_timestamps(self, pcm, sample_rate):
        return [_VadEvent()] if any(pcm) else []


class _Segment:
    start_ms = 0
    end_ms = 1000
    text = "今天天气不错"
    confidence = 0.98


class _AsrResult:
    text = "今天天气不错"
    confidence = 0.98
    language = "zh"
    segments = (_Segment(),)


class _Asr:
    def transcribe(self, pcm, sample_rate):
        return _AsrResult()


class _Speech:
    def transcribe(self, pcm, sample_rate):
        return {
            "speech_detected": True,
            "text": "今天天气不错",
            "confidence": 0.98,
            "language": "zh",
            "segments": [{"start_ms": 0, "end_ms": 1000, "text": "今天天气不错", "confidence": 0.98}],
        }


class _Llm:
    def generate_stream(self, prompt, **kwargs):
        assert "今天天气不错" in prompt
        yield "**是呀**，"
        yield "很适合聊聊天。"


class _Embedding:
    def embed_batch(self, texts):
        return [[1.0] + [0.0] * 511 for _ in texts]


def test_speech_runtime_keeps_timestamps_and_never_needs_path():
    runtime = SpeechRuntime(
        "/unused",
        vad_factory=lambda: _Vad(),
        asr_factory=lambda: _Asr(),
    )
    result = runtime.transcribe(b"\x01\x00" * 320)
    assert result["speech_detected"] is True
    assert result["segments"][0]["start_ms"] == 0
    assert result["segments"][0]["end_ms"] == 1000


def test_speech_runtime_embedding_endpoint_is_bounded_and_512_dimensional():
    runtime = SpeechRuntime(
        "/unused",
        vad_factory=lambda: _Vad(),
        asr_factory=lambda: _Asr(),
        embedding_factory=lambda: _Embedding(),
    )
    client = TestClient(build_app(runtime=runtime))
    response = client.post("/api/v1/embeddings", json={"texts": ["红茶", "徒步"]})
    assert response.status_code == 200
    assert response.json()["embedding_dim"] == 512
    assert len(response.json()["vectors"]) == 2
    assert client.post("/api/v1/embeddings", json={"texts": []}).status_code == 422


def test_speech_http_rejects_format_and_size():
    app = build_app(runtime=SpeechRuntime("/unused", vad_factory=lambda: _Vad(), asr_factory=lambda: _Asr()))
    client = TestClient(app)
    assert client.post("/api/v1/utterances/transcribe", content=b"x" * 640).status_code == 415
    response = client.post(
        "/api/v1/utterances/transcribe",
        content=b"x" * 641,
        headers={"content-type": "application/octet-stream"},
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_turn_pipeline_final_creates_one_turn_and_sanitizes():
    orchestrator = ConversationOrchestrator()
    session = orchestrator.open_session()
    assert orchestrator.transition(session.id, SessionState.LISTENING)
    pipeline = TurnPipeline(
        orchestrator,
        _Speech(),
        _Llm(),
        PromptCompiler(),
        OutputSanitizer(),
        profile_provider=lambda: {"name": "小雅", "persona": "温柔"},
    )
    events = [event async for event in pipeline.run(session.id, 1, b"\x01\x00" * 320)]
    types = [event.type for event in events]
    assert types.count("transcript.final") == 1
    assert types.count("reply.text.final") == 1
    assert [event.event_seq for event in events] == sorted(event.event_seq for event in events)
    final = next(event for event in events if event.type == "reply.text.final")
    assert final.payload["text_final"] == "是呀，很适合聊聊天。"
    assert all(event.turn_id in {1, None} for event in events)
    assert orchestrator.get(session.id).state == SessionState.LISTENING
    assert orchestrator.next_turn_id(session.id) == 2
    assert pipeline.metrics()["active_turns"] == 0
    assert pipeline.metrics()["llm_queue_depth"] == 0
    assert pipeline.metrics()["llm_queue_max_observed"] <= pipeline.metrics()["llm_queue_capacity"]


@pytest.mark.asyncio
async def test_no_speech_does_not_create_turn():
    class SilentSpeech:
        def transcribe(self, pcm, sample_rate):
            return {"speech_detected": False, "text": "", "segments": []}

    orchestrator = ConversationOrchestrator()
    session = orchestrator.open_session()
    orchestrator.transition(session.id, SessionState.LISTENING)
    pipeline = TurnPipeline(
        orchestrator, SilentSpeech(), _Llm(), PromptCompiler(), OutputSanitizer()
    )
    events = [event async for event in pipeline.run(session.id, 1, b"\0" * 640)]
    assert [event.type for event in events] == ["transcript.partial"]
    assert orchestrator.next_turn_id(session.id) == 1
    assert session.active_turn is None


@pytest.mark.asyncio
async def test_turn_pipeline_emits_one_generation_and_records_server_stages():
    class _Tts:
        last_metrics = {}

        def synthesize_stream(self, text, *_args):
            assert text
            yield b"\x01\x00" * 320

    from cyberwife.application.media_pipeline import MediaPipeline

    orchestrator = ConversationOrchestrator()
    session = orchestrator.open_session()
    orchestrator.transition(session.id, SessionState.LISTENING)
    runtime_metrics = RuntimeMetrics()
    pipeline = TurnPipeline(
        orchestrator,
        _Speech(),
        _Llm(),
        PromptCompiler(),
        OutputSanitizer(),
        media_pipeline=MediaPipeline(_Tts()),
        voice_reference_provider=lambda: ("ref.wav", "参考"),
        runtime_metrics=runtime_metrics,
    )
    events = [event async for event in pipeline.run(session.id, 1, b"\x01\x00" * 320)]
    turn_events = [event for event in events if event.turn_id == 1]
    assert {event.payload["generation"] for event in turn_events} == {1}
    audio = next(event for event in turn_events if event.type == "reply.audio.chunk")
    assert isinstance(audio.payload["asr_final_wall_ms"], float)
    assert audio.payload["server_elapsed_ms"] >= 0
    sample = pipeline.metrics()["latency"]["samples"][0]
    assert sample["generation"] == 1
    assert sample["llm_playable_ms"] is not None
    assert sample["tts_first_packet_ms"] is not None
    assert sample["browser_first_non_silent_ms"] is None


def test_turn_pipeline_rejects_unsafe_first_playable_threshold():
    orchestrator = ConversationOrchestrator()
    with pytest.raises(ValueError, match="first_playable_min_chars"):
        TurnPipeline(
            orchestrator,
            _Speech(),
            _Llm(),
            PromptCompiler(),
            OutputSanitizer(),
            first_playable_min_chars=3,
        )


@pytest.mark.asyncio
async def test_short_reply_emits_every_generated_audio_frame():
    class ShortLlm:
        def generate_stream(self, prompt, **kwargs):
            yield "我在。"

    class TwoFrameTts:
        last_metrics = {}

        def synthesize_stream(self, text, *_args):
            assert text == "我在。"
            yield b"\x01\x00" * 320
            yield b"\x02\x00" * 320

    from cyberwife.application.media_pipeline import MediaPipeline

    orchestrator = ConversationOrchestrator()
    session = orchestrator.open_session()
    orchestrator.transition(session.id, SessionState.LISTENING)
    pipeline = TurnPipeline(
        orchestrator,
        _Speech(),
        ShortLlm(),
        PromptCompiler(),
        OutputSanitizer(),
        media_pipeline=MediaPipeline(TwoFrameTts()),
        voice_reference_provider=lambda: ("ref.wav", "参考"),
    )
    events = [event async for event in pipeline.run(session.id, 1, b"\x01\x00" * 320)]
    audio = [event for event in events if event.type == "reply.audio.chunk"]
    assert len(audio) == 2
    assert [event.payload["clock_ms"] for event in audio] == [0, 20]


@pytest.mark.asyncio
async def test_first_audio_does_not_wait_for_tts_stream_completion():
    release_tail = threading.Event()

    class FastLlm:
        def generate_stream(self, prompt, **kwargs):
            yield "我会认真听你慢慢说。"

    class PausedTts:
        last_metrics = {}

        def synthesize_stream(self, text, *_args):
            yield b"\x01\x00" * 320
            release_tail.wait(timeout=2)
            yield b"\x02\x00" * 320

    from cyberwife.application.media_pipeline import MediaPipeline

    orchestrator = ConversationOrchestrator()
    session = orchestrator.open_session()
    orchestrator.transition(session.id, SessionState.LISTENING)
    pipeline = TurnPipeline(
        orchestrator,
        _Speech(),
        FastLlm(),
        PromptCompiler(),
        OutputSanitizer(),
        media_pipeline=MediaPipeline(PausedTts()),
        voice_reference_provider=lambda: ("ref.wav", "参考"),
    )

    first_seen = asyncio.get_running_loop().create_future()

    async def consume():
        async for event in pipeline.run(session.id, 1, b"\x01\x00" * 320):
            if event.type == "reply.audio.chunk" and not first_seen.done():
                first_seen.set_result(event)

    task = asyncio.create_task(consume())
    try:
        audio = await asyncio.wait_for(asyncio.shield(first_seen), timeout=0.2)
        assert audio.payload["clock_ms"] == 0
    finally:
        release_tail.set()
        await task
