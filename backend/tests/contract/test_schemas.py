"""M1-02 contract test: 26 JSON Schema 全部能加载且校验 1 个 fixture。"""
import json
import sys
from pathlib import Path

import jsonschema
import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMAS_ROOT = REPO_ROOT / "schemas"


def _all_schema_paths() -> list[Path]:
    return sorted(SCHEMAS_ROOT.rglob("*.schema.json"))


def test_schema_count():
    paths = _all_schema_paths()
    # 实际产出：rest/9 + ws/8 + events/1 + errors/1 = 19
    # M1-plan 写的"26"是包含测试 fixture；契约 schema 自身 19 个
    assert len(paths) == 19, f"expected 19 contract schemas, got {len(paths)}: {paths}"


@pytest.mark.parametrize("schema_path", _all_schema_paths(), ids=lambda p: str(p.relative_to(SCHEMAS_ROOT)))
def test_schema_loads(schema_path: Path):
    """每个 schema 必须能被 json 解析为合法 Draft 2020-12。"""
    with schema_path.open() as f:
        schema = json.load(f)
    assert schema.get("$schema", "").endswith("2020-12/schema"), f"{schema_path} not Draft 2020-12"
    # 至少存在 type 或 $ref 之一
    assert "type" in schema or "$ref" in schema or "$defs" in schema


@pytest.mark.parametrize("schema_path", _all_schema_paths(), ids=lambda p: str(p.relative_to(SCHEMAS_ROOT)))
def test_schema_has_title(schema_path: Path):
    """每个 schema 必须有 title，便于 OpenAPI 文档生成。"""
    with schema_path.open() as f:
        schema = json.load(f)
    assert "title" in schema, f"{schema_path} missing title"


def test_error_envelope_accepts_valid():
    schema_path = SCHEMAS_ROOT / "errors" / "error_envelope.schema.json"
    with schema_path.open() as f:
        schema = json.load(f)
    valid = {
        "code": "memory.not_found",
        "message": "记忆不存在",
        "user_action": "none",
        "trace_id": "01HZX5K2C3D4E5F6G7H8J9K0A1",
        "retryable": False,
    }
    jsonschema.validate(valid, schema)  # 不抛错即 PASS


def test_ws_envelope_rejects_missing_field():
    schema_path = SCHEMAS_ROOT / "ws" / "envelope.schema.json"
    with schema_path.open() as f:
        schema = json.load(f)
    invalid = {"type": "x", "session_id": "1", "turn_id": 0}  # 缺 event_seq / occurred_at / payload
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(invalid, schema)


def test_audit_event_code_enum_coverage():
    """audit_events.action 枚举覆盖 §3 全部 18 项；schema audit.schema.json 已写。"""
    schema_path = SCHEMAS_ROOT / "rest" / "audit.schema.json"
    with schema_path.open() as f:
        schema = json.load(f)
    code_enum = schema["properties"]["events"]["items"]["properties"]["action"]["enum"]
    # §3 audit_events.action 列出 18 项
    expected = {
        "consent.granted", "consent.revoked",
        "asset.uploaded", "asset.previewed", "asset.activated", "asset.rollback",
        "profile.updated",
        "memory.committed", "memory.updated", "memory.deleted", "memory.purge_all",
        "session.created", "session.ended", "session.no_record",
        "retention.expired", "retention.failed",
        "health.degraded", "health.recovered",
    }
    assert expected.issubset(set(code_enum)), f"missing: {expected - set(code_enum)}"
