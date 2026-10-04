import json
from pathlib import Path


def test_application_heartbeat_contract_is_versioned_and_non_sensitive():
    # Keep this contract test dependency-light: routes.py imports the full
    # LiveTalking stack, while this check validates the exact wire shape used
    # by that route and documented in implementation-contracts.md.
    source = (Path(__file__).parents[1] / "server" / "routes.py").read_text(encoding="utf-8")
    assert '"type": "avatar.heartbeat"' in source
    assert '"version": 1' in source
    assert "AVATAR_HEARTBEAT_INTERVAL_SECONDS = 0.5" in source
    assert "asyncio.wait_for" in source


def test_heartbeat_json_shape_has_no_user_payload():
    # Import after the lightweight source guard only when the Avatar runtime
    # dependencies are available (the production test environment has them).
    try:
        from server.routes import avatar_heartbeat
    except (ImportError, ModuleNotFoundError) as error:
        import pytest
        pytest.skip(f"Avatar runtime dependency unavailable: {error}")

    payload = avatar_heartbeat("session-contract", monotonic_ms=1234)
    assert payload == {
        "type": "avatar.heartbeat",
        "version": 1,
        "session_id": "session-contract",
        "monotonic_ms": 1234,
    }
    assert not ({"text", "audio", "path", "model", "avatar_id"} & payload.keys())
    json.dumps(payload)
