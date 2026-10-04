"""B5.5 isolated backup/restore/uninstall/clear acceptance."""

import json
import sqlite3
import tempfile
from pathlib import Path

from ops.data_lifecycle import DATA_SENTINEL, INSTALL_SENTINEL, backup, clear_data, restore, uninstall


def main() -> None:
    output = Path("audit/v1/B5/B5.5-data-lifecycle/result.json")
    with tempfile.TemporaryDirectory(prefix="cw-b55-") as temporary:
        root = Path(temporary)
        data = root / "data"; data.mkdir(); (data / DATA_SENTINEL).write_text("test")
        conn = sqlite3.connect(data / "cyberwife.db"); conn.execute("CREATE TABLE proof(value TEXT)"); conn.execute("INSERT INTO proof VALUES ('private-test-value')"); conn.commit(); conn.close()
        (data / "assets").mkdir(); (data / "assets" / "portrait.bin").write_bytes(b"portrait")
        (data / "avatar" / "avatars").mkdir(parents=True); (data / "avatar" / "avatars" / "voice.bin").write_bytes(b"voice")
        archive = root / "backup.zip"
        backed = backup(data, archive)
        restored_root = root / "restored"; restored = restore(archive, restored_root)
        restored_value = sqlite3.connect(restored_root / "cyberwife.db").execute("SELECT value FROM proof").fetchone()[0]
        install = root / "install"; install.mkdir(); (install / INSTALL_SENTINEL).write_text("test"); (install / "app.bin").write_bytes(b"app")
        uninstalled = uninstall(install, restored_root, "UNINSTALL KEEP DATA")
        wrong_confirmation_rejected = False
        try: clear_data(restored_root, "yes")
        except ValueError: wrong_confirmation_rejected = True
        cleared = clear_data(restored_root, "DELETE CYBERWIFE DATA")
        result = {
            "schema_version": 1, "evidence_level": "isolated_real_sqlite_filesystem_hashes",
            "backup": backed, "restore": restored, "restored_value_matches": restored_value == "private-test-value",
            "uninstall": uninstalled, "wrong_confirmation_rejected": wrong_confirmation_rejected, "clear": cleared,
        }
        result["pass"] = all((backed["entries"] == 3, restored["integrity_check"] == "ok", result["restored_value_matches"], uninstalled["install_removed"], uninstalled["data_preserved"], wrong_confirmation_rejected, cleared["deleted"], not restored_root.exists()))
    output.parent.mkdir(parents=True, exist_ok=True); output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2)); raise SystemExit(0 if result["pass"] else 2)


if __name__ == "__main__": main()
