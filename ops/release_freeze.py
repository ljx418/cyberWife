#!/usr/bin/env python3
"""Generate a deterministic, path-sanitised cyberWife V1 release manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import subprocess
from pathlib import Path
from typing import Any

import yaml


ACTIVE_MODELS = {
    "qwen3-14b-instruct-q4_k_m",
    "faster-whisper-large-v3-turbo",
    "qwen3-tts-12hz-1.7b-base",
    "cosyvoice2-0.5b",
    "livetalking-wav2lip256",
    "silero-vad-v5",
    "bge-small-zh-v1.5",
}

AVATAR_WORKFLOW_MODELS = {
    "wan22-i2v-high-noise-14b-fp8",
    "wan22-i2v-low-noise-14b-fp8",
    "wan22-i2v-lightx2v-high-lora",
    "wan22-i2v-lightx2v-low-lora",
    "umt5-xxl-fp8",
    "wan21-vae",
    "insightface-scrfd-det10g",
    "qwen-image-2.1-q6-k",
    "qwen3vl-8b-bf16",
    "qwen-image-2.1-vae-bf16",
}
WORKFLOW_MODELS = ACTIVE_MODELS | AVATAR_WORKFLOW_MODELS

SOURCE_ROOTS = ("backend", "prototype", "workers", "ops", "tests", "docs", "config", "migrations")
SOURCE_SUFFIXES = {
    ".cmd", ".css", ".drawio", ".html", ".js", ".json", ".md", ".mjs",
    ".ps1", ".py", ".sql", ".svg", ".toml", ".ts", ".tsx", ".yaml", ".yml",
}
EXCLUDED_PARTS = {
    ".git", ".pytest_cache", "__pycache__", "audit", "assets", "dist",
    "node_modules", "test-results",
}
DEPENDENCY_FILES = (
    "requirements-m0.txt",
    "backend/requirements-m1.txt",
    "backend/requirements-m3-cosyvoice.txt",
    "backend/requirements-runtime-core-cu128.txt",
    "prototype/package-lock.json",
    "workers/avatar/requirements-cyberwife-v1.txt",
    "workers/avatar/requirements-runtime-cu128.txt",
)
ROOT_SOURCE_FILES = ("Start-cyberWife.cmd", "Stop-cyberWife.cmd", "README.md", ".gitignore")
LOCAL_SOURCE_NAMES = {
    "model-registry.local.yaml", "runtime.local.toml",
    "local-artifacts.local.json", "local-artifacts.private.json",
}
EVIDENCE_FILES = (
    "audit/v1/INST1/isolated-runtime-result.json",
    "audit/v1/INST1/offline-install-result.json",
    "audit/v1/B5/B5-AC00-final2/result.json",
    "audit/v1/B5/B5.4B-onboarding-final/result.json",
    "audit/v1/B5/B5.4C-accessibility-final2/result.json",
    "audit/v1/B5/B5.4C-tts-fallback/result.json",
    "audit/v1/B5/B5.4C-AC03-20turn/manifest.json",
    "audit/v1/B5/B5.4C-AC04A/result.json",
    "audit/v1/B5/B5.4C-AC05-generation-fence/manifest.json",
    "audit/v1/B5/B5.4C-AC06-route12-final/result.json",
    "audit/v1/B5/B5.4C-AC07-recall/result.json",
    "audit/v1/B5/B5.4C-AC08-edit-delete/result.json",
    "audit/v1/B5/B5.4C-AC09-no-record/result.json",
    "audit/v1/B5/B5.4C-AC10-retention/result.json",
    "audit/v1/B5/B5.4C-AC12-recovery/result.json",
    "audit/v1/B5/B5.4C-AC13-egress-whitebox/result.json",
    "audit/v1/B5/B5.5-data-lifecycle/result.json",
    "audit/v1/B5/B5.5-AC14-soak-r7/manifest.json",
    "audit/v1/B5/B5.5-AC14-soak-r7/lifecycle.json",
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record(path: Path, workspace: Path) -> dict[str, Any]:
    return {
        "path": path.relative_to(workspace).as_posix(),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def collect_sources(workspace: Path) -> list[dict[str, Any]]:
    files: set[Path] = set()
    tracked: list[Path] | None = None
    if (workspace / ".git").exists():
        result = subprocess.run(
            ["git", "-C", str(workspace), "ls-files", "-z"],
            capture_output=True,
        )
        if result.returncode == 0:
            tracked = [workspace / value.decode("utf-8") for value in result.stdout.split(b"\0") if value]
    candidates = tracked if tracked is not None else [
        path for root_name in SOURCE_ROOTS
        if (workspace / root_name).exists()
        for path in (workspace / root_name).rglob("*")
    ]
    for path in candidates:
        relative = path.relative_to(workspace)
        in_source_root = any(relative.parts and relative.parts[0] == root for root in SOURCE_ROOTS)
        if (
            in_source_root
            and path.is_file()
            and path.suffix.lower() in SOURCE_SUFFIXES
            and not EXCLUDED_PARTS.intersection(relative.parts)
            and path.name not in LOCAL_SOURCE_NAMES
        ):
            files.add(path)
    for name in ROOT_SOURCE_FILES:
        path = workspace / name
        if path.is_file():
            files.add(path)
    return [record(path, workspace) for path in sorted(files)]


def collect_named_files(workspace: Path, names: tuple[str, ...]) -> list[dict[str, Any]]:
    missing = [name for name in names if not (workspace / name).is_file()]
    if missing:
        raise ValueError(f"missing required files: {missing}")
    return [record(workspace / name, workspace) for name in names]


def evidence_passed(document: dict[str, Any]) -> bool:
    if document.get("pass") is True or document.get("passed") is True:
        return True
    if str(document.get("result", "")).upper() == "PASS":
        return True
    summary = document.get("summary")
    return isinstance(summary, dict) and str(summary.get("result", "")).upper() == "PASS"


def collect_evidence(workspace: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for name in EVIDENCE_FILES:
        path = workspace / name
        if not path.is_file():
            raise ValueError(f"missing release evidence: {name}")
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        passed = evidence_passed(document)
        entries.append({**record(path, workspace), "result": "PASS" if passed else "FAIL"})
    return entries


def collect_models(registry_path: Path, workflow_path: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    registry = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    workflow = json.loads(workflow_path.read_text(encoding="utf-8-sig"))
    coverage = workflow.get("extra", {}).get("cyberwife_model_coverage", {})
    covered = set(coverage.get("covered_logical_ids", []))
    rows = {item["logical_id"]: item for item in registry.get("models", [])}
    if covered != WORKFLOW_MODELS:
        raise ValueError(f"workflow coverage mismatch: expected={sorted(WORKFLOW_MODELS)}, actual={sorted(covered)}")
    if not ACTIVE_MODELS.issubset(rows):
        raise ValueError(f"registry missing active models: {sorted(ACTIVE_MODELS - set(rows))}")

    models: list[dict[str, Any]] = []
    for logical_id in sorted(ACTIVE_MODELS):
        item = rows[logical_id]
        digest = str(item.get("sha256", ""))
        if item.get("status") != "verified" or item.get("license_review") != "approved":
            raise ValueError(f"model is not release-approved: {logical_id}")
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError(f"model has no fixed sha256: {logical_id}")
        models.append({
            "logical_id": logical_id,
            "component": item.get("component"),
            "filename_or_revision": item.get("filename_or_revision"),
            "size_bytes": item.get("size_bytes"),
            "sha256": digest,
            "license_id": item.get("license_id"),
            "license_review": item.get("license_review"),
            "status": item.get("status"),
        })
    return models, {
        "covered_logical_ids": sorted(covered),
        "coverage_sha256": sha256_file(workflow_path),
        "covered_count": len(covered),
        "runtime_logical_ids": sorted(ACTIVE_MODELS),
        "offline_avatar_build_logical_ids": sorted(AVATAR_WORKFLOW_MODELS),
        "deletion_candidates": sorted(coverage.get("explicitly_not_covered", [])),
    }


def collect_artifacts(workspace: Path) -> list[dict[str, Any]]:
    dist = workspace / "prototype/dist"
    if not (dist / "index.html").is_file():
        raise ValueError("prototype/dist/index.html missing; run npm run build")
    return [record(path, workspace) for path in sorted(dist.rglob("*")) if path.is_file()]


def command_version(command: list[str]) -> str:
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True).stdout.strip().splitlines()[0]
    except (OSError, subprocess.CalledProcessError, IndexError):
        return "unavailable"


def build_manifest(workspace: Path, registry_path: Path, workflow_path: Path) -> dict[str, Any]:
    models, workflow = collect_models(registry_path, workflow_path)
    body: dict[str, Any] = {
        "schema_version": 1,
        "release": "cyberWife-v1-personal-research",
        "scope": {
            "deployment": "single-user-local-loopback",
            "commercial_use": "NO-GO: Wav2Lip-ResearchOnly",
        },
        "runtime": {
            "python": platform.python_version(),
            "node": command_version(["node", "--version"]),
            "platform": platform.system().lower(),
        },
        "sources": collect_sources(workspace),
        "dependencies": collect_named_files(workspace, DEPENDENCY_FILES),
        "release_artifacts": collect_artifacts(workspace),
        "models": models,
        "workflow_coverage": workflow,
        "evidence": collect_evidence(workspace),
    }
    checks = {
        "active_models_exactly_7": len(models) == 7,
        "workflow_matches_release_models": workflow["covered_logical_ids"] == sorted(WORKFLOW_MODELS),
        "all_evidence_pass": all(item["result"] == "PASS" for item in body["evidence"]),
        "production_frontend_present": any(item["path"] == "prototype/dist/index.html" for item in body["release_artifacts"]),
    }
    body["checks"] = checks
    body["result"] = "PASS" if all(checks.values()) else "FAIL"
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    body["release_id"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    serialized = json.dumps(body, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if re.search(r"(?:[A-Za-z]:\\|/home/|/mnt/)", serialized):
        raise ValueError("manifest contains an absolute private path")
    return body


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--workflow-index", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = args.workspace.resolve()
    registry = args.registry or workspace / "config/model-registry.local.yaml"
    output = args.output or workspace / "audit/v1/B5/B5.6-freeze/release-manifest.json"
    manifest = build_manifest(workspace, registry, args.workflow_index)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"result": manifest["result"], "release_id": manifest["release_id"], "output": str(output)}))
    return 0 if manifest["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
