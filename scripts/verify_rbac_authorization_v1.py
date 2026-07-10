from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.security import permissions_for, required_permission
from app.services.authorization_service import (
    AuthorizationError,
    assign_organization_role,
    build_authorization_context,
    filter_person_fields,
    list_permissions_for_actor,
    list_roles_for_actor,
    revoke_organization_role,
    revoke_system_role,
)
from app.services.membership_person_link_service import bind_person
from app.services.membership_user_link_service import bind_user as bind_membership_user
from app.services.organization_access_service import (
    bind_membership_to_organization,
    bind_user_to_organization,
    create_organization,
    update_organization,
)
from app.v04c_review import db_connection, default_db_path
from scripts.migrate_organization_core_v1 import migrate as migrate_org
from scripts.migrate_rbac_core_v1 import migrate as migrate_rbac

TEST_PREFIX = f"RBAC-{datetime.now():%Y%m%d%H%M%S}"


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def check(results: list[bool], name: str, func) -> None:
    try:
        func()
        print(f"PASS {name}")
        results.append(True)
    except Exception as exc:
        print(f"FAIL {name}: {exc}")
        results.append(False)


def expect_error(code_or_status, func) -> None:
    try:
        func()
    except AuthorizationError as exc:
        if isinstance(code_or_status, int):
            assert exc.status_code == code_or_status, f"expected {code_or_status}, got {exc.status_code}/{exc.code}"
        else:
            assert exc.code == code_or_status, f"expected {code_or_status}, got {exc.code}"
        return
    raise AssertionError(f"expected error {code_or_status}")


def cleanup(db_path: Path) -> None:
    with db_connection(db_path) as conn:
        org_ids = [r[0] for r in conn.execute("SELECT id FROM organizations WHERE organization_no LIKE ? OR external_id LIKE ?", (f"ORG-{TEST_PREFIX}%", f"ORG-{TEST_PREFIX}%")).fetchall()]
        if org_ids:
            marks = ",".join("?" for _ in org_ids)
            conn.execute(f"DELETE FROM organization_user_roles WHERE organization_id IN ({marks})", org_ids)
            conn.execute(f"DELETE FROM organization_membership_links WHERE organization_id IN ({marks})", org_ids)
            conn.execute(f"DELETE FROM organization_user_links WHERE organization_id IN ({marks})", org_ids)
            conn.execute(f"DELETE FROM organization_access_audit WHERE organization_id IN ({marks})", org_ids)
            conn.execute(f"DELETE FROM authorization_audit_logs WHERE organization_id IN ({marks})", org_ids)
            conn.execute(f"DELETE FROM organizations WHERE id IN ({marks})", org_ids)
        mids = [r[0] for r in conn.execute("SELECT id FROM v04f_club_memberships WHERE member_no LIKE ?", (f"QBM-{TEST_PREFIX}%",)).fetchall()]
        if mids:
            marks = ",".join("?" for _ in mids)
            conn.execute(f"DELETE FROM organization_membership_links WHERE membership_id IN ({marks})", mids)
            conn.execute(f"DELETE FROM membership_user_link_audit WHERE membership_id IN ({marks})", mids)
            conn.execute(f"DELETE FROM membership_user_link_requests WHERE membership_id IN ({marks})", mids)
            conn.execute(f"DELETE FROM membership_person_link_audit WHERE membership_id IN ({marks})", mids)
            conn.execute(f"DELETE FROM v04f_club_memberships WHERE id IN ({marks})", mids)
        conn.execute("DELETE FROM auth_user_roles WHERE user_id IN (SELECT id FROM v05a_users WHERE username LIKE ?)", (f"rbac_%",))
        conn.execute("DELETE FROM authorization_audit_logs WHERE target_user_id IN (SELECT id FROM v05a_users WHERE username LIKE ?)", (f"rbac_%",))
        conn.execute("DELETE FROM v05a_users WHERE username LIKE ?", (f"rbac_{TEST_PREFIX.lower()}%",))
        conn.execute("DELETE FROM people WHERE external_id LIKE ?", (f"PER-{TEST_PREFIX}%",))
        conn.commit()


