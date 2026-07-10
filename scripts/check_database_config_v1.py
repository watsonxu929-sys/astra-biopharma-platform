from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import get_settings, resolved_database_url, resolved_db_path
from app.database import DATABASE_URL, DB_PATH
from app.v04c_review import default_db_path


def main() -> int:
    settings = get_settings()
    print(f"config.database_url={settings.database_url}")
    print(f"config.app_db_path={settings.app_db_path}")
    print(f"app.database.DATABASE_URL={DATABASE_URL}")
    print(f"app.database.DB_PATH={DB_PATH}")
    print(f"migration.default_db_path={default_db_path()}")
    print(f"verification.default_db_path={default_db_path()}")
    paths = {str(settings.app_db_path), str(DB_PATH), str(default_db_path())}
    if len(paths) != 1:
        print(f"ERROR: database path mismatch: {sorted(paths)}")
        return 1
    if settings.database_url != DATABASE_URL:
        print("ERROR: database URL mismatch")
        return 1
    print("database_config=unified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
