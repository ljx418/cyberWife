"""Safe backup/restore/uninstall/data-clear primitives for cyberWife V1."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path


DATA_SENTINEL = ".cyberwife-data-root"
INSTALL_SENTINEL = ".cyberwife-install-root"
BACKUP_PATHS = ("cyberwife.db", "assets", "avatar/avatars")


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def safe_root(path: Path, sentinel: str) -> Path:
    root = path.resolve()
    if root == Path(root.anchor) or len(root.parts) < 4 or not (root / sentinel).is_file():
        raise ValueError(f"refusing unsafe root without {sentinel}: {root}")
    return root


def backup(source: Path, archive: Path) -> dict:
    source = safe_root(source, DATA_SENTINEL)
    archive = archive.resolve()
    if source == archive or source in archive.parents:
        raise ValueError("backup archive must be outside the data root")
    archive.parent.mkdir(parents=True, exist_ok=True)
    entries: dict[str, str] = {}
    with tempfile.TemporaryDirectory(prefix="cw-backup-") as temporary:
        snapshot = Path(temporary) / "cyberwife.db"
        database = source / "cyberwife.db"
        if database.exists():
            with sqlite3.connect(database) as original, sqlite3.connect(snapshot) as target:
                original.backup(target)
            if sqlite3.connect(snapshot).execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RuntimeError("database snapshot integrity failed")
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as bundle:
            for relative in BACKUP_PATHS:
                target = snapshot if relative == "cyberwife.db" else source / relative
                if target.is_file():
                    entries[relative] = digest(target); bundle.write(target, relative)
                elif target.is_dir():
                    for item in sorted(target.rglob("*")):
                        if item.is_symlink():
                            raise ValueError(f"symlink not allowed in backup: {item}")
                        if item.is_file():
                            name = item.relative_to(source).as_posix()
                            entries[name] = digest(item); bundle.write(item, name)
            manifest = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(), "entries": entries}
            bundle.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    return {"archive": str(archive), "entries": len(entries), "sha256": digest(archive)}


def restore(archive: Path, target: Path) -> dict:
    target = target.resolve()
    if target.exists() and any(target.iterdir()):
        raise ValueError("restore target must be absent or empty")
    target.mkdir(parents=True, exist_ok=True)
    (target / DATA_SENTINEL).write_text("cyberWife V1 data root\n", encoding="utf-8")
    with zipfile.ZipFile(archive.resolve()) as bundle:
        manifest = json.loads(bundle.read("manifest.json"))
        for name, expected in manifest["entries"].items():
            destination = (target / name).resolve()
            if target not in destination.parents:
                raise ValueError("backup contains path traversal")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with bundle.open(name) as source, destination.open("wb") as output:
                shutil.copyfileobj(source, output)
            if digest(destination) != expected:
                raise RuntimeError(f"hash mismatch: {name}")
    database = target / "cyberwife.db"
    integrity = sqlite3.connect(database).execute("PRAGMA integrity_check").fetchone()[0] if database.exists() else "absent"
    if database.exists() and integrity != "ok":
        raise RuntimeError("restored database integrity failed")
    return {"target": str(target), "entries": len(manifest["entries"]), "integrity_check": integrity}


def uninstall(install_root: Path, data_root: Path, confirmation: str) -> dict:
    if confirmation != "UNINSTALL KEEP DATA":
        raise ValueError("exact uninstall confirmation required")
    install_root = safe_root(install_root, INSTALL_SENTINEL)
    data_root = safe_root(data_root, DATA_SENTINEL)
    before = {str(item.relative_to(data_root)): digest(item) for item in data_root.rglob("*") if item.is_file()}
    shutil.rmtree(install_root)
    after = {str(item.relative_to(data_root)): digest(item) for item in data_root.rglob("*") if item.is_file()}
    return {"install_removed": not install_root.exists(), "data_preserved": before == after, "data_files": len(after)}


def clear_data(data_root: Path, confirmation: str) -> dict:
    if confirmation != "DELETE CYBERWIFE DATA":
        raise ValueError("exact data deletion confirmation required")
    data_root = safe_root(data_root, DATA_SENTINEL)
    files = sum(1 for item in data_root.rglob("*") if item.is_file())
    shutil.rmtree(data_root)
    return {"deleted": True, "file_count": files, "content_in_receipt": False}


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    p = sub.add_parser("backup"); p.add_argument("--source", type=Path, required=True); p.add_argument("--archive", type=Path, required=True)
    p = sub.add_parser("restore"); p.add_argument("--archive", type=Path, required=True); p.add_argument("--target", type=Path, required=True)
    p = sub.add_parser("uninstall"); p.add_argument("--install-root", type=Path, required=True); p.add_argument("--data-root", type=Path, required=True); p.add_argument("--confirmation", required=True)
    p = sub.add_parser("clear-data"); p.add_argument("--data-root", type=Path, required=True); p.add_argument("--confirmation", required=True)
    args = parser.parse_args()
    if args.action == "backup": result = backup(args.source, args.archive)
    elif args.action == "restore": result = restore(args.archive, args.target)
    elif args.action == "uninstall": result = uninstall(args.install_root, args.data_root, args.confirmation)
    else: result = clear_data(args.data_root, args.confirmation)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
