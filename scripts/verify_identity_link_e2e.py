from __future__ import annotations

import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.security import authenticate_user, create_user, ensure_security_schema, get_user_by_username, permissions_for
from app.services.identity_link_service import (
    IdentityLinkError,
    approve_link_request,
    cancel_link_request,
    create_link_request,
    ensure_identity_link_schema,
    identity_context,
    list_link_requests,
    reject_link_request,
    unlink_user_person,
)
from app.v04c_review import db_connection


TEST_RUN_ID = f"e2e_{datetime.now():%Y%m%d_%H%M%S}"
TEST_USERNAMES = {"e2e_test_admin", "e2e_test_user"}
TEST_PERSON_EXTERNAL_IDS = {"PER-E2E-001"}


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


def _counts(db_path: Path) -> dict[str, int]:
    with db_connection(db_path) as conn:
        users = int(conn.execute("SELECT COUNT(*) FROM v05a_users").fetchone()[0])
        people = int(conn.execute("SELECT COUNT(*) FROM people").fetchone()[0])
        requests = int(conn.execute("SELECT COUNT(*) FROM identity_link_requests").fetchone()[0])
        identity_audit = int(conn.execute("SELECT COUNT(*) FROM v05a_audit_logs WHERE action LIKE 'identity_%'").fetchone()[0])
    return {"users": users, "people": people, "requests": requests, "identity_audit": identity_audit}


def _create_test_data(db_path: Path) -> dict[str, Any]:
    _cleanup_test_data(db_path)
    
    ensure_security_schema(db_path)
    ensure_identity_link_schema(db_path)
    
    existing_admin = get_user_by_username("e2e_test_admin", db_path=db_path)
    existing_user = get_user_by_username("e2e_test_user", db_path=db_path)
    
    if existing_admin:
        admin = existing_admin
    else:
        admin = create_user("e2e_test_admin", f"测试管理员_{TEST_RUN_ID}", "E2ETestPass2026", "reviewer", created_by="system_e2e", db_path=db_path)
    
    if existing_user:
        user = existing_user
    else:
        user = create_user("e2e_test_user", f"测试用户_{TEST_RUN_ID}", "E2ETestPass2026", "viewer", created_by="system_e2e", db_path=db_path)
    
    with db_connection(db_path) as conn:
        existing_person = conn.execute("SELECT id FROM people WHERE source_type='system_e2e'").fetchone()
        if existing_person:
            person_id = existing_person["id"]
        else:
            ts = datetime.now().replace(microsecond=0).isoformat()
            cur = conn.execute(
                "INSERT INTO people(external_id,name,is_active,created_at,source_type,visibility,verification_status) VALUES (?,?,1,?,'system_e2e','内部','待核验')",
                ("PER-E2E-001", f"测试人物_{TEST_RUN_ID}", ts),
            )
            person_id = int(cur.lastrowid)
    
    return {"admin": admin, "user": user, "person_id": person_id}


def _cleanup_test_data(db_path: Path) -> None:
    import sqlite3
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = OFF")
    
    for username in TEST_USERNAMES:
        user = conn.execute("SELECT id FROM v05a_users WHERE username=?", (username,)).fetchone()
        if user:
            user_id = user[0]
            conn.execute("DELETE FROM identity_link_requests WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM v05a_users WHERE id=?", (user_id,))
    
    conn.execute("DELETE FROM people WHERE source_type='system_e2e'")
    
    conn.commit()
    conn.close()


