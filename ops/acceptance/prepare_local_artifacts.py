"""Validate and publish a private, offline cyberWife runtime artifact bundle."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import tempfile
import wave
from pathlib import Path

import yaml


FORMAT = "cyberwife-local-artifacts"
REQUIRED_MODELS = (
    "qwen3-14b-instruct-q4_k_m",
    "faster-whisper-large-v3-turbo",
    "qwen3-tts-12hz-1.7b-base",
    "cosyvoice2-0.5b",
    "livetalking-wav2lip256",
    "silero-vad-v5",
    "bge-small-zh-v1.5",
)
AVATAR_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _checked_path(raw: object, *, kind: str) -> Path:
    path = Path(str(raw or "")).expanduser().resolve()
    if kind == "file" and not path.is_file():
        raise ValueError(f"required file is missing: {path.name}")
    if kind == "directory" and not path.is_dir():
        raise ValueError(f"required directory is missing: {path.name}")
    return path


def _check_declared_hash(path: Path, declared: object) -> str:
    actual = sha256_file(path)
    if declared and str(declared).lower() != actual:
        raise ValueError(f"SHA256 mismatch: {path.name}")
    return actual


def _validate_avatar(path: Path, avatar_id: str) -> None:
    required = (
        path / "manifest.json",
        path / "coords.pkl",
        path / "full_imgs" / "00000000.png",
        path / "face_imgs" / "00000000.png",
    )
    if not all(item.is_file() for item in required):
        raise ValueError("bootstrap avatar is incomplete")
    manifest = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("avatar_id") != avatar_id:
        raise ValueError("bootstrap avatar ID does not match its manifest")


def _publish_directory(staged: Path, target: Path) -> None:
    """Replace one private generated directory, restoring the old copy on failure."""
    target.parent.mkdir(parents=True, exist_ok=True)
    backup = target.with_name(f".{target.name}.previous")
    if backup.exists():
        shutil.rmtree(backup)
    if target.exists():
        os.replace(target, backup)
    try:
        os.replace(staged, target)
    except Exception:
        if backup.exists():
            os.replace(backup, target)
        raise
    shutil.rmtree(backup, ignore_errors=True)


def prepare(manifest_path: Path, repo_root: Path, data_root: Path, report_path: Path) -> dict:
    document = json.loads(manifest_path.read_text(encoding="utf-8"))
    if document.get("schema_version") != 1 or document.get("format") != FORMAT:
        raise ValueError("unsupported local artifact manifest")
    models = document.get("models")
    if not isinstance(models, dict):
        raise ValueError("models must be an object")
    resolved: dict[str, Path] = {}
    for logical_id in REQUIRED_MODELS:
        entry = models.get(logical_id)
        if not isinstance(entry, dict) or not entry.get("license_accepted"):
            raise ValueError(f"model artifact/license missing: {logical_id}")
        kind = str(entry.get("kind", ""))
        if kind not in {"file", "directory"}:
            raise ValueError(f"invalid model artifact kind: {logical_id}")
        resolved[logical_id] = _checked_path(entry.get("path"), kind=kind)
        if kind == "file":
            _check_declared_hash(resolved[logical_id], entry.get("sha256"))

    source = document.get("cosyvoice_source", {})
    if not isinstance(source, dict) or not source.get("license_accepted"):
        raise ValueError("CosyVoice source/license missing")
    cosy_source = _checked_path(source.get("path"), kind="directory")

    bootstrap = document.get("bootstrap", {})
    voice = bootstrap.get("voice", {}) if isinstance(bootstrap, dict) else {}
    avatar = bootstrap.get("avatar", {}) if isinstance(bootstrap, dict) else {}
    if voice.get("consent") is not True or avatar.get("consent") is not True:
        raise ValueError("bootstrap voice and avatar require explicit consent")
    transcript = str(voice.get("transcript", "")).strip()
    if not transcript or len(transcript) > 500:
        raise ValueError("bootstrap voice transcript must contain 1..500 characters")
    voice_path = _checked_path(voice.get("path"), kind="file")
    voice_hash = _check_declared_hash(voice_path, voice.get("sha256"))
    with wave.open(str(voice_path), "rb") as stream:
        if stream.getnchannels() != 1 or stream.getsampwidth() != 2 or stream.getframerate() not in {16000, 22050, 24000, 44100, 48000}:
            raise ValueError("bootstrap voice must be mono 16-bit PCM WAV")
    avatar_id = str(avatar.get("avatar_id", ""))
    if not AVATAR_ID.fullmatch(avatar_id):
        raise ValueError("invalid bootstrap avatar ID")
    avatar_path = _checked_path(avatar.get("path"), kind="directory")
    _validate_avatar(avatar_path, avatar_id)

    example_path = repo_root / "config" / "model-registry.example.yaml"
    local_path = repo_root / "config" / "model-registry.local.yaml"
    registry_source = local_path if local_path.is_file() else example_path
    registry = yaml.safe_load(registry_source.read_text(encoding="utf-8"))
    for entry in registry.get("models", []):
        logical_id = entry.get("logical_id")
        if logical_id in resolved:
            entry["absolute_path"] = str(resolved[logical_id])
            manifest_entry = models[logical_id]
            if manifest_entry.get("sha256"):
                entry["sha256"] = str(manifest_entry["sha256"]).lower()
            entry["size_bytes"] = (
                resolved[logical_id].stat().st_size if resolved[logical_id].is_file()
                else int(entry.get("size_bytes", 0) or 0)
            )
            if registry_source == example_path:
                entry["status"] = "licensed"

    data_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=".artifacts-", dir=data_root))
    try:
        staged_bootstrap = staging / "bootstrap"
        staged_voice = staged_bootstrap / "voice" / "reference.wav"
        staged_avatar = staging / "avatar" / avatar_id
        staged_source = staging / "source" / "CosyVoice"
        staged_voice.parent.mkdir(parents=True)
        staged_avatar.parent.mkdir(parents=True)
        shutil.copy2(voice_path, staged_voice)
        shutil.copytree(avatar_path, staged_avatar)
        staged_source.parent.mkdir(parents=True)
        # Preserve the upstream repository's relative and optional development
        # symlinks. Following them can escape the artifact root or fail on an
        # intentionally unavailable training-only target.
        shutil.copytree(cosy_source, staged_source, symlinks=True)
        private_manifest = {
            "schema_version": 1,
            "voice_reference_audio": str(data_root / "bootstrap" / "voice" / "reference.wav"),
            "voice_reference_text": transcript,
            "voice_sha256": voice_hash,
            "avatar_id": avatar_id,
        }
        (staged_bootstrap / "manifest.json").write_text(
            json.dumps(private_manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (staged_bootstrap / "avatar-id").write_text(avatar_id + "\n", encoding="ascii")
        _publish_directory(staged_bootstrap, data_root / "bootstrap")
        _publish_directory(staged_avatar, data_root / "avatar" / "avatars" / avatar_id)
        _publish_directory(staged_source, data_root / "src" / "CosyVoice")
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(staging, ignore_errors=True)

    registry_path = local_path
    registry_tmp = registry_path.with_suffix(".yaml.tmp")
    registry_tmp.write_text(yaml.safe_dump(registry, allow_unicode=True, sort_keys=False), encoding="utf-8")
    os.replace(registry_tmp, registry_path)
    report = {
        "schema_version": 1,
        "result": "PASS",
        "artifact_manifest_sha256": sha256_file(manifest_path),
        "model_logical_ids": list(REQUIRED_MODELS),
        "bootstrap_avatar_id": avatar_id,
        "bootstrap_voice_sha256": voice_hash,
        "stores_private_paths": False,
        "stores_transcript": False,
    }
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def verify_published(repo_root: Path, data_root: Path) -> dict:
    registry_path = repo_root / "config" / "model-registry.local.yaml"
    private_path = data_root / "bootstrap" / "manifest.json"
    if not registry_path.is_file() or not private_path.is_file():
        raise ValueError("published registry/bootstrap manifest is missing")
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8")) or {}
    by_id = {entry.get("logical_id"): entry for entry in registry.get("models", [])}
    for logical_id in REQUIRED_MODELS:
        value = str(by_id.get(logical_id, {}).get("absolute_path", ""))
        if not value or not Path(value).expanduser().exists():
            raise ValueError(f"published model path is unavailable: {logical_id}")
    private = json.loads(private_path.read_text(encoding="utf-8"))
    avatar_id = str(private.get("avatar_id", ""))
    voice_path = Path(str(private.get("voice_reference_audio", "")))
    if not AVATAR_ID.fullmatch(avatar_id) or not voice_path.is_file():
        raise ValueError("published bootstrap voice/avatar metadata is invalid")
    if sha256_file(voice_path) != private.get("voice_sha256"):
        raise ValueError("published bootstrap voice SHA256 mismatch")
    _validate_avatar(data_root / "avatar" / "avatars" / avatar_id, avatar_id)
    if not (data_root / "src" / "CosyVoice").is_dir():
        raise ValueError("published CosyVoice source is missing")
    return {"schema_version": 1, "result": "PASS", "bootstrap_avatar_id": avatar_id}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "verify"))
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--data-root", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.action == "prepare":
        if args.manifest is None:
            parser.error("prepare requires --manifest")
        result = prepare(args.manifest, args.repo_root, args.data_root, args.report)
    else:
        result = verify_published(args.repo_root, args.data_root)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
