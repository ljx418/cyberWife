"""Fail-closed V1 final gate aggregator; never copies private source reports."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REVISION = re.compile(r"^[0-9a-f]{40,64}$")
HASH = re.compile(r"^[0-9a-f]{64}$")
RELEASE_SECTIONS = ("sources", "dependencies", "release_artifacts", "evidence")
NARRATOR_TASKS = ("settings", "start", "interrupt", "persona", "delete_memory")
CLEAN_KEYS = (
    "data_root_absent", "core_venv_absent", "avatar_venv_absent",
    "runtime_config_absent", "model_registry_absent",
)
INSTALL_STEPS = (
    "offline-prepare", "local-cosy-source", "installer-verify", "start-1",
    "start-2", "status", "recover-avatar", "stop-1", "stop-2",
)
PORTABILITY_STEPS = (
    "release-bind", "isolated-runtimes", "offline-wheelhouse",
    "portable-artifacts", "tracked-frontend", "portable-path-contract",
    "start-1", "start-2", "status", "recover-avatar", "stop-1", "stop-2",
)
PORTABILITY_ISOLATION_KEYS = (
    "fresh_core_venv", "fresh_avatar_venv", "no_system_site_packages",
    "no_index_install", "alternate_data_root_exercised",
    "portable_artifact_bundle_verified", "tracked_frontend",
    "parameterized_runtime_paths",
)
PORTABILITY_LIMITATIONS = (
    "same_windows_identity", "same_wsl_machine_id", "same_gpu_driver_stack",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _number(value: object, default: float = 0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    if not path.is_file():
        return None, ["report_missing"]
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return None, ["report_invalid_json"]
    return (value, []) if isinstance(value, dict) else (None, ["report_invalid_schema"])


def _gate(name: str, errors: list[str], *, missing_is_pending: bool = False) -> dict[str, Any]:
    unique = sorted(set(errors))
    result = "PASS" if not unique else ("PENDING" if missing_is_pending and unique == ["report_missing"] else "FAIL")
    return {"name": name, "result": result, "errors": unique}


def _verify_records(workspace: Path, document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    root = workspace.resolve()
    for section in RELEASE_SECTIONS:
        seen: set[str] = set()
        records = document.get(section)
        if not isinstance(records, list):
            errors.append(f"release_{section}_invalid")
            continue
        for record in records:
            if not isinstance(record, dict):
                errors.append(f"release_{section}_invalid")
                continue
            relative = str(record.get("path", ""))
            expected = str(record.get("sha256", "")).lower()
            if not relative or relative in seen or not HASH.fullmatch(expected):
                errors.append(f"release_{section}_record_invalid")
                continue
            seen.add(relative)
            candidate = (root / relative).resolve()
            try:
                candidate.relative_to(root)
            except ValueError:
                errors.append(f"release_{section}_path_escape")
                continue
            if not candidate.is_file():
                errors.append(f"release_{section}_file_missing")
                continue
            if candidate.stat().st_size != _number(record.get("size_bytes"), -1) or _sha256(candidate) != expected:
                errors.append(f"release_{section}_hash_mismatch")
    return errors


def verify_release(workspace: Path, path: Path) -> dict[str, Any]:
    document, errors = _load(path)
    if document is None:
        return _gate("release-freeze", errors, missing_is_pending=True)
    if document.get("schema_version") != 1 or document.get("result") != "PASS":
        errors.append("release_not_pass")
    if not HASH.fullmatch(str(document.get("release_id", "")).lower()):
        errors.append("release_id_invalid")
    checks = document.get("checks")
    if not isinstance(checks, dict) or not checks or not all(value is True for value in checks.values()):
        errors.append("release_checks_not_pass")
    errors.extend(_verify_records(workspace, document))
    return _gate("release-freeze", errors)


def _health_ready(value: object) -> bool:
    if not isinstance(value, dict) or value.get("status") != "ready":
        return False
    components = value.get("components")
    return isinstance(components, dict) and bool(components) and all(status == "ready" for status in components.values())


def verify_human(path: Path, revision: str) -> dict[str, Any]:
    document, errors = _load(path)
    if document is None:
        return _gate("human-machine-live", errors, missing_is_pending=True)
    if document.get("schema_version") != 2 or document.get("gate") != "ACC1-and-UX6-human-machine-bound-gate":
        errors.append("human_schema_invalid")
    if document.get("workspace_revision") != revision:
        errors.append("revision_mismatch")
    if document.get("result") != "PASS" or document.get("machine_result") != "PASS" or document.get("human_result") != "PASS":
        errors.append("human_gate_not_pass")
    if document.get("stores_raw_audio") is not False or document.get("stores_transcript_or_reply_content") is not False:
        errors.append("human_privacy_contract_invalid")
    if not str(document.get("operator", "")).strip():
        errors.append("human_operator_missing")
    if document.get("screen_reader") != "Windows Narrator" or document.get("page_origin") != "http://127.0.0.1:7860":
        errors.append("human_environment_invalid")
    if not _health_ready(document.get("health_before")) or not _health_ready(document.get("health_after")):
        errors.append("human_health_invalid")
    evidence = document.get("evidence", {})
    completed = evidence.get("completed_turn_ids", []) if isinstance(evidence, dict) else []
    completed_ids = {value for value in completed if isinstance(value, int)} if isinstance(completed, list) else set()
    if not isinstance(evidence, dict) or not all((
        len(completed_ids) >= 3,
        _number(evidence.get("distinct_transcript_turns")) >= 3,
        _number(evidence.get("distinct_reply_turns")) >= 3,
        _number(evidence.get("distinct_audio_turns")) >= 3,
        _number(evidence.get("emitted_pcm_frames")) > 0,
        _number(evidence.get("max_active_microphone_tracks")) >= 1,
        _number(evidence.get("barge_in_count")) >= 1,
        _number(evidence.get("cancelled_count")) >= 1,
        evidence.get("post_cancel_completed") is True,
        _number(evidence.get("error_count"), -1) == 0,
        evidence.get("live_canvas_observed") is True,
        evidence.get("active_avatar_socket_bound") is True,
        _number(evidence.get("idle_advance_after_stop_seconds")) >= 0.5,
    )):
        errors.append("human_machine_evidence_invalid")
    narrator = document.get("narrator", {})
    if not isinstance(narrator, dict) or not all(narrator.get(key) is True for key in NARRATOR_TASKS):
        errors.append("narrator_tasks_invalid")
    perception = document.get("perception", {})
    quality_scores = (
        "lip_sync_score", "mouth_naturalness_score",
        "speaking_clarity_score", "idle_naturalness_score",
    )
    if not isinstance(perception, dict) or not (
        perception.get("mouth_motion_observed") is True
        and all(1 <= _number(perception.get(key), -1) <= 5 for key in quality_scores)
        and _number(perception.get("idle_naturalness_score"), -1) >= 4
        and perception.get("transition_continuity_observed") is True
        and perception.get("idle_continues_after_stop") is True
    ):
        errors.append("perception_gate_invalid")
    return _gate("human-machine-live", errors)


def verify_install(path: Path, revision: str) -> dict[str, Any]:
    document, errors = _load(path)
    if document is None:
        return _gate("deployment-portability", errors, missing_is_pending=True)
    if document.get("schema_version") != 1 or document.get("gate") != "INST1-AC06-clean-machine":
        errors.append("install_schema_invalid")
    if document.get("workspace_revision") != revision:
        errors.append("revision_mismatch")
    if document.get("result") != "PASS" or document.get("identity_differs_from_development") is not True:
        errors.append("install_gate_not_pass")
    if document.get("offline_only") is not True:
        errors.append("install_not_offline")
    clean = document.get("clean_before", {})
    if not isinstance(clean, dict) or not all(clean.get(key) is True for key in CLEAN_KEYS):
        errors.append("install_not_clean_before")
    steps = document.get("steps", [])
    step_map = {
        item.get("name"): item.get("pass") for item in steps
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    } if isinstance(steps, list) else {}
    if not all(step_map.get(name) is True for name in INSTALL_STEPS):
        errors.append("install_steps_incomplete")
    for key in ("windows_sid_hash", "wsl_machine_id_hash", "wheelhouse_manifest_sha256", "artifact_manifest_sha256"):
        if not HASH.fullmatch(str(document.get(key, "")).lower()):
            errors.append("install_binding_invalid")
    if not REVISION.fullmatch(str(document.get("cosyvoice_revision", "")).lower()):
        errors.append("install_binding_invalid")
    gate = _gate("deployment-portability", errors)
    gate["assurance_level"] = "independent-clean-machine"
    return gate


def verify_portability(path: Path, revision: str, release_id: str = "") -> dict[str, Any]:
    """Verify the explicitly reduced, same-machine isolated portability gate.

    This is deliberately a different schema from the independent clean-machine
    report.  It cannot be mistaken for proof of another Windows/WSL/driver stack.
    """
    document, errors = _load(path)
    if document is None:
        return _gate("deployment-portability", errors, missing_is_pending=True)
    if document.get("schema_version") != 1 or document.get("gate") != "INST1-AC07-single-machine-portability":
        errors.append("portability_schema_invalid")
    if document.get("workspace_revision") != revision:
        errors.append("revision_mismatch")
    if release_id and document.get("release_id") != release_id:
        errors.append("release_mismatch")
    if (
        document.get("result") != "PASS"
        or document.get("assurance_level") != "single-machine-isolated-portability"
        or document.get("same_machine") is not True
        or document.get("cross_machine_driver_verified") is not False
    ):
        errors.append("portability_gate_not_pass")
    if document.get("offline_only") is not True:
        errors.append("portability_not_offline")
    isolation = document.get("isolation", {})
    if not isinstance(isolation, dict) or not all(isolation.get(key) is True for key in PORTABILITY_ISOLATION_KEYS):
        errors.append("portability_isolation_incomplete")
    steps = document.get("steps", [])
    step_map = {
        item.get("name"): item.get("pass") for item in steps
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    } if isinstance(steps, list) else {}
    if not all(step_map.get(name) is True for name in PORTABILITY_STEPS):
        errors.append("portability_steps_incomplete")
    limitations = document.get("limitations", [])
    if not isinstance(limitations, list) or not all(value in limitations for value in PORTABILITY_LIMITATIONS):
        errors.append("portability_limitations_missing")
    for key in ("release_id", "wheelhouse_manifest_sha256", "artifact_manifest_sha256"):
        if not HASH.fullmatch(str(document.get(key, "")).lower()):
            errors.append("portability_binding_invalid")
    if not REVISION.fullmatch(str(document.get("cosyvoice_revision", "")).lower()):
        errors.append("portability_binding_invalid")
    gate = _gate("deployment-portability", errors)
    gate["assurance_level"] = "single-machine-isolated-portability"
    gate["limitations"] = list(PORTABILITY_LIMITATIONS)
    return gate


def audit_completion(
    workspace: Path,
    release: Path,
    human: Path,
    deployment: Path,
    revision: str,
    deployment_policy: str = "clean-machine",
) -> dict[str, Any]:
    revision = revision.lower()
    if deployment_policy not in {"clean-machine", "single-machine-portability"}:
        raise ValueError("unsupported deployment policy")
    release_document, _ = _load(release)
    release_id = str(release_document.get("release_id", "")) if release_document else ""
    deployment_gate = (
        verify_install(deployment, revision)
        if deployment_policy == "clean-machine"
        else verify_portability(deployment, revision, release_id)
    )
    gates = [verify_release(workspace, release), verify_human(human, revision), deployment_gate]
    states = {gate["result"] for gate in gates}
    result = "FAIL" if "FAIL" in states else ("PENDING" if "PENDING" in states else "PASS")
    return {
        "schema_version": 1,
        "gate": "cyberwife-v1-final-completion",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workspace_revision": revision,
        "scope": "personal-research-v1",
        "deployment_policy": deployment_policy,
        "deployment_assurance": deployment_gate.get("assurance_level", "unverified"),
        "commercial_use": "NO-GO: Wav2Lip-ResearchOnly",
        "gates": gates,
        "result": result,
        "stores_private_report_content": False,
    }


def _git_revision(workspace: Path) -> str:
    value = subprocess.run(
        ["git", "-C", str(workspace), "rev-parse", "HEAD"], check=True,
        capture_output=True, text=True,
    ).stdout.strip().lower()
    if not REVISION.fullmatch(value):
        raise ValueError("current Git revision is invalid")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--release", type=Path)
    parser.add_argument("--human", type=Path)
    parser.add_argument("--deployment-report", "--install", dest="deployment", type=Path, required=True)
    parser.add_argument(
        "--deployment-policy",
        choices=("clean-machine", "single-machine-portability"),
        default="single-machine-portability",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    workspace = args.workspace.resolve()
    release = args.release or workspace / "audit/v1/B5/B5.6-freeze/release-manifest.json"
    human = args.human or workspace / "audit/v1/ACC1/human-gate.json"
    output = args.output or workspace / "audit/v1/V1FINAL/completion.json"
    result = audit_completion(
        workspace, release, human, args.deployment, _git_revision(workspace), args.deployment_policy,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["result"] == "PASS" else (2 if result["result"] == "PENDING" else 1)


if __name__ == "__main__":
    raise SystemExit(main())