def create_user(conn, key: str, role: str = "viewer") -> int:
    ts = now_iso()
    return int(conn.execute(
        "INSERT INTO v05a_users(username,password_hash,display_name,role,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
        (f"rbac_{TEST_PREFIX.lower()}_{key}", "test-hash", f"RBAC验证{key}", role, "active", ts, ts),
    ).lastrowid)


def create_member(conn, key: str) -> int:
    ts = now_iso()
    return int(conn.execute(
        "INSERT INTO v04f_club_memberships(member_no,person_id,member_level,status,joined_at,created_at,updated_at) VALUES (?,NULL,'standard','active',?,?,?)",
        (f"QBM-{TEST_PREFIX}-{key}", ts, ts, ts),
    ).lastrowid)


def role_id(db_path: Path, key: str) -> int:
    with db_connection(db_path) as conn:
        return int(conn.execute("SELECT id FROM auth_roles WHERE role_key=?", (key,)).fetchone()[0])


def create_data(db_path: Path) -> dict[str, int]:
    with db_connection(db_path) as conn:
        admin = create_user(conn, "admin", "admin")
        a = create_user(conn, "a")
        b = create_user(conn, "b")
        c = create_user(conn, "c")
        d = create_user(conn, "d")
        member_a = create_member(conn, "A")
        member_b = create_member(conn, "B")
        member_c = create_member(conn, "C")
        person = int(conn.execute(
            "INSERT INTO people(external_id,name,is_active,created_at,source_type,visibility,verification_status,organization_network) VALUES (?,?,1,?,'system_verify','内部','待核验','投资人')",
            (f"PER-{TEST_PREFIX}-A", f"RBAC验证人物{TEST_PREFIX}", now_iso()),
        ).lastrowid)
        conn.execute("UPDATE v05a_users SET person_id=? WHERE id=?", (person, d))
        conn.commit()
    admin_user = {"id": admin, "username": f"rbac_{TEST_PREFIX.lower()}_admin", "role": "admin"}
    org_a = create_organization({"organization_no": f"ORG-{TEST_PREFIX}-A", "name": f"RBAC组织A-{TEST_PREFIX}"}, actor=admin_user, db_path=db_path)["organization_id"]
    org_b = create_organization({"organization_no": f"ORG-{TEST_PREFIX}-B", "name": f"RBAC组织B-{TEST_PREFIX}"}, actor=admin_user, db_path=db_path)["organization_id"]
    org_c = create_organization({"organization_no": f"ORG-{TEST_PREFIX}-C", "name": f"RBAC组织C-{TEST_PREFIX}"}, actor=admin_user, db_path=db_path)["organization_id"]
    return {"admin": admin, "a": a, "b": b, "c": c, "d": d, "member_a": member_a, "member_b": member_b, "member_c": member_c, "person": person, "org_a": org_a, "org_b": org_b, "org_c": org_c}


def actor(data: dict[str, int], key: str, role: str = "viewer") -> dict:
    return {"id": data[key], "username": f"rbac_{TEST_PREFIX.lower()}_{key}", "role": role}


