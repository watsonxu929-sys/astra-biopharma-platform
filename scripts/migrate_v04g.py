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
CREATE TABLE IF NOT EXISTS v04g_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v04g_monitoring_sources (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_no TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    url TEXT NOT NULL,
    subject_type TEXT,
    subject_id TEXT,
    check_frequency TEXT NOT NULL DEFAULT 'manual',
    is_enabled INTEGER NOT NULL DEFAULT 1,
    owner TEXT,
    fetch_mode TEXT NOT NULL DEFAULT 'web',
    last_checked_at TEXT,
    last_changed_at TEXT,
    last_success_at TEXT,
    last_error_at TEXT,
    consecutive_failures INTEGER NOT NULL DEFAULT 0,
    note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deactivated_at TEXT,
    CHECK(subject_type IS NULL OR subject_type IN ('organization','person','project','event','resource')),
    CHECK(fetch_mode IN ('web','manual')),
    CHECK(is_enabled IN (0,1))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04g_active_source_scope
ON v04g_monitoring_sources(url, COALESCE(subject_type, ''), COALESCE(subject_id, ''))
WHERE deactivated_at IS NULL;

CREATE INDEX IF NOT EXISTS ix_v04g_source_enabled
ON v04g_monitoring_sources(is_enabled, last_checked_at, consecutive_failures);

CREATE TABLE IF NOT EXISTS v04g_monitoring_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_no TEXT NOT NULL UNIQUE,
    monitoring_source_id INTEGER NOT NULL,
    status TEXT NOT NULL,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    http_status INTEGER,
    content_length INTEGER NOT NULL DEFAULT 0,
    content_hash TEXT,
    changed INTEGER NOT NULL DEFAULT 0,
    error_type TEXT,
    error_message TEXT,
    diff_summary TEXT,
    created_snapshot_id INTEGER,
    created_proposal_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    CHECK(status IN ('pending','running','success','unchanged','partial','failed','skipped')),
    FOREIGN KEY(monitoring_source_id) REFERENCES v04g_monitoring_sources(id)
);

CREATE INDEX IF NOT EXISTS ix_v04g_run_source_time
ON v04g_monitoring_runs(monitoring_source_id, created_at DESC);

CREATE TABLE IF NOT EXISTS v04g_source_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_no TEXT NOT NULL UNIQUE,
    monitoring_source_id INTEGER NOT NULL,
    monitoring_run_id INTEGER NOT NULL,
    page_title TEXT,
    url TEXT,
    captured_at TEXT NOT NULL,
    raw_content TEXT,
    cleaned_text TEXT,
    content_hash TEXT NOT NULL,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(monitoring_source_id, content_hash),
    FOREIGN KEY(monitoring_source_id) REFERENCES v04g_monitoring_sources(id),
    FOREIGN KEY(monitoring_run_id) REFERENCES v04g_monitoring_runs(id)
);

CREATE INDEX IF NOT EXISTS ix_v04g_snapshot_source_time
ON v04g_source_snapshots(monitoring_source_id, created_at DESC);

CREATE TABLE IF NOT EXISTS v04g_update_proposals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_no TEXT NOT NULL UNIQUE,
    monitoring_source_id INTEGER NOT NULL,
    monitoring_run_id INTEGER NOT NULL,
    snapshot_id INTEGER,
    subject_type TEXT,
    subject_id TEXT,
    proposal_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT,
    proposed_value TEXT,
    evidence_excerpt TEXT,
    confidence_level TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'pending',
    conflict_level TEXT NOT NULL DEFAULT 'none',
    review_note TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    applied_at TEXT,
    apply_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(status IN ('pending','under_review','approved','rejected','ignored','applied','apply_failed','expired')),
    CHECK(confidence_level IN ('low','medium','high')),
    CHECK(conflict_level IN ('none','value_conflict','candidate_conflict','manual_required')),
    FOREIGN KEY(monitoring_source_id) REFERENCES v04g_monitoring_sources(id),
    FOREIGN KEY(monitoring_run_id) REFERENCES v04g_monitoring_runs(id),
    FOREIGN KEY(snapshot_id) REFERENCES v04g_source_snapshots(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04g_open_proposal
ON v04g_update_proposals(
    monitoring_source_id,
    COALESCE(subject_type, ''),
    COALESCE(subject_id, ''),
    proposal_type,
    field_name,
    COALESCE(proposed_value, '')
)
WHERE status IN ('pending','under_review');

CREATE INDEX IF NOT EXISTS ix_v04g_proposal_status
ON v04g_update_proposals(status, created_at DESC);

CREATE TABLE IF NOT EXISTS v04g_update_apply_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    proposal_id INTEGER NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    table_name TEXT NOT NULL,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    snapshot_id INTEGER,
    applied_by TEXT,
    applied_at TEXT NOT NULL,
    note TEXT,
    FOREIGN KEY(proposal_id) REFERENCES v04g_update_proposals(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04g_apply_once
ON v04g_update_apply_logs(proposal_id);
"""


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = BACKUP_DIR / f"app_before_v04g_{stamp}.db"
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
    print("v0.4G migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

