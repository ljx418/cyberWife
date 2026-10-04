"""B5.3/AC-13: real-model local-boundary and privacy acceptance.

The runner stores hashes and aggregate facts only. Raw microphone PCM and
transcripts stay in memory (or /dev/shm for the reused B3 driver) and are
removed before the result is written.
"""
from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import io
import json
import os
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import httpx

from cyberwife.domain.memory import MemoryRecord
from cyberwife.infrastructure.sqlite_memory_repository import SqliteMemoryRepository
from cyberwife.infrastructure.sqlite_repository import SqliteRepository
from tests.b3.accept_turns import run as run_real_turns


PROJECT_MARKERS = (
    "cyberwife.api.server", "workers.speech_worker.server", "app.py --bind 127.0.0.1",
    "llama-server", "vite.js --host 127.0.0.1", "/vite --host 127.0.0.1",
)
AUDIO_SUFFIXES = {".wav", ".mp3", ".ogg", ".flac", ".pcm", ".webm", ".m4a"}


def sha(value: str | bytes) -> str:
    if isinstance(value, str):
        value = value.encode("utf-8")
    return hashlib.sha256(value).hexdigest()


def audio_inventory(roots: list[Path]) -> dict[str, int]:
    result: dict[str, int] = {}
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES:
                result[sha(str(path.resolve()))] = path.stat().st_size
    return result


def project_linux_pids() -> dict[int, str]:
    rows: dict[int, str] = {}
    for item in Path("/proc").iterdir():
        if not item.name.isdigit():
            continue
        try:
            command = (item / "cmdline").read_bytes().replace(b"\0", b" ").decode("utf-8", "replace")
        except (OSError, PermissionError):
            continue
        if any(marker in command for marker in PROJECT_MARKERS):
            rows[int(item.name)] = command
    return rows


def is_loopback(endpoint: str) -> bool:
    endpoint = endpoint.strip("[]")
    host = endpoint.rsplit(":", 1)[0].strip("[]") if ":" in endpoint else endpoint
    return host in {"127.0.0.1", "::1", "localhost", "*"} or host.startswith("127.")


def linux_sockets() -> tuple[list[dict], list[dict]]:
    pids = project_linux_pids()
    listeners: list[dict] = []
    external: list[dict] = []
    for mode, target in (("-Hlntp", listeners), ("-Hntp state established", external)):
        completed = subprocess.run(f"ss {mode}", shell=True, capture_output=True, text=True, timeout=5)
        for line in completed.stdout.splitlines():
            matched = re.search(r'pid=(\d+)', line)
            if not matched or int(matched.group(1)) not in pids:
                continue
            fields = line.split()
            # `ss state established` omits the State column while `ss -l`
            # includes it. Keep address columns explicit or the Process field
            # is easily misclassified as a public peer.
            offset = 3 if target is listeners else 2
            local = fields[offset] if len(fields) > offset + 1 else ""
            peer = fields[offset + 1] if len(fields) > offset + 1 else ""
            row = {"pid": int(matched.group(1)), "local": local, "peer": peer}
            if target is listeners or not is_loopback(peer):
                target.append(row)
    return listeners, external


