from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.security import create_user, ensure_security_schema, get_user_by_username
from app.services.identity_link_service import ensure_identity_link_schema
from app.v04c_review import db_connection


TEST_RUN_ID = f"e2e_{datetime.now():%Y%m%d_%H%M%S}"


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
    print(f"允许创建测试账号: {'是' if settings.app_env == 'development' else '否'}")
    print(f"test_run_id: {TEST_RUN_ID}")
    print(f"==============")


def main() -> int:
    settings = get_settings()
    
    _diagnose_env()
    
    if settings.app_env != "development":
        print("错误：仅在 development 环境下允许创建测试账号")
        return 1
    
    db_path = settings.sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    
    ensure_security_schema(db_path, allow_migration=True)
    ensure_identity_link_schema(db_path, allow_migration=True)
    
    print("\n=== 创建测试数据 ===")
    
    existing_admin = get_user_by_username("e2e_test_admin", db_path=db_path)
    existing_user = get_user_by_username("e2e_test_user", db_path=db_path)
    
    if existing_admin:
        print(f"测试管理员 e2e_test_admin 已存在 (ID: {existing_admin['id']})")
        admin = existing_admin
    else:
        admin = create_user("e2e_test_admin", f"测试管理员_{TEST_RUN_ID}", "E2ETestPass2026", "reviewer", created_by="system_e2e", db_path=db_path)
        print(f"已创建测试管理员: {admin['username']} (ID: {admin['id']})")
    
    if existing_user:
        print(f"测试用户 e2e_test_user 已存在 (ID: {existing_user['id']})")
        user = existing_user
    else:
        user = create_user("e2e_test_user", f"测试用户_{TEST_RUN_ID}", "E2ETestPass2026", "viewer", created_by="system_e2e", db_path=db_path)
        print(f"已创建测试用户: {user['username']} (ID: {user['id']})")
    
    with db_connection(db_path) as conn:
        existing_person = conn.execute(
            "SELECT id,external_id,name FROM people WHERE external_id=?",
            ("PER-E2E-001",)
        ).fetchone()
        
        if existing_person:
            print(f"测试人物 PER-E2E-001 已存在 (ID: {existing_person['id']})")
            person_id = existing_person["id"]
        else:
            ts = datetime.now().replace(microsecond=0).isoformat()
            cur = conn.execute(
                """
                INSERT INTO people(external_id,name,is_active,created_at,source_type)
                VALUES (?,?,1,?,'system_e2e')
                """,
                ("PER-E2E-001", f"测试人物_{TEST_RUN_ID}", ts),
            )
            person_id = int(cur.lastrowid)
            print(f"已创建测试人物: PER-E2E-001 (ID: {person_id})")
    
    print(f"\n测试数据创建完成")
    print(f"test_run_id: {TEST_RUN_ID}")
    print(f"admin_id: {admin['id']}")
    print(f"user_id: {user['id']}")
    print(f"person_id: {person_id}")
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
