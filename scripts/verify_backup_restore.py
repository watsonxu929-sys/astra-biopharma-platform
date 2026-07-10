from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.operations.backup_service import create_backup
from app.services.operations.restore_service import restore_backup, validate_backup
from scripts.migrate_v05kl import migrate


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="verify_backup_restore_") as tmp:
        db = Path(tmp) / "app.db"
        migrate(db, backup=False)
        conn = sqlite3.connect(db)
        conn.execute("CREATE TABLE IF NOT EXISTS verify_data(id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO verify_data(name) VALUES ('before')")
        conn.commit()
        conn.close()
        backup = create_backup(backup_type="verify", created_by="verify", db_path=db, target_dir=Path(tmp) / "backups")
        assert validate_backup(backup["backup_id"], db_path=db)["ok"]
        conn = sqlite3.connect(db)
        conn.execute("INSERT INTO verify_data(name) VALUES ('after')")
        conn.commit()
        conn.close()
        restored = restore_backup(backup["backup_id"], dry_run=False, confirm=True, target_path=db, db_path=db, created_by="verify")
        assert restored["status"] == "restored"
        conn = sqlite3.connect(db)
        count = conn.execute("SELECT COUNT(*) FROM verify_data").fetchone()[0]
        conn.close()
        assert count == 1
    print("backup_restore verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
