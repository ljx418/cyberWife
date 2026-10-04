import pytest

from cyberwife.infrastructure.runtime_metrics import RuntimeMetrics


def test_runtime_metrics_only_completes_after_browser_confirmation():
    clock = iter((10.0, 10.4, 11.2))
    metrics = RuntimeMetrics(max_samples=4, clock=lambda: next(clock))
    metrics.begin(
        trace_id="01HZX5K2C3D4E5F6G7H8J9K0A1",
        session_id=7,
        turn_id=3,
        generation=2,
        bucket="normal",
        asr_final_wall_ms=1_000.0,
    )
    metrics.mark("01HZX5K2C3D4E5F6G7H8J9K0A1", "llm_playable")
    metrics.mark("01HZX5K2C3D4E5F6G7H8J9K0A1", "tts_first_packet")

    before = metrics.snapshot()
    assert before["buckets"]["normal"]["complete_count"] == 0
    assert before["buckets"]["normal"]["p50_ms"] is None

    assert metrics.confirm_playback(
        trace_id="01HZX5K2C3D4E5F6G7H8J9K0A1",
        session_id=7,
        turn_id=3,
        generation=2,
        asr_to_playback_ms=1_500.0,
        browser_first_non_silent_wall_ms=2_500.0,
    )
    after = metrics.snapshot()
    sample = after["samples"][0]
    assert after["buckets"]["normal"]["complete_count"] == 1
    assert after["buckets"]["normal"]["p50_ms"] == 1_500.0
    assert sample["asr_to_llm_playable_ms"] == 400.0
    assert sample["llm_playable_to_tts_first_packet_ms"] == 800.0
    assert sample["tts_first_packet_to_browser_ms"] == 300.0
    assert "text" not in sample


def test_runtime_metrics_rejects_duplicate_wrong_identity_and_bad_values():
    metrics = RuntimeMetrics(clock=lambda: 1.0)
    trace_id = "01HZX5K2C3D4E5F6G7H8J9K0A2"
    metrics.begin(
        trace_id=trace_id,
        session_id=1,
        turn_id=1,
        generation=1,
        bucket="normal",
        asr_final_wall_ms=100.0,
    )
    metrics.mark(trace_id, "llm_playable", at=1.1)
    metrics.mark(trace_id, "tts_first_packet", at=1.2)
    assert not metrics.confirm_playback(
        trace_id=trace_id,
        session_id=1,
        turn_id=1,
        generation=0,
        asr_to_playback_ms=300.0,
        browser_first_non_silent_wall_ms=400.0,
    )
    assert not metrics.confirm_playback(
        trace_id=trace_id,
        session_id=1,
        turn_id=1,
        generation=1,
        asr_to_playback_ms=-1.0,
        browser_first_non_silent_wall_ms=400.0,
    )
    assert metrics.confirm_playback(
        trace_id=trace_id,
        session_id=1,
        turn_id=1,
        generation=1,
        asr_to_playback_ms=300.0,
        browser_first_non_silent_wall_ms=400.0,
    )
    assert not metrics.confirm_playback(
        trace_id=trace_id,
        session_id=1,
        turn_id=1,
        generation=1,
        asr_to_playback_ms=301.0,
        browser_first_non_silent_wall_ms=401.0,
    )


def test_runtime_metrics_buckets_are_independent_and_bounded():
    metrics = RuntimeMetrics(max_samples=2, clock=lambda: 1.0)
    for index, bucket in enumerate(("normal", "cache-hit", "config-invalid"), 1):
        trace_id = f"01HZX5K2C3D4E5F6G7H8J9K{index:02d}"
        metrics.begin(
            trace_id=trace_id,
            session_id=1,
            turn_id=index,
            generation=index,
            bucket=bucket,
            asr_final_wall_ms=100.0,
        )
    snapshot = metrics.snapshot()
    assert len(snapshot["samples"]) == 2
    assert set(snapshot["buckets"]) == {"normal", "cache-hit", "config-invalid"}
    assert snapshot["buckets"]["normal"]["complete_count"] == 0


def test_runtime_metrics_rejects_unknown_stage_and_bucket():
    metrics = RuntimeMetrics()
    with pytest.raises(ValueError, match="bucket"):
        metrics.begin(
            trace_id="01HZX5K2C3D4E5F6G7H8J9K0A3",
            session_id=1,
            turn_id=1,
            generation=1,
            bucket="other",
            asr_final_wall_ms=1.0,
        )
