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
CREATE TABLE IF NOT EXISTS v05e_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v05e_industry_signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_no TEXT NOT NULL UNIQUE,
    signal_type TEXT NOT NULL,
    signal_level TEXT NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    subject_type TEXT,
    subject_id TEXT,
    occurred_at TEXT,
    discovered_at TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    evidence_excerpt TEXT,
    confidence INTEGER NOT NULL DEFAULT 60,
    level_reason TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    is_read INTEGER NOT NULL DEFAULT 0,
    converted_action_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(signal_level IN ('critical','high','medium','low')),
    CHECK(status IN ('new','reviewed','important','ignored','converted','expired')),
    CHECK(is_read IN (0,1)),
    CHECK(confidence BETWEEN 0 AND 100)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05e_signal_source
ON v05e_industry_signals(source_type, source_id, signal_type, COALESCE(subject_type,''), COALESCE(subject_id,''));

CREATE INDEX IF NOT EXISTS ix_v05e_signal_status_level
ON v05e_industry_signals(status, signal_level, discovered_at DESC);

CREATE INDEX IF NOT EXISTS ix_v05e_signal_subject
ON v05e_industry_signals(subject_type, subject_id, discovered_at DESC);

CREATE TABLE IF NOT EXISTS v05e_watchlists (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_no TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    category TEXT NOT NULL,
    description TEXT,
    owner_user_id INTEGER,
    owner_username TEXT,
    visibility TEXT NOT NULL DEFAULT 'private',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(category IN ('key_organization','key_person','key_project','key_track','investment_target','investment_observation','cooperation_opportunity','risk_observation','custom')),
    CHECK(visibility IN ('private','team')),
    CHECK(status IN ('active','archived'))
);

CREATE INDEX IF NOT EXISTS ix_v05e_watchlist_owner
ON v05e_watchlists(owner_user_id, visibility, status);

CREATE TABLE IF NOT EXISTS v05e_watchlist_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    watchlist_id INTEGER NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    reason TEXT,
    owner_user_id INTEGER,
    owner_username TEXT,
    added_at TEXT NOT NULL,
    last_reviewed_at TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    note TEXT,
    removed_at TEXT,
    FOREIGN KEY(watchlist_id) REFERENCES v05e_watchlists(id),
    CHECK(subject_type IN ('organization','person','project')),
    CHECK(priority IN ('critical','high','medium','low')),
    CHECK(status IN ('active','removed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05e_watchlist_active_item
ON v05e_watchlist_items(watchlist_id, subject_type, subject_id)
WHERE status='active';

CREATE INDEX IF NOT EXISTS ix_v05e_watchlist_item_subject
ON v05e_watchlist_items(subject_type, subject_id, status);
"""


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        target = BACKUP_DIR / f"app_before_v05e_{datetime.now():%Y%m%d_%H%M%S}.db"
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
    print("v0.5E migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

