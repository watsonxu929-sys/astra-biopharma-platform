from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.security import permissions_for, required_permission
from app.services.membership_user_link_service import bind_user as bind_membership_user
from app.services.organization_access_service import (
    OrganizationAccessError,
    bind_membership_to_organization,
    bind_user_to_organization,
    create_organization,
    get_accessible_organization_or_403,
    get_organization_context,
    get_user_organizations,
    list_organization_memberships,
    unbind_user_from_organization,
    update_organization,
)
from app.v04c_review import db_connection, default_db_path
from scripts.migrate_organization_core_v1 import migrate as migrate_organization_core

TEST_PREFIX = f"OCV1-{datetime.now():%Y%m%d%H%M%S}"


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
    except OrganizationAccessError as exc:
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
            conn.execute(f"DELETE FROM organization_membership_links WHERE organization_id IN ({marks})", org_ids)
            conn.execute(f"DELETE FROM organization_user_links WHERE organization_id IN ({marks})", org_ids)
            conn.execute(f"DELETE FROM organization_access_audit WHERE organization_id IN ({marks})", org_ids)
            conn.execute(f"DELETE FROM organizations WHERE id IN ({marks})", org_ids)
        mids = [r[0] for r in conn.execute("SELECT id FROM v04f_club_memberships WHERE member_no LIKE ?", (f"QBM-{TEST_PREFIX}%",)).fetchall()]
        if mids:
            marks = ",".join("?" for _ in mids)
            conn.execute(f"DELETE FROM membership_user_link_audit WHERE membership_id IN ({marks})", mids)
            conn.execute(f"DELETE FROM membership_user_link_requests WHERE membership_id IN ({marks})", mids)
            conn.execute(f"DELETE FROM v04f_club_memberships WHERE id IN ({marks})", mids)
        conn.execute("DELETE FROM v05a_users WHERE username LIKE ?", (f"{TEST_PREFIX.lower()}_%",))
        conn.execute("DELETE FROM people WHERE external_id LIKE ?", (f"PER-{TEST_PREFIX}%",))
        conn.commit()


