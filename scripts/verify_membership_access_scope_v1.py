from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.membership_access_service import (
    MembershipAccessError,
    can_access_membership,
    get_accessible_membership_or_403,
    get_accessible_memberships,
    get_membership_context,
    require_membership_admin,
)
from app.services.membership_user_link_service import bind_user, unbind_user
from app.v04c_review import db_connection
from scripts.migrate_user_membership_link_v1 import migrate as migrate_user_membership_link
from scripts.test_db_utils import run_migration_suite, temporary_database

TS = "2024-01-01T00:00:00"


def check(results: list[bool], name: str, condition: bool, detail: str = "") -> None:
    print(("PASS" if condition else "FAIL"), name, detail)
    results.append(bool(condition))


def expect_error(status_code: int, func) -> bool:
    try:
        func()
    except MembershipAccessError as exc:
        return exc.status_code == status_code
    return False


def create_user(conn, username: str, role: str = "viewer") -> int:
    conn.execute(
        """
        INSERT INTO v05a_users(username,password_hash,display_name,role,status,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (username, "verify", username, role, "active", TS, TS),
    )
    return int(conn.execute("SELECT id FROM v05a_users WHERE username=?", (username,)).fetchone()[0])


def create_membership(conn, member_no: str, person_id: int) -> int:
    conn.execute(
        """
        INSERT INTO v04f_club_memberships(member_no,person_id,member_level,status,joined_at,created_at,updated_at)
        VALUES (?,?,?,?,?,?,?)
        """,
        (member_no, person_id, "standard", "active", TS, TS, TS),
    )
    return int(conn.execute("SELECT id FROM v04f_club_memberships WHERE member_no=?", (member_no,)).fetchone()[0])


def main() -> int:
    results: list[bool] = []
    with temporary_database("membership_scope_") as db_path:
        run_migration_suite(db_path)
        migrate_user_membership_link(db_path, backup=False)
        with db_connection(db_path) as conn:
            conn.execute("CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, name TEXT, external_id TEXT)")
            conn.execute("CREATE TABLE IF NOT EXISTS organizations(id INTEGER PRIMARY KEY, standard_name TEXT, external_id TEXT)")
            conn.execute("INSERT INTO people(id,name,external_id) VALUES (1001,'Scope Person A','scope-person-a')")
            conn.execute("INSERT INTO people(id,name,external_id) VALUES (1002,'Scope Person B','scope-person-b')")
            conn.execute("INSERT INTO people(id,name,external_id) VALUES (1003,'Scope Person C','scope-person-c')")
            user_a_id = create_user(conn, "scope_user_a")
            user_b_id = create_user(conn, "scope_user_b")
            admin_id = create_user(conn, "scope_admin", "admin")
            member_a_id = create_membership(conn, "SCOPE_A", 1001)
            member_b_id = create_membership(conn, "SCOPE_B", 1002)
            member_c_id = create_membership(conn, "SCOPE_C", 1003)
            conn.commit()

        user_a = {"id": user_a_id, "username": "scope_user_a", "role": "viewer", "status": "active"}
        user_b = {"id": user_b_id, "username": "scope_user_b", "role": "viewer", "status": "active"}
        admin = {"id": admin_id, "username": "scope_admin", "role": "admin", "status": "active"}

        bind_user(member_a_id, user_a_id, "verify bind", "verify", db_path=db_path)
        bind_user(member_b_id, user_a_id, "verify bind", "verify", db_path=db_path)
        bind_user(member_c_id, user_b_id, "verify bind", "verify", db_path=db_path)

        check(results, "anonymous has no memberships", get_accessible_memberships(None, db_path=db_path) == [])
        a_members = get_accessible_memberships(user_a, db_path=db_path)
        a_ids = {item["id"] for item in a_members}
        check(results, "user A can access own membership A", member_a_id in a_ids)
        check(results, "user A can access own membership B", member_b_id in a_ids)
        check(results, "user A cannot access user B membership", member_c_id not in a_ids)
        check(results, "tampered membership_id returns 403", expect_error(403, lambda: get_accessible_membership_or_403(user_a, member_c_id, db_path=db_path)))
        check(results, "nonexistent membership_id returns 404", expect_error(404, lambda: get_accessible_membership_or_403(user_a, 999999, db_path=db_path)))
        check(results, "can_access_membership enforces scope", not can_access_membership(user_a, member_c_id, db_path=db_path))

        context = get_membership_context(user_a, db_path=db_path)
        check(results, "user A context sees two memberships", context["membership_count"] == 2 and context["can_switch"] is True, str(context))
        check(results, "ordinary user is not membership admin", expect_error(403, lambda: require_membership_admin(user_a)))
        try:
            require_membership_admin(admin)
            admin_ok = True
        except MembershipAccessError:
            admin_ok = False
        check(results, "admin passes membership admin check", admin_ok)
        check(results, "admin can access with explicit admin allowance", get_accessible_membership_or_403(admin, member_c_id, db_path=db_path, allow_admin=True)["id"] == member_c_id)

        unbind_user(member_a_id, "verify unbind", "verify", db_path=db_path)
        after_unbind = {item["id"] for item in get_accessible_memberships(user_a, db_path=db_path)}
        check(results, "unbound membership disappears", member_a_id not in after_unbind)
        check(results, "stale selected membership is rejected", expect_error(403, lambda: get_accessible_membership_or_403(user_a, member_a_id, db_path=db_path)))

        unbind_user(member_b_id, "verify unbind", "verify", db_path=db_path)
        empty_context = get_membership_context(user_a, db_path=db_path)
        check(results, "user with no remaining membership has empty context", empty_context["has_membership"] is False and empty_context["membership_count"] == 0, str(empty_context))

        with db_connection(db_path) as conn:
            audit_count = conn.execute("SELECT COUNT(*) FROM membership_user_link_audit").fetchone()[0]
        check(results, "bind and unbind write audit", audit_count >= 5, str(audit_count))

    print(f"verify_membership_access_scope_v1 passed={sum(results)} failed={len(results)-sum(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

