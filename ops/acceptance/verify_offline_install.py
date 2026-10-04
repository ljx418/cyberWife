#!/usr/bin/env python3
"""Aggregate path-sanitised evidence for the INST1.3 offline install gate."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from wheelhouse_manifest import verify as verify_wheelhouse


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--wheelhouse", type=Path, required=True)
    parser.add_argument("--prepare-report", type=Path, required=True)
    parser.add_argument("--runtime-report", type=Path, required=True)
    parser.add_argument("--installer", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    manifest_path = args.wheelhouse / "wheelhouse-manifest.json"
    manifest = verify_wheelhouse(args.wheelhouse)
    prepare = json.loads(args.prepare_report.read_text(encoding="utf-8-sig"))
    runtime = json.loads(args.runtime_report.read_text(encoding="utf-8"))
    installer = args.installer.read_text(encoding="utf-8")
    runtime_checks = runtime.get("checks", {})
    checks = {
        "wheelhouse_components": manifest.get("components") == ["core", "avatar"],
        "wheelhouse_files_present": manifest.get("file_count", 0) > 0,
        "wheelhouse_manifest_verified": manifest.get("file_count") == len(manifest.get("files", [])),
        "installer_dependency_mode": prepare.get("dependency_mode") == "wheelhouse",
        "installer_ready": prepare.get("ready") is True and prepare.get("required_failure_count") == 0,
        "runtime_checks_10_of_10": len(runtime_checks) == 10
        and all(item.get("pass") is True for item in runtime_checks.values()),
        "installer_no_index_contract": "'--no-index', '--find-links'" in installer,
        "component_separation_contract": "$componentWheelhouse" in installer,
    }
    result = {
        "schema_version": 1,
        "stage": "INST1.3",
        "evidence_scope": "component_wheelhouse_and_fresh_no_index_install",
        "wheelhouse": {
            "file_count": manifest.get("file_count"),
            "hardlinked_file_count": manifest.get("hardlinked_file_count"),
            "manifest_sha256": digest(manifest_path),
        },
        "checks": checks,
        "passed": all(checks.values()),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
