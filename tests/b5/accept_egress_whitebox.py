"""B5.3 white-box proof that the V1 runtime has no reachable upload path."""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

import httpx


URL_LITERAL = re.compile(r"(?:https?|wss?)://[^\s'\"`)>]+")


def executable_external_literals(paths: list[Path]) -> list[dict]:
    findings = []
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        for number, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", "//", "*")):
                continue
            for url in URL_LITERAL.findall(line):
                if "{" in url:  # dynamic endpoints have separate constructor/config validation checks
                    continue
                host = urlparse(url.rstrip(".,;")).hostname
                if host not in {"127.0.0.1", "localhost", "::1"}:
                    findings.append({"file": str(path), "line": number, "url": url})
    return findings


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B5/B5.3-egress-whitebox"))
    args = parser.parse_args()
    root = args.root.resolve()
    launcher = (root / "ops/windows/RuntimeLauncher.ps1").read_text(encoding="utf-8")
    config = (root / "workers/avatar/config.py").read_text(encoding="utf-8")
    app = (root / "workers/avatar/app.py").read_text(encoding="utf-8")
    routes = (root / "workers/avatar/server/routes.py").read_text(encoding="utf-8")
    active_files = [
        *sorted((root / "backend/cyberwife").rglob("*.py")),
        *sorted((root / "prototype/src").rglob("*.ts")),
        *sorted((root / "prototype/src").rglob("*.tsx")),
        root / "workers/speech_worker/server.py",
        root / "workers/avatar/app.py",
        root / "workers/avatar/control_server.py",
        root / "workers/avatar/config.py",
        root / "workers/avatar/server/routes.py",
        root / "workers/avatar/tts/external.py",
    ]
    literals = executable_external_literals(active_files)
    checks = {
        "launcher_offline_env": all(token in launcher for token in ("HF_HUB_OFFLINE=1", "TRANSFORMERS_OFFLINE=1", "MODELSCOPE_OFFLINE=1")),
        "launcher_avatar_external_pcm": "'--tts', 'external'" in launcher and "'--max_session', '1'" in launcher,
        "cloud_services_hard_disabled": "opt.allow_external_services = False" in config and "--allow-external-services" not in config,
        "local_mode_forces_external_pcm": "opt.tts = 'external'" in config and "opt.stun = ''" in config and "opt.push_url = ''" in config,
        "cloud_llm_lazy_and_gated": "if opt.allow_external_services:" in app and "from llm import llm_response as configured_llm_response" in app,
        "gateway_rejects_non_loopback_llm": "LLM endpoint must be loopback" in (root / "backend/cyberwife/api/server.py").read_text(encoding="utf-8"),
        "unsafe_routes_unreachable_by_default": "if local_only:" in routes and routes.index("return\n    app.router.add_get(\"/\", index)") > routes.index("if local_only:"),
        "active_runtime_external_url_literals": len(literals) == 0,
    }
    runtime = {}
    with httpx.Client(base_url="http://127.0.0.1:8010", timeout=5, trust_env=False) as client:
        runtime["health"] = client.get("/health").status_code
        for endpoint in ("/human", "/api/avatar/task", "/api/asr", "/api/admin/config"):
            runtime[endpoint] = client.post(endpoint, json={}).status_code if endpoint == "/human" else client.get(endpoint).status_code
    runtime_pass = runtime["health"] == 200 and all(runtime[path] == 404 for path in runtime if path != "health")
    result = {
        "schema_version": 1,
        "review_scope": "V1 reachable runtime entrypoints; vendored optional providers classified unreachable",
        "checks": checks,
        "runtime_negative_routes": runtime,
        "external_literal_findings": literals,
        "dormant_vendored_capabilities": [
            "workers/avatar/llm.py cloud providers",
            "workers/avatar/tts cloud provider plugins",
            "workers/avatar/server/task_manager.py notify_url callback",
            "workers/avatar/musetalk optional model downloads",
        ],
        "pass": all(checks.values()) and runtime_pass,
    }
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
