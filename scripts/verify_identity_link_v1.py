from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.security import authenticate_user, create_user, ensure_security_schema, permissions_for
from app.services.identity_link_service import (
    IdentityLinkError,
    approve_link_request,
    cancel_link_request,
    create_link_request,
    ensure_identity_link_schema,
    identity_context,
    reject_link_request,
    unlink_user_person,
)


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
    print(f"==============")


def assert_true(value: bool, message: str) -> None:
    if not value:
        raise AssertionError(message)


def expect_error(code: str, fn) -> None:
    try:
        fn()
    except IdentityLinkError as exc:
        if exc.code != code:
            raise AssertionError(f"expected {code}, got {exc.code}: {exc.message}") from exc
        return
    raise AssertionError(f"expected error {code}")


def seed_people(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS people(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute("INSERT INTO people(external_id,name,created_at) VALUES ('PER-001','张三','2026-07-03T00:00:00')")
        conn.execute("INSERT INTO people(external_id,name,created_at) VALUES ('PER-002','李四','2026-07-03T00:00:00')")


def audit_count(db_path: Path) -> int:
    with sqlite3.connect(db_path) as conn:
        return int(conn.execute("SELECT COUNT(*) FROM v05a_audit_logs WHERE action LIKE 'identity_%'").fetchone()[0])


def main() -> int:
    _diagnose_env()
    with tempfile.TemporaryDirectory(prefix="identity_link_v1_", ignore_cleanup_errors=True) as tmp:
        db_path = Path(tmp) / "app.db"
        seed_people(db_path)
        ensure_security_schema(db_path, allow_migration=True)
        ensure_identity_link_schema(db_path, allow_migration=True)

        admin = create_user("admin_user", "管理员", "IdentityPass2026", "admin", db_path=db_path)
        reviewer = create_user("reviewer_user", "审核员", "IdentityPass2026", "reviewer", db_path=db_path)
        user1 = create_user("normal_user", "普通用户", "IdentityPass2026", "viewer", db_path=db_path)
        user2 = create_user("second_user", "第二用户", "IdentityPass2026", "viewer", db_path=db_path)

        ctx = identity_context(int(user1["id"]), db_path=db_path)
        assert_true(ctx["link_status"] == "unlinked" and ctx["person"] is None, "未绑定用户查询身份失败")

        req1 = create_link_request(int(user1["id"]), 1, "本人账号绑定", user1, db_path=db_path)
        assert_true(req1["status"] == "pending" and req1["status_label"] == "待审核", "发起绑定申请失败")
        expect_error("PENDING_REQUEST_EXISTS", lambda: create_link_request(int(user1["id"]), 2, "重复申请", user1, db_path=db_path))
        expect_error("PERSON_NOT_FOUND", lambda: create_link_request(int(user2["id"]), 999, "不存在", user2, db_path=db_path))

        approved = approve_link_request(int(req1["id"]), reviewer, db_path=db_path)
        assert_true(approved["status"] == "approved", "管理员批准失败")
        linked = identity_context(int(user1["id"]), db_path=db_path)
        assert_true(linked["link_status"] == "linked" and linked["person"]["id"] == 1, "批准后 User 和 Person 未正确绑定")
        approve_link_request(int(req1["id"]), reviewer, db_path=db_path)
        expect_error("PERSON_ALREADY_LINKED", lambda: create_link_request(int(user2["id"]), 1, "占用人物", user2, db_path=db_path))
        expect_error("USER_ALREADY_LINKED", lambda: create_link_request(int(user1["id"]), 2, "占用账号", user1, db_path=db_path))

        req2 = create_link_request(int(user2["id"]), 2, "绑定李四", user2, db_path=db_path)
        rejected = reject_link_request(int(req2["id"]), "身份信息无法核验", reviewer, db_path=db_path)
        assert_true(rejected["status"] == "rejected", "拒绝申请失败")
        reject_link_request(int(req2["id"]), "身份信息无法核验", reviewer, db_path=db_path)

        req3 = create_link_request(int(user2["id"]), 2, "重新申请", user2, db_path=db_path)
        cancelled = cancel_link_request(int(user2["id"]), user2, db_path=db_path)
        assert_true(cancelled["id"] == req3["id"] and cancelled["status"] == "cancelled", "取消申请失败")
        expect_error("NO_PENDING_REQUEST", lambda: cancel_link_request(int(user2["id"]), user2, db_path=db_path))

        unlinked = unlink_user_person(int(user1["id"]), "管理员解除绑定", admin, db_path=db_path)
        assert_true(unlinked["link_status"] == "unlinked", "管理员解除绑定失败")
        after_unlink = identity_context(int(user1["id"]), db_path=db_path)
        assert_true(after_unlink["person"] is None, "解除后 User 仍有绑定")
        with sqlite3.connect(db_path) as conn:
            person_exists = conn.execute("SELECT COUNT(*) FROM people WHERE id=1").fetchone()[0]
            user_exists = conn.execute("SELECT COUNT(*) FROM v05a_users WHERE id=?", (user1["id"],)).fetchone()[0]
        assert_true(person_exists == 1 and user_exists == 1, "解除后 User 或 Person 被误删")

        viewer_permissions = permissions_for(user2)
        reviewer_permissions = permissions_for(reviewer)
        admin_permissions = permissions_for(admin)
        assert_true("identity.view_self" in viewer_permissions and "identity.request_link" in viewer_permissions, "普通用户身份权限缺失")
        assert_true("identity.review_link" not in viewer_permissions, "普通用户不应有审核权限")
        assert_true("identity.review_link" in reviewer_permissions, "审核员身份审核权限缺失")
        assert_true("identity.unlink" in admin_permissions, "管理员解除绑定权限缺失")

        logged_in, error = authenticate_user("normal_user", "IdentityPass2026", db_path=db_path)
        assert_true(logged_in is not None and not error, "现有登录函数异常")
        assert_true(audit_count(db_path) >= 5, "身份绑定审计日志缺失")

    print("verify_identity_link_v1 passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