def run_existing(script: str) -> None:
    result = subprocess.run([str(ROOT / ".venv" / "Scripts" / "python.exe"), str(ROOT / script)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=240)
    if result.returncode != 0:
        raise AssertionError(result.stdout[-1500:])


def main() -> int:
    db_path = default_db_path()
    migrate_org(db_path, backup=False)
    migrate_rbac(db_path, backup=False)
    cleanup(db_path)
    data = create_data(db_path)
    admin = actor(data, "admin", "admin")
    user_a = actor(data, "a")
    user_b = actor(data, "b")
    user_c = actor(data, "c")
    user_d = actor(data, "d")
    results: list[bool] = []
    try:
        bind_user_to_organization(data["org_a"], data["a"], actor=admin, db_path=db_path)
        bind_user_to_organization(data["org_a"], data["b"], actor=admin, db_path=db_path)
        bind_user_to_organization(data["org_a"], data["c"], actor=admin, db_path=db_path)
        bind_user_to_organization(data["org_b"], data["a"], actor=admin, db_path=db_path)
        bind_user_to_organization(data["org_b"], data["b"], actor=admin, db_path=db_path)
        bind_membership_to_organization(data["org_a"], data["member_a"], actor=admin, db_path=db_path)
        bind_membership_user(data["member_b"], data["b"], "RBAC验证", admin["username"], db_path=db_path)
        bind_person(data["member_c"], data["person"], "RBAC验证", admin["username"], db_path=db_path)
        assign_organization_role(admin, data["org_a"], data["a"], "organization_admin", db_path=db_path)
        assign_organization_role(admin, data["org_b"], data["a"], "organization_viewer", db_path=db_path)
        assign_organization_role(admin, data["org_a"], data["b"], "organization_editor", db_path=db_path)
        assign_organization_role(admin, data["org_a"], data["c"], "organization_viewer", db_path=db_path)
        check(results, "内置角色正确创建", lambda: assert_roles(db_path))
        check(results, "权限键唯一", lambda: assert_unique(db_path, "auth_permissions", "permission_key"))
        check(results, "角色权限不得重复", lambda: assert_role_permissions_unique(db_path))
        check(results, "User可在不同Organization拥有不同角色", lambda: assert_multi_org_roles(db_path, data))
        check(results, "组织角色只在对应组织生效", lambda: assert_org_role_scope(user_a, data, db_path))
        check(results, "User退出组织后角色立即失效", lambda: assert_role_loses_after_leave(data, user_b, admin, db_path))
        check(results, "Organization停用后组织角色立即失效", lambda: assert_role_loses_after_disable(data, user_a, admin, db_path))
        check(results, "organization_admin可管理本组织成员角色", lambda: assign_organization_role(user_a, data["org_a"], data["c"], "organization_member", db_path=db_path))
        check(results, "organization_admin不能管理其他组织", lambda: expect_error(403, lambda: assign_organization_role(user_a, data["org_b"], data["b"], "organization_member", db_path=db_path)))
        check(results, "organization_admin不能分配system_admin", lambda: expect_error(403, lambda: assign_organization_role(user_a, data["org_a"], data["c"], "system_admin", db_path=db_path)))
        check(results, "organization_admin不能分配platform_operator", lambda: expect_error(403, lambda: assign_organization_role(user_a, data["org_a"], data["c"], "platform_operator", db_path=db_path)))
        check(results, "organization_editor不能管理角色", lambda: expect_error(403, lambda: assign_organization_role(user_b, data["org_a"], data["c"], "organization_member", db_path=db_path)))
        check(results, "organization_member不能管理角色", lambda: assert_member_cannot_manage(data, user_c, db_path))
        check(results, "organization_viewer不能执行写操作", lambda: assert_viewer_readonly(user_c, data, db_path))
        check(results, "普通用户不能给自己提权", lambda: expect_error(403, lambda: assign_organization_role(user_c, data["org_a"], data["c"], "organization_admin", db_path=db_path)))
        check(results, "普通用户不能调用角色分配接口", lambda: assert_role_api_requires_service())
        check(results, "最后一个organization_admin不能被普通撤销", lambda: expect_error("LAST_ORGANIZATION_ADMIN", lambda: revoke_organization_role(admin, data["org_a"], data["a"], role_id(db_path, "organization_admin"), db_path=db_path)))
        check(results, "最后一个system_admin不能被普通撤销", lambda: assert_last_system_admin_protected(db_path))
        check(results, "system_admin可以管理平台范围", lambda: assert_system_admin_context(admin, db_path))
        check(results, "manage_club现有管理员仍然有效", lambda: assert_manage_club_compat(admin, db_path))
        check(results, "无权限访问返回403", lambda: expect_error(403, lambda: build_authorization_context(user_c, organization_id=data["org_b"], db_path=db_path)))
        check(results, "不存在资源返回404", lambda: expect_error(404, lambda: build_authorization_context(user_c, organization_id=999999999, db_path=db_path)))
        check(results, "多组织上下文切换正确", lambda: assert_switch_context(user_a, data, db_path))
        check(results, "非法organization_id切换被拒绝", lambda: expect_error(403, lambda: build_authorization_context(user_a, organization_id=data["org_c"], db_path=db_path)))
        check(results, "合法membership_id上下文正确", lambda: assert_membership_context(user_b, data, db_path))
        check(results, "非法membership_id切换被拒绝", lambda: expect_error(403, lambda: build_authorization_context(user_a, membership_id=data["member_b"], db_path=db_path)))
        check(results, "User-Person不自动产生组织权限", lambda: assert_no_org_from_person(user_d, db_path))
        check(results, "Person-Membership不自动产生会员权限", lambda: assert_no_member_from_person_membership(user_d, db_path))
        check(results, "Membership-Organization不自动产生用户组织权限", lambda: assert_no_org_from_membership_org(user_d, data, db_path))
        check(results, "产业身份标签不影响系统权限", lambda: assert_industry_profile_no_auth(user_d, db_path))
        check(results, "敏感字段不会泄露给无权用户", lambda: assert_sensitive_fields_filtered(user_c, data, db_path))
        check(results, "审计日志记录角色变更", lambda: assert_audit_exists(db_path, data["org_a"]))
        check(results, "权限变更后立即生效", lambda: assert_permission_change_immediate(data, user_c, admin, db_path))
        check(results, "迁移重复执行安全", lambda: (migrate_rbac(db_path, backup=False), migrate_rbac(db_path, backup=False)))
        check(results, "v0.5E专项验证继续通过", lambda: [run_existing(s) for s in ["scripts/verify_identity_link_v1.py", "scripts/verify_membership_person_link_v1.py", "scripts/verify_user_membership_link_v1.py", "scripts/verify_identity_membership_access_v1.py"]])
        check(results, "v0.5F专项验证继续通过", lambda: run_existing("scripts/verify_organization_core_v1.py"))
    finally:
        cleanup(db_path)
    print("=" * 60)
    print(f"测试结果: {sum(results)}/{len(results)} 通过")
    return 0 if all(results) else 1


def assert_roles(db_path: Path) -> None:
    with db_connection(db_path) as conn:
        roles = {r[0] for r in conn.execute("SELECT role_key FROM auth_roles WHERE status='active'")}
    assert {"system_admin", "platform_operator", "organization_admin", "organization_editor", "organization_member", "organization_viewer"}.issubset(roles)


def assert_unique(db_path: Path, table: str, col: str) -> None:
    with db_connection(db_path) as conn:
        dup = conn.execute(f"SELECT {col},COUNT(*) c FROM {table} GROUP BY {col} HAVING c>1 LIMIT 1").fetchone()
    assert dup is None


def assert_role_permissions_unique(db_path: Path) -> None:
    with db_connection(db_path) as conn:
        dup = conn.execute("SELECT role_id,permission_id,COUNT(*) c FROM auth_role_permissions GROUP BY role_id,permission_id HAVING c>1 LIMIT 1").fetchone()
    assert dup is None


def assert_multi_org_roles(db_path: Path, data: dict[str, int]) -> None:
    with db_connection(db_path) as conn:
        rows = conn.execute("SELECT organization_id,role_key FROM organization_user_roles ur JOIN auth_roles r ON r.id=ur.role_id WHERE ur.user_id=? AND ur.status='active'", (data["a"],)).fetchall()
    assert (data["org_a"], "organization_admin") in [(r[0], r[1]) for r in rows]
    assert (data["org_b"], "organization_viewer") in [(r[0], r[1]) for r in rows]


def assert_org_role_scope(user, data, db_path):
    ctx_a = build_authorization_context(user, organization_id=data["org_a"], db_path=db_path)
    ctx_b = build_authorization_context(user, organization_id=data["org_b"], db_path=db_path)
    assert "organization:manage_roles" in ctx_a.permission_keys
    assert "organization:manage_roles" not in ctx_b.permission_keys


def assert_role_loses_after_leave(data, user, admin, db_path):
    from app.services.organization_access_service import unbind_user_from_organization
    unbind_user_from_organization(data["org_a"], data["b"], actor=admin, db_path=db_path)
    ctx = build_authorization_context(user, db_path=db_path)
    assert "organization_editor" not in ctx.organization_role_keys


def assert_role_loses_after_disable(data, user, admin, db_path):
    update_organization(data["org_b"], {"status": "inactive"}, actor=admin, db_path=db_path)
    expect_error(403, lambda: build_authorization_context(user, organization_id=data["org_b"], db_path=db_path))


def assert_member_cannot_manage(data, user, db_path):
    assign_organization_role({"id": data["admin"], "username": "admin", "role": "admin"}, data["org_a"], data["c"], "organization_member", db_path=db_path)
    expect_error(403, lambda: assign_organization_role(user, data["org_a"], data["b"], "organization_viewer", db_path=db_path))


def assert_viewer_readonly(user, data, db_path):
    ctx = build_authorization_context(user, organization_id=data["org_a"], db_path=db_path)
    assert "data:write" not in ctx.permission_keys


def assert_role_api_requires_service():
    assert required_permission(f"/api/v1/organizations/1/users/1/roles", "POST") == "view_internal"


def assert_last_system_admin_protected(db_path: Path):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".db") as tmp:
        tmp_path = Path(tmp.name)
    shutil.copy2(db_path, tmp_path)
    try:
        with db_connection(tmp_path) as conn:
            conn.execute("UPDATE v05a_users SET role='viewer' WHERE role='admin'")
            rid = role_id(tmp_path, "system_admin")
            row = conn.execute("SELECT id FROM v05a_users ORDER BY id LIMIT 1").fetchone()
            if row:
                uid = int(row[0])
            else:
                uid = int(conn.execute("INSERT INTO v05a_users(username,password_hash,display_name,role,status,created_at,updated_at) VALUES ('rbac_temp_admin','x','临时系统管理员','viewer','active',datetime('now'),datetime('now'))").lastrowid)
            conn.execute("INSERT OR IGNORE INTO auth_user_roles(user_id,role_id,status,assigned_at,created_at,updated_at) VALUES (?,?,'active',datetime('now'),datetime('now'),datetime('now'))", (uid, rid))
            conn.commit()
        expect_error("LAST_SYSTEM_ADMIN", lambda: revoke_system_role({"id": uid, "username": "temp", "role": "admin"}, uid, rid, db_path=tmp_path))
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def assert_system_admin_context(admin, db_path):
    ctx = build_authorization_context(admin, db_path=db_path)
    assert ctx.is_system_admin
    assert "platform" in ctx.available_data_scopes


