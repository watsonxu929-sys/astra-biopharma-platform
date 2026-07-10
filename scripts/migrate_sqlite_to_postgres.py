from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings


def _sqlite_tables(path: Path) -> list[str]:
    if not path.exists():
        return []
    conn = sqlite3.connect(path)
    try:
        return [r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()]
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="SQLite 到 PostgreSQL 安全迁移辅助工具")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--confirm", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    settings = get_settings()
    tables = _sqlite_tables(settings.sqlite_path)
    print(f"source_sqlite={settings.sqlite_path}")
    print(f"tables={len(tables)}")
    for table in tables[:80]:
        print(f"TABLE {table}")
    if args.validate_only or args.dry_run or not args.confirm:
        print("DRY-RUN：未连接 PostgreSQL，未修改 SQLite，未迁移数据。")
        return 0
    try:
        import psycopg  # type: ignore  # noqa: F401
    except Exception:
        print("未安装 PostgreSQL 驱动，无法执行正式迁移；SQLite 未被修改。")
        return 2
    print("正式迁移入口已就绪，但当前补丁不自动切换生产配置。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
