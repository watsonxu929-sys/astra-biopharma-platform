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
CREATE TABLE IF NOT EXISTS v05b_import_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_no TEXT NOT NULL UNIQUE,
    import_type TEXT NOT NULL,
    original_filename TEXT,
    source_url TEXT,
    raw_text TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    total_count INTEGER NOT NULL DEFAULT 0,
    selected_count INTEGER NOT NULL DEFAULT 0,
    saved_count INTEGER NOT NULL DEFAULT 0,
    failed_count INTEGER NOT NULL DEFAULT 0,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    completed_at TEXT,
    CHECK(status IN ('draft','reviewing','partially_saved','completed','failed','cancelled'))
);

CREATE INDEX IF NOT EXISTS ix_v05b_jobs_status_created
ON v05b_import_jobs(status, created_at DESC);

CREATE TABLE IF NOT EXISTS v05b_media_assets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asset_no TEXT NOT NULL UNIQUE,
    job_id INTEGER,
    draft_id INTEGER,
    membership_id INTEGER,
    person_id INTEGER,
    asset_type TEXT NOT NULL DEFAULT 'avatar',
    original_filename TEXT,
    stored_filename TEXT NOT NULL,
    mime_type TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    width INTEGER,
    height INTEGER,
    source_type TEXT NOT NULL DEFAULT 'upload',
    source_url TEXT,
    source_title TEXT,
    source_locator TEXT,
    sha256 TEXT,
    is_active INTEGER NOT NULL DEFAULT 1,
    confirmed_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deactivated_at TEXT,
    FOREIGN KEY(job_id) REFERENCES v05b_import_jobs(id)
);

CREATE INDEX IF NOT EXISTS ix_v05b_media_member
ON v05b_media_assets(membership_id, is_active, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_v05b_media_job
ON v05b_media_assets(job_id, draft_id, is_active);

CREATE TABLE IF NOT EXISTS v05b_import_drafts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    row_no INTEGER NOT NULL DEFAULT 1,
    source_locator TEXT,
    name TEXT,
    organization_name TEXT,
    title TEXT,
    mobile TEXT,
    email TEXT,
    wechat TEXT,
    city TEXT,
    industry_tags TEXT,
    expertise_tags TEXT,
    offered_resources TEXT,
    cooperation_needs TEXT,
    self_introduction TEXT,
    referral_source TEXT,
    referrer_name TEXT,
    preferred_contact_method TEXT,
    member_level TEXT NOT NULL DEFAULT 'standard',
    member_status TEXT NOT NULL DEFAULT 'active',
    owner TEXT,
    source_text TEXT,
    warnings_json TEXT,
    duplicate_json TEXT,
    image_asset_id INTEGER,
    selected INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft',
    saved_person_id INTEGER,
    saved_organization_id INTEGER,
    saved_membership_id INTEGER,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(job_id, row_no),
    FOREIGN KEY(job_id) REFERENCES v05b_import_jobs(id),
    FOREIGN KEY(image_asset_id) REFERENCES v05b_media_assets(id),
    CHECK(member_status IN ('pending','active','inactive','suspended','exited')),
    CHECK(status IN ('draft','ready','saved','skipped','failed'))
);

CREATE INDEX IF NOT EXISTS ix_v05b_drafts_job_status
ON v05b_import_drafts(job_id, status, row_no);

CREATE TABLE IF NOT EXISTS v05b_member_contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    membership_id INTEGER NOT NULL UNIQUE,
    mobile TEXT,
    email TEXT,
    wechat TEXT,
    preferred_contact_method TEXT,
    source_job_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id),
    FOREIGN KEY(source_job_id) REFERENCES v05b_import_jobs(id)
);

CREATE INDEX IF NOT EXISTS ix_v05b_contacts_mobile
ON v05b_member_contacts(mobile);

CREATE INDEX IF NOT EXISTS ix_v05b_contacts_email
ON v05b_member_contacts(email);

CREATE TABLE IF NOT EXISTS v05b_web_image_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id INTEGER NOT NULL,
    draft_id INTEGER,
    source_url TEXT NOT NULL,
    image_url TEXT NOT NULL,
    alt_text TEXT,
    local_asset_id INTEGER,
    status TEXT NOT NULL DEFAULT 'candidate',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(job_id, image_url),
    FOREIGN KEY(job_id) REFERENCES v05b_import_jobs(id),
    FOREIGN KEY(draft_id) REFERENCES v05b_import_drafts(id),
    FOREIGN KEY(local_asset_id) REFERENCES v05b_media_assets(id),
    CHECK(status IN ('candidate','assigned','ignored','failed'))
);

CREATE INDEX IF NOT EXISTS ix_v05b_web_images_job
ON v05b_web_image_candidates(job_id, status, id);
"""


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = BACKUP_DIR / f"app_before_v05b_{stamp}.db"
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
    print("v0.5B migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

