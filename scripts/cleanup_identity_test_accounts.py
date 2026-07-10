from __future__ import annotations

import os
import sys
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings


TEST_USERNAMES = {"e2e_test_admin", "e2e_test_user"}


def _diagnose_env() -> None:
    settings = get_settings()
    env_from = "os.environ" if "APP_ENV" in os.environ else ".env file"
    db_path = settings.sqlite_path
    sanitized_path = str(db_path).replace(str(ROOT), "$ROOT") if ROOT in db_path.parents else str(db_path)
    print(f"=== 环境诊断 ===")
    print(f"APP_ENV: {settings.app_env}")
    print(f"配置来源: {env_from}")
    print(f"数据库类型: {settings.db_backend}")
    print(f"数据库路径(脱敏): {sanitized_path}")
    print(f"允许清理测试数据: {'是' if settings.app_env == 'development' else '否'}")
    print(f"==============")


def _counts(db_path: Path) -> dict[str, int]:
    conn = sqlite3.connect(db_path)
    users = int(conn.execute("SELECT COUNT(*) FROM v05a_users").fetchone()[0])
    people = int(conn.execute("SELECT COUNT(*) FROM people").fetchone()[0])
    requests = int(conn.execute("SELECT COUNT(*) FROM identity_link_requests").fetchone()[0])
    audit = int(conn.execute("SELECT COUNT(*) FROM v05a_audit_logs WHERE action LIKE 'identity_%'").fetchone()[0])
    conn.close()
    return {"users": users, "people": people, "requests": requests, "identity_audit": audit}


def main(dry_run: bool = False) -> int:
    settings = get_settings()
    
    _diagnose_env()
    
    if settings.app_env != "development":
        print("错误：仅在 development 环境下允许清理测试数据")
        return 1
    
    db_path = settings.sqlite_path
    
    print("\n=== 清理前数据统计 ===")
    before = _counts(db_path)
    print(f"用户总数: {before['users']}")
    print(f"人物总数: {before['people']}")
    print(f"绑定申请总数: {before['requests']}")
    print(f"身份审计日志: {before['identity_audit']}")
    
    if dry_run:
        print("\n--- DRY RUN 模式 ---")
        print("将删除以下测试数据（实际不会执行）:")
        print(f"  用户: {TEST_USERNAMES}")
        print(f"  人物: source_type='system_e2e'")
        return 0
    
    print("\n=== 开始清理测试数据 ===")
    
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    
    deleted_users = 0
    for username in TEST_USERNAMES:
        user = conn.execute("SELECT id FROM v05a_users WHERE username=?", (username,)).fetchone()
        if user:
            user_id = user[0]
            conn.execute("DELETE FROM identity_link_requests WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM v05a_users WHERE id=?", (user_id,))
            deleted_users += 1
            print(f"已删除测试用户: {username} (ID: {user_id})")
    
    conn.execute("DELETE FROM identity_link_requests")
    conn.execute("DELETE FROM people WHERE source_type='system_e2e'")
    deleted_people = conn.execute("SELECT changes()").fetchone()[0]
    
    conn.commit()
    conn.close()
    
    print(f"\n=== 清理后数据统计 ===")
    after = _counts(db_path)
    print(f"用户总数: {after['users']} (减少: {before['users'] - after['users']})")
    print(f"人物总数: {after['people']} (减少: {before['people'] - after['people']})")
    print(f"绑定申请总数: {after['requests']} (减少: {before['requests'] - after['requests']})")
    print(f"身份审计日志: {after['identity_audit']}")
    
    print(f"\n清理完成:")
    print(f"  删除用户: {deleted_users}")
    print(f"  删除人物: {deleted_people}")
    print(f"  删除绑定申请: {before['requests']}")
    
    return 0


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv or "-n" in sys.argv
    raise SystemExit(main(dry_run=dry_run))
