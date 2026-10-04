from workers.speech_worker.server import SpeechRuntime


def test_speech_runtime_warm_loads_each_model_once_and_releases_temporaries(monkeypatch):
    calls = {"vad": 0, "asr": 0, "embedding": 0, "cleanup": 0}

    def factory(name):
        class Model:
            def speech_timestamps(self, pcm, sample_rate):
                assert pcm and sample_rate == 16000
                return []

            def transcribe(self, pcm, sample_rate):
                assert pcm and sample_rate == 16000
                return object()

            def embed_batch(self, texts):
                assert texts == ["本地预热"]
                return [[0.0]]

        def create():
            calls[name] += 1
            return Model()
        return create

    runtime = SpeechRuntime(
        "unused",
        vad_factory=factory("vad"),
        asr_factory=factory("asr"),
        embedding_factory=factory("embedding"),
    )
    monkeypatch.setattr(
        runtime,
        "release_transient_memory",
        lambda: calls.__setitem__("cleanup", calls["cleanup"] + 1),
    )

    runtime.warm()
    runtime.warm()

    assert calls == {"vad": 1, "asr": 1, "embedding": 1, "cleanup": 2}
