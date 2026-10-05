from types import SimpleNamespace

from cyberwife.adapters.faster_whisper_adapter import (
    MANDARIN_SIMPLIFIED_PROMPT,
    FasterWhisperAdapter,
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
    from opencc import OpenCC

    adapter._model = Model()
    adapter._simplifier = OpenCC("t2s")
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
        }
    ]
    assert "普通话" in MANDARIN_SIMPLIFIED_PROMPT
    assert "简体中文" in MANDARIN_SIMPLIFIED_PROMPT
