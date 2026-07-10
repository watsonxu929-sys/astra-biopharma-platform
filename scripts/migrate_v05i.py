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

from scripts.migrate_v05h import migrate as migrate_v05h

DB_PATH = resolved_db_path()
BACKUP_DIR = DB_PATH.parent / "backups" if (ROOT / "data").resolve() not in DB_PATH.resolve().parents else ROOT / "data" / "backups"

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS v05i_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v05i_pipeline_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_no TEXT NOT NULL UNIQUE,
    source_id INTEGER NOT NULL,
    collection_job_id INTEGER,
    collection_item_count INTEGER NOT NULL DEFAULT 0,
    processing_job_count INTEGER NOT NULL DEFAULT 0,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    approved_candidate_count INTEGER NOT NULL DEFAULT 0,
    applied_count INTEGER NOT NULL DEFAULT 0,
    signal_count INTEGER NOT NULL DEFAULT 0,
    report_job_id INTEGER,
    current_stage TEXT NOT NULL DEFAULT 'pending',
    status TEXT NOT NULL DEFAULT 'pending',
    started_at TEXT,
    finished_at TEXT,
    failed_stage TEXT,
    error_code TEXT,
    error_summary TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    pilot_mode INTEGER NOT NULL DEFAULT 1,
    dry_run INTEGER NOT NULL DEFAULT 1,
    actual_scope_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(source_id) REFERENCES v04g_monitoring_sources(id),
    FOREIGN KEY(collection_job_id) REFERENCES v04g_monitoring_runs(id),
    FOREIGN KEY(report_job_id) REFERENCES v05h_report_jobs(id),
    CHECK(status IN ('pending','collecting','collected','processing','waiting_review','applying','signaling','reporting','completed','partial','failed','cancelled')),
    CHECK(current_stage IN ('pending','collecting','collected','processing','waiting_review','applying','signaling','reporting','completed','failed','cancelled')),
    CHECK(pilot_mode IN (0,1)),
    CHECK(dry_run IN (0,1))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05i_source_active_run
ON v05i_pipeline_runs(source_id)
WHERE status IN ('pending','collecting','collected','processing','waiting_review','applying','signaling','reporting');

CREATE INDEX IF NOT EXISTS ix_v05i_pipeline_status
ON v05i_pipeline_runs(status, current_stage, created_at DESC);

CREATE TABLE IF NOT EXISTS v05i_pipeline_stage_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_id INTEGER NOT NULL,
    stage_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    related_table TEXT,
    related_id INTEGER,
    count_value INTEGER NOT NULL DEFAULT 0,
    started_at TEXT,
    finished_at TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_summary TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(pipeline_run_id) REFERENCES v05i_pipeline_runs(id),
    CHECK(status IN ('pending','running','success','waiting_review','skipped','failed','cancelled'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05i_stage_once
ON v05i_pipeline_stage_runs(pipeline_run_id, stage_name, COALESCE(related_table,''), COALESCE(related_id,0));

CREATE TABLE IF NOT EXISTS v05i_pipeline_quality_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_no TEXT NOT NULL UNIQUE,
    pipeline_run_id INTEGER,
    source_id INTEGER,
    sample_type TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    target_no TEXT,
    review_status TEXT NOT NULL DEFAULT 'pending',
    correctness TEXT,
    error_type TEXT,
    reviewer TEXT,
    review_note TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(pipeline_run_id) REFERENCES v05i_pipeline_runs(id),
    CHECK(review_status IN ('pending','reviewed')),
    CHECK(correctness IS NULL OR correctness IN ('correct','incorrect','partial'))
);

CREATE INDEX IF NOT EXISTS ix_v05i_samples_status
ON v05i_pipeline_quality_samples(review_status, sample_type, created_at DESC);

CREATE TABLE IF NOT EXISTS v05i_pilot_source_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_key TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    expected_structure TEXT,
    last_run_at TEXT,
    last_result TEXT,
    passed INTEGER NOT NULL DEFAULT 0,
    known_limits TEXT,
    acceptance_note TEXT,
    pipeline_run_id INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(pipeline_run_id) REFERENCES v05i_pipeline_runs(id),
    CHECK(passed IN (0,1))
);

CREATE INDEX IF NOT EXISTS ix_v05i_pilot_results
ON v05i_pilot_source_results(source_type, last_run_at DESC);
"""


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        target = BACKUP_DIR / f"app_before_v05i_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(db_path, target)
        backup_path = str(target)
    migrate_v05h(db_path, backup=False)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(TABLE_SQL)
        conn.commit()
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("v0.5I migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

