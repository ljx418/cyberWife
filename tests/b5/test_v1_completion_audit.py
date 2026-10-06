import hashlib
import json
from pathlib import Path

from ops.acceptance.audit_v1_completion import audit_completion


REVISION = "a" * 40


def _record(root: Path, relative: str, content: bytes) -> dict:
    target = root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {
        "path": relative,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }


def _fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    record = _record(tmp_path, "backend/app.py", b"release\n")
    release = tmp_path / "release.json"
    release.write_text(json.dumps({
        "schema_version": 1,
        "result": "PASS",
        "release_id": "b" * 64,
        "checks": {"all_evidence_pass": True},
        "sources": [record],
        "dependencies": [],
        "release_artifacts": [],
        "evidence": [],
    }), encoding="utf-8")
    human = tmp_path / "human.json"
    human.write_text(json.dumps({
        "schema_version": 2,
        "gate": "ACC1-and-UX6-human-machine-bound-gate",
        "workspace_revision": REVISION,
        "operator": "tester",
        "page_origin": "http://127.0.0.1:7860",
        "screen_reader": "Windows Narrator",
        "stores_raw_audio": False,
        "stores_transcript_or_reply_content": False,
        "machine_result": "PASS",
        "human_result": "PASS",
        "result": "PASS",
        "health_before": {"status": "ready", "components": {"llm": "ready"}},
        "health_after": {"status": "ready", "components": {"llm": "ready"}},
        "evidence": {
            "emitted_pcm_frames": 10,
            "max_active_microphone_tracks": 1,
            "completed_turn_ids": [1, 2, 4],
            "distinct_transcript_turns": 3,
            "distinct_reply_turns": 3,
            "distinct_audio_turns": 3,
            "barge_in_count": 1,
            "cancelled_count": 1,
            "post_cancel_completed": True,
            "error_count": 0,
            "live_canvas_observed": True,
            "active_avatar_socket_bound": True,
            "idle_advance_after_stop_seconds": 0.8,
        },
        "narrator": {key: True for key in ("settings", "start", "interrupt", "persona", "delete_memory")},
        "perception": {
            "mouth_motion_observed": True,
            "lip_sync_score": 4,
            "mouth_naturalness_score": 4,
            "idle_naturalness_score": 4,
            "idle_continues_after_stop": True,
        },
    }), encoding="utf-8")
    install = tmp_path / "install.json"
    install.write_text(json.dumps({
        "schema_version": 1,
        "gate": "INST1-AC06-clean-machine",
        "workspace_revision": REVISION,
        "windows_sid_hash": "c" * 64,
        "wsl_machine_id_hash": "d" * 64,
        "wheelhouse_manifest_sha256": "e" * 64,
        "artifact_manifest_sha256": "f" * 64,
        "cosyvoice_revision": "1" * 40,
        "identity_differs_from_development": True,
        "clean_before": {key: True for key in (
            "data_root_absent", "core_venv_absent", "avatar_venv_absent",
            "runtime_config_absent", "model_registry_absent",
        )},
        "offline_only": True,
        "steps": [{"name": name, "pass": True} for name in (
            "offline-prepare", "local-cosy-source", "installer-verify", "start-1",
            "start-2", "status", "recover-avatar", "stop-1", "stop-2",
        )],
        "result": "PASS",
    }), encoding="utf-8")
    return release, human, install


def _portability_fixture(tmp_path: Path) -> Path:
    report = tmp_path / "portability.json"
    report.write_text(json.dumps({
        "schema_version": 1,
        "gate": "INST1-AC07-single-machine-portability",
        "workspace_revision": REVISION,
        "release_id": "b" * 64,
        "wheelhouse_manifest_sha256": "e" * 64,
        "artifact_manifest_sha256": "f" * 64,
        "cosyvoice_revision": "1" * 40,
        "assurance_level": "single-machine-isolated-portability",
        "same_machine": True,
        "cross_machine_driver_verified": False,
        "offline_only": True,
        "isolation": {key: True for key in (
            "fresh_core_venv", "fresh_avatar_venv", "no_system_site_packages",
            "no_index_install", "alternate_data_root_exercised",
            "portable_artifact_bundle_verified", "tracked_frontend",
            "parameterized_runtime_paths",
        )},
        "limitations": [
            "same_windows_identity", "same_wsl_machine_id", "same_gpu_driver_stack",
        ],
        "steps": [{"name": name, "pass": True} for name in (
            "release-bind", "isolated-runtimes", "offline-wheelhouse",
            "portable-artifacts", "tracked-frontend", "portable-path-contract",
            "start-1", "start-2", "status", "recover-avatar", "stop-1", "stop-2",
        )],
        "result": "PASS",
    }), encoding="utf-8")
    return report


