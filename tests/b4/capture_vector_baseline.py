"""Capture the pre-B4 VectorIndex fallback and transaction behavior.

This is a one-time migration baseline, not a target-state product test.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

from cyberwife.infrastructure.vector_index import VectorIndex


class TrackingConnection(sqlite3.Connection):
    commits: int

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.commits = 0

    def commit(self) -> None:
        self.commits += 1
        super().commit()


def capture() -> dict:
    with patch.dict(sys.modules, {"sqlite_vec": None}):
        fallback_conn = sqlite3.connect(":memory:")
        fallback = VectorIndex(fallback_conn, dim=2)
        fallback.ensure_schema()
        fallback.insert(7, [1.0, 0.0])
        fallback_result = fallback.search([1.0, 0.0])

    tracked = sqlite3.connect(":memory:", factory=TrackingConnection)
    live = VectorIndex(tracked, dim=2)
    live.ensure_schema()
    before = tracked.commits
    if live.using_sqlite_vec:
        live.insert(11, [0.0, 1.0])
        after_insert = tracked.commits
        live.delete(11)
        after_delete = tracked.commits
    else:
        after_insert = before
        after_delete = before

    return {
        "schema_version": 1,
        "purpose": "pre_B4_migration_baseline_only",
        "memory_fallback": {
            "activated": not fallback.using_sqlite_vec,
            "accepted_write": fallback.count() == 1,
            "search_result": fallback_result,
        },
        "sqlite_vec": {
            "available": live.using_sqlite_vec,
            "commits_before": before,
            "commits_after_insert": after_insert,
            "commits_after_delete": after_delete,
            "index_commits_internally": live.using_sqlite_vec and after_delete - before == 2,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    result = capture()
    result["baseline_captured"] = bool(
        result["memory_fallback"]["activated"]
        and result["memory_fallback"]["accepted_write"]
        and result["sqlite_vec"]["available"]
        and result["sqlite_vec"]["index_commits_internally"]
    )
    path = Path(args.output)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["baseline_captured"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
