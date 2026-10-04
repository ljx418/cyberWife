"""Runtime configuration loading for the Windows + WSL2 V1 topology."""
from __future__ import annotations

import os
import re
import tomllib
from pathlib import Path
from typing import Any


def _merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def normalize_local_path(value: str) -> str:
    """Translate a Windows absolute path to its WSL mount when running on POSIX."""
    expanded = os.path.expandvars(os.path.expanduser(value))
    if os.name == "posix" and re.match(r"^[A-Za-z]:[\\/]", expanded):
        drive = expanded[0].lower()
        suffix = expanded[2:].replace("\\", "/").lstrip("/")
        return f"/mnt/{drive}/{suffix}"
    return expanded


def load_runtime_config(repo_root: Path, config_path: Path | None = None) -> dict[str, Any]:
    """Load defaults then overlay a local TOML file.

    ``runtime.local.toml`` intentionally contains only machine-specific fields,
    so it must never replace the checked-in defaults wholesale.
    """
    default_path = repo_root / "config" / "default.example.toml"
    with default_path.open("rb") as stream:
        config = tomllib.load(stream)
    selected = config_path or repo_root / "config" / "runtime.local.toml"
    if selected.exists() and selected.resolve() != default_path.resolve():
        with selected.open("rb") as stream:
            config = _merge(config, tomllib.load(stream))
    for key, value in list(config.get("paths", {}).items()):
        if isinstance(value, str):
            config["paths"][key] = normalize_local_path(value)
    return config
