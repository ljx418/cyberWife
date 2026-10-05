"""B3-AC06: one-hour mixed real-model soak with attributed resource sampling."""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import os
import re
import shlex
import statistics
import struct
import subprocess
import time
import wave
from datetime import datetime, timezone
from pathlib import Path

import httpx
import websockets

from tests.b3.accept_turns import avatar_transport


_SAFE_AVATAR_ID = re.compile(r"^[A-Za-z0-9_-]{1,80}$")


def resolve_active_avatar_id(client: httpx.Client, base: str) -> str:
    response = client.get(base + "/api/v1/avatar/active")
    response.raise_for_status()
    avatar_id = str(response.json().get("avatar_id", ""))
    if not _SAFE_AVATAR_ID.fullmatch(avatar_id):
        raise ValueError("active avatar id is missing or unsafe")
    return avatar_id


def read_pcm(path: Path) -> bytes:
    with wave.open(str(path), "rb") as source:
        if (source.getframerate(), source.getnchannels(), source.getsampwidth()) != (16000, 1, 2):
            raise ValueError("acceptance audio must be PCM16/16kHz/mono")
        value = source.readframes(source.getnframes())
    return value + b"\0" * ((-len(value)) % 640)


def proc_value(path: Path, key: str) -> int:
    try:
        for line in path.read_text().splitlines():
            if line.startswith(key + ":"):
                return int(line.split()[1])
    except (OSError, ValueError):
        pass
    return 0


_PROJECT_MODULES = {
    "gateway": "cyberwife.api.server",
    "speech": "workers.speech_worker.server",
}


def project_component(command: str) -> str | None:
    """Attribute only actual service argv, never a shell containing marker text."""
    try:
        argv = shlex.split(command)
    except ValueError:
        return None
    for index, value in enumerate(argv[:-1]):
        if value == "-m":
            module = argv[index + 1]
            for component, expected in _PROJECT_MODULES.items():
                if module == expected:
                    return component
    executable_names = {Path(value).name for value in argv[:2]}
    if "app.py" in executable_names and "--bind" in argv and "--listenport" in argv:
        return "avatar"
    return None


def wsl_resources() -> tuple[float, float, int, int, dict[str, dict[str, float | int]]]:
    meminfo = Path("/proc/meminfo")
    available_mb = proc_value(meminfo, "MemAvailable") / 1024
    rss_kb = 0
    tasks = 0
    components: dict[str, dict[str, float | int]] = {
        name: {"pid": 0, "rss_mb": 0.0, "tasks": 0}
        for name in ("gateway", "speech", "avatar")
    }
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit() or int(directory.name) == os.getpid():
            continue
        try:
            command = (directory / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="ignore")
        except OSError:
            continue
        component = project_component(command)
        if component is not None:
            rss_kb += proc_value(directory / "status", "VmRSS")
            task_dir = directory / "task"
            try:
                process_tasks = sum(1 for _ in task_dir.iterdir())
                tasks += process_tasks
            except OSError:
                process_tasks = 0
            entry = components[component]
            entry["pid"] = int(directory.name)
            entry["rss_mb"] = round(proc_value(directory / "status", "VmRSS") / 1024, 3)
            entry["tasks"] = process_tasks
    swap_in = 0
    for line in Path("/proc/vmstat").read_text().splitlines():
        if line.startswith("pswpin "):
            swap_in = int(line.split()[1])
            break
    return rss_kb / 1024, available_mb, swap_in, tasks, components


