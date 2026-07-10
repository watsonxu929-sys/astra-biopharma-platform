from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import resolved_db_path

from app.security import ensure_security_schema
from app.services.identity_link_service import backup_database, ensure_identity_link_schema

DB_PATH = resolved_db_path()


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = backup_database(db_path) if backup else ""
    if backup and db_path.exists() and not backup_path:
        raise RuntimeError("正式数据库备份失败，已停止迁移")
    ensure_security_schema(db_path)
    ensure_identity_link_schema(db_path)
    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("identity link v1 migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    print("no historical users or people were auto-linked")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


