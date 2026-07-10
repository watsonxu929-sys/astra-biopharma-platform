﻿﻿﻿from __future__ import annotations

import sqlite3
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.membership_user_link_service import (
    MembershipUserLinkError,
    bind_user,
    get_link_info,
    get_link_request,
    get_memberships_for_user,
    is_membership_owned_by_user,
    request_membership_link,
    unbind_user,
)
from app.v04c_review import db_connection, default_db_path
from scripts.migrate_user_membership_link_v1 import migrate as migrate_user_membership

TEST_PREFIX = f"UMV1-{datetime.now():%Y%m%d%H%M%S}"


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def run_test(name: str, func):
    try:
        func()
        print(f"PASS {name}")
        return True
    except Exception as exc:
        print(f"FAIL {name}: {exc}")
        return False


def cleanup(db_path: Path) -> None:
    with db_connection(db_path) as conn:
        mids = [row[0] for row in conn.execute("SELECT id FROM v04f_club_memberships WHERE member_no LIKE ?", (f"QBM-{TEST_PREFIX}%",)).fetchall()]
        if mids:
            marks = ",".join("?" for _ in mids)
            conn.execute(f"DELETE FROM membership_user_link_requests WHERE membership_id IN ({marks})", mids)
            conn.execute(f"DELETE FROM membership_user_link_audit WHERE membership_id IN ({marks})", mids)
            conn.execute(f"DELETE FROM v04f_club_memberships WHERE id IN ({marks})", mids)
        conn.execute("DELETE FROM v05a_users WHERE username LIKE ?", (f"user_{TEST_PREFIX}%",))
        conn.execute("DELETE FROM v05a_users WHERE username LIKE ?", (f"admin_{TEST_PREFIX}%",))
        conn.commit()


