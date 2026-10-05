import hashlib
import json
import struct
import wave
from pathlib import Path

from cyberwife.api.server import _load_bootstrap_voice


def _voice(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as output:
        output.setnchannels(1)
        output.setsampwidth(2)
        output.setframerate(16000)
        output.writeframes(struct.pack("<h", 300) * 160)


def test_bootstrap_voice_is_bounded_to_private_data_root_and_hash_checked(tmp_path: Path):
    voice = tmp_path / "bootstrap/voice/reference.wav"
    _voice(voice)
    manifest = tmp_path / "bootstrap/manifest.json"
    manifest.write_text(json.dumps({
        "voice_reference_audio": str(voice),
        "voice_reference_text": "本地授权参考音频",
        "voice_sha256": hashlib.sha256(voice.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    assert _load_bootstrap_voice({"bootstrap": {"manifest": str(manifest)}}, tmp_path) == (
        str(voice.resolve()), "本地授权参考音频"
    )
    voice.write_bytes(b"tampered")
    assert _load_bootstrap_voice({"bootstrap": {"manifest": str(manifest)}}, tmp_path) is None


def test_bootstrap_voice_rejects_path_escape(tmp_path: Path):
    outside = tmp_path.parent / "outside.wav"
    _voice(outside)
    manifest = tmp_path / "bootstrap/manifest.json"
    manifest.parent.mkdir(parents=True)
    manifest.write_text(json.dumps({
        "voice_reference_audio": str(outside),
        "voice_reference_text": "不应读取",
        "voice_sha256": hashlib.sha256(outside.read_bytes()).hexdigest(),
    }), encoding="utf-8")
    assert _load_bootstrap_voice({"bootstrap": {"manifest": str(manifest)}}, tmp_path) is None
