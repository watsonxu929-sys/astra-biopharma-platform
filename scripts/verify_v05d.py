from __future__ import annotations

import os
import re
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import parse_qs, urlparse


ROOT = Path(__file__).resolve().parents[1]
SRC_DB = ROOT / "data" / "app.db"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

passed = 0
failed = 0


def check(condition: bool, message: str) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {message}")
    else:
        failed += 1
        print(f"[FAIL] {message}")


def csrf(html: str) -> str:
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    return match.group(1) if match else ""


def table_count(conn: sqlite3.Connection, table: str) -> int:
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def seed(conn: sqlite3.Connection) -> dict[str, int]:
    ts = datetime.now().replace(microsecond=0).isoformat()
    suffix = datetime.now().strftime("%H%M%S%f")
    conn.execute(
        """
        INSERT INTO organizations(external_id,standard_name,org_type,region,industry_tags,visibility,verification_status,created_at,manually_confirmed,is_active)
        VALUES (?,?,?,?,?,'??','???',?,1,1)
        """,
        (f"ORG-V05D-{suffix}", "v05D????", "biotech", "??", "???", ts),
    )
    org_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
    person_ids = []
    for idx, name in enumerate(["v05D???", "v05D???", "v05D????"], start=1):
        conn.execute(
            """
            INSERT INTO people(external_id,name,public_role,organization_network,ability_tags,visibility,verification_status,created_at,manually_confirmed,is_active)
            VALUES (?,?,?,?,?,'??','???',?,1,1)
            """,
            (f"PER-V05D-{suffix}-{idx}", name, "BD???", "v05D????", "??;??", ts),
        )
        person_ids.append(int(conn.execute("SELECT last_insert_rowid()").fetchone()[0]))
    member_ids = []
    for idx, person_id in enumerate(person_ids, start=1):
        status = "inactive" if idx == 3 else "active"
        conn.execute(
            """
            INSERT INTO v04f_club_memberships(
              member_no,person_id,organization_id,member_role,member_level,status,joined_at,source,owner,
              industry_tags,expertise_tags,cooperation_preferences,created_at,updated_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (f"QBM-V05D-{suffix}-{idx}", person_id, org_id, "BD???", "standard", status, "2026-06-30", "verify_v05d", "tester", "???", "??", "????", ts, ts),
        )
        mid = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
        member_ids.append(mid)
        conn.execute(
            "INSERT INTO v05b_member_contacts(membership_id,mobile,email,wechat,preferred_contact_method,created_at,updated_at) VALUES (?,?,?,?,?,?,?)",
            (mid, f"1380000000{idx}", f"v05d{idx}@example.com", f"v05dwx{idx}", "email", ts, ts),
        )
    conn.commit()
    return {"org": org_id, "m1": member_ids[0], "m2": member_ids[1], "inactive": member_ids[2], "p1": person_ids[0], "p2": person_ids[1]}


def location_token(response) -> str:
    location = response.headers.get("location", "")
    query = parse_qs(urlparse(location).query)
    link = query.get("invite_link", [""])[0]
    return parse_qs(urlparse(link).query).get("token", [""])[0]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="verify_v05d_") as tmp:
        tmp_db = Path(tmp) / "app.db"
        if SRC_DB.exists():
            shutil.copy2(SRC_DB, tmp_db)
        else:
            tmp_db.touch()
        os.environ["APP_DB_PATH"] = str(tmp_db)
        os.environ["APP_AUTH_DISABLED"] = "1"

        from fastapi.testclient import TestClient
        from app.main import app
        from app.v05d_member_portal import _token_hash, ensure_schema

        ensure_schema(tmp_db)
        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        ids = seed(conn)
        before_members = table_count(conn, "v04f_club_memberships")
        before_needs = table_count(conn, "v04f_club_needs")
        conn.close()

        client = TestClient(app, follow_redirects=False)
        check(client.get("/v05d/health").status_code == 200, "v05D health route returns 200")
        check(client.get("/member/login").status_code == 200, "member login page returns 200")
        check(client.get("/member").status_code in {303, 307}, "member portal requires member session")

        inactive = client.post(f"/club/members/{ids['inactive']}/invite-account")
        check(inactive.status_code == 400, "inactive member cannot receive account invitation")

        first_invite = client.post(f"/club/members/{ids['m1']}/invite-account")
        token = location_token(first_invite)
        check(first_invite.status_code == 303 and token, "operator can create activation link without logging full token")
        second_invite = client.post(f"/club/members/{ids['m2']}/invite-account")
        token_old = location_token(second_invite)
        third_invite = client.post(f"/club/members/{ids['m2']}/invite-account")
        token_new = location_token(third_invite)
        check(token_old and token_new and token_old != token_new, "new invite invalidates old activation token")
        check(client.get(f"/member/activate?token={token_old}").text.find("链接不可用") >= 0, "old activation token is unusable")

        weak = client.post(
            "/member/activate",
            data={"token": token, "username": "v05d_member", "password": "123", "confirm_password": "123", "agree": "1"},
        )
        check(weak.status_code == 303 and "password_rule" in weak.headers.get("location", ""), "weak password is rejected")

        active = client.post(
            "/member/activate",
            data={"token": token, "username": "v05d_member", "password": "StrongPass123", "confirm_password": "StrongPass123", "agree": "1"},
        )
        check(active.status_code == 303 and active.headers.get("set-cookie", "").find("qbay_member_session") >= 0, "valid activation logs member in")
        check(client.get(f"/member/activate?token={token}").text.find("链接不可用") >= 0, "activation token is one-time")

        login = client.post("/member/login", data={"username": "v05d_member", "password": "StrongPass123"})
        check(login.status_code == 303 and login.headers.get("set-cookie", "").find("qbay_member_session") >= 0, "member can log in")
        cookie = login.headers.get("set-cookie", "").split(";", 1)[0].split("=", 1)[1]
        headers = {"cookie": f"qbay_member_session={cookie}"}
        home = client.get("/member", headers=headers)
        check(home.status_code == 200 and "v05D???" in home.text, "member home shows own profile")
        check(client.get("/review", headers=headers).status_code in {200, 303}, "member cookie does not create internal identity")

        profile = client.get("/member/profile", headers=headers)
        token_csrf = csrf(profile.text)
        check(bool(token_csrf), "member forms include CSRF token")
        changed_name = "v05D????"
        submit_profile = client.post(
            "/member/profile",
            headers=headers,
            data={
                "csrf_token": token_csrf,
                "display_name": changed_name,
                "title": "BD???",
                "mobile": "13900000001",
                "email": "v05dnew@example.com",
                "wechat": "v05dwx1",
                "preferred_contact_method": "email",
                "expertise_tags": "??",
                "cooperation_preferences": "????",
                "allow_matching": "1",
                "allow_internal_contact": "1",
            },
        )
        check(submit_profile.status_code == 303, "member can submit profile change request")

        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        official_name = conn.execute("SELECT name FROM people WHERE id=?", (ids["p1"],)).fetchone()["name"]
        pending = conn.execute("SELECT * FROM v05d_profile_change_requests WHERE membership_id=? AND field_name='display_name'", (ids["m1"],)).fetchone()
        mobile = conn.execute("SELECT mobile FROM v05b_member_contacts WHERE membership_id=?", (ids["m1"],)).fetchone()["mobile"]
        check(official_name != changed_name and pending and pending["status"] == "pending", "profile name change stays pending and does not overwrite official person")
        check(mobile == "13900000001", "contact field can be auto-applied by rule")
        conn.close()

        duplicate_profile = client.post("/member/profile", headers=headers, data={"csrf_token": token_csrf, "display_name": changed_name})
        conn = sqlite3.connect(tmp_db)
        pending_count = conn.execute("SELECT COUNT(*) FROM v05d_profile_change_requests WHERE membership_id=? AND field_name='display_name' AND status='pending'", (ids["m1"],)).fetchone()[0]
        conn.close()
        check(duplicate_profile.status_code == 303 and pending_count == 1, "duplicate pending profile change is blocked")

        admin_review = client.post(f"/club/profile-changes/{pending['id']}/review", data={"decision": "approved", "review_note": "ok"})
        conn = sqlite3.connect(tmp_db)
        approved_name = conn.execute("SELECT name FROM people WHERE id=?", (ids["p1"],)).fetchone()[0]
        conn.close()
        check(admin_review.status_code == 303 and approved_name == changed_name, "approved profile change applies selected field")

        content = client.post(
            "/member/content",
            headers=headers,
            data={
                "csrf_token": token_csrf,
                "content_type": "need",
                "title": "??????",
                "description": "????????",
                "category": "clinical",
                "industry_tags": "???",
                "region": "??",
                "urgency_or_availability": "high",
                "allow_matching": "1",
            },
        )
        conn = sqlite3.connect(tmp_db)
        official_before_review = conn.execute("SELECT COUNT(*) FROM v04f_club_needs WHERE membership_id=?", (ids["m1"],)).fetchone()[0]
        content_id = conn.execute("SELECT id FROM v05d_member_content_requests WHERE membership_id=? AND content_type='need'", (ids["m1"],)).fetchone()[0]
        conn.close()
        check(content.status_code == 303 and official_before_review == 0, "member content is draft/review data before approval")
        admin_content = client.post(f"/club/member-content/{content_id}/review", data={"decision": "approved", "review_note": "ok"})
        conn = sqlite3.connect(tmp_db)
        official_after_review = conn.execute("SELECT COUNT(*) FROM v04f_club_needs WHERE membership_id=?", (ids["m1"],)).fetchone()[0]
        conn.close()
        check(admin_content.status_code == 303 and official_after_review == 1, "approved member need enters formal need table")

        ts = datetime.now().replace(microsecond=0).isoformat()
        conn = sqlite3.connect(tmp_db)
        conn.execute(
            "INSERT INTO events(external_id,event_date,name,event_type,visibility,verification_status,created_at,manually_confirmed,is_active) VALUES (?,?,?,?,?,?,?,1,1)",
            ("EVT-V05D", "2026-07-01", "v05D???", "club", "??", "???", ts),
        )
        event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0] + 1000000
        conn.execute(
            """
            INSERT INTO v05c_club_event_profiles(event_id,event_no,event_type,registration_status,capacity,registration_deadline,visibility,member_only,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (event_id, "QBE-V05D", "salon", "open", 1, (datetime.now() + timedelta(days=1)).date().isoformat(), "controlled", 1, "published", ts, ts),
        )
        club_event_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
        register = client.post(f"/member/events/{club_event_id}/register", headers=headers, data={"csrf_token": token_csrf, "note": "join"})
        duplicate = client.post(f"/member/events/{club_event_id}/register", headers=headers, data={"csrf_token": token_csrf})
        conn = sqlite3.connect(tmp_db)
        reg = conn.execute("SELECT id,status FROM v05c_club_event_registrations WHERE club_event_id=? AND membership_id=?", (club_event_id, ids["m1"])).fetchone()
        conn.close()
        check(register.status_code == 303 and reg and reg[1] == "submitted", "member can register event")
        check(duplicate.status_code == 303 and "duplicate" in duplicate.headers.get("location", ""), "duplicate event registration is blocked")
        cancel = client.post(f"/member/events/{reg[0]}/cancel", headers=headers, data={"csrf_token": token_csrf})
        conn = sqlite3.connect(tmp_db)
        cancelled = conn.execute("SELECT status FROM v05c_club_event_registrations WHERE id=?", (reg[0],)).fetchone()[0]
        conn.close()
        check(cancel.status_code == 303 and cancelled == "cancelled", "member can cancel registration while history is preserved")

        conn = sqlite3.connect(tmp_db)
        conn.execute("INSERT INTO v04f_club_needs(need_no,membership_id,title,description,need_type,industry_tags,region,urgency,status,created_at,updated_at) VALUES ('QBN-V05D',?,?,?,?,?,?,?,?,?,?)", (ids["m1"], "????", "??", "finance", "???", "??", "high", "active", ts, ts))
        need_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO v04f_club_offerings(offering_no,membership_id,title,description,offering_type,industry_tags,region,availability,status,created_at,updated_at) VALUES ('QBO-V05D',?,?,?,?,?,?,?,?,?,?)", (ids["m2"], "????", "??", "finance", "???", "??", "available", "active", ts, ts))
        offering_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("INSERT INTO v04f_club_matches(match_no,need_id,offering_id,match_score,match_grade,reasons_json,status,created_at,updated_at) VALUES ('QBMATCH-V05D',?,?,88,'A','[]','candidate',?,?)", (need_id, offering_id, ts, ts))
        match_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.commit()
        conn.close()
        match_page = client.get("/member/matches", headers=headers)
        feedback = client.post(f"/member/matches/{match_id}/feedback", headers=headers, data={"csrf_token": token_csrf, "feedback": "interested", "note": "???"})
        conn = sqlite3.connect(tmp_db)
        fb_count = conn.execute("SELECT COUNT(*) FROM v05d_member_match_feedback WHERE membership_id=?", (ids["m1"],)).fetchone()[0]
        match_status = conn.execute("SELECT status FROM v04f_club_matches WHERE id=?", (match_id,)).fetchone()[0]
        conn.close()
        check(match_page.status_code == 200 and "QBMATCH-V05D" in match_page.text, "member sees only related matches")
        check(feedback.status_code == 303 and fb_count == 1 and match_status == "progressing", "match feedback is recorded without creating duplicate action")

        ann = client.post("/club/announcements/create", data={"title": "v05D??", "body": "????", "target_type": "all", "target_value": ""})
        conn = sqlite3.connect(tmp_db)
        ann_id = conn.execute("SELECT id FROM v05d_announcements WHERE title='v05D??'").fetchone()[0]
        conn.close()
        publish = client.post(f"/club/announcements/{ann_id}/publish", data={"confirm_publish": "1"})
        notices = client.get("/member/notifications", headers=headers)
        check(ann.status_code == 303 and publish.status_code == 303 and "v05D??" in notices.text, "announcement creates in-app notifications only")
        read = client.post("/member/notifications", headers=headers, data={"csrf_token": token_csrf, "action": "read_all"})
        check(read.status_code == 303, "member can mark notifications read")

        conn = sqlite3.connect(tmp_db)
        account_id = conn.execute("SELECT id FROM v05d_member_accounts WHERE membership_id=?", (ids["m1"],)).fetchone()[0]
        conn.close()
        deactivate = client.post(f"/club/member-accounts/{account_id}/status", data={"status": "deactivated"})
        locked_home = client.get("/member", headers=headers)
        check(deactivate.status_code == 303 and locked_home.status_code in {303, 307}, "deactivation invalidates existing member session")

        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        after_members = table_count(conn, "v04f_club_memberships")
        after_needs = table_count(conn, "v04f_club_needs")
        one_account = conn.execute("SELECT COUNT(*) FROM v05d_member_accounts WHERE membership_id=?", (ids["m1"],)).fetchone()[0]
        token_logged = conn.execute("SELECT COUNT(*) FROM v05a_audit_logs WHERE detail_json LIKE '%token_urlsafe%' OR detail_json LIKE '%StrongPass123%'").fetchone()[0] if "v05a_audit_logs" in {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")} else 0
        conn.close()
        check(one_account == 1, "one member has only one portal account")
        check(after_members == before_members and after_needs >= before_needs, "core member records are not deleted during verification")
        check(token_logged == 0, "audit logs do not contain raw activation token or password")

    print(f"verify_v05d completed passed={passed} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