def windows_sockets() -> tuple[list[dict], list[dict]]:
    script = r'''$processes = @{}; Get-CimInstance Win32_Process -ErrorAction SilentlyContinue | ForEach-Object { $processes[[int]$_.ProcessId] = [string]$_.CommandLine }
    $r = foreach ($c in Get-NetTCPConnection -ErrorAction SilentlyContinue) {
      $cmd = $processes[[int]$c.OwningProcess]
      if ($cmd -match 'llama-server|RuntimeLauncher|cyberWife') {
        [pscustomobject]@{state=[string]$c.State;local="$($c.LocalAddress):$($c.LocalPort)";remote="$($c.RemoteAddress):$($c.RemotePort)";pid=$c.OwningProcess}
      }
    }; @($r) | ConvertTo-Json -Compress'''
    completed = subprocess.run(["powershell.exe", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=30)
    raw = completed.stdout.strip().lstrip("\ufeff")
    if not raw:
        return [], []
    value = json.loads(raw)
    rows = value if isinstance(value, list) else [value]
    listeners = [row for row in rows if str(row.get("state", "")).lower() == "listen"]
    external = [row for row in rows if str(row.get("state", "")).lower() == "established" and not is_loopback(str(row.get("remote", "")))]
    return listeners, external


def offline_environment() -> dict:
    rows = []
    required = {"HF_HUB_OFFLINE": "1", "TRANSFORMERS_OFFLINE": "1"}
    for pid, command in project_linux_pids().items():
        if not any(marker in command for marker in ("cyberwife.api.server", "workers.speech_worker.server", "app.py --bind")):
            continue
        try:
            env = dict(item.split("=", 1) for item in (Path(f"/proc/{pid}/environ").read_bytes().decode("utf-8", "replace").split("\0")) if "=" in item)
        except (OSError, PermissionError):
            env = {}
        rows.append({"pid": pid, "role_hash": sha(command)[:16], "offline": all(env.get(k) == v for k, v in required.items())})
    return {"processes": rows, "pass": len(rows) >= 3 and all(row["offline"] for row in rows)}


def scan_logs(log_roots: list[Path], needles: list[str]) -> dict:
    hits = []
    for root in log_roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.stat().st_size > 20 * 1024 * 1024:
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for index, needle in enumerate(needles):
                if needle and needle in text:
                    hits.append({"path_hash": sha(str(path.resolve()))[:16], "rule": f"sensitive-{index}"})
    return {"files_scanned": sum(1 for root in log_roots if root.exists() for path in root.rglob("*") if path.is_file()), "hits": hits}


async def sample_network(stop: asyncio.Event, snapshots: list[dict]) -> None:
    while not stop.is_set():
        listeners, external = await asyncio.to_thread(linux_sockets)
        snapshots.append({"listeners": listeners, "external": external})
        try:
            await asyncio.wait_for(stop.wait(), timeout=0.25)
        except asyncio.TimeoutError:
            pass


async def memory_api_flow(http_base: str, db: Path) -> dict:
    marker = f"B5PRIVACY-{os.urandom(8).hex()}"
    async with httpx.AsyncClient(base_url=http_base, timeout=120, trust_env=False) as client:
        embedded = (await client.post("http://127.0.0.1:8091/api/v1/embeddings", json={"texts": [marker]})).json()["vectors"][0]
        repo = SqliteRepository(db)
        memory_repo = SqliteMemoryRepository(repo.conn, repo.lock)
        now = datetime.now(timezone.utc)
        memory_id = memory_repo.upsert(MemoryRecord(id=0, source_session_id=None, content=marker, confidence=1.0, created_at=now, updated_at=now), embedded)
        try:
            listed = (await client.get("/api/v1/memories")).json()["items"]
            edited_text = marker + "-EDITED"
            edited = (await client.patch(f"/api/v1/memories/{memory_id}", json={"content": edited_text})).json()
            searched = (await client.get("/api/v1/memories", params={"q": edited_text})).json()["items"]
            deleted = (await client.delete(f"/api/v1/memories/{memory_id}")).json()
            after = (await client.get("/api/v1/memories")).json()["items"]
        finally:
            # Idempotent cleanup if an HTTP assertion failed.
            memory_repo.delete(memory_id)
            repo.close()
    return {
        "marker_sha256": sha(marker), "listed": any(int(row["id"]) == memory_id for row in listed),
        "edited": edited.get("content") == edited_text,
        "searched": any(int(row["id"]) == memory_id for row in searched),
        "deleted": deleted.get("deleted") is True,
        "absent_after": all(int(row["id"]) != memory_id for row in after),
    }


async def execute(args) -> dict:
    audio_roots = [Path("/home/administrator/.cyberWife"), args.workspace / "runtime", args.workspace / "data"]
    before_audio = audio_inventory(audio_roots)
    samples: list[dict] = []
    stop = asyncio.Event()
    sampler = asyncio.create_task(sample_network(stop, samples))
    with tempfile.TemporaryDirectory(prefix="cw-b5-privacy-", dir="/dev/shm") as temp:
        turn_args = SimpleNamespace(
            audio=args.audio, turns=5, expected="今天天气不错，我想和你聊聊天",
            http_base=args.http_base, ws_base=args.ws_base, timeout=120.0, evidence=Path(temp),
        )
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            turn_summary, turn_rows, avatar = await run_real_turns(turn_args)
    memory = await memory_api_flow(args.http_base, args.db)
    stop.set()
    await sampler
    linux_listeners, linux_external_now = linux_sockets()
    windows_listeners, windows_external = windows_sockets()
    after_audio = audio_inventory(audio_roots)
    transcript_hashes = [sha(str(row.get("transcript", ""))) for row in turn_rows]
    known_transcripts = sorted({str(row.get("transcript", "")) for row in turn_rows if row.get("transcript")})
    logs = scan_logs([
        Path("/home/administrator/.cyberWife/logs"),
        Path("/mnt/c/Users/Administrator/AppData/Local/cyberWife/logs"),
    ], known_transcripts)
    external_rows = [row for sample in samples for row in sample["external"]] + linux_external_now + windows_external
    sampled_external = list({(row["pid"], row["local"], row.get("peer", row.get("remote", ""))): row for row in external_rows}.values())
    expected_ports = {4173, 7860, 8010, 8011, 8090, 8091}
    listener_rows = linux_listeners + windows_listeners
    observed_ports = set()
    non_loopback = []
    for row in listener_rows:
        local = str(row.get("local", ""))
        try: observed_ports.add(int(local.rsplit(":", 1)[1]))
        except (ValueError, IndexError): pass
        if not is_loopback(local): non_loopback.append(row)
    ignore_text = (args.workspace / ".gitignore").read_text(encoding="utf-8")
    workspace_boundary = {
        "git_metadata_present": (args.workspace / ".git").exists(),
        "required_ignore_rules": {rule: rule in ignore_text for rule in ("assets/", "audit/", "*.wav", "*.png", "*.gguf", "config/runtime.local.toml")},
        "public_stun_references": sum(1 for path in (args.workspace / "config").glob("*.toml") if "stun:" in path.read_text(encoding="utf-8", errors="ignore").lower()),
    }
    result = {
        "schema_version": 1,
        "evidence_level": "real_audio_models_avatar_sqlite_vector_continuous_socket_sampling",
        "turns": {**turn_summary, "transcript_sha256": transcript_hashes, "raw_transcript_persisted": False},
        "avatar": {"frames": avatar["frames"], "protocol_version": avatar["protocol_version"]},
        "memory_flow": memory,
        "network": {
            "sample_count": len(samples), "expected_ports": sorted(expected_ports), "observed_ports": sorted(observed_ports),
            "non_loopback_listeners": non_loopback, "external_established": sampled_external,
        },
        "offline_environment": offline_environment(),
        "acceptance_basis": {
            "physical_disconnect": "waived_by_user_because_it_interrupts_the_host_terminal",
            "replacement": "functional_completeness_plus_whitebox_egress_review_plus_runtime_socket_sampling",
        },
        "privacy": {
            "new_audio_files": sorted(set(after_audio) - set(before_audio)), "log_scan": logs,
            "workspace_boundary": workspace_boundary,
        },
    }
    result["pass"] = all((
        turn_summary["result"] == "PASS", avatar["frames"] > 0,
        all(memory[key] for key in ("listed", "edited", "searched", "deleted", "absent_after")),
        expected_ports.issubset(observed_ports), not non_loopback,
        not result["network"]["external_established"], result["offline_environment"]["pass"],
        not result["privacy"]["new_audio_files"], not logs["hits"],
        all(workspace_boundary["required_ignore_rules"].values()), workspace_boundary["public_stun_references"] == 0,
    ))
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--real-models", action="store_true")
    parser.add_argument("--workspace", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--audio", type=Path, default=Path("audit/tts_nonstreaming.wav"))
    parser.add_argument("--db", type=Path, default=Path("/home/administrator/.cyberWife/cyberwife.db"))
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--ws-base", default="ws://127.0.0.1:7860")
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B5/B5.3-privacy"))
    args = parser.parse_args()
    if not args.real_models:
        raise SystemExit(3)
    result = asyncio.run(execute(args))
    args.evidence.mkdir(parents=True, exist_ok=True)
    (args.evidence / "result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__":
    main()