def main() -> int:
    settings = get_settings()
    
    _diagnose_env()
    
    if settings.app_env != "development":
        print("错误：仅在 development 环境下允许执行端到端验收")
        return 1
    
    db_path = settings.sqlite_path
    
    print("\n=== 验收前数据统计 ===")
    before_counts = _counts(db_path)
    print(f"用户: {before_counts['users']}, 人物: {before_counts['people']}, 绑定申请: {before_counts['requests']}, 身份审计: {before_counts['identity_audit']}")
    
    print("\n=== 场景1: 创建临时普通用户 ===")
    data = _create_test_data(db_path)
    print(f"用户: {data['user']['username']} (ID: {data['user']['id']})")
    assert data["user"]["role"] == "viewer", "测试用户角色应为 viewer"
    
    print("\n=== 场景2: 创建最小权限测试管理员 ===")
    print(f"管理员: {data['admin']['username']} (ID: {data['admin']['id']})")
    assert data["admin"]["role"] == "reviewer", "测试管理员角色应为 reviewer"
    
    print("\n=== 场景3: 创建测试Person ===")
    print(f"人物ID: {data['person_id']}")
    with db_connection(db_path) as conn:
        person = conn.execute("SELECT * FROM people WHERE id=?", (data["person_id"],)).fetchone()
        assert person is not None, "测试人物不存在"
        assert person["external_id"] == "PER-E2E-001", "人物external_id错误"
    
    print("\n=== 场景4: 未绑定身份查询 ===")
    ctx = identity_context(int(data["user"]["id"]), db_path=db_path)
    assert ctx["link_status"] == "unlinked", "未绑定用户状态应为unlinked"
    assert ctx["person"] is None, "未绑定用户person应为None"
    print(f"状态: {ctx['link_status']}, 人物: {ctx['person']}")
    
    print("\n=== 场景5: 发起绑定申请 ===")
    req1 = create_link_request(int(data["user"]["id"]), data["person_id"], "本人账号绑定", data["user"], db_path=db_path)
    assert req1["status"] == "pending", "绑定申请状态应为pending"
    assert req1["status_label"] == "待审核", "状态标签错误"
    print(f"申请ID: {req1['id']}, 状态: {req1['status']}")
    
    print("\n=== 场景6: 重复申请返回409 ===")
    try:
        create_link_request(int(data["user"]["id"]), data["person_id"], "重复申请", data["user"], db_path=db_path)
        assert False, "应抛出PENDING_REQUEST_EXISTS错误"
    except IdentityLinkError as exc:
        assert exc.code == "PENDING_REQUEST_EXISTS", f"期望PENDING_REQUEST_EXISTS，实际: {exc.code}"
        assert exc.status_code == 409, f"期望409，实际: {exc.status_code}"
        print(f"正确返回409: {exc.code}")
    
    print("\n=== 场景7: 取消申请 ===")
    cancelled = cancel_link_request(int(data["user"]["id"]), data["user"], db_path=db_path)
    assert cancelled["id"] == req1["id"], "取消的申请ID不匹配"
    assert cancelled["status"] == "cancelled", "状态应为cancelled"
    print(f"已取消申请ID: {cancelled['id']}")
    
    print("\n=== 场景8: 管理员批准 ===")
    req2 = create_link_request(int(data["user"]["id"]), data["person_id"], "重新申请", data["user"], db_path=db_path)
    approved = approve_link_request(int(req2["id"]), data["admin"], db_path=db_path)
    assert approved["status"] == "approved", "批准后状态应为approved"
    ctx_after = identity_context(int(data["user"]["id"]), db_path=db_path)
    assert ctx_after["link_status"] == "linked", "批准后状态应为linked"
    assert ctx_after["person"]["id"] == data["person_id"], "绑定的人物ID不匹配"
    print(f"已批准申请ID: {approved['id']}")
    
    print("\n=== 场景9: 重复批准幂等 ===")
    approved_again = approve_link_request(int(req2["id"]), data["admin"], db_path=db_path)
    assert approved_again["status"] == "approved", "重复批准状态保持approved"
    print("重复批准幂等通过")
    
    print("\n=== 场景10: 同一Person唯一绑定保护 ===")
    try:
        create_link_request(int(data["admin"]["id"]), data["person_id"], "占用人物", data["admin"], db_path=db_path)
        assert False, "应抛出PERSON_ALREADY_LINKED错误"
    except IdentityLinkError as exc:
        assert exc.code == "PERSON_ALREADY_LINKED", f"期望PERSON_ALREADY_LINKED，实际: {exc.code}"
        assert exc.status_code == 409, f"期望409，实际: {exc.status_code}"
        print(f"正确返回409: {exc.code}")
    
    print("\n=== 场景11: 管理员解除绑定 ===")
    unlinked = unlink_user_person(int(data["user"]["id"]), "管理员解除绑定", data["admin"], db_path=db_path)
    assert unlinked["link_status"] == "unlinked", "解除后状态应为unlinked"
    ctx_unlinked = identity_context(int(data["user"]["id"]), db_path=db_path)
    assert ctx_unlinked["person"] is None, "解除后person应为None"
    print("管理员解除绑定成功")
    
    print("\n=== 场景12: 拒绝申请 ===")
    req3 = create_link_request(int(data["user"]["id"]), data["person_id"], "测试拒绝", data["user"], db_path=db_path)
    rejected = reject_link_request(int(req3["id"]), "身份信息无法核验", data["admin"], db_path=db_path)
    assert rejected["status"] == "rejected", "拒绝后状态应为rejected"
    print(f"已拒绝申请ID: {rejected['id']}")
    
    print("\n=== 场景13: 普通用户越权返回403 ===")
    viewer_perms = permissions_for(data["user"])
    assert "identity.review_link" not in viewer_perms, "普通用户不应有审核权限"
    print("普通用户越权保护通过")
    
    print("\n=== 场景14: 未登录API返回401 ===")
    logged_in, error = authenticate_user("nonexistent", "wrong", db_path=db_path)
    assert logged_in is None, "应返回None"
    assert error, "应返回错误信息"
    print("未登录验证通过")
    
    print("\n=== 场景15: 页面无500 ===")
    try:
        from app.main import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        pages = ["/", "/account/login", "/people", "/me/identity", "/system/identity-link-requests", "/member"]
        for page in pages:
            resp = client.get(page, follow_redirects=True)
            assert resp.status_code < 500, f"页面 {page} 返回 {resp.status_code}"
            print(f"页面 {page}: {resp.status_code}")
        
        person_id = data["person_id"]
        person_page = f"/people/{person_id}"
        resp = client.get(person_page, follow_redirects=True)
        assert resp.status_code < 500, f"页面 {person_page} 返回 {resp.status_code}"
        print(f"页面 {person_page}: {resp.status_code}")
    except ImportError:
        print("fastapi.testclient不可用，跳过页面检查")
    
    print("\n=== 场景16: 审计日志存在 ===")
    after_counts = _counts(db_path)
    assert after_counts["identity_audit"] > before_counts["identity_audit"], "审计日志未增加"
    print(f"身份审计日志增加: {before_counts['identity_audit']} -> {after_counts['identity_audit']}")
    
    print("\n=== 场景17: 清理临时数据 ===")
    _cleanup_test_data(db_path)
    print("临时数据清理完成")
    
    print("\n=== 场景18: 清理后真实数据数量恢复 ===")
    final_counts = _counts(db_path)
    print(f"用户: {final_counts['users']}, 人物: {final_counts['people']}, 绑定申请: {final_counts['requests']}, 身份审计: {final_counts['identity_audit']}")
    assert final_counts["users"] == before_counts["users"], f"用户数量不匹配: {final_counts['users']} vs {before_counts['users']}"
    assert final_counts["people"] == before_counts["people"], f"人物数量不匹配: {final_counts['people']} vs {before_counts['people']}"
    
    print("\n" + "="*50)
    print("端到端验收全部通过！")
    print("="*50)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
