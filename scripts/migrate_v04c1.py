from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.v04c1_ingestion import default_db_path, ensure_v04c1_schema  # noqa: E402


def main() -> int:
    db_path = default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"app_before_v04c1_{stamp}.db"
        shutil.copy2(db_path, backup_path)
        print(f"[BACKUP] {backup_path}")
    else:
        print(f"[INFO] 数据库尚不存在，将新建：{db_path}")

    path = ensure_v04c1_schema(allow_migration=True)
    print(f"[OK] v0.4C-1 数据表迁移完成：{path}")
    print("[SAFE] 未删除或重建任何原有业务表。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
