from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import resolved_db_path
DB_PATH = resolved_db_path()
BACKUP_DIR = DB_PATH.parent / "backups" if (ROOT / "data").resolve() not in DB_PATH.resolve().parents else ROOT / "data" / "backups"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS v04f_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v04f_lead_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_no TEXT NOT NULL UNIQUE,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    funnel_stage TEXT NOT NULL DEFAULT '待识别',
    system_score INTEGER NOT NULL DEFAULT 0,
    system_grade TEXT NOT NULL DEFAULT 'C',
    scoring_json TEXT,
    manual_grade TEXT,
    manual_override_reason TEXT,
    owner TEXT,
    next_action TEXT,
    next_action_at TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    last_scored_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deactivated_at TEXT,
    CHECK(subject_type IN ('organization','project')),
    CHECK(status IN ('active','paused','inactive')),
    CHECK(system_score BETWEEN 0 AND 100)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04f_active_lead_subject
ON v04f_lead_records(subject_type, subject_id)
WHERE status='active';

CREATE INDEX IF NOT EXISTS ix_v04f_lead_stage_score
ON v04f_lead_records(funnel_stage, system_score DESC, updated_at DESC);

CREATE TABLE IF NOT EXISTS v04f_lead_stage_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    old_stage TEXT,
    new_stage TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'manual',
    reason TEXT,
    changed_at TEXT NOT NULL,
    FOREIGN KEY(lead_id) REFERENCES v04f_lead_records(id)
);

CREATE TABLE IF NOT EXISTS v04f_lead_suggestions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_id INTEGER NOT NULL,
    suggestion_key TEXT NOT NULL,
    title TEXT NOT NULL,
    basis TEXT,
    priority TEXT,
    recommended_due TEXT,
    converted_action_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(lead_id, suggestion_key),
    FOREIGN KEY(lead_id) REFERENCES v04f_lead_records(id)
);

CREATE TABLE IF NOT EXISTS v04f_club_applications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    application_no TEXT NOT NULL UNIQUE,
    applicant_name TEXT NOT NULL,
    mobile TEXT,
    email TEXT,
    wechat TEXT,
    organization_name TEXT,
    title TEXT,
    city TEXT,
    industry_tags TEXT,
    expertise_tags TEXT,
    offered_resources TEXT,
    cooperation_needs TEXT,
    self_introduction TEXT,
    referral_source TEXT,
    referrer_name TEXT,
    preferred_contact_method TEXT,
    consent_to_store INTEGER NOT NULL DEFAULT 0,
    consent_to_contact INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'submitted',
    review_note TEXT,
    submitted_at TEXT NOT NULL,
    reviewed_at TEXT,
    reviewed_by TEXT,
    matched_person_id INTEGER,
    matched_organization_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(status IN ('submitted','under_review','need_more_info','approved','rejected','withdrawn'))
);

CREATE INDEX IF NOT EXISTS ix_v04f_app_status ON v04f_club_applications(status, submitted_at DESC);
CREATE INDEX IF NOT EXISTS ix_v04f_app_contact ON v04f_club_applications(mobile, email, submitted_at DESC);

CREATE TABLE IF NOT EXISTS v04f_club_memberships (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    member_no TEXT NOT NULL UNIQUE,
    person_id INTEGER NOT NULL,
    organization_id INTEGER,
    member_role TEXT,
    member_level TEXT NOT NULL DEFAULT 'standard',
    status TEXT NOT NULL DEFAULT 'active',
    joined_at TEXT NOT NULL,
    expired_at TEXT,
    source TEXT,
    owner TEXT,
    industry_tags TEXT,
    expertise_tags TEXT,
    cooperation_preferences TEXT,
    internal_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deactivated_at TEXT,
    CHECK(status IN ('pending','active','inactive','suspended','exited'))
);

CREATE INDEX IF NOT EXISTS ix_v04f_member_person
ON v04f_club_memberships(person_id);

CREATE INDEX IF NOT EXISTS ix_v04f_member_status ON v04f_club_memberships(status, member_level, joined_at DESC);

CREATE TABLE IF NOT EXISTS v04f_club_needs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    need_no TEXT NOT NULL UNIQUE,
    membership_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    need_type TEXT,
    industry_tags TEXT,
    region TEXT,
    urgency TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    valid_until TEXT,
    related_project_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id)
);

CREATE TABLE IF NOT EXISTS v04f_club_offerings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    offering_no TEXT NOT NULL UNIQUE,
    membership_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    offering_type TEXT,
    industry_tags TEXT,
    region TEXT,
    availability TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    related_resource_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id)
);

CREATE TABLE IF NOT EXISTS v04f_club_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_no TEXT NOT NULL UNIQUE,
    need_id INTEGER NOT NULL,
    offering_id INTEGER NOT NULL,
    match_score INTEGER NOT NULL,
    match_grade TEXT NOT NULL,
    reasons_json TEXT,
    missing_json TEXT,
    status TEXT NOT NULL DEFAULT 'candidate',
    confirmed_by TEXT,
    confirmed_at TEXT,
    reject_reason TEXT,
    action_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(need_id, offering_id),
    FOREIGN KEY(need_id) REFERENCES v04f_club_needs(id),
    FOREIGN KEY(offering_id) REFERENCES v04f_club_offerings(id)
);

CREATE INDEX IF NOT EXISTS ix_v04f_match_status ON v04f_club_matches(status, match_score DESC);
"""


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = BACKUP_DIR / f"app_before_v04f_{stamp}.db"
        shutil.copy2(db_path, target)
        backup_path = str(target)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("v0.4F migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


