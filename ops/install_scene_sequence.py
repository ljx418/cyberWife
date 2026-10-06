#!/usr/bin/env python3
"""Install a human-approved scene sequence into the active private idle job."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from cyberwife.application.avatar_asset_service import AvatarAssetService
from cyberwife.infrastructure.asset_store import AssetStore
from cyberwife.infrastructure.sqlite_repository import SqliteRepository


ROOT = Path(__file__).resolve().parents[1]
APPROVAL_TOKEN = "UX13-FRONTAL-V2-APPROVED"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--close-keyframe", required=True, type=Path)
    parser.add_argument("--approval-token", required=True)
    parser.add_argument("--database", type=Path, default=Path("/home/administrator/.cyberWife/cyberwife.db"))
    parser.add_argument("--assets-root", type=Path, default=Path("/home/administrator/.cyberWife/assets"))
    parser.add_argument("--avatar-root", type=Path, default=Path("/home/administrator/.cyberWife/avatar/avatars"))
    args = parser.parse_args()
    if args.approval_token != APPROVAL_TOKEN:
        raise SystemExit("explicit UX13 frontal approval token required")

    repository = SqliteRepository(args.database, ROOT / "migrations" / "0001_init.sql")
    active = repository.get_active_avatar_derivative()
    if active is None:
        raise SystemExit("no active avatar derivative")
    service = AvatarAssetService(
        repository,
        asset_store=AssetStore(args.assets_root),
        avatar_root=args.avatar_root,
    )
    result = service.install_approved_sequence(
        int(active["id"]),
        manifest_path=args.manifest,
        close_keyframe=args.close_keyframe,
        visually_approved=True,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
