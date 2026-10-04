import hashlib
import json
from pathlib import Path

import pytest
import yaml

from ops.release_freeze import ACTIVE_MODELS, DEPENDENCY_FILES, WORKFLOW_MODELS, build_manifest


def _write(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")


def _fixture(tmp_path: Path) -> tuple[Path, Path]:
    for name in DEPENDENCY_FILES:
        _write(tmp_path / name, "locked\n")
    _write(tmp_path / "prototype/dist/index.html", "<main>release</main>\n")
    _write(tmp_path / "backend/app.py", "VERSION = 1\n")
    _write(tmp_path / "config/model-registry.local.yaml", yaml.safe_dump({
        "models": [{
            "logical_id": logical_id,
            "component": "test",
            "absolute_path": f"C:\\private\\{logical_id}",
            "filename_or_revision": "fixed",
            "size_bytes": 1,
            "sha256": hashlib.sha256(logical_id.encode()).hexdigest(),
            "license_id": "MIT",
            "license_review": "approved",
            "status": "verified",
        } for logical_id in ACTIVE_MODELS],
    }, sort_keys=False))
    workflow = tmp_path / "workflow.json"
    _write(workflow, json.dumps({
        "extra": {"cyberwife_model_coverage": {
            "covered_logical_ids": sorted(WORKFLOW_MODELS),
            "explicitly_not_covered": ["unused-model"],
        }},
    }))
    for name in __import__("ops.release_freeze", fromlist=["EVIDENCE_FILES"]).EVIDENCE_FILES:
        _write(tmp_path / name, json.dumps({"pass": True}))
    return tmp_path / "config/model-registry.local.yaml", workflow


def test_manifest_is_deterministic_and_does_not_expose_private_paths(tmp_path: Path) -> None:
    registry, workflow = _fixture(tmp_path)
    first = build_manifest(tmp_path, registry, workflow)
    second = build_manifest(tmp_path, registry, workflow)
    assert first == second
    assert first["result"] == "PASS"
    assert len(first["models"]) == 7
    serialized = json.dumps(first)
    assert "C:\\\\private" not in serialized
    assert str(tmp_path) not in serialized


def test_manifest_rejects_unfixed_active_model(tmp_path: Path) -> None:
    registry, workflow = _fixture(tmp_path)
    document = yaml.safe_load(registry.read_text())
    document["models"][0]["sha256"] = "torch-hub-cache"
    registry.write_text(yaml.safe_dump(document), encoding="utf-8")
    with pytest.raises(ValueError, match="no fixed sha256"):
        build_manifest(tmp_path, registry, workflow)