def assert_manage_club_compat(admin, db_path):
    assert "manage_club" in permissions_for(admin)
    ctx = build_authorization_context(admin, db_path=db_path)
    assert ctx.is_system_admin


def assert_switch_context(user, data, db_path):
    ctx = build_authorization_context(user, organization_id=data["org_a"], db_path=db_path)
    assert ctx.active_organization_id == data["org_a"]


def assert_membership_context(user, data, db_path):
    ctx = build_authorization_context(user, membership_id=data["member_b"], db_path=db_path)
    assert ctx.active_membership_id == data["member_b"]
    assert "membership" in ctx.available_data_scopes


def assert_no_org_from_person(user, db_path):
    ctx = build_authorization_context(user, db_path=db_path)
    assert ctx.accessible_organization_ids == ()


def assert_no_member_from_person_membership(user, db_path):
    ctx = build_authorization_context(user, db_path=db_path)
    assert ctx.accessible_membership_ids == ()


def assert_no_org_from_membership_org(user, data, db_path):
    ctx = build_authorization_context(user, db_path=db_path)
    assert data["org_a"] not in ctx.accessible_organization_ids


def assert_industry_profile_no_auth(user, db_path):
    ctx = build_authorization_context(user, db_path=db_path)
    assert "organization:manage_roles" not in ctx.permission_keys


def assert_sensitive_fields_filtered(user, data, db_path):
    ctx = build_authorization_context(user, organization_id=data["org_a"], db_path=db_path)
    filtered = filter_person_fields({"name": "张三", "mobile": "13800000000", "email": "a@example.com"}, ctx)
    assert "mobile" not in filtered and "email" not in filtered


def assert_audit_exists(db_path, org_id):
    with db_connection(db_path) as conn:
        count = int(conn.execute("SELECT COUNT(*) FROM authorization_audit_logs WHERE organization_id=?", (org_id,)).fetchone()[0])
    assert count > 0


def assert_permission_change_immediate(data, user, admin, db_path):
    assign_organization_role(admin, data["org_a"], data["c"], "organization_editor", db_path=db_path)
    ctx = build_authorization_context(user, organization_id=data["org_a"], db_path=db_path)
    assert "data:write" in ctx.permission_keys


if __name__ == "__main__":
    raise SystemExit(main())

