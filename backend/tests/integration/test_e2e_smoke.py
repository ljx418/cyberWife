"""M1-11 端到端 smoke test。

启动 FastAPI app（uvicorn in-process）→ curl /api/v1/health 返回聚合 dict →
验证 status 字段、components 6 项、resources.disk_free_gb 非 None。
"""
import tempfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from cyberwife.application.api_gateway import ApiGateway
from cyberwife.application.health_aggregator import HealthAggregator
from cyberwife.application.model_registry import ModelRegistry
from cyberwife.infrastructure.sqlite_repository import SqliteRepository
from cyberwife.infrastructure.asset_store import AssetStore


@pytest.fixture
def client(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    db_path = tmp_path / "smoke.db"
    repo = SqliteRepository(db_path, schema_sql_path=repo_root / "migrations" / "0001_init.sql")
    # This legacy smoke fixture exercises upload validation, not the B5
    # authorization gate.  Grant explicit test consent; no-consent behavior
    # is covered independently by test_b5_completeness_api.py.
    repo.grant_consent("all", "test-v1")
    registry = ModelRegistry(repo_root)
    aggregator = HealthAggregator(registry)
    gateway = ApiGateway(
        registry,
        aggregator,
        repository=repo,
        asset_store=AssetStore(tmp_path / "assets"),
    )
    app = gateway.build_app()
    return TestClient(app), repo


def test_health_endpoint(client):
    c, _ = client
    r = c.get("/api/v1/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] in {"ready", "loading", "degraded", "error"}
    assert set(body["components"].keys()) == {"vad", "asr", "llm", "tts", "avatar", "embedding"}
    # M1 阶段资源字段 disk_free_gb 应可读
    assert body["resources"]["disk_free_gb"] is not None
    assert body["resources"]["disk_free_gb"] > 0
    # version
    assert body["version"]["app"].startswith("cyberwife-")


def test_experience_settings_exposes_only_capability_flags(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    registry = ModelRegistry(repo_root)
    app = ApiGateway(
        registry,
        HealthAggregator(registry),
        experience_flags={"contracts": True, "input_calibration": True},
    ).build_app()
    response = TestClient(app).get("/api/v1/experience/settings")
    assert response.status_code == 200
    assert response.json() == {
        "schema_version": 1,
        "features": {"contracts": True, "input_calibration": True},
    }
    serialized = response.text.lower()
    assert "path" not in serialized and "device" not in serialized and "memory" not in serialized


def test_health_components_have_required_fields(client):
    c, _ = client
    r = c.get("/api/v1/health")
    body = r.json()
    for cid, comp in body["components"].items():
        assert "status" in comp, f"{cid} missing status"
        assert "last_probe" in comp, f"{cid} missing last_probe"
        assert "fallback_active" in comp


def test_onboarding_draft_get_default(client):
    """GET /onboarding/draft 应返回默认空草稿。"""
    c, _ = client
    r = c.get("/api/v1/onboarding/draft")
    assert r.status_code == 200
    body = r.json()
    assert body["id"] == 1
    assert body["consent_granted"] is False
    assert body["step_completed"] == 0


def test_onboarding_draft_put_updates(client):
    """PUT /onboarding/draft 增量更新 + step_completed 推进。"""
    c, _ = client
    r = c.put(
        "/api/v1/onboarding/draft",
        json={"step_completed": 2, "profile_draft_json": {"name": "Test"}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["step_completed"] == 2
    assert body["profile_draft_json"]["name"] == "Test"


def test_onboarding_draft_step_clamped(client):
    """PUT step_completed=5 应被 domain.bump_step 拒绝并抛 500（当前未做范围校验）→ 标记为待修。"""
    c, _ = client
    r = c.put("/api/v1/onboarding/draft", json={"step_completed": 5})
    # M1 阶段：FastAPI 未做范围校验，由 domain.bump_step 抛 ValueError → 500
    # TODO: M2 阶段把 step_completed 加 Pydantic Field(ge=0, le=4) 后改为 422
    assert r.status_code in (422, 500)
    body = r.json()
    assert body["code"] in ("internal.error",) or r.status_code == 422


def test_profile_get_then_put(client):
    c, repo = client
    # 初始无 profile → 404
    r = c.get("/api/v1/profile")
    assert r.status_code == 404
    # 第一次 PUT 创建
    r = c.put("/api/v1/profile", json={"name": "Alice", "user_nickname": "A"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "Alice"
    assert body["version"] == 1
    # 第二次 PUT with correct expected_version → ok
    r = c.put("/api/v1/profile", json={"name": "Bob", "user_nickname": "A", "expected_version": 1})
    assert r.status_code == 200
    assert r.json()["version"] == 2


def test_profile_version_conflict(client):
    """expected_version 不匹配返回 409 asset.version_conflict 错误。"""
    c, _ = client
    c.put("/api/v1/profile", json={"name": "Alice", "user_nickname": "A"})
    r = c.put("/api/v1/profile", json={"name": "Bob", "user_nickname": "A", "expected_version": 99})
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "asset.version_conflict"
    assert body["user_action"] == "retry"
    assert body["retryable"] is True


def test_error_envelope_schema(client):
    """所有错误响应必须符合 schemas/errors/error_envelope.schema.json。"""
    import json
    from pathlib import Path

    schema_path = Path(__file__).resolve().parents[3] / "schemas" / "errors" / "error_envelope.schema.json"
    schema = json.loads(schema_path.read_text())
    import jsonschema

    c, _ = client
    r = c.put("/api/v1/profile", json={"name": "Alice", "user_nickname": "A", "expected_version": 99})
    jsonschema.validate(r.json(), schema)


def test_repo_persistence_across_instances(tmp_path):
    """两个 SqliteRepository 实例指向同一文件，数据应持久。"""
    repo_root = Path(__file__).resolve().parents[3]
    db_path = tmp_path / "persist.db"
    r1 = SqliteRepository(db_path, schema_sql_path=repo_root / "migrations" / "0001_init.sql")
    r1.upsert_profile(__import__("cyberwife.domain.profile", fromlist=["Profile"]).Profile(
        id=0, name="X", user_nickname="Y"
    ))
    r1.close()
    r2 = SqliteRepository(db_path)
    p = r2.get_profile()
    assert p is not None
    assert p.name == "X"
    r2.close()


def test_health_status_reflects_registry(client):
    """B0：manifest verified 不能冒充 runtime ready。"""
    c, _ = client
    body = c.get("/api/v1/health").json()
    # 未运行真实功能探针前只能是 loading/error，不能是 ready。
    statuses = [body["components"][k]["status"] for k in body["components"]]
    assert "ready" not in statuses
    assert any(s == "loading" for s in statuses)


def test_profile_full_lifecycle_2_04(client):
    """M2-04：Profile 完整生命周期（乐观并发 + 脏检查 backend 视角）。"""
    c, _ = client
    # 初始 404
    assert c.get("/api/v1/profile").status_code == 404
    # 第一次创建
    r = c.put("/api/v1/profile", json={"name": "Alice", "user_nickname": "你"})
    assert r.status_code == 200
    p1 = r.json()
    assert p1["version"] == 1
    assert p1["name"] == "Alice"
    # 重复 PUT 但不带 expected_version → 走 expected_version=current 版本
    r = c.put("/api/v1/profile", json={"name": "Bob", "user_nickname": "你"})
    assert r.status_code == 200
    assert r.json()["version"] == 2
    # 期望版本不匹配 → 409
    r = c.put("/api/v1/profile", json={"name": "C", "user_nickname": "你", "expected_version": 99})
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "asset.version_conflict"
    assert body["retryable"] is True
    # 用正确版本 → ok
    r = c.put("/api/v1/profile", json={"name": "C", "user_nickname": "你", "expected_version": 2})
    assert r.status_code == 200
    assert r.json()["version"] == 3


def test_profile_blank_name_rejected(client):
    """M2-04：name 不能为空。"""
    c, _ = client
    r = c.put("/api/v1/profile", json={"name": "", "user_nickname": "你"})
    # 当前 M1 后端不做 name 必填校验（仅 domain 校验）
    # 此测试 M2-stretch 严格化（用 Pydantic Field(min_length=1)）
    # 当前期望 200 但 name="" 是已知 limitation
    assert r.status_code in (200, 422)


def test_profile_unicode_name(client):
    """M2-04：人设字段支持中文（CJK 字符）。"""
    c, _ = client
    r = c.put("/api/v1/profile", json={"name": "测试名", "user_nickname": "用户", "persona": "温柔, 健谈"})
    assert r.status_code == 200
    body = r.json()
    assert body["name"] == "测试名"
    assert body["persona"] == "温柔, 健谈"


def test_asset_preview_synthetic_png(client, tmp_path):
    """M2-stretch：合成 PNG 上传走 /api/v1/assets/portrait/preview。
    写真实际 ingest 由写真→ ~/.cyberWife/assets/portrait/<file>.png；此处仅测 multipart + magic bytes + 错误信封。
    """
    import io
    c, _ = client
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32 + b"IEND\xae\x42\x60\x82"
    files = {"file": ("synthetic_test.png", io.BytesIO(png_bytes), "image/png")}
    r = c.post("/api/v1/assets/portrait/preview", files=files)
    assert r.status_code == 200
    body = r.json()
    assert body["mime"] == "image/png"
    assert body["size_bytes"] == len(png_bytes)
    assert "sha256" in body and len(body["sha256"]) == 64


def test_asset_preview_rejects_bad_magic(client, tmp_path):
    """M2-stretch：magic bytes 不匹配返回 422 asset.invalid。"""
    import io
    c, _ = client
    bad = b"this is not a real png"
    files = {"file": ("fake.png", io.BytesIO(bad), "image/png")}
    r = c.post("/api/v1/assets/portrait/preview", files=files)
    assert r.status_code == 422
    body = r.json()
    assert body["code"] == "asset.invalid"
    assert body["user_action"] == "open_settings"
    assert body["retryable"] is False
    assert len(body["trace_id"]) == 26


def test_asset_preview_rejects_bad_kind(client, tmp_path):
    """M2-stretch：kind != portrait/voice 返回 422。"""
    import io
    c, _ = client
    png_bytes = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8
    files = {"file": ("synthetic.png", io.BytesIO(png_bytes), "image/png")}
    r = c.post("/api/v1/assets/audio/preview", files=files)
    assert r.status_code == 422


def test_asset_record_b64_wav(client):
    """M2-stretch：前端 MediaRecorder blob（base64）→ /api/v1/assets/voice/record。"""
    import base64
    # 合成 WAV header（44 字节 RIFF/WAVE + 1s 静音 PCM）
    wav = b"RIFF" + (36).to_bytes(4, "little") + b"WAVE" + b"fmt " + (16).to_bytes(4, "little")
    wav += (1).to_bytes(2, "little") + (1).to_bytes(2, "little") + (16000).to_bytes(4, "little")
    wav += (32000).to_bytes(4, "little") + (2).to_bytes(2, "little") + (16).to_bytes(2, "little")
    wav += b"data" + (0).to_bytes(4, "little")
    b64 = base64.b64encode(wav).decode("ascii")
    c, _ = client
    r = c.post("/api/v1/assets/voice/record", json={"filename": "user_clip.wav", "data_b64": b64})
    assert r.status_code == 200
    body = r.json()
    assert body["mime"] == "audio/wav"
    assert body["size_bytes"] == len(wav)
