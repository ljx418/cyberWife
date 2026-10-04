"""M1-04 unit test: 6 个 port 接口契约（不可实例化抽象基类）。"""
import pytest

from cyberwife.ports.asr import AsrPort, AsrResult
from cyberwife.ports.llm import LlmPort
from cyberwife.ports.tts import TtsPort
from cyberwife.ports.avatar import AvatarPort
from cyberwife.ports.embedding import EmbeddingPort
from cyberwife.ports.repositories import (
    SessionRepository,
    TurnRepository,
    MemoryRepository,
    ProfileRepository,
    ConsentRepository,
    AssetRepository,
    OnboardingDraftRepository,
    RetentionServicePort,
)


@pytest.mark.parametrize("port_cls", [
    AsrPort,
    LlmPort,
    TtsPort,
    AvatarPort,
    EmbeddingPort,
    SessionRepository,
    TurnRepository,
    MemoryRepository,
    ProfileRepository,
    ConsentRepository,
    AssetRepository,
    OnboardingDraftRepository,
    RetentionServicePort,
])
def test_cannot_instantiate_abstract(port_cls):
    with pytest.raises(TypeError):
        port_cls()


def test_embedding_dim_constant():
    assert EmbeddingPort.EMBEDDING_DIM == 512


def test_asr_result_defaults():
    r = AsrResult(text="hi", confidence=0.9)
    assert r.language == "zh"
    assert r.is_partial is False