def test_completion_passes_only_when_all_three_current_gates_pass(tmp_path: Path):
    release, human, install = _fixture(tmp_path)
    result = audit_completion(tmp_path, release, human, install, REVISION)
    assert result["result"] == "PASS"
    assert [gate["result"] for gate in result["gates"]] == ["PASS", "PASS", "PASS"]
    serialized = json.dumps(result)
    assert "operator" not in serialized and "windows_sid_hash" not in serialized


def test_completion_reports_missing_external_evidence_as_pending(tmp_path: Path):
    release, _, _ = _fixture(tmp_path)
    result = audit_completion(tmp_path, release, tmp_path / "missing-human.json", tmp_path / "missing-install.json", REVISION)
    assert result["result"] == "PENDING"
    assert {gate["result"] for gate in result["gates"]} == {"PASS", "PENDING"}


def test_completion_rejects_stale_release_or_revision(tmp_path: Path):
    release, human, install = _fixture(tmp_path)
    (tmp_path / "backend/app.py").write_bytes(b"changed\n")
    stale = audit_completion(tmp_path, release, human, install, REVISION)
    assert stale["result"] == "FAIL"
    (tmp_path / "backend/app.py").write_bytes(b"release\n")
    document = json.loads(human.read_text())
    document["workspace_revision"] = "c" * 40
    human.write_text(json.dumps(document))
    mismatch = audit_completion(tmp_path, release, human, install, REVISION)
    assert mismatch["result"] == "FAIL"
    assert "revision_mismatch" in mismatch["gates"][1]["errors"]


def test_completion_fails_closed_on_malformed_untrusted_fields(tmp_path: Path):
    release, human, install = _fixture(tmp_path)
    document = json.loads(human.read_text())
    document["evidence"]["completed_turn_ids"] = [{"not": "hashable"}]
    document["perception"]["lip_sync_score"] = "not-a-number"
    human.write_text(json.dumps(document))
    result = audit_completion(tmp_path, release, human, install, REVISION)
    assert result["result"] == "FAIL"
    assert "human_machine_evidence_invalid" in result["gates"][1]["errors"]
    assert "perception_gate_invalid" in result["gates"][1]["errors"]


def test_completion_rejects_static_mouth_even_when_subjective_scores_are_high(tmp_path: Path):
    release, human, install = _fixture(tmp_path)
    document = json.loads(human.read_text())
    document["perception"]["mouth_motion_observed"] = False
    document["perception"]["lip_sync_score"] = 5
    document["perception"]["mouth_naturalness_score"] = 5
    human.write_text(json.dumps(document))
    result = audit_completion(tmp_path, release, human, install, REVISION)
    assert result["result"] == "FAIL"
    assert "perception_gate_invalid" in result["gates"][1]["errors"]


def test_completion_accepts_explicit_single_machine_portability_policy(tmp_path: Path):
    release, human, _ = _fixture(tmp_path)
    portability = _portability_fixture(tmp_path)
    result = audit_completion(
        tmp_path, release, human, portability, REVISION, "single-machine-portability",
    )
    assert result["result"] == "PASS"
    assert result["deployment_assurance"] == "single-machine-isolated-portability"
    assert result["gates"][2]["limitations"] == [
        "same_windows_identity", "same_wsl_machine_id", "same_gpu_driver_stack",
    ]


def test_clean_machine_report_cannot_masquerade_as_reduced_policy(tmp_path: Path):
    release, human, install = _fixture(tmp_path)
    result = audit_completion(
        tmp_path, release, human, install, REVISION, "single-machine-portability",
    )
    assert result["result"] == "FAIL"
    assert "portability_schema_invalid" in result["gates"][2]["errors"]


def test_portability_fails_closed_when_isolation_or_limit_is_missing(tmp_path: Path):
    release, human, _ = _fixture(tmp_path)
    portability = _portability_fixture(tmp_path)
    document = json.loads(portability.read_text())
    document["isolation"]["no_index_install"] = False
    document["limitations"].remove("same_gpu_driver_stack")
    portability.write_text(json.dumps(document))
    result = audit_completion(
        tmp_path, release, human, portability, REVISION, "single-machine-portability",
    )
    assert result["result"] == "FAIL"
    assert "portability_isolation_incomplete" in result["gates"][2]["errors"]
    assert "portability_limitations_missing" in result["gates"][2]["errors"]


def test_portability_must_bind_the_current_release_id(tmp_path: Path):
    release, human, _ = _fixture(tmp_path)
    portability = _portability_fixture(tmp_path)
    document = json.loads(portability.read_text())
    document["release_id"] = "9" * 64
    portability.write_text(json.dumps(document))
    result = audit_completion(
        tmp_path, release, human, portability, REVISION, "single-machine-portability",
    )
    assert result["result"] == "FAIL"
    assert "release_mismatch" in result["gates"][2]["errors"]
