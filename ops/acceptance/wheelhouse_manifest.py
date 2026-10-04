#!/usr/bin/env python3
"""Build or verify a deterministic manifest for the offline wheelhouse."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path


MANIFEST_NAME = "wheelhouse-manifest.json"
COMPONENTS = ("core", "avatar")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def collect(root: Path) -> list[dict[str, object]]:
    records: list[dict[str, object]] = []
    for component in COMPONENTS:
        directory = root / component
        if not directory.is_dir():
            raise ValueError(f"missing wheelhouse component: {component}")
        wheels = sorted(directory.glob("*.whl"))
        if not wheels:
            raise ValueError(f"empty wheelhouse component: {component}")
        records.extend(
            {
                "path": wheel.relative_to(root).as_posix(),
                "size_bytes": wheel.stat().st_size,
                "sha256": sha256(wheel),
            }
            for wheel in wheels
        )
    return records


def deduplicate(root: Path) -> int:
    """Hard-link byte-identical component wheels when both live on one filesystem."""
    linked = 0
    for avatar_wheel in sorted((root / "avatar").glob("*.whl")):
        core_wheel = root / "core" / avatar_wheel.name
        if (
            core_wheel.is_file()
            and core_wheel.stat().st_dev == avatar_wheel.stat().st_dev
            and not core_wheel.samefile(avatar_wheel)
            and core_wheel.stat().st_size == avatar_wheel.stat().st_size
            and sha256(core_wheel) == sha256(avatar_wheel)
        ):
            avatar_wheel.unlink()
            os.link(core_wheel, avatar_wheel)
            linked += 1
    return linked


def build(root: Path) -> dict[str, object]:
    hardlinked_file_count = deduplicate(root)
    files = collect(root)
    manifest = {
        "schema_version": 1,
        "format": "cyberwife-offline-wheelhouse",
        "python": "3.12",
        "platform": "linux-x86_64",
        "components": list(COMPONENTS),
        "file_count": len(files),
        "hardlinked_file_count": hardlinked_file_count,
        "files": files,
    }
    (root / MANIFEST_NAME).write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return manifest


def verify(root: Path) -> dict[str, object]:
    path = root / MANIFEST_NAME
    manifest = json.loads(path.read_text(encoding="utf-8"))
    expected = manifest.get("files")
    if (
        manifest.get("schema_version") != 1
        or manifest.get("format") != "cyberwife-offline-wheelhouse"
        or manifest.get("components") != list(COMPONENTS)
        or not isinstance(expected, list)
        or manifest.get("file_count") != len(expected)
    ):
        raise ValueError("invalid wheelhouse manifest schema")
    actual = collect(root)
    if expected != actual:
        raise ValueError("wheelhouse contents or SHA256 do not match manifest")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("build", "verify"))
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    manifest = build(args.root) if args.action == "build" else verify(args.root)
    print(json.dumps({"result": "PASS", "file_count": manifest["file_count"]}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
