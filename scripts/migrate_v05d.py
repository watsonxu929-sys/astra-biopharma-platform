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
CREATE TABLE IF NOT EXISTS v05d_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v05d_member_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_no TEXT NOT NULL UNIQUE,
    membership_id INTEGER NOT NULL UNIQUE,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    status TEXT NOT NULL DEFAULT 'invited',
    must_change_password INTEGER NOT NULL DEFAULT 0,
    activated_at TEXT,
    last_login_at TEXT,
    failed_login_count INTEGER NOT NULL DEFAULT 0,
    locked_until TEXT,
    session_version INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deactivated_at TEXT,
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id),
    CHECK(status IN ('invited','active','locked','suspended','deactivated'))
);

CREATE INDEX IF NOT EXISTS ix_v05d_member_accounts_status
ON v05d_member_accounts(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS v05d_activation_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL DEFAULT 'active',
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(account_id) REFERENCES v05d_member_accounts(id),
    CHECK(status IN ('active','used','revoked','expired'))
);

CREATE INDEX IF NOT EXISTS ix_v05d_activation_account
ON v05d_activation_tokens(account_id, status, expires_at);

CREATE TABLE IF NOT EXISTS v05d_password_reset_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_no TEXT NOT NULL UNIQUE,
    account_id INTEGER,
    username TEXT,
    verification_note TEXT,
    status TEXT NOT NULL DEFAULT 'submitted',
    token_hash TEXT,
    expires_at TEXT,
    reviewed_by TEXT,
    review_note TEXT,
    submitted_at TEXT NOT NULL,
    reviewed_at TEXT,
    used_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(account_id) REFERENCES v05d_member_accounts(id),
    CHECK(status IN ('submitted','approved','rejected','token_created','used','expired'))
);

CREATE TABLE IF NOT EXISTS v05d_profile_change_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_no TEXT NOT NULL UNIQUE,
    membership_id INTEGER NOT NULL,
    field_name TEXT NOT NULL,
    current_value TEXT,
    proposed_value TEXT,
    evidence_note TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewed_by TEXT,
    review_note TEXT,
    submitted_at TEXT NOT NULL,
    reviewed_at TEXT,
    applied_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id),
    CHECK(status IN ('pending','approved','rejected','withdrawn','applied','apply_failed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05d_profile_pending_field
ON v05d_profile_change_requests(membership_id, field_name)
WHERE status='pending';

CREATE TABLE IF NOT EXISTS v05d_member_privacy_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    membership_id INTEGER NOT NULL UNIQUE,
    show_avatar INTEGER NOT NULL DEFAULT 0,
    show_organization INTEGER NOT NULL DEFAULT 0,
    show_title INTEGER NOT NULL DEFAULT 0,
    show_city INTEGER NOT NULL DEFAULT 0,
    show_expertise INTEGER NOT NULL DEFAULT 0,
    show_offerings INTEGER NOT NULL DEFAULT 0,
    show_needs INTEGER NOT NULL DEFAULT 0,
    allow_matching INTEGER NOT NULL DEFAULT 1,
    allow_event_invites INTEGER NOT NULL DEFAULT 1,
    allow_internal_contact INTEGER NOT NULL DEFAULT 1,
    allow_member_directory INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id)
);

CREATE TABLE IF NOT EXISTS v05d_member_content_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    request_no TEXT NOT NULL UNIQUE,
    membership_id INTEGER NOT NULL,
    content_type TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT,
    industry_tags TEXT,
    region TEXT,
    urgency_or_availability TEXT,
    valid_until TEXT,
    cooperation_preference TEXT,
    allow_matching INTEGER NOT NULL DEFAULT 1,
    related_candidate TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    official_record_id INTEGER,
    reviewed_by TEXT,
    review_note TEXT,
    submitted_at TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id),
    CHECK(content_type IN ('need','offering')),
    CHECK(status IN ('draft','submitted','approved','rejected','need_more_info','withdrawn','published','stopped'))
);

CREATE INDEX IF NOT EXISTS ix_v05d_content_status
ON v05d_member_content_requests(content_type, status, updated_at DESC);

CREATE TABLE IF NOT EXISTS v05d_member_match_feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feedback_no TEXT NOT NULL UNIQUE,
    match_id INTEGER NOT NULL,
    membership_id INTEGER NOT NULL,
    side TEXT NOT NULL,
    feedback TEXT NOT NULL,
    note TEXT,
    status_after TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(match_id) REFERENCES v04f_club_matches(id),
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id),
    CHECK(side IN ('requester','provider')),
    CHECK(feedback IN ('interested','unsure','not_interested','already_cooperating','need_operator_contact','info_inaccurate'))
);

CREATE INDEX IF NOT EXISTS ix_v05d_match_feedback_member
ON v05d_member_match_feedback(membership_id, created_at DESC);

CREATE TABLE IF NOT EXISTS v05d_member_notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    notification_no TEXT NOT NULL UNIQUE,
    membership_id INTEGER NOT NULL,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    body TEXT,
    related_type TEXT,
    related_id TEXT,
    status TEXT NOT NULL DEFAULT 'unread',
    read_at TEXT,
    created_at TEXT NOT NULL,
    expires_at TEXT,
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id),
    CHECK(category IN ('account','profile','event','matching','need','offering','review','system')),
    CHECK(status IN ('unread','read','archived'))
);

CREATE INDEX IF NOT EXISTS ix_v05d_notifications_member
ON v05d_member_notifications(membership_id, status, created_at DESC);

CREATE TABLE IF NOT EXISTS v05d_announcements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    announcement_no TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    target_type TEXT NOT NULL DEFAULT 'all',
    target_value TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    recipient_count INTEGER NOT NULL DEFAULT 0,
    created_by TEXT,
    published_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    published_at TEXT,
    revoked_at TEXT,
    CHECK(target_type IN ('all','level','industry','event','member')),
    CHECK(status IN ('draft','published','revoked'))
);
"""

SAFE_MEMBER_COLUMNS = {
    "is_org_contact": "INTEGER NOT NULL DEFAULT 0",
    "is_org_admin_candidate": "INTEGER NOT NULL DEFAULT 0",
    "org_admin_status": "TEXT",
}


def _backup(db_path: Path) -> str:
    if not db_path.exists():
        return ""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    target = BACKUP_DIR / f"app_before_v05d_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(db_path, target)
    return str(target)


def _tables(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def _columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = _backup(db_path) if backup else ""
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        if "v04f_club_memberships" in _tables(conn):
            existing = _columns(conn, "v04f_club_memberships")
            for column, ddl in SAFE_MEMBER_COLUMNS.items():
                if column not in existing:
                    conn.execute(f"ALTER TABLE v04f_club_memberships ADD COLUMN {column} {ddl}")
        conn.commit()
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("v0.5D migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

