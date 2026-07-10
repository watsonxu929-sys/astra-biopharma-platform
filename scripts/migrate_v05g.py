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

from scripts.migrate_v05f import migrate as migrate_v05f

DB_PATH = resolved_db_path()
BACKUP_DIR = DB_PATH.parent / "backups" if (ROOT / "data").resolve() not in DB_PATH.resolve().parents else ROOT / "data" / "backups"

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS v05g_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v05g_processing_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_no TEXT NOT NULL UNIQUE,
    collection_item_id INTEGER,
    snapshot_id INTEGER,
    trigger_type TEXT NOT NULL DEFAULT 'manual',
    status TEXT NOT NULL DEFAULT 'pending',
    priority TEXT NOT NULL DEFAULT 'medium',
    queued_only INTEGER NOT NULL DEFAULT 1,
    reprocess INTEGER NOT NULL DEFAULT 0,
    structure_type TEXT,
    subject_count INTEGER NOT NULL DEFAULT 0,
    block_count INTEGER NOT NULL DEFAULT 0,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    matched_count INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    error_type TEXT,
    error_message TEXT,
    operator_username TEXT,
    started_at TEXT,
    finished_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(collection_item_id) REFERENCES v05f_collection_items(id),
    FOREIGN KEY(snapshot_id) REFERENCES v04g_source_snapshots(id),
    CHECK(status IN ('pending','running','success','needs_review','failed','skipped','cancelled')),
    CHECK(priority IN ('critical','high','medium','low'))
);

CREATE INDEX IF NOT EXISTS ix_v05g_jobs_status
ON v05g_processing_jobs(status, priority, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_v05g_jobs_item
ON v05g_processing_jobs(collection_item_id, created_at DESC);

CREATE TABLE IF NOT EXISTS v05g_processing_blocks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    block_no TEXT NOT NULL UNIQUE,
    processing_job_id INTEGER NOT NULL,
    collection_item_id INTEGER,
    snapshot_id INTEGER,
    block_index INTEGER NOT NULL,
    parent_block_id INTEGER,
    block_type TEXT NOT NULL DEFAULT 'paragraph',
    structure_type TEXT,
    subject_label TEXT,
    subject_type_candidate TEXT,
    text TEXT NOT NULL,
    text_hash TEXT NOT NULL,
    char_start INTEGER NOT NULL DEFAULT 0,
    char_end INTEGER NOT NULL DEFAULT 0,
    evidence_excerpt TEXT,
    confidence_score INTEGER NOT NULL DEFAULT 50,
    warning_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(processing_job_id) REFERENCES v05g_processing_jobs(id),
    FOREIGN KEY(collection_item_id) REFERENCES v05f_collection_items(id),
    FOREIGN KEY(snapshot_id) REFERENCES v04g_source_snapshots(id),
    FOREIGN KEY(parent_block_id) REFERENCES v05g_processing_blocks(id)
);

CREATE INDEX IF NOT EXISTS ix_v05g_blocks_job
ON v05g_processing_blocks(processing_job_id, block_index);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05g_block_hash
ON v05g_processing_blocks(processing_job_id, text_hash, block_index);

CREATE TABLE IF NOT EXISTS v05g_extraction_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_no TEXT NOT NULL UNIQUE,
    processing_job_id INTEGER NOT NULL,
    collection_item_id INTEGER,
    snapshot_id INTEGER,
    block_id INTEGER,
    candidate_type TEXT NOT NULL,
    subject_type TEXT,
    subject_id TEXT,
    subject_label TEXT,
    matched_subject_id TEXT,
    matched_subject_label TEXT,
    field_name TEXT,
    raw_value TEXT,
    normalized_value TEXT,
    payload_json TEXT,
    evidence_excerpt TEXT,
    source_url TEXT,
    source_title TEXT,
    source_position TEXT,
    extraction_rule TEXT,
    fact_level TEXT NOT NULL DEFAULT 'unknown',
    confidence_score INTEGER NOT NULL DEFAULT 50,
    confidence_level TEXT NOT NULL DEFAULT 'medium',
    validation_status TEXT NOT NULL DEFAULT 'needs_review',
    review_status TEXT NOT NULL DEFAULT 'pending',
    review_note TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    applied_at TEXT,
    warning_json TEXT,
    content_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(processing_job_id) REFERENCES v05g_processing_jobs(id),
    FOREIGN KEY(collection_item_id) REFERENCES v05f_collection_items(id),
    FOREIGN KEY(snapshot_id) REFERENCES v04g_source_snapshots(id),
    FOREIGN KEY(block_id) REFERENCES v05g_processing_blocks(id),
    CHECK(candidate_type IN ('organization','person','project','product','event','relationship','resource','need','risk','opportunity','field')),
    CHECK(fact_level IN ('fact','inference','unknown')),
    CHECK(confidence_level IN ('high','medium','low')),
    CHECK(validation_status IN ('valid','needs_review','blocked')),
    CHECK(review_status IN ('pending','approved','rejected','applied','apply_failed','needs_review'))
);

