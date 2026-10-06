#!/usr/bin/env python3
"""Build the reduced-assurance, same-machine portability acceptance report.

The report intentionally contains no user names or absolute private paths.  It
combines frozen fresh-venv/offline-install evidence with a current-host lifecycle
run.  It does not claim that another Windows, WSL kernel or GPU driver was tested.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wheelhouse_manifest import verify as verify_wheelhouse
from prepare_local_artifacts import verify_published


RUNTIME_STEPS = ("start-1", "start-2", "status", "recover-avatar", "stop-1", "stop-2")
REQUIRED_ISOLATED_CHECKS = {
    "core_isolated", "avatar_isolated", "core_python_312", "avatar_python_312",
    "core_pip_check", "avatar_pip_check", "core_dependencies", "avatar_dependencies",
    "core_project_sources", "avatar_project_sources",
}
REQUIRED_OFFLINE_CHECKS = {
    "wheelhouse_components", "wheelhouse_files_present", "wheelhouse_manifest_verified",
    "installer_dependency_mode", "installer_ready", "runtime_checks_10_of_10",
    "installer_no_index_contract", "component_separation_contract",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"invalid JSON object: {path.name}")
    return value


def git(workspace: Path, *arguments: str) -> str:
    return subprocess.run(
        ["git", "-C", str(workspace), *arguments], check=True,
        capture_output=True, text=True,
    ).stdout.strip()


def build_report(
    workspace: Path,
    wheelhouse: Path,
    data_root: Path,
    artifact_report_path: Path,
    lifecycle_path: Path,
) -> dict[str, Any]:
    release_path = workspace / "audit/v1/B5/B5.6-freeze/release-manifest.json"
    isolated_path = workspace / "audit/v1/INST1/isolated-runtime-result.json"
    offline_path = workspace / "audit/v1/INST1/offline-install-result.json"
    prepare_path = workspace / "audit/v1/INST1/offline-prepare-result.json"
    release = load(release_path)
    isolated = load(isolated_path)
    offline = load(offline_path)
    prepare = load(prepare_path)
    artifact = load(artifact_report_path)
    lifecycle = load(lifecycle_path)

    revision = git(workspace, "rev-parse", "HEAD").lower()
    if git(workspace, "status", "--porcelain", "--untracked-files=no"):
        raise ValueError("tracked working tree must be clean")
    if release.get("result") != "PASS" or not re.fullmatch(r"[0-9a-f]{64}", str(release.get("release_id", ""))):
        raise ValueError("release freeze is not PASS")

    release_evidence = {
        item.get("path"): item.get("sha256")
        for item in release.get("evidence", []) if isinstance(item, dict)
    }
    for path in (isolated_path, offline_path):
        relative = path.relative_to(workspace).as_posix()
        if release_evidence.get(relative) != sha256(path):
            raise ValueError(f"release does not bind current {path.name}")

    isolated_checks = isolated.get("checks", {})
    if (
        isolated.get("passed") is not True
        or not REQUIRED_ISOLATED_CHECKS.issubset(isolated_checks)
        or not all(isolated_checks[name].get("pass") is True for name in REQUIRED_ISOLATED_CHECKS)
    ):
        raise ValueError("fresh isolated runtime evidence is incomplete")
    offline_checks = offline.get("checks", {})
    if (
        offline.get("passed") is not True
        or not REQUIRED_OFFLINE_CHECKS.issubset(offline_checks)
        or not all(offline_checks[name] is True for name in REQUIRED_OFFLINE_CHECKS)
    ):
        raise ValueError("offline installation evidence is incomplete")
    if (
        prepare.get("ready") is not True
        or prepare.get("dependency_mode") != "wheelhouse"
        or not str(prepare.get("wsl_home", "")).startswith("/tmp/")
        or not str(prepare.get("data_root_wsl", "")).endswith("/.cyberWife")
    ):
        raise ValueError("alternate data-root evidence is incomplete")

    manifest = verify_wheelhouse(wheelhouse)
    wheelhouse_hash = sha256(wheelhouse / "wheelhouse-manifest.json")
    if offline.get("wheelhouse", {}).get("manifest_sha256") != wheelhouse_hash:
        raise ValueError("wheelhouse is not the one bound by offline evidence")
    if manifest.get("file_count", 0) < 1:
        raise ValueError("wheelhouse is empty")

    if not all((
        artifact.get("schema_version") == 1,
        artifact.get("result") == "PASS",
        artifact.get("stores_private_paths") is False,
        artifact.get("stores_transcript") is False,
        re.fullmatch(r"[0-9a-f]{64}", str(artifact.get("artifact_manifest_sha256", ""))) is not None,
    )):
        raise ValueError("portable local artifact report is invalid")
    verify_published(workspace, data_root)

    frontend = workspace / "prototype/dist/index.html"
    git(workspace, "ls-files", "--error-unmatch", frontend.relative_to(workspace).as_posix())
    if not frontend.is_file():
        raise ValueError("tracked production frontend is missing")
    install_text = (workspace / "ops/windows/Install-CyberWife.ps1").read_text(encoding="utf-8-sig")
    launcher_text = (workspace / "ops/windows/RuntimeLauncher.ps1").read_text(encoding="utf-8-sig")
    if not all(token in install_text for token in ("$WslHome", "$ArtifactManifestWsl", "$WheelhouseWsl")):
        raise ValueError("installer paths are not parameterized")
    if not all(token in launcher_text for token in ("$WslHome", "$DataRootWsl", "$ConfigWsl")):
        raise ValueError("runtime paths are not parameterized")
    for text in (install_text, launcher_text):
        if "/home/administrator" in text.lower() or "c:\\users\\administrator" in text.lower():
            raise ValueError("deployment scripts contain a development-user path")

    lifecycle_steps = lifecycle.get("steps", [])
    lifecycle_map = {
        item.get("name"): item.get("pass") for item in lifecycle_steps
        if isinstance(item, dict)
    } if isinstance(lifecycle_steps, list) else {}
    if not all(lifecycle_map.get(name) is True for name in RUNTIME_STEPS):
        raise ValueError("current-host lifecycle is incomplete")
    if lifecycle.get("ports_closed_after") is not True:
        raise ValueError("managed ports were not closed")

    cosy_source = data_root / "src/CosyVoice"
    cosy_revision = git(cosy_source, "rev-parse", "HEAD").lower()
    common_steps = [
        "release-bind", "isolated-runtimes", "offline-wheelhouse",
        "portable-artifacts", "tracked-frontend", "portable-path-contract",
    ]
    return {
        "schema_version": 1,
        "gate": "INST1-AC07-single-machine-portability",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "workspace_revision": revision,
        "release_id": release["release_id"].lower(),
        "wheelhouse_manifest_sha256": wheelhouse_hash,
        "artifact_manifest_sha256": artifact["artifact_manifest_sha256"].lower(),
        "cosyvoice_revision": cosy_revision,
        "assurance_level": "single-machine-isolated-portability",
        "same_machine": True,
        "cross_machine_driver_verified": False,
        "offline_only": True,
        "isolation": {
            "fresh_core_venv": True,
            "fresh_avatar_venv": True,
            "no_system_site_packages": True,
            "no_index_install": True,
            "alternate_data_root_exercised": True,
            "portable_artifact_bundle_verified": True,
            "tracked_frontend": True,
            "parameterized_runtime_paths": True,
        },
        "steps": ([{"name": name, "pass": True} for name in common_steps] + lifecycle_steps),
        "limitations": [
            "same_windows_identity", "same_wsl_machine_id", "same_gpu_driver_stack",
        ],
        "result": "PASS",
        "stores_private_paths": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--data-root", type=Path, required=True)
    parser.add_argument("--artifact-report", type=Path, required=True)
    parser.add_argument("--lifecycle", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(
        args.workspace.resolve(), args.wheelhouse.resolve(), args.data_root.resolve(),
        args.artifact_report.resolve(), args.lifecycle.resolve(),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
