from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.security import permissions_for
from app.services.membership_access_service import (
    MembershipAccessError,
    get_accessible_membership_or_403,
    get_membership_context,
)
from app.services.membership_person_link_service import bind_person
from app.services.membership_user_link_service import bind_user, unbind_user
from app.v04c_review import db_connection, default_db_path
from scripts.migrate_user_membership_link_v1 import migrate as migrate_user_link

TEST_PREFIX = f"IMA-{datetime.now():%Y%m%d%H%M%S}"


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def pass_fail(results: list[bool], name: str, func) -> None:
    try:
        func()
        print(f"PASS {name}")
        results.append(True)
    except Exception as exc:
        print(f"FAIL {name}: {exc}")
        results.append(False)


def expect_access_error(status_code: int, func) -> None:
    try:
        func()
    except MembershipAccessError as exc:
        assert exc.status_code == status_code, f"expected {status_code}, got {exc.status_code}"
        return
    raise AssertionError(f"expected MembershipAccessError {status_code}")


def cleanup(db_path: Path) -> None:
    with db_connection(db_path) as conn:
        mids = [row[0] for row in conn.execute("SELECT id FROM v04f_club_memberships WHERE member_no LIKE ?", (f"QBM-{TEST_PREFIX}%",)).fetchall()]
        if mids:
            marks = ",".join("?" for _ in mids)
            conn.execute(f"DELETE FROM membership_user_link_requests WHERE membership_id IN ({marks})", mids)
            conn.execute(f"DELETE FROM membership_user_link_audit WHERE membership_id IN ({marks})", mids)
            conn.execute(f"DELETE FROM membership_person_link_audit WHERE membership_id IN ({marks})", mids)
            conn.execute(f"DELETE FROM v04f_club_memberships WHERE id IN ({marks})", mids)
        conn.execute("DELETE FROM v05a_users WHERE username LIKE ?", (f"{TEST_PREFIX.lower()}_%",))
        conn.execute("DELETE FROM people WHERE external_id LIKE ?", (f"PER-{TEST_PREFIX}%",))
        conn.commit()


def create_data(db_path: Path) -> dict[str, int]:
    ts = now_iso()
    with db_connection(db_path) as conn:
        person_a = conn.execute(
            "INSERT INTO people(external_id,name,is_active,created_at,source_type,visibility,verification_status) VALUES (?,?,1,?,'system_verify','内部','待核验')",
            (f"PER-{TEST_PREFIX}-A", f"访问隔离测试人物A-{TEST_PREFIX}", ts),
        ).lastrowid
        person_b = conn.execute(
            "INSERT INTO people(external_id,name,is_active,created_at,source_type,visibility,verification_status) VALUES (?,?,1,?,'system_verify','内部','待核验')",
            (f"PER-{TEST_PREFIX}-B", f"访问隔离测试人物B-{TEST_PREFIX}", ts),
        ).lastrowid
        users = {}
        for key, role in [("a", "viewer"), ("b", "viewer"), ("person_only", "viewer"), ("admin", "admin")]:
            users[key] = conn.execute(
                """
                INSERT INTO v05a_users(username,password_hash,display_name,role,status,created_at,updated_at,person_id)
                VALUES (?,?,?,?,?,?,?,NULL)
                """,
                (f"{TEST_PREFIX.lower()}_{key}", "test-hash", f"访问隔离{key}", role, "active", ts, ts),
            ).lastrowid
        conn.execute("UPDATE v05a_users SET person_id=? WHERE id=?", (person_b, users["person_only"]))
        memberships = {}
        for key, level in [("a", "standard"), ("b", "premium"), ("c", "vip"), ("person_only", "standard")]:
            memberships[key] = conn.execute(
                """
                INSERT INTO v04f_club_memberships(member_no,person_id,member_level,status,joined_at,created_at,updated_at)
                VALUES (?,NULL,?,'active',?,?,?)
                """,
                (f"QBM-{TEST_PREFIX}-{key.upper()}", level, ts, ts, ts),
            ).lastrowid
        conn.commit()
    return {"person_a": person_a, "person_b": person_b, **{f"user_{k}": v for k, v in users.items()}, **{f"member_{k}": v for k, v in memberships.items()}}


def run_existing_script(script: str) -> None:
    result = subprocess.run([str(ROOT / ".venv" / "Scripts" / "python.exe"), str(ROOT / script)], cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=120)
    if result.returncode != 0:
        raise AssertionError(result.stdout[-1200:])


