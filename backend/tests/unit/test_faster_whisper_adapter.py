from types import SimpleNamespace

from cyberwife.adapters.faster_whisper_adapter import (
    MANDARIN_HOTWORDS,
    MANDARIN_SIMPLIFIED_PROMPT,
    FasterWhisperAdapter,
    MandarinTranscriptNormalizer,
)


def test_asr_uses_mandarin_simplified_stable_decode_contract():
    calls = []

    class Model:
        def transcribe(self, audio, **kwargs):
            calls.append(kwargs)
            return (
                iter(
                    [
                        SimpleNamespace(
                            start=0.0,
                            end=0.8,
                            text="今天天氣怎麼樣",
                            avg_logprob=-0.05,
                        )
                    ]
                ),
                SimpleNamespace(language="zh"),
            )

    adapter = FasterWhisperAdapter.__new__(FasterWhisperAdapter)
    adapter._model = Model()
    adapter._normalizer = MandarinTranscriptNormalizer()
    adapter._logger = SimpleNamespace(emit=lambda *_args, **_kwargs: None)

    result = adapter.transcribe(b"\x01\x00" * 1600)

    assert result.text == "今天天气怎么样"
    assert calls == [
        {
            "language": "zh",
            "task": "transcribe",
            "beam_size": 1,
            "vad_filter": False,
            "condition_on_previous_text": False,
            "initial_prompt": MANDARIN_SIMPLIFIED_PROMPT,
            "hotwords": MANDARIN_HOTWORDS,
        }
    ]
    assert "普通话" in MANDARIN_SIMPLIFIED_PROMPT
    assert "简体中文" in MANDARIN_SIMPLIFIED_PROMPT


def test_mandarin_normalizer_conservatively_rewrites_cantonese_function_words():
    normalizer = MandarinTranscriptNormalizer()

    assert normalizer.normalize("而家喺呢度，點解冇人？") == "现在在这里，为什么没有人？"
    assert normalizer.normalize("你係咪想睇下乜嘢？") == "你是不是想看看什么？"
    assert normalizer.normalize("這個係我嘅，已經做好咗。") == "这个是我的，已经做好了。"


def test_mandarin_normalizer_does_not_rewrite_ambiguous_mandarin_content():
    normalizer = MandarinTranscriptNormalizer()

    text = "关系系统正在维护，今天和小粤一起讲粤语。"
    assert normalizer.normalize(text) == text
    assert normalizer.normalize("今天 weather 很好") == "今天 weather 很好"
    assert normalizer.normalize("你好呀 今天过得怎么样") == "你好呀今天过得怎么样"


def test_asr_full_text_and_segments_share_the_same_mandarin_normalization():
    class Model:
        def transcribe(self, audio, **kwargs):
            return (
                iter(
                    [
                        SimpleNamespace(start=0.0, end=0.4, text="而家喺呢度，", avg_logprob=-0.1),
                        SimpleNamespace(start=0.4, end=0.8, text="點解冇人？", avg_logprob=-0.1),
                    ]
                ),
                SimpleNamespace(language="zh"),
            )

    adapter = FasterWhisperAdapter.__new__(FasterWhisperAdapter)
    adapter._model = Model()
    adapter._normalizer = MandarinTranscriptNormalizer()
    adapter._logger = SimpleNamespace(emit=lambda *_args, **_kwargs: None)

    result = adapter.transcribe(b"\x01\x00" * 1600)

    assert result.text == "现在在这里，为什么没有人？"
    assert [segment.text for segment in result.segments] == ["现在在这里，", "为什么没有人？"]
    assert [(segment.start_ms, segment.end_ms) for segment in result.segments] == [(0, 400), (400, 800)]
