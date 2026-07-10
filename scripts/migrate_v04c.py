from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.settings import resolved_db_path  # noqa: E402
from app.v04c_review import ensure_v04c_schema  # noqa: E402


def backup_dir_for(db_path: Path) -> Path:
    if (PROJECT_ROOT / "data") in db_path.resolve().parents:
        return PROJECT_ROOT / "data" / "backups"
    return db_path.parent / "backups"


def main() -> int:
    db_path = resolved_db_path()
    if db_path.exists():
        backup_dir = backup_dir_for(db_path)
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup_path = backup_dir / f"app_before_v04c_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(db_path, backup_path)
        print(f"[OK] database backup created: {backup_path}")
    else:
        print(f"[INFO] database does not exist, creating: {db_path}")

    created_path = ensure_v04c_schema(db_path, allow_migration=True)
    with sqlite3.connect(created_path) as conn:
        tables = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v04c_%' ORDER BY name"
            )
        ]
    print(f"[OK] v0.4C migration completed: {created_path}")
    for table in tables:
        print(f"  - {table}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
