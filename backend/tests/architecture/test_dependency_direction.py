"""Enforce the target dependency direction at the source boundary."""
from __future__ import annotations

import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "cyberwife"
APPLICATION_LAYERS = ("application", "domain", "ports")
FORBIDDEN = ("cyberwife.infrastructure", "cyberwife.adapters", "cyberwife.api")


def test_inner_layers_do_not_import_outer_layers() -> None:
    violations: list[str] = []
    for layer in APPLICATION_LAYERS:
        for path in (ROOT / layer).rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names: list[str] = []
                if isinstance(node, ast.Import):
                    names = [alias.name for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    names = [node.module]
                for name in names:
                    if name.startswith(FORBIDDEN):
                        violations.append(f"{path.relative_to(ROOT)}:{node.lineno} -> {name}")
    assert violations == [], "reverse dependencies:\n" + "\n".join(violations)
