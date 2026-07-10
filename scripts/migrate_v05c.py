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
CREATE TABLE IF NOT EXISTS v05c_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v05c_field_mapping_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_name TEXT NOT NULL UNIQUE,
    source_structure TEXT NOT NULL DEFAULT 'table',
    header_row INTEGER NOT NULL DEFAULT 1,
    mapping_json TEXT NOT NULL,
    default_json TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v05c_club_event_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL UNIQUE,
    event_no TEXT NOT NULL UNIQUE,
    event_type TEXT,
    registration_status TEXT NOT NULL DEFAULT 'closed',
    capacity INTEGER NOT NULL DEFAULT 0,
    registration_deadline TEXT,
    venue TEXT,
    online_link TEXT,
    organizer TEXT,
    owner TEXT,
    visibility TEXT NOT NULL DEFAULT 'internal',
    member_only INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'draft',
    target_members TEXT,
    related_tags TEXT,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES events(id),
    CHECK(registration_status IN ('closed','open')),
    CHECK(visibility IN ('public','controlled','internal')),
    CHECK(status IN ('draft','published','registration_open','registration_closed','ongoing','completed','cancelled'))
);

CREATE INDEX IF NOT EXISTS ix_v05c_event_status
ON v05c_club_event_profiles(status, registration_status, updated_at DESC);

CREATE TABLE IF NOT EXISTS v05c_club_event_registrations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    registration_no TEXT NOT NULL UNIQUE,
    club_event_id INTEGER NOT NULL,
    membership_id INTEGER,
    applicant_name TEXT NOT NULL,
    organization_name TEXT,
    title TEXT,
    mobile TEXT,
    email TEXT,
    registration_source TEXT NOT NULL DEFAULT 'public',
    status TEXT NOT NULL DEFAULT 'submitted',
    review_note TEXT,
    registered_at TEXT NOT NULL,
    reviewed_at TEXT,
    checked_in_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(club_event_id) REFERENCES v05c_club_event_profiles(id),
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id),
    CHECK(status IN ('submitted','approved','waitlisted','rejected','cancelled'))
);

CREATE INDEX IF NOT EXISTS ix_v05c_registration_event_status
ON v05c_club_event_registrations(club_event_id, status, registered_at DESC);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05c_registration_mobile
ON v05c_club_event_registrations(club_event_id, mobile)
WHERE mobile IS NOT NULL AND mobile <> '';

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05c_registration_email
ON v05c_club_event_registrations(club_event_id, email)
WHERE email IS NOT NULL AND email <> '';

CREATE TABLE IF NOT EXISTS v05c_club_event_participation (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    club_event_id INTEGER NOT NULL,
    registration_id INTEGER,
    membership_id INTEGER,
    attendance_status TEXT NOT NULL DEFAULT 'registered',
    check_in_method TEXT,
    check_in_time TEXT,
    contribution_note TEXT,
    follow_up_note TEXT,
    satisfaction_score INTEGER,
    feedback TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(club_event_id) REFERENCES v05c_club_event_profiles(id),
    FOREIGN KEY(registration_id) REFERENCES v05c_club_event_registrations(id),
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id),
    CHECK(attendance_status IN ('registered','checked_in','attended','absent','left_early')),
    UNIQUE(club_event_id, registration_id)
);

CREATE INDEX IF NOT EXISTS ix_v05c_participation_member
ON v05c_club_event_participation(membership_id, check_in_time DESC);

CREATE TABLE IF NOT EXISTS v05c_member_activity_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    membership_id INTEGER NOT NULL UNIQUE,
    score INTEGER NOT NULL DEFAULT 0,
    level TEXT NOT NULL DEFAULT 'normal',
    details_json TEXT NOT NULL DEFAULT '{}',
    latest_activity_at TEXT,
    risk_reminder TEXT,
    calculated_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id)
);
"""

SAFE_DRAFT_COLUMNS = {
    "source_structure": "TEXT",
    "field_confidence_json": "TEXT",
    "field_evidence_json": "TEXT",
    "quality_flags_json": "TEXT",
    "manually_confirmed_fields": "TEXT",
}


def _backup(db_path: Path) -> str:
    if not db_path.exists():
        return ""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"app_before_v05c_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(db_path, target)
    return str(target)


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = _backup(db_path) if backup else ""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        if "v05b_import_drafts" in {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}:
            existing = _columns(conn, "v05b_import_drafts")
            for column, ddl in SAFE_DRAFT_COLUMNS.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE v05b_import_drafts ADD COLUMN {column} {ddl}")
        conn.commit()
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("v0.5C migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


