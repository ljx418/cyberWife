from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]
PNG = b"\x89PNG\r\n\x1a\n" + b"b5-real-http-portrait"
WAV = b"RIFF" + b"\x00" * 40


def wait_ready(base, process):
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("completeness server exited")
        try:
            if httpx.get(f"{base}/api/v1/health", timeout=1, trust_env=False).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(.1)
    raise RuntimeError("completeness server timeout")


def start_server(db, assets, port):
    env = {**os.environ, "PYTHONPATH": f"{ROOT / 'backend'}:{ROOT}"}
    process = subprocess.Popen(
        [sys.executable, "-m", "tests.b5.completeness_server", "--db", str(db), "--assets", str(assets), "--port", str(port)],
        cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
    )
    wait_ready(f"http://127.0.0.1:{port}", process)
    return process


def stop(process):
    process.terminate()
    try: process.wait(10)
    except subprocess.TimeoutExpired:
        process.kill(); process.wait(5)


def run(args):
    args.evidence.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cw-b5-ac00-") as temporary:
        area = Path(temporary); db = area / "complete.db"; assets = area / "assets"
        base = f"http://127.0.0.1:{args.port}"
        process = start_server(db, assets, args.port)
        client = httpx.Client(base_url=base, timeout=10, trust_env=False)
        try:
            blocked_upload = client.post("/api/v1/assets/portrait/preview", files={"file": ("blocked.png", PNG)}).status_code
            client.post("/api/v1/consents", json={"scope": "all", "policy_version": "v1"}).raise_for_status()
            portrait1 = client.post("/api/v1/assets/portrait/preview", files={"file": ("one.png", PNG)}).json()
            portrait2 = client.post("/api/v1/assets/portrait/preview", files={"file": ("two.png", PNG + b"2")}).json()
            voice1 = client.post("/api/v1/assets/voice/preview", files={"file": ("one.wav", WAV)}).json()
            voice2 = client.post("/api/v1/assets/voice/preview", files={"file": ("two.wav", WAV + b"2")}).json()
            for item in (portrait1, voice1): client.post(f"/api/v1/assets/{item['id']}/activate").raise_for_status()
            for item in (portrait2, voice2): client.post(f"/api/v1/assets/{item['id']}/activate").raise_for_status()
            restored = {
                kind: client.post(f"/api/v1/assets/{kind}/restore").json()["id"]
                for kind in ("portrait", "voice")
            }
            profile_payload = {"name": "小雅", "user_nickname": "阿林", "persona": "温柔自然", "relationship_context": "伴侣", "example_dialogue": "我陪你。", "expected_version": 0}
            profile1 = client.put("/api/v1/profile", json=profile_payload).json()
            profile2 = client.put("/api/v1/profile", json={**profile_payload, "persona": "温柔自然会倾听", "expected_version": 1}).json()
            stale_status = client.put("/api/v1/profile", json={**profile_payload, "expected_version": 1}).status_code
            ui = subprocess.run(
                ["node", "tests/b5/accept_completeness_ui.mjs", str(args.evidence / "ui.json"), base],
                cwd=ROOT, capture_output=True, text=True, timeout=60,
            )
            ui_result = json.loads((args.evidence / "ui.json").read_text(encoding="utf-8")) if (args.evidence / "ui.json").exists() else {"pass": False, "stderr": ui.stderr}
            revoke = client.delete("/api/v1/consents/all").json()
            blocked_activate = client.post(f"/api/v1/assets/{portrait2['id']}/activate").status_code
            active_after_revoke = sum(item["is_active"] for item in client.get("/api/v1/assets/portrait").json()["items"])
            audits = client.get("/api/v1/audit").json()["items"]
        finally:
            client.close(); stop(process)
        process = start_server(db, assets, args.port)
        try:
            profile_after_restart = httpx.get(f"{base}/api/v1/profile", timeout=5, trust_env=False).json()
        finally:
            stop(process)
        result = {
            "schema_version": 1, "evidence_level": "real_http_sqlite_files_windows_chrome",
            "blocked_upload_status": blocked_upload,
            "asset_versions": {"portrait": [portrait1["id"], portrait2["id"]], "voice": [voice1["id"], voice2["id"]]},
            "restored": restored, "profile_versions": [profile1["version"], profile2["version"]],
            "stale_profile_status": stale_status, "revoke": revoke,
            "blocked_activate_status": blocked_activate, "active_after_revoke": active_after_revoke,
            "profile_after_restart": profile_after_restart, "audit_actions": sorted({item["action"] for item in audits}),
            "ui": ui_result,
        }
        result["pass"] = all((
            blocked_upload == 403, restored == {"portrait": portrait1["id"], "voice": voice1["id"]},
            result["profile_versions"] == [1, 2], stale_status == 409,
            profile_after_restart.get("version") == 2 and profile_after_restart.get("persona") == "温柔自然会倾听",
            blocked_activate == 403, active_after_revoke == 0,
            {"consent.granted", "consent.revoked", "asset.previewed", "asset.activated", "asset.rollback"}.issubset(result["audit_actions"]),
            ui_result.get("pass") is True,
        ))
        (args.evidence / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--port", type=int, default=7862)
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B5/B5-AC00"))
    args = parser.parse_args()
    if not args.real: raise SystemExit(3)
    raise SystemExit(0 if run(args)["pass"] else 2)


if __name__ == "__main__": main()
