"""Combine consecutive browser probe runs without changing their raw evidence."""
from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path


def percentile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower, upper = math.floor(position), math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    return round(ordered[lower] * (upper - position) + ordered[upper] * (position - lower), 3)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    parser.add_argument("inputs", nargs="+", type=Path)
    args = parser.parse_args()
    rows = []
    for directory in args.inputs:
        rows.extend(json.loads((directory / "samples.json").read_text(encoding="utf-8")))
    for index, row in enumerate(rows, 1):
        row["sample_index"] = index
    args.output.mkdir(parents=True, exist_ok=True)
    totals = [float(row["asr_to_browser_first_non_silent_ms"]) for row in rows]
    metrics = {
        "schema_version": 1,
        "bucket": rows[0]["bucket"] if rows else None,
        "sample_count": len(rows),
        "complete_count": sum(bool(row["complete"]) for row in rows),
        "p50_ms": percentile(totals, 0.5),
        "p95_ms": percentile(totals, 0.95),
        "cache_hit_count": sum(row["bucket"] == "cache-hit" for row in rows),
        "config_invalid_count": sum(row["bucket"] == "config-invalid" for row in rows),
        "source_runs": [str(path) for path in args.inputs],
    }
    (args.output / "samples.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if rows:
        with (args.output / "samples.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)


if __name__ == "__main__":
    main()
