import sqlite3
from pathlib import Path
import sys

db_path = Path("data/app.db").resolve()
print("=" * 60)
print("账号只读检查")
print("=" * 60)
print("数据库路径:", db_path)
print("数据库存在:", db_path.exists())

if not db_path.exists():
    print("错误：未找到 data/app.db。请把本工具放到项目根目录。")
    sys.exit(1)

db = sqlite3.connect(str(db_path))
db.row_factory = sqlite3.Row
try:
    tables = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()]
    print("用户相关表:", [n for n in tables if "user" in n.lower()])

    table = "v05a_users"
    if table not in tables:
        print("未找到 v05a_users。当前数据库可能不正确或尚未迁移。")
        sys.exit(2)

    columns = [r[1] for r in db.execute(
        "PRAGMA table_info(v05a_users)"
    ).fetchall()]
    print("用户表字段:", columns)

    candidates = [
        "id", "username", "display_name", "role", "status", "is_active",
        "failed_login_count", "locked_until", "deactivated_at",
        "must_change_password", "created_at", "updated_at"
    ]
    selected = [c for c in candidates if c in columns]
    rows = db.execute(
        f"SELECT {', '.join(selected)} FROM v05a_users ORDER BY id"
    ).fetchall()

    print("账号记录:")
    for row in rows:
        print(dict(row))
    if not rows:
        print("未找到任何账号。")
finally:
    db.close()

print("检查完成。本工具没有修改数据库。")
