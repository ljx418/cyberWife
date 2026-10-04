from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx


ROOT = Path(__file__).resolve().parents[2]


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_ready(base: str, process: subprocess.Popen) -> None:
    for _ in range(100):
        if process.poll() is not None:
            raise RuntimeError("isolated onboarding server exited")
        try:
            if httpx.get(f"{base}/api/v1/health", timeout=1, trust_env=False).status_code == 200:
                return
        except Exception:
            pass
        time.sleep(0.1)
    raise RuntimeError("isolated onboarding server timeout")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B5/B5.4B-onboarding"))
    parser.add_argument("--cycles", type=int, default=5)
    args = parser.parse_args()
    args.evidence.mkdir(parents=True, exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(prefix="cw-b54b-") as temporary:
        area = Path(temporary)
        for cycle in range(1, args.cycles + 1):
            port = free_port()
            db = area / f"cycle-{cycle}.db"
            assets = area / f"assets-{cycle}"
            env = {**os.environ, "PYTHONPATH": f"{ROOT / 'backend'}:{ROOT}"}
            process = subprocess.Popen(
                [sys.executable, "-m", "tests.b5.completeness_server", "--db", str(db), "--assets", str(assets), "--port", str(port)],
                cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
            output = args.evidence / f"cycle-{cycle}.json"
            try:
                base = f"http://127.0.0.1:{port}"
                wait_ready(base, process)
                completed = subprocess.run(
                    ["node", "tests/b5/accept_onboarding_ui.mjs", str(output), base,
                     str(ROOT / "docs/review/assets/baseline/current-default-1920.png"),
                     str(ROOT / "audit/tts_nonstreaming.wav")],
                    cwd=ROOT, env=env, capture_output=True, text=True, timeout=120,
                )
                row = json.loads(output.read_text(encoding="utf-8")) if output.exists() else {"pass": False, "error": completed.stderr[-2000:]}
                row["cycle"] = cycle
                row["exit_code"] = completed.returncode
                rows.append(row)
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill(); process.wait(timeout=5)
    summary = {
        "schema_version": 1,
        "evidence_level": "five_isolated_windows_chrome_onboarding_cycles",
        "cycles": args.cycles,
        "passed": sum(1 for row in rows if row.get("pass")),
        "rows": rows,
    }
    summary["pass"] = summary["passed"] == args.cycles
    (args.evidence / "result.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    raise SystemExit(0 if summary["pass"] else 2)


if __name__ == "__main__":
    main()