def main() -> int:
    db_path = default_db_path()
    migrate_user_link(db_path, backup=False)
    cleanup(db_path)
    data = create_data(db_path)
    results: list[bool] = []

    user_a = {"id": data["user_a"], "username": f"{TEST_PREFIX.lower()}_a", "role": "viewer"}
    user_b = {"id": data["user_b"], "username": f"{TEST_PREFIX.lower()}_b", "role": "viewer"}
    user_person_only = {"id": data["user_person_only"], "username": f"{TEST_PREFIX.lower()}_person_only", "role": "viewer"}
    admin = {"id": data["user_admin"], "username": f"{TEST_PREFIX.lower()}_admin", "role": "admin"}

    try:
        pass_fail(results, "三条关系表和字段存在且相互独立", lambda: _assert_schema(db_path))
        pass_fail(results, "User-Membership服务不调用Person-Membership服务", lambda: _assert_no_cross_service())
        pass_fail(results, "无会员用户返回空上下文", lambda: _assert_empty_context(user_b, db_path))
        pass_fail(results, "User A可访问Membership A", lambda: _bind_and_access(data, user_a, db_path))
        pass_fail(results, "User A不可访问Membership B", lambda: expect_access_error(403, lambda: get_accessible_membership_or_403(user_a, data["member_b"], db_path)))
        pass_fail(results, "篡改URL membership_id被阻止", lambda: expect_access_error(403, lambda: get_accessible_membership_or_403(user_a, data["member_b"], db_path)))
        pass_fail(results, "一个User可拥有多个Membership", lambda: _bind_second_membership(data, user_a, db_path))
        pass_fail(results, "多个合法Membership均可访问", lambda: _assert_multiple_accessible(data, user_a, db_path))
        pass_fail(results, "解除绑定后立即失去访问", lambda: _assert_unlink_loses_access(data, user_a, db_path))
        pass_fail(results, "浏览器陈旧选择不能绕过解绑", lambda: expect_access_error(403, lambda: get_accessible_membership_or_403(user_a, data["member_c"], db_path)))
        pass_fail(results, "User-Person存在但无User-Membership不给会员访问", lambda: _assert_person_only_no_membership(user_person_only, db_path))
        pass_fail(results, "Person-Membership存在但无User-Membership不给会员访问", lambda: _assert_person_membership_no_user(data, user_b, db_path))
        pass_fail(results, "管理员可使用原后台权限访问", lambda: get_accessible_membership_or_403(admin, data["member_b"], db_path, allow_admin=True))
        pass_fail(results, "普通用户不具备绑定审核管理权限", lambda: _assert_plain_user_no_admin_permissions(user_a))
        pass_fail(results, "不存在Membership返回404", lambda: expect_access_error(404, lambda: get_accessible_membership_or_403(user_a, 999999999, db_path)))
        pass_fail(results, "存在但未授权Membership返回403", lambda: expect_access_error(403, lambda: get_accessible_membership_or_403(user_a, data["member_b"], db_path)))
        pass_fail(results, "User-Membership迁移可重复执行", lambda: (migrate_user_link(db_path, backup=False), migrate_user_link(db_path, backup=False)))
        pass_fail(results, "原三条关系专项验证仍通过", lambda: [run_existing_script(s) for s in ["scripts/verify_identity_link_v1.py", "scripts/verify_membership_person_link_v1.py", "scripts/verify_user_membership_link_v1.py"]])
    finally:
        cleanup(db_path)

    print("=" * 60)
    print(f"测试结果: {sum(results)}/{len(results)} 通过")
    return 0 if all(results) else 1


def _assert_schema(db_path: Path) -> None:
    with db_connection(db_path) as conn:
        member_cols = {r["name"] for r in conn.execute("PRAGMA table_info(v04f_club_memberships)").fetchall()}
        user_cols = {r["name"] for r in conn.execute("PRAGMA table_info(v05a_users)").fetchall()}
        assert "user_id" in member_cols
        assert "person_id" in member_cols
        assert "person_id" in user_cols
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='membership_person_link_audit'").fetchone()
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='membership_user_link_audit'").fetchone()


def _assert_no_cross_service() -> None:
    text = (ROOT / "app" / "services" / "membership_user_link_service.py").read_text(encoding="utf-8")
    assert "membership_person_link_service" not in text
    assert "bind_person" not in text


def _assert_empty_context(user: dict, db_path: Path) -> None:
    ctx = get_membership_context(user, db_path)
    assert ctx["has_membership"] is False
    assert ctx["membership_count"] == 0
    assert ctx["memberships"] == []


def _bind_and_access(data: dict[str, int], user: dict, db_path: Path) -> None:
    bind_user(data["member_a"], data["user_a"], "访问隔离测试", "verify", db_path=db_path)
    member = get_accessible_membership_or_403(user, data["member_a"], db_path)
    assert member["membership_id"] == data["member_a"]


def _bind_second_membership(data: dict[str, int], user: dict, db_path: Path) -> None:
    bind_user(data["member_c"], data["user_a"], "第二会员", "verify", db_path=db_path)
    ctx = get_membership_context(user, db_path)
    assert ctx["membership_count"] >= 2
    assert ctx["can_switch"] is True


def _assert_multiple_accessible(data: dict[str, int], user: dict, db_path: Path) -> None:
    ids = {m["membership_id"] for m in get_membership_context(user, db_path)["memberships"]}
    assert {data["member_a"], data["member_c"]}.issubset(ids)
    assert get_accessible_membership_or_403(user, data["member_a"], db_path)
    assert get_accessible_membership_or_403(user, data["member_c"], db_path)


def _assert_unlink_loses_access(data: dict[str, int], user: dict, db_path: Path) -> None:
    unbind_user(data["member_c"], "解绑后失效", "verify", db_path=db_path)
    expect_access_error(403, lambda: get_accessible_membership_or_403(user, data["member_c"], db_path))


def _assert_person_only_no_membership(user: dict, db_path: Path) -> None:
    ctx = get_membership_context(user, db_path)
    assert ctx["membership_count"] == 0


def _assert_person_membership_no_user(data: dict[str, int], user: dict, db_path: Path) -> None:
    bind_person(data["member_person_only"], data["person_b"], "仅Person-Membership", "verify", db_path=db_path)
    ctx = get_membership_context(user, db_path)
    assert data["member_person_only"] not in {m["membership_id"] for m in ctx["memberships"]}
    expect_access_error(403, lambda: get_accessible_membership_or_403(user, data["member_person_only"], db_path))


def _assert_plain_user_no_admin_permissions(user: dict) -> None:
    perms = permissions_for(user)
    assert "manage_club" not in perms
    assert "manage_users" not in perms


if __name__ == "__main__":
    raise SystemExit(main())