def create_data(db_path: Path) -> dict[str, int]:
    ts = now_iso()
    with db_connection(db_path) as conn:
        user_id = conn.execute(
            """
            INSERT INTO v05a_users(username,password_hash,display_name,role,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (f"user_{TEST_PREFIX}", "test-hash", "测试普通用户", "viewer", "active", ts, ts),
        ).lastrowid
        user2_id = conn.execute(
            """
            INSERT INTO v05a_users(username,password_hash,display_name,role,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (f"user_{TEST_PREFIX}_2", "test-hash", "测试普通用户2", "viewer", "active", ts, ts),
        ).lastrowid
        admin_id = conn.execute(
            """
            INSERT INTO v05a_users(username,password_hash,display_name,role,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (f"admin_{TEST_PREFIX}", "test-hash", "测试管理员", "admin", "active", ts, ts),
        ).lastrowid
        member1_id = conn.execute(
            """
            INSERT INTO v04f_club_memberships(member_no,person_id,member_level,status,joined_at,created_at,updated_at)
            VALUES (NULLIF(?,''),NULL,'standard','active',?,?,?)
            """,
            (f"QBM-{TEST_PREFIX}-001", ts, ts, ts),
        ).lastrowid
        member2_id = conn.execute(
            """
            INSERT INTO v04f_club_memberships(member_no,person_id,member_level,status,joined_at,created_at,updated_at)
            VALUES (NULLIF(?,''),NULL,'premium','active',?,?,?)
            """,
            (f"QBM-{TEST_PREFIX}-002", ts, ts, ts),
        ).lastrowid
        conn.commit()
    return {"user": user_id, "user2": user2_id, "admin": admin_id, "member1": member1_id, "member2": member2_id}


def expect_error(code: str, func) -> None:
    try:
        func()
    except MembershipUserLinkError as exc:
        assert exc.code == code, f"expected {code}, got {exc.code}"
        return
    raise AssertionError(f"expected {code}")


def main() -> int:
    db_path = default_db_path()
    print(f"数据库路径: {db_path}")
    migrate_user_membership(db_path, backup=False)
    cleanup(db_path)
    data = create_data(db_path)
    results: list[bool] = []

    def test_empty():
        assert get_memberships_for_user(999999, db_path=db_path) == []

    def test_bind():
        result = bind_user(data["member1"], data["user"], "测试绑定", "admin", db_path=db_path)
        assert result["link_status"] == "linked"
        assert result["user"]["id"] == data["user"]

    def test_multi_memberships():
        bind_user(data["member2"], data["user"], "测试第二会员", "admin", db_path=db_path)
        rows = get_memberships_for_user(data["user"], db_path=db_path)
        assert {r["id"] for r in rows} >= {data["member1"], data["member2"]}

    def test_membership_unique():
        expect_error("ALREADY_LINKED_TO_OTHER", lambda: bind_user(data["member1"], data["user2"], "冲突", "admin", db_path=db_path))

    def test_idempotent():
        result = bind_user(data["member1"], data["user"], "重复绑定", "admin", db_path=db_path)
        assert result["link_status"] == "linked"

    def test_request():
        unbind_user(data["member2"], "先解绑", "admin", db_path=db_path)
        result = request_membership_link(data["user2"], data["member2"], "申请绑定", db_path=db_path)
        assert result["status"] == "pending"
        assert result["user_id"] == data["user2"]

    def test_duplicate_request():
        expect_error("DUPLICATE_REQUEST", lambda: request_membership_link(data["user2"], data["member2"], "重复申请", db_path=db_path))

    def test_request_query():
        with db_connection(db_path) as conn:
            req = conn.execute("SELECT id FROM membership_user_link_requests WHERE membership_id=? AND status='pending'", (data["member2"],)).fetchone()
        assert req
        queried = get_link_request(int(req[0]), db_path=db_path)
        assert queried["status"] == "pending"

    def test_ownership():
        assert is_membership_owned_by_user(data["user"], data["member1"], db_path=db_path)
        assert not is_membership_owned_by_user(data["user2"], data["member1"], db_path=db_path)

    def test_unbind():
        result = unbind_user(data["member1"], "测试解绑", "admin", db_path=db_path)
        assert result["link_status"] == "unlinked"

    def test_retained():
        with db_connection(db_path) as conn:
            assert conn.execute("SELECT 1 FROM v04f_club_memberships WHERE id=?", (data["member1"],)).fetchone()
            assert conn.execute("SELECT 1 FROM v05a_users WHERE id=?", (data["user"],)).fetchone()
            assert conn.execute("SELECT user_id FROM v04f_club_memberships WHERE id=?", (data["member1"],)).fetchone()[0] is None

    def test_audit():
        with db_connection(db_path) as conn:
            count = conn.execute("SELECT COUNT(*) FROM membership_user_link_audit WHERE membership_id=?", (data["member1"],)).fetchone()[0]
        assert count >= 2

    def test_conflict_status():
        bind_user(data["member1"], data["user"], "重新绑定", "admin", db_path=db_path)
        expect_error("ALREADY_LINKED_TO_OTHER", lambda: bind_user(data["member1"], data["admin"], "冲突", "admin", db_path=db_path))

    def test_person_tables_independent():
        with db_connection(db_path) as conn:
            assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='membership_person_link_audit'").fetchone()
            assert conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='membership_user_link_audit'").fetchone()

    for name, func in [
        ("User无Membership时返回空列表", test_empty),
        ("管理员绑定Membership到User", test_bind),
        ("一个User可拥有多个Membership", test_multi_memberships),
        ("一个Membership不能绑定多个User", test_membership_unique),
        ("重复绑定幂等", test_idempotent),
        ("用户申请绑定", test_request),
        ("重复申请被阻止", test_duplicate_request),
        ("申请进入待审核", test_request_query),
        ("用户只能拥有直接绑定的Membership", test_ownership),
        ("管理员解除绑定", test_unbind),
        ("解除后User和Membership均保留", test_retained),
        ("审计日志存在", test_audit),
        ("冲突返回409", test_conflict_status),
        ("Person-Membership与User-Membership审计表独立", test_person_tables_independent),
    ]:
        results.append(run_test(name, func))

    cleanup(db_path)
    print("=" * 60)
    print(f"测试结果: {sum(results)}/{len(results)} 通过")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
