"""Privacy-safe V2-X contract evidence summaries."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from cyberwife.domain.source_pack import SourcePackManifest


def contract_evidence(flags: dict[str, bool], manifest: SourcePackManifest | None) -> dict[str, Any]:
    manifest_hash = None
    counts = {"sources": 0, "appearances": 0, "scenes": 0, "renditions": 0}
    revision = None
    if manifest is not None:
        public = manifest.to_dict()
        encoded = json.dumps(public, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
        manifest_hash = hashlib.sha256(encoded).hexdigest()
        revision = manifest.revision
        counts = {key: len(public[key]) for key in counts}
    return {
        "schema_version": 1,
        "flags": {key: bool(flags[key]) for key in sorted(flags)},
        "manifest": {"present": manifest is not None, "revision": revision, "sha256": manifest_hash, **counts},
    }