def windows_resources() -> tuple[float, float]:
    pid_dir = Path("/mnt/c/Users/Administrator/AppData/Local/cyberWife/pid")
    pids = []
    for path in pid_dir.glob("*.json"):
        try:
            pids.append(int(json.loads(path.read_text(encoding="utf-8-sig"))["pid"]))
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            pass
    joined = ",".join(str(pid) for pid in pids) or "0"
    command = (
        "$o=Get-CimInstance Win32_OperatingSystem;"
        f"$p=Get-Process -Id @({joined}) -ErrorAction SilentlyContinue;"
        "@{available_mb=[math]::Round($o.FreePhysicalMemory/1024,3);"
        "private_mb=[math]::Round((($p|Measure-Object PM -Sum).Sum)/1MB,3)}|ConvertTo-Json -Compress"
    )
    output = subprocess.check_output(["powershell.exe", "-NoProfile", "-Command", command], text=True, timeout=4)
    value = json.loads(output)
    return float(value["private_mb"]), float(value["available_mb"])


def gpu_resources() -> tuple[float, float]:
    output = subprocess.check_output([
        "nvidia-smi", "--query-gpu=memory.used,memory.total", "--format=csv,noheader,nounits"
    ], text=True, timeout=4).strip().splitlines()[0]
    used, total = (float(part.strip()) for part in output.split(","))
    return used / 1024, total / 1024


def runtime_metrics(base: str) -> dict:
    with httpx.Client(timeout=4, trust_env=False) as client:
        return client.get(base + "/api/v1/runtime/metrics").json()


def sample_sync(base: str, elapsed_s: float) -> dict:
    wsl_rss, wsl_available, swap_in, linux_tasks, linux_components = wsl_resources()
    windows_private, windows_available = windows_resources()
    gpu_used, gpu_total = gpu_resources()
    metrics = runtime_metrics(base)
    normal = metrics.get("latency", {}).get("buckets", {}).get("normal", {})
    return {
        "observed_at": datetime.now(timezone.utc).isoformat(), "elapsed_s": round(elapsed_s, 3),
        "wsl_project_rss_mb": round(wsl_rss, 3), "windows_project_private_mb": windows_private,
        "project_ram_mb": round(wsl_rss + windows_private, 3),
        "wsl_available_mb": round(wsl_available, 3), "windows_available_mb": windows_available,
        "swap_in_pages": swap_in, "gpu_used_gb": round(gpu_used, 3), "gpu_total_gb": round(gpu_total, 3),
        "linux_project_tasks": linux_tasks, "pipeline_active_turns": metrics.get("active_turns", 0),
        "linux_components": linux_components,
        "runtime_tasks": metrics.get("runtime_tasks", 0), "llm_queue_depth": metrics.get("llm_queue_depth", 0),
        "outbound_queue_depth": metrics.get("outbound_queue_depth", 0), "latency_p95_ms": normal.get("p95_ms") or 0,
        "python_thread_count": metrics.get("python_thread_count", 0),
        "python_threads_by_name": metrics.get("python_threads_by_name", {}),
    }


def theil_sen(values: list[tuple[float, float]]) -> float:
    slopes = []
    for index, (x1, y1) in enumerate(values):
        for x2, y2 in values[index + 1:]:
            if x2 > x1:
                slopes.append((y2 - y1) / ((x2 - x1) / 60))
    return statistics.median(slopes) if slopes else 0.0


