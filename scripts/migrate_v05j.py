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

from scripts.migrate_v05i import migrate as migrate_v05i
from scripts.migrate_v04f import migrate as migrate_v04f

DB_PATH = resolved_db_path()
BACKUP_DIR = DB_PATH.parent / "backups" if (ROOT / "data").resolve() not in DB_PATH.resolve().parents else ROOT / "data" / "backups"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS v05j_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS research_topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_no TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT,
    topic_type TEXT NOT NULL DEFAULT 'custom',
    status TEXT NOT NULL DEFAULT 'draft',
    track_tags TEXT,
    region_filters TEXT,
    subject_types TEXT,
    time_range_type TEXT NOT NULL DEFAULT 'custom',
    period_start TEXT,
    period_end TEXT,
    owner_id INTEGER,
    visibility TEXT NOT NULL DEFAULT 'team',
    refresh_mode TEXT NOT NULL DEFAULT 'manual',
    last_refreshed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(status IN ('draft','active','paused','archived'))
);

CREATE INDEX IF NOT EXISTS ix_research_topics_status
ON research_topics(status, topic_type, updated_at DESC);

CREATE TABLE IF NOT EXISTS research_topic_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    inclusion_type TEXT NOT NULL DEFAULT 'manual',
    reason TEXT,
    source TEXT,
    added_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(topic_id) REFERENCES research_topics(id),
    UNIQUE(topic_id, subject_type, subject_id),
    CHECK(inclusion_type IN ('manual','rule','imported','recommended'))
);

CREATE INDEX IF NOT EXISTS ix_research_topic_subjects
ON research_topic_subjects(topic_id, subject_type, subject_id);

CREATE TABLE IF NOT EXISTS research_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    snapshot_at TEXT NOT NULL,
    subject_count INTEGER NOT NULL DEFAULT 0,
    event_count INTEGER NOT NULL DEFAULT 0,
    signal_count INTEGER NOT NULL DEFAULT 0,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    source_version TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(topic_id) REFERENCES research_topics(id)
);

CREATE INDEX IF NOT EXISTS ix_research_snapshots_topic
ON research_snapshots(topic_id, snapshot_at DESC);

CREATE TABLE IF NOT EXISTS investment_assessments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_no TEXT NOT NULL UNIQUE,
    organization_id TEXT NOT NULL,
    topic_id INTEGER,
    assessment_type TEXT NOT NULL DEFAULT 'single_company',
    regional_type TEXT,
    track TEXT,
    stage TEXT,
    score_total INTEGER,
    score_breakdown_json TEXT NOT NULL DEFAULT '{}',
    grade TEXT NOT NULL DEFAULT 'UNVERIFIED',
    qbay_fit TEXT,
    qiantang_rental_fit TEXT,
    qiantang_land_fit TEXT,
    constraints_json TEXT NOT NULL DEFAULT '[]',
    opportunities_json TEXT NOT NULL DEFAULT '[]',
    relationship_clues_json TEXT NOT NULL DEFAULT '[]',
    recommended_actions_json TEXT NOT NULL DEFAULT '[]',
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    data_gaps_json TEXT NOT NULL DEFAULT '[]',
    rule_version TEXT NOT NULL DEFAULT 'qbay-investment-assistant-1.0.0',
    status TEXT NOT NULL DEFAULT 'draft',
    reviewed_by TEXT,
    reviewed_at TEXT,
    lead_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(topic_id) REFERENCES research_topics(id),
    FOREIGN KEY(lead_id) REFERENCES v04f_lead_records(id),
    CHECK(status IN ('draft','generated','needs_review','approved','rejected','outdated'))
);

CREATE INDEX IF NOT EXISTS ix_investment_assessments_org
ON investment_assessments(organization_id, status, updated_at DESC);
"""


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        target = BACKUP_DIR / f"app_before_v05j_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(db_path, target)
        backup_path = str(target)
    migrate_v05i(db_path, backup=False)
    migrate_v04f(db_path, backup=False)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        _ensure_column(conn, "events", "related_organization_id", "INTEGER")
        _ensure_column(conn, "resources", "owner_organization_id", "INTEGER")
        _ensure_column(conn, "projects", "owner_organization_id", "INTEGER")
        conn.commit()
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    if table not in tables:
        return
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    if column not in columns:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def main() -> int:
    result = migrate()
    print("v0.5J migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