def create_user(conn, key: str, role: str = "viewer") -> int:
    ts = now_iso()
    return int(conn.execute(
        """
        INSERT INTO v05a_users(username,password_hash,display_name,role,status,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (f"{TEST_PREFIX.lower()}_{key}", "test-hash", f"组织验证{key}", role, "active", ts, ts),
    ).lastrowid)


def create_member(conn, key: str) -> int:
    ts = now_iso()
    return int(conn.execute(
        """
        INSERT INTO v04f_club_memberships(member_no,person_id,member_level,status,joined_at,created_at,updated_at)
        VALUES (?,NULL,'standard','active',?,?,?)
        """,
        (f"QBM-{TEST_PREFIX}-{key}", ts, ts, ts),
    ).lastrowid)


def create_data(db_path: Path) -> dict[str, int]:
    with db_connection(db_path) as conn:
        user_a = create_user(conn, "a")
        user_b = create_user(conn, "b")
        user_c = create_user(conn, "c")
        admin = create_user(conn, "admin", "admin")
        member_a = create_member(conn, "A")
        member_b = create_member(conn, "B")
        member_c = create_member(conn, "C")
        person_id = int(conn.execute(
            "INSERT INTO people(external_id,name,is_active,created_at,source_type,visibility,verification_status) VALUES (?,?,1,?,'system_verify','内部','待核验')",
            (f"PER-{TEST_PREFIX}-A", f"组织验证人物{TEST_PREFIX}", now_iso()),
        ).lastrowid)
        conn.execute("UPDATE v05a_users SET person_id=? WHERE id=?", (person_id, user_c))
        conn.commit()
    admin_user = {"id": admin, "username": f"{TEST_PREFIX.lower()}_admin", "role": "admin"}
    org_a = create_organization({"organization_no": f"ORG-{TEST_PREFIX}-A", "name": f"组织A-{TEST_PREFIX}", "organization_type": "company", "unified_social_credit_code": f"USCC-{TEST_PREFIX}-A"}, actor=admin_user, db_path=db_path)["organization_id"]
    org_b = create_organization({"organization_no": f"ORG-{TEST_PREFIX}-B", "name": f"组织B-{TEST_PREFIX}", "organization_type": "park", "unified_social_credit_code": f"USCC-{TEST_PREFIX}-B"}, actor=admin_user, db_path=db_path)["organization_id"]
    org_c = create_organization({"organization_no": f"ORG-{TEST_PREFIX}-C", "name": f"组织C-{TEST_PREFIX}", "organization_type": "service_provider"}, actor=admin_user, db_path=db_path)["organization_id"]
    return {"user_a": user_a, "user_b": user_b, "user_c": user_c, "admin": admin, "member_a": member_a, "member_b": member_b, "member_c": member_c, "person": person_id, "org_a": org_a, "org_b": org_b, "org_c": org_c}


def run_existing(script: str) -> None:
    result = subprocess.run([str(ROOT / ".venv" / "Scripts" / "python.exe"), str(ROOT / script)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=180)
    if result.returncode != 0:
        raise AssertionError(result.stdout[-1500:])


def main() -> int:
    db_path = default_db_path()
    migrate_organization_core(db_path, backup=False)
    cleanup(db_path)
    data = create_data(db_path)
    user_a = {"id": data["user_a"], "username": f"{TEST_PREFIX.lower()}_a", "role": "viewer"}
    user_b = {"id": data["user_b"], "username": f"{TEST_PREFIX.lower()}_b", "role": "viewer"}
    user_c = {"id": data["user_c"], "username": f"{TEST_PREFIX.lower()}_c", "role": "viewer"}
    admin = {"id": data["admin"], "username": f"{TEST_PREFIX.lower()}_admin", "role": "admin"}
    results: list[bool] = []
    try:
        check(results, "Organization 可以创建", lambda: assert_true(data["org_a"] > 0))
        check(results, "organization_no 唯一", lambda: expect_error("DUPLICATE_ORGANIZATION", lambda: create_organization({"organization_no": f"ORG-{TEST_PREFIX}-A", "name": "重复组织"}, actor=admin, db_path=db_path)))
        check(results, "非空统一社会信用代码唯一", lambda: expect_error("DUPLICATE_CREDIT_CODE", lambda: create_organization({"organization_no": f"ORG-{TEST_PREFIX}-D", "name": "重复信用代码", "unified_social_credit_code": f"USCC-{TEST_PREFIX}-A"}, actor=admin, db_path=db_path)))
        check(results, "同一User可以加入多个Organization", lambda: (bind_user_to_organization(data["org_a"], data["user_a"], actor=admin, db_path=db_path), bind_user_to_organization(data["org_b"], data["user_a"], actor=admin, db_path=db_path)))
        check(results, "一个Organization可以拥有多个User", lambda: bind_user_to_organization(data["org_a"], data["user_b"], actor=admin, db_path=db_path))
        check(results, "同一User-Organization不能重复有效绑定", lambda: expect_error("DUPLICATE_LINK", lambda: bind_user_to_organization(data["org_a"], data["user_a"], actor=admin, db_path=db_path)))
        check(results, "一个User最多一个有效主组织", lambda: assert_one_primary(db_path, data["user_a"]))
        check(results, "切换主组织后旧主组织取消", lambda: assert_switch_primary(db_path, data, admin))
        check(results, "普通用户只查看自己加入的Organization", lambda: assert_user_orgs(user_a, db_path, {data["org_a"], data["org_b"]}))
        check(results, "User A不能查看User B独占Organization", lambda: expect_error(403, lambda: get_accessible_organization_or_403(user_a, data["org_c"], db_path)))
        check(results, "修改URL organization_id无法越权", lambda: expect_error(403, lambda: get_accessible_organization_or_403(user_a, data["org_c"], db_path)))
        check(results, "无组织用户返回空上下文", lambda: assert_empty_context(user_c, db_path))
        check(results, "单组织用户返回正确默认组织", lambda: assert_single_context(user_b, db_path, data["org_a"]))
        check(results, "多组织用户返回可切换上下文", lambda: assert_multi_context(user_a, db_path))
        check(results, "User解绑后立即失去访问权", lambda: assert_unbind_loses_access(data, user_b, admin, db_path))
        check(results, "停用组织后普通用户不能继续访问", lambda: assert_inactive_blocks(data, user_a, admin, db_path))
        check(results, "一个Organization可以绑定多个Membership", lambda: assert_multiple_memberships(data, admin, db_path))
        check(results, "一个Membership不得重复绑定多个有效Organization", lambda: expect_error("MEMBERSHIP_ALREADY_LINKED", lambda: bind_membership_to_organization(data["org_c"], data["member_a"], actor=admin, db_path=db_path)))
        check(results, "Membership-Organization不自动授予User访问权限", lambda: assert_member_org_no_user_access(data, user_c, db_path))
        check(results, "User-Membership不自动建立User-Organization", lambda: assert_user_membership_no_org(data, user_c, admin, db_path))
        check(results, "User-Person不自动建立User-Organization", lambda: assert_empty_context(user_c, db_path))
        check(results, "管理员可以管理组织及关系", lambda: get_accessible_organization_or_403(admin, data["org_a"], db_path, allow_admin=True))
        check(results, "普通用户不能调用管理员组织写接口", lambda: assert_plain_user_no_admin(user_a))
        check(results, "迁移脚本重复执行安全", lambda: (migrate_organization_core(db_path, backup=False), migrate_organization_core(db_path, backup=False)))
        check(results, "现有四个身份关系专项验证仍通过", lambda: [run_existing(s) for s in ["scripts/verify_identity_link_v1.py", "scripts/verify_membership_person_link_v1.py", "scripts/verify_user_membership_link_v1.py", "scripts/verify_identity_membership_access_v1.py"]])
    finally:
        cleanup(db_path)
    print("=" * 60)
    print(f"测试结果: {sum(results)}/{len(results)} 通过")
    return 0 if all(results) else 1


def assert_true(value: bool) -> None:
    assert value


def assert_one_primary(db_path: Path, user_id: int) -> None:
    with db_connection(db_path) as conn:
        count = conn.execute("SELECT COUNT(*) FROM organization_user_links WHERE user_id=? AND status='active' AND is_primary=1", (user_id,)).fetchone()[0]
    assert count == 1


def assert_switch_primary(db_path: Path, data: dict[str, int], admin: dict) -> None:
    bind_user_to_organization(data["org_b"], data["user_a"], is_primary=True, actor=admin, db_path=db_path)
    with db_connection(db_path) as conn:
        rows = conn.execute("SELECT organization_id,is_primary FROM organization_user_links WHERE user_id=? AND status='active'", (data["user_a"],)).fetchall()
    primaries = [r[0] for r in rows if r[1] == 1]
    assert primaries == [data["org_b"]]


def assert_user_orgs(user: dict, db_path: Path, expected_ids: set[int]) -> None:
    ids = {int(o["organization_id"]) for o in get_user_organizations(int(user["id"]), db_path)}
    assert ids == expected_ids


def assert_empty_context(user: dict, db_path: Path) -> None:
    ctx = get_organization_context(user, db_path)
    assert ctx["has_organization"] is False
    assert ctx["organization_count"] == 0
    assert ctx["organizations"] == []


def assert_single_context(user: dict, db_path: Path, org_id: int) -> None:
    ctx = get_organization_context(user, db_path)
    assert ctx["has_organization"] is True
    assert ctx["organization_count"] == 1
    assert ctx["default_organization_id"] == org_id
    assert ctx["can_switch"] is False


def assert_multi_context(user: dict, db_path: Path) -> None:
    ctx = get_organization_context(user, db_path)
    assert ctx["organization_count"] >= 2
    assert ctx["can_switch"] is True


def assert_unbind_loses_access(data: dict[str, int], user: dict, admin: dict, db_path: Path) -> None:
    unbind_user_from_organization(data["org_a"], data["user_b"], actor=admin, db_path=db_path)
    expect_error(403, lambda: get_accessible_organization_or_403(user, data["org_a"], db_path))


def assert_inactive_blocks(data: dict[str, int], user: dict, admin: dict, db_path: Path) -> None:
    update_organization(data["org_b"], {"status": "inactive"}, actor=admin, db_path=db_path)
    expect_error(403, lambda: get_accessible_organization_or_403(user, data["org_b"], db_path))


def assert_multiple_memberships(data: dict[str, int], admin: dict, db_path: Path) -> None:
    bind_membership_to_organization(data["org_a"], data["member_a"], actor=admin, db_path=db_path)
    bind_membership_to_organization(data["org_a"], data["member_b"], actor=admin, db_path=db_path)
    rows = list_organization_memberships(data["org_a"], db_path)
    ids = {int(r["membership_id"]) for r in rows}
    assert {data["member_a"], data["member_b"]}.issubset(ids)


def assert_member_org_no_user_access(data: dict[str, int], user: dict, db_path: Path) -> None:
    expect_error(403, lambda: get_accessible_organization_or_403(user, data["org_a"], db_path))


def assert_user_membership_no_org(data: dict[str, int], user: dict, admin: dict, db_path: Path) -> None:
    bind_membership_user(data["member_c"], data["user_c"], "验证不自动组织授权", admin["username"], db_path=db_path)
    ctx = get_organization_context(user, db_path)
    assert ctx["organization_count"] == 0


def assert_plain_user_no_admin(user: dict) -> None:
    assert "manage_club" not in permissions_for(user)
    assert required_permission("/api/v1/organizations", "POST") == "manage_club"


if __name__ == "__main__":
    raise SystemExit(main())