def trend(rows: list[dict], key: str, duration_s: float) -> float:
    cutoff = max(0.0, duration_s - 1800)
    buckets: dict[int, list[float]] = {}
    for row in rows:
        if row["elapsed_s"] >= cutoff:
            bucket = int((row["elapsed_s"] - cutoff) // 300)
            buckets.setdefault(bucket, []).append(float(row[key]))
    points = [(cutoff + bucket * 300 + 150, statistics.median(values)) for bucket, values in sorted(buckets.items())]
    return round(theil_sen(points), 6)


def evaluate(samples: list[dict], actions: list[dict], args) -> dict:
    duration_s = args.minutes * 60
    trend_window_evaluable = duration_s >= 600
    valid = [row for row in samples if "sample_error" not in row]
    slopes = {key: trend(valid, key, duration_s) for key in (
        "project_ram_mb", "linux_project_tasks", "runtime_tasks",
        "llm_queue_depth", "outbound_queue_depth", "latency_p95_ms",
        "python_thread_count",
    )}
    minute_ends: dict[int, int] = {}
    for row in valid:
        minute_ends[int(float(row["elapsed_s"]) // 60)] = int(row["swap_in_pages"])
    minute_deltas = [
        max(0, value - previous)
        for previous, value in zip(
            [minute_ends[key] for key in sorted(minute_ends)[:-1]],
            [minute_ends[key] for key in sorted(minute_ends)[1:]],
        )
    ]
    # pswpin is host-wide and counts 4 KiB pages. Tiny page faults from the
    # evidence collector itself are not sustained memory pressure. A material
    # swap-in minute is >=1 MiB; three consecutive material minutes fail.
    material_pages_per_minute = 256
    consecutive = max_consecutive_material = 0
    for delta in minute_deltas:
        consecutive = consecutive + 1 if delta >= material_pages_per_minute else 0
        max_consecutive_material = max(max_consecutive_material, consecutive)
    complete_passed = sum(row["kind"] == "complete" and row["result"] == "PASS" for row in actions)
    interrupt_passed = sum(row["kind"] == "interrupt" and row["result"] == "PASS" for row in actions)
    passed = all((
        trend_window_evaluable,
        len(actions) == args.min_turns + args.interrupts,
        complete_passed >= args.min_turns, interrupt_passed >= args.interrupts,
        not any("sample_error" in row for row in samples),
        max(row["project_ram_mb"] for row in valid) <= 14 * 1024,
        max(row["gpu_used_gb"] for row in valid) <= 22,
        min(row["wsl_available_mb"] for row in valid) >= 2048,
        min(row["windows_available_mb"] for row in valid) >= 2048,
        slopes["project_ram_mb"] <= 20, slopes["linux_project_tasks"] <= 0.1,
        slopes["runtime_tasks"] <= 0.1, slopes["llm_queue_depth"] <= 0.1,
        slopes["outbound_queue_depth"] <= 0.1, slopes["latency_p95_ms"] <= 20,
        slopes["python_thread_count"] <= 0.1,
        max_consecutive_material < 3,
    ))
    return {
        "evidence_level": "e2e_real_models_60_minute_resource_soak",
        "duration_minutes": args.minutes, "samples": len(samples), "actions": len(actions),
        "trend_window_evaluable": trend_window_evaluable,
        "complete_passed": complete_passed, "interrupt_passed": interrupt_passed,
        "slopes_per_minute": slopes,
        "max_project_ram_mb": max(row["project_ram_mb"] for row in valid),
        "max_gpu_used_gb": max(row["gpu_used_gb"] for row in valid),
        "min_wsl_available_mb": min(row["wsl_available_mb"] for row in valid),
        "min_windows_available_mb": min(row["windows_available_mb"] for row in valid),
        "swap_in_total_pages": valid[-1]["swap_in_pages"] - valid[0]["swap_in_pages"],
        "max_swap_in_pages_per_minute": max(minute_deltas, default=0),
        "material_swap_threshold_pages_per_minute": material_pages_per_minute,
        "max_consecutive_material_swap_minutes": max_consecutive_material,
        "result": "PASS" if passed else "FAIL",
    }


async def send_audio(socket, turn_id: int, pcm: bytes, event_seq: int) -> None:
    for chunk, offset in enumerate(range(0, len(pcm), 640)):
        await socket.send(struct.pack("<IH", turn_id, chunk) + pcm[offset:offset + 640])
    await socket.send(json.dumps({"type": "audio.silence", "turn_id": turn_id, "event_seq": event_seq}))


async def run(args) -> tuple[dict, list[dict], list[dict], list[str]]:
    duration_s = args.minutes * 60
    action_count = args.min_turns + args.interrupts
    pcm = read_pcm(args.audio)
    samples, actions, raw_gpu = [], [], []
    stop_sampling = asyncio.Event()
    started = time.monotonic()

    async def sampler() -> None:
        next_at = started
        last_reported_minute = -1
        while not stop_sampling.is_set():
            now = time.monotonic()
            if now < next_at:
                try:
                    await asyncio.wait_for(stop_sampling.wait(), next_at - now)
                    break
                except asyncio.TimeoutError:
                    pass
            elapsed = time.monotonic() - started
            try:
                samples.append(await asyncio.to_thread(sample_sync, args.http_base, elapsed))
                if not raw_gpu or elapsed - (len(raw_gpu) - 1) * 60 >= 60:
                    raw_gpu.append(await asyncio.to_thread(subprocess.check_output, ["nvidia-smi"], text=True, timeout=5))
            except Exception as error:
                samples.append({"observed_at": datetime.now(timezone.utc).isoformat(), "elapsed_s": round(elapsed, 3), "sample_error": str(error)})
            args.evidence.mkdir(parents=True, exist_ok=True)
            (args.evidence / "resources.partial.json").write_text(json.dumps(samples, ensure_ascii=False) + "\n", encoding="utf-8")
            minute = int(elapsed // 60)
            if minute > last_reported_minute:
                last_reported_minute = minute
                print("PROGRESS " + json.dumps({"minute": minute, "sample": samples[-1]}, ensure_ascii=False), flush=True)
            next_at += args.sample_seconds

    client = httpx.Client(timeout=10, trust_env=False)
    session_id = int(client.post(args.http_base + "/api/v1/sessions", json={}).json()["id"])
    avatar_id = resolve_active_avatar_id(client, args.http_base)
    avatar_stats = {
        "frames": 0, "generations": set(), "session_id": None,
        "protocol_version": None, "avatar_id": avatar_id,
    }
    avatar_ready, avatar_stop = asyncio.Event(), asyncio.Event()
    avatar_task = asyncio.create_task(
        avatar_transport(avatar_stats, avatar_ready, avatar_stop, avatar_id)
    )
    sampler_task = asyncio.create_task(sampler())
    client_seq = 0
    try:
        await asyncio.wait_for(avatar_ready.wait(), 15)
        ws_base = args.http_base.replace("http://", "ws://", 1).replace("https://", "wss://", 1)
        async with websockets.connect(f"{ws_base}/ws/v1/sessions/{session_id}", max_size=2**20) as socket:
            await socket.recv()
            interval = duration_s / action_count
            completed = interrupted = 0
            for action_index in range(action_count):
                target = started + action_index * interval
                if time.monotonic() < target:
                    await asyncio.sleep(target - time.monotonic())
                turn_id = action_index + 1
                kind = "interrupt" if action_index % 3 == 2 and interrupted < args.interrupts else "complete"
                if action_count - action_index <= args.interrupts - interrupted:
                    kind = "interrupt"
                client_seq += 1
                action_started = time.monotonic()
                await send_audio(socket, turn_id, pcm, client_seq)
                event_types, media_modes = [], []
                passed = False
                playback_confirmed = False
                while True:
                    event = json.loads(await asyncio.wait_for(socket.recv(), args.turn_timeout))
                    event_types.append(event["type"])
                    if event["type"] == "media.state": media_modes.append(event["payload"].get("mode"))
                    if event["type"] == "reply.audio.chunk" and not playback_confirmed:
                        client_seq += 1
                        await socket.send(json.dumps({
                            "type": "audio.playback.started", "turn_id": turn_id,
                            "trace_id": event["payload"]["trace_id"],
                            "generation": event["payload"]["generation"],
                            "asr_to_playback_ms": event["payload"]["server_elapsed_ms"],
                            "browser_first_non_silent_wall_ms": time.time() * 1000,
                            "event_seq": client_seq,
                        }))
                        playback_confirmed = True
                    if kind == "interrupt" and event["type"] == "reply.audio.chunk":
                        client_seq += 1
                        await socket.send(json.dumps({"type": "barge_in.detected", "turn_id": turn_id, "event_seq": client_seq}))
                        kind = "interrupt_sent"
                    elif kind == "interrupt_sent" and event["type"] == "turn.cancelled":
                        interrupted += 1; passed = not event["payload"].get("component_errors"); break
                    elif kind == "complete" and event["type"] == "reply.audio.complete":
                        client_seq += 1
                        await socket.send(json.dumps({"type": "audio.playback.ended", "turn_id": turn_id, "generation": event["payload"]["generation"], "event_seq": client_seq}))
                    elif kind == "complete" and event["type"] == "state.changed" and event["payload"].get("reason") in {"playback_complete", "text_complete"}:
                        completed += 1; passed = True; break
                    if event["type"] == "error": break
                actions.append({
                    "turn": turn_id, "kind": "interrupt" if kind == "interrupt_sent" else kind,
                    "elapsed_s": round(time.monotonic() - started, 3),
                    "duration_ms": round((time.monotonic() - action_started) * 1000, 3),
                    "event_count": len(event_types), "media_modes": media_modes,
                    "result": "PASS" if passed and not media_modes else "FAIL",
                })
                args.evidence.mkdir(parents=True, exist_ok=True)
                (args.evidence / "actions.partial.json").write_text(json.dumps(actions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            remaining = started + duration_s - time.monotonic()
            if remaining > 0: await asyncio.sleep(remaining)
    finally:
        stop_sampling.set(); avatar_stop.set()
        await asyncio.gather(sampler_task, avatar_task, return_exceptions=True)
        client.delete(f"{args.http_base}/api/v1/sessions/{session_id}"); client.close()

    summary = evaluate(samples, actions, args)
    summary["avatar"] = {
        **avatar_stats,
        "generations": sorted(avatar_stats["generations"]),
    }
    return summary, samples, actions, raw_gpu


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--minutes", type=float, default=60)
    parser.add_argument("--min-turns", type=int, default=20)
    parser.add_argument("--interrupts", type=int, default=10)
    parser.add_argument("--sample-seconds", type=float, default=5)
    parser.add_argument("--turn-timeout", type=float, default=120)
    parser.add_argument("--audio", type=Path, default=Path("audit/tts_nonstreaming.wav"))
    parser.add_argument("--http-base", default="http://127.0.0.1:7860")
    parser.add_argument("--evidence", type=Path, default=Path("audit/v1/B3/AC06"))
    parser.add_argument("--recompute", action="store_true")
    args = parser.parse_args()
    if args.recompute:
        samples = json.loads((args.evidence / "resources.partial.json").read_text(encoding="utf-8"))
        actions = json.loads((args.evidence / "actions.partial.json").read_text(encoding="utf-8"))
        raw_path = args.evidence / "nvidia-smi.txt"
        raw_gpu = [raw_path.read_text(encoding="utf-8")] if raw_path.exists() else []
        summary = evaluate(samples, actions, args)
    else:
        summary, samples, actions, raw_gpu = asyncio.run(run(args))
    args.evidence.mkdir(parents=True, exist_ok=True)
    headers = sorted({key for row in samples for key in row})
    with (args.evidence / "resources.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=headers); writer.writeheader(); writer.writerows(samples)
    (args.evidence / "actions.json").write_text(json.dumps(actions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.evidence / "nvidia-smi.txt").write_text("\n\n".join(raw_gpu), encoding="utf-8")
    (args.evidence / "manifest.json").write_text(json.dumps({"schema_version": 1, "command": f"python -m tests.b3.accept_soak --minutes {args.minutes} --min-turns {args.min_turns} --interrupts {args.interrupts}", "summary": summary}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("SUMMARY " + json.dumps(summary, ensure_ascii=False), flush=True)
    raise SystemExit(0 if summary["result"] == "PASS" else 2)


if __name__ == "__main__": main()