CREATE INDEX IF NOT EXISTS ix_v05g_candidates_review
ON v05g_extraction_candidates(review_status, confidence_score DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_v05g_candidates_subject
ON v05g_extraction_candidates(subject_type, subject_id, matched_subject_id);

CREATE INDEX IF NOT EXISTS ix_v05g_candidates_item
ON v05g_extraction_candidates(collection_item_id, candidate_type);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05g_candidate_dedupe
ON v05g_extraction_candidates(processing_job_id, candidate_type, COALESCE(subject_type,''), COALESCE(subject_label,''), COALESCE(field_name,''), content_hash);

CREATE TABLE IF NOT EXISTS v05g_subject_match_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_no TEXT NOT NULL UNIQUE,
    processing_job_id INTEGER NOT NULL,
    extraction_candidate_id INTEGER,
    collection_item_id INTEGER,
    candidate_subject_type TEXT NOT NULL,
    candidate_label TEXT NOT NULL,
    matched_subject_type TEXT,
    matched_subject_id TEXT,
    matched_subject_label TEXT,
    match_method TEXT NOT NULL,
    match_score INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'candidate',
    ambiguity_count INTEGER NOT NULL DEFAULT 0,
    evidence_excerpt TEXT,
    warning_json TEXT,
    created_at TEXT NOT NULL,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_note TEXT,
    FOREIGN KEY(processing_job_id) REFERENCES v05g_processing_jobs(id),
    FOREIGN KEY(extraction_candidate_id) REFERENCES v05g_extraction_candidates(id),
    FOREIGN KEY(collection_item_id) REFERENCES v05f_collection_items(id),
    CHECK(status IN ('candidate','confirmed','rejected','ambiguous','new_subject'))
);

CREATE INDEX IF NOT EXISTS ix_v05g_matches_status
ON v05g_subject_match_candidates(status, match_score DESC, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_v05g_matches_candidate
ON v05g_subject_match_candidates(extraction_candidate_id, match_score DESC);

CREATE TABLE IF NOT EXISTS v05g_candidate_review_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'manual',
    note TEXT,
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(candidate_id) REFERENCES v05g_extraction_candidates(id)
);

CREATE INDEX IF NOT EXISTS ix_v05g_review_history_candidate
ON v05g_candidate_review_history(candidate_id, created_at DESC);

CREATE TABLE IF NOT EXISTS v05g_candidate_application_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    application_no TEXT NOT NULL UNIQUE,
    target_table TEXT,
    target_external_id TEXT,
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    result TEXT NOT NULL DEFAULT 'success',
    error_message TEXT,
    actor TEXT NOT NULL DEFAULT 'manual',
    applied_at TEXT NOT NULL,
    FOREIGN KEY(candidate_id) REFERENCES v05g_extraction_candidates(id),
    CHECK(result IN ('success','skipped','failed'))
);

CREATE INDEX IF NOT EXISTS ix_v05g_application_candidate
ON v05g_candidate_application_logs(candidate_id, applied_at DESC);
"""


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        target = BACKUP_DIR / f"app_before_v05g_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(db_path, target)
        backup_path = str(target)
    migrate_v05f(db_path, backup=False)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(TABLE_SQL)
        conn.commit()
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("v0.5G migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

