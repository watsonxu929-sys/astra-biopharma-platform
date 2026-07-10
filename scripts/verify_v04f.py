from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("APP_AUTH_DISABLED", "1")

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.services.club_matching_service import match_need_offering  # noqa: E402
from app.services.lead_scoring_service import manual_grade_requires_reason, score_lead  # noqa: E402
from app.v04c_review import db_connection  # noqa: E402
from app.v04f_operations import get_or_create_lead, lead_detail  # noqa: E402
from scripts.migrate_v04f import migrate  # noqa: E402


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def create_core_tables(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE organizations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                standard_name TEXT,
                org_type TEXT,
                region TEXT,
                industry_tags TEXT,
                resources TEXT,
                needs TEXT,
                visibility TEXT,
                verification_status TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE TABLE people(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                name TEXT,
                public_role TEXT,
                organization_network TEXT,
                ability_tags TEXT,
                visibility TEXT,
                verification_status TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE TABLE projects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                name TEXT,
                project_type TEXT,
                owner_external_id TEXT,
                owner_organization_id INTEGER,
                focus_tags TEXT,
                typical_needs TEXT,
                target_actions TEXT,
                visibility TEXT,
                status TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE TABLE relations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                source_external_id TEXT,
                relation_type TEXT,
                target_external_id TEXT,
                evidence_source TEXT,
                visibility TEXT,
                verification_status TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE TABLE events(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                event_date TEXT,
                name TEXT,
                event_type TEXT,
                related_entity TEXT,
                related_organization_id INTEGER,
                fact_summary TEXT,
                visibility TEXT,
                verification_status TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE TABLE resources(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                owner_external_id TEXT,
                owner_organization_id INTEGER,
                category TEXT,
                description TEXT,
                region TEXT,
                applicable_to TEXT,
                visibility TEXT,
                verification_status TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE TABLE actions(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                task TEXT,
                target_external_id TEXT,
                target_organization_id INTEGER,
                completion_standard TEXT,
                owner TEXT,
                priority TEXT,
                status TEXT,
                suggested_deadline TEXT,
                source_type TEXT,
                created_at TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO organizations(external_id, standard_name, org_type, region, industry_tags, visibility, verification_status, created_at)
            VALUES ('ORG-F-001', 'QBay Bio', 'biotech', 'Shanghai', 'ADC;CRO', 'internal', 'confirmed', ?)
            """,
            (datetime.now().isoformat(),),
        )
        conn.execute(
            """
            INSERT INTO people(external_id, name, public_role, organization_network, ability_tags, visibility, verification_status, created_at)
            VALUES ('PER-F-001', 'Alice Chen', 'BD lead', 'QBay Bio', 'partnering', 'internal', 'confirmed', ?)
            """,
            (datetime.now().isoformat(),),
        )
        conn.execute(
            """
            INSERT INTO projects(external_id, name, project_type, owner_external_id, focus_tags, typical_needs, target_actions, visibility, status, created_at)
            VALUES ('PRJ-F-001', 'ADC Partnering', 'drug project', 'ORG-F-001', 'ADC;partnering', 'financing', 'contact BD', 'internal', 'active', ?)
            """,
            (datetime.now().isoformat(),),
        )
        conn.execute(
            """
            INSERT INTO relations(external_id, source_external_id, relation_type, target_external_id, evidence_source, visibility, verification_status, created_at)
            VALUES ('REL-F-001', 'PER-F-001', 'employment', 'ORG-F-001', 'public profile', 'internal', 'pending', ?)
            """,
            (datetime.now().isoformat(),),
        )
        conn.commit()
    finally:
        conn.close()


def verify_leads(path: Path) -> None:
    create_core_tables(path)
    migrate(path, backup=False)
    lead = get_or_create_lead("organization", "ORG-F-001", owner="verify", db_path=path)
    duplicate = get_or_create_lead("organization", "ORG-F-001", owner="verify", db_path=path)
    check(lead["id"] == duplicate["id"], "same subject does not create duplicate active lead")
    detail = lead_detail(int(lead["id"]), db_path=path)
    check(0 <= int(detail["lead"]["system_score"]) <= 100, "system score is between 0 and 100")
    check(detail["scoring"]["dimensions"], "score contains explanations")
    risky = score_lead({"subject": {"tags": "", "type": "organization"}, "stats": {}, "review": {"open_count": 3, "conflict_count": 1}, "completeness": {"percent": 20}, "lead": {}})
    check(risky["dimensions"]["risk_adjustment"] < 0, "risk can deduct score")
    check(manual_grade_requires_reason("B", "A", ""), "manual grade override requires reason when higher")
    with db_connection(path) as conn:
        conn.execute(
            "UPDATE v04f_lead_records SET funnel_stage='待联系', updated_at=? WHERE id=?",
            (datetime.now().isoformat(), lead["id"]),
        )
        conn.execute(
            "INSERT INTO v04f_lead_stage_history(lead_id, old_stage, new_stage, actor, reason, changed_at) VALUES (?, '待识别', '待联系', 'verify', 'test', ?)",
            (lead["id"], datetime.now().isoformat()),
        )
        history_count = conn.execute("SELECT COUNT(*) AS c FROM v04f_lead_stage_history WHERE lead_id=?", (lead["id"],)).fetchone()["c"]
        before_actions = conn.execute("SELECT COUNT(*) AS c FROM actions").fetchone()["c"]
    check(history_count >= 2, "funnel stage changes keep history")
    check(before_actions == 0, "recommendations do not automatically create actions")


def verify_club(path: Path) -> None:
    migrate(path, backup=False)
    with db_connection(path) as conn:
        ts = datetime.now().isoformat()
        app_no = "QBA-VERIFY-001"
        conn.execute(
            """
            INSERT INTO v04f_club_applications(
                application_no, applicant_name, mobile, email, organization_name, title,
                industry_tags, expertise_tags, offered_resources, cooperation_needs,
                consent_to_store, consent_to_contact, submitted_at, created_at, updated_at
            ) VALUES (?, 'Alice Chen', '13800000000', 'alice@example.test', 'QBay Bio', 'BD lead',
                      'ADC;CRO', 'partnering', 'BD network', 'financing partner', 1, 1, ?, ?, ?)
            """,
            (app_no, ts, ts, ts),
        )
        app = conn.execute("SELECT * FROM v04f_club_applications WHERE application_no=?", (app_no,)).fetchone()
        conn.execute(
            """
            INSERT INTO v04f_club_memberships(
                member_no, person_id, organization_id, member_role, member_level, status,
                joined_at, source, owner, industry_tags, expertise_tags, cooperation_preferences,
                created_at, updated_at
            ) VALUES ('QBM-VERIFY-001', 1, 1, 'BD lead', 'standard', 'active',
                      ?, ?, 'verify', 'ADC;CRO', 'partnering', 'financing partner', ?, ?)
            """,
            (ts, app["application_no"], ts, ts),
        )
        try:
            conn.execute(
                """
                INSERT INTO v04f_club_memberships(member_no, person_id, status, joined_at, created_at, updated_at)
                VALUES ('QBM-VERIFY-002', 1, 'active', ?, ?, ?)
                """,
                (ts, ts, ts),
            )
            duplicate_blocked = False
        except sqlite3.IntegrityError:
            duplicate_blocked = True
        member_id = conn.execute("SELECT id FROM v04f_club_memberships WHERE member_no='QBM-VERIFY-001'").fetchone()["id"]
        conn.execute(
            "INSERT INTO v04f_club_needs(need_no, membership_id, title, description, need_type, industry_tags, region, urgency, created_at, updated_at) VALUES ('QBN-VERIFY-001', ?, 'Need financing', 'Need investor connection', 'investment', 'ADC;CRO', 'Shanghai', 'high', ?, ?)",
            (member_id, ts, ts),
        )
        conn.execute(
            "INSERT INTO v04f_club_offerings(offering_no, membership_id, title, description, offering_type, industry_tags, region, availability, created_at, updated_at) VALUES ('QBO-VERIFY-SELF', ?, 'Investor network', 'Can introduce investors', 'investment', 'ADC', 'Shanghai', 'available', ?, ?)",
            (member_id, ts, ts),
        )
        need = dict(conn.execute("SELECT * FROM v04f_club_needs").fetchone())
        offering = dict(conn.execute("SELECT * FROM v04f_club_offerings").fetchone())
    check(duplicate_blocked, "same person cannot create duplicate active membership")
    check(match_need_offering(need, offering) is None, "same member is not self-matched by default")
    other = dict(offering)
    other["id"] = 2
    other["membership_id"] = 999
    result = match_need_offering(need, other)
    check(result and result["score"] > 0 and result["reasons"], "need and offering generate explainable match")


def verify_routes() -> None:
    client = TestClient(app)
    checks = ["/leads", "/club", "/club/apply", "/club/admin/applications", "/club/members", "/club/matches", "/v04f/health"]
    for path in checks:
        response = client.get(path)
        check(response.status_code == 200, f"{path} returns 200")
    bad = client.post("/club/apply", data={"applicant_name": "Bot", "mobile": "1", "consent_to_store": "1", "consent_to_contact": "1", "website": "spam"})
    check(bad.status_code == 400, "honeypot submission is blocked")
    no_consent = client.post("/club/apply", data={"applicant_name": "No Consent", "mobile": "1"})
    check(no_consent.status_code == 400, "application without consent is rejected")
    no_contact = client.post("/club/apply", data={"applicant_name": "No Contact", "consent_to_store": "1", "consent_to_contact": "1"})
    check(no_contact.status_code == 400, "mobile or email is required")
    check("13800000000" not in client.get("/club/apply").text, "public page does not expose contact data")
    client.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v04f_verify_") as tmp:
        db_path = Path(tmp) / "verify.db"
        verify_leads(db_path)
        verify_club(db_path)
    verify_routes()
    print("ALL V0.4F CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
