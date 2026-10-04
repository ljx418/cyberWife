"""Bounded, privacy-safe runtime latency measurements.

The collector deliberately keeps only numeric timing data and opaque turn
identifiers.  Conversation text, audio, persona data, and filesystem paths do
not enter this module.
"""
from __future__ import annotations

import math
import threading
import time
from collections.abc import Callable
from typing import Any


_BUCKETS = ("normal", "cache-hit", "config-invalid")
_SERVER_STAGES = ("llm_playable", "tts_first_packet")


def _round_ms(value: float | None) -> float | None:
    return None if value is None else round(value, 3)


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 3)
    position = (len(ordered) - 1) * percentile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return round(ordered[lower], 3)
    weight = position - lower
    return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 3)


class RuntimeMetrics:
    """Collect per-turn stage timing without persisting user content."""

    def __init__(
        self,
        *,
        max_samples: int = 512,
        clock: Callable[[], float] = time.perf_counter,
    ) -> None:
        if max_samples < 1:
            raise ValueError("max_samples must be positive")
        self._max_samples = max_samples
        self._clock = clock
        self._lock = threading.Lock()
        self._samples: list[dict[str, Any]] = []
        self._by_trace: dict[str, dict[str, Any]] = {}

    def begin(
        self,
        *,
        trace_id: str,
        session_id: int,
        turn_id: int,
        generation: int,
        bucket: str,
        asr_final_wall_ms: float,
        at: float | None = None,
    ) -> None:
        if bucket not in _BUCKETS:
            raise ValueError(f"unsupported bucket: {bucket}")
        started = self._clock() if at is None else float(at)
        sample = {
            "trace_id": str(trace_id),
            "session_id": int(session_id),
            "turn_id": int(turn_id),
            "generation": int(generation),
            "bucket": bucket,
            "asr_final_ms": 0.0,
            "llm_playable_ms": None,
            "tts_first_packet_ms": None,
            "browser_first_non_silent_ms": None,
            "asr_to_llm_playable_ms": None,
            "llm_playable_to_tts_first_packet_ms": None,
            "tts_first_packet_to_browser_ms": None,
            "asr_to_browser_first_non_silent_ms": None,
            "complete": False,
            "_started_at": started,
            "_asr_final_wall_ms": float(asr_final_wall_ms),
            "_confirmed": False,
        }
        with self._lock:
            previous = self._by_trace.pop(str(trace_id), None)
            if previous is not None and previous in self._samples:
                self._samples.remove(previous)
            while len(self._samples) >= self._max_samples:
                evicted = self._samples.pop(0)
                self._by_trace.pop(evicted["trace_id"], None)
            self._samples.append(sample)
            self._by_trace[str(trace_id)] = sample

    def mark(self, trace_id: str, stage: str, *, at: float | None = None) -> bool:
        if stage not in _SERVER_STAGES:
            raise ValueError(f"unsupported stage: {stage}")
        observed = self._clock() if at is None else float(at)
        with self._lock:
            sample = self._by_trace.get(str(trace_id))
            if sample is None:
                return False
            field = f"{stage}_ms"
            if sample[field] is not None:
                return False
            elapsed_ms = max(0.0, (observed - sample["_started_at"]) * 1000)
            if stage == "tts_first_packet":
                llm_ms = sample["llm_playable_ms"]
                if llm_ms is None or elapsed_ms < llm_ms:
                    return False
            sample[field] = _round_ms(elapsed_ms)
            self._derive(sample)
            return True

    def confirm_playback(
        self,
        *,
        trace_id: str,
        session_id: int,
        turn_id: int,
        generation: int,
        asr_to_playback_ms: float,
        browser_first_non_silent_wall_ms: float,
    ) -> bool:
        try:
            elapsed = float(asr_to_playback_ms)
            browser_wall = float(browser_first_non_silent_wall_ms)
        except (TypeError, ValueError):
            return False
        if not math.isfinite(elapsed) or not math.isfinite(browser_wall):
            return False
        if elapsed < 0 or elapsed > 600_000 or browser_wall <= 0:
            return False
        with self._lock:
            sample = self._by_trace.get(str(trace_id))
            if sample is None or sample["_confirmed"]:
                return False
            if (
                sample["session_id"] != int(session_id)
                or sample["turn_id"] != int(turn_id)
                or sample["generation"] != int(generation)
            ):
                return False
            tts_ms = sample["tts_first_packet_ms"]
            if tts_ms is None or elapsed < tts_ms:
                return False
            sample["browser_first_non_silent_ms"] = _round_ms(elapsed)
            sample["_browser_first_non_silent_wall_ms"] = browser_wall
            sample["_confirmed"] = True
            sample["complete"] = True
            self._derive(sample)
            return True

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            public = [self._public(sample) for sample in self._samples]
        buckets: dict[str, dict[str, Any]] = {}
        for bucket in _BUCKETS:
            selected = [row for row in public if row["bucket"] == bucket]
            complete = [
                float(row["asr_to_browser_first_non_silent_ms"])
                for row in selected
                if row["complete"]
            ]
            buckets[bucket] = {
                "sample_count": len(selected),
                "complete_count": len(complete),
                "p50_ms": _percentile(complete, 0.50),
                "p95_ms": _percentile(complete, 0.95),
            }
        return {
            "schema_version": 1,
            "max_samples": self._max_samples,
            "buckets": buckets,
            "samples": public,
        }

    @staticmethod
    def _derive(sample: dict[str, Any]) -> None:
        llm_ms = sample["llm_playable_ms"]
        tts_ms = sample["tts_first_packet_ms"]
        browser_ms = sample["browser_first_non_silent_ms"]
        sample["asr_to_llm_playable_ms"] = _round_ms(llm_ms)
        if llm_ms is not None and tts_ms is not None:
            sample["llm_playable_to_tts_first_packet_ms"] = _round_ms(tts_ms - llm_ms)
        if tts_ms is not None and browser_ms is not None:
            sample["tts_first_packet_to_browser_ms"] = _round_ms(browser_ms - tts_ms)
        sample["asr_to_browser_first_non_silent_ms"] = _round_ms(browser_ms)

    @staticmethod
    def _public(sample: dict[str, Any]) -> dict[str, Any]:
        return {key: value for key, value in sample.items() if not key.startswith("_")}
