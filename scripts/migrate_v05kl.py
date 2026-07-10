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

from scripts.migrate_v05j import migrate as migrate_v05j

DB_PATH = resolved_db_path()
BACKUP_DIR = DB_PATH.parent / "backups" if (ROOT / "data").resolve() not in DB_PATH.resolve().parents else ROOT / "data" / "backups"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS v05kl_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS task_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_uid TEXT NOT NULL UNIQUE,
    task_type TEXT NOT NULL,
    queue_name TEXT NOT NULL DEFAULT 'default',
    status TEXT NOT NULL DEFAULT 'pending',
    priority INTEGER NOT NULL DEFAULT 100,
    payload_json TEXT NOT NULL DEFAULT '{}',
    idempotency_key TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    not_before TEXT,
    locked_by TEXT,
    locked_at TEXT,
    heartbeat_at TEXT,
    timeout_seconds INTEGER NOT NULL DEFAULT 600,
    error_code TEXT,
    error_summary TEXT,
    result_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    finished_at TEXT,
    CHECK(status IN ('pending','running','success','failed','retrying','cancelled','dead'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_task_queue_idempotency
ON task_queue(task_type, idempotency_key)
WHERE idempotency_key IS NOT NULL AND status IN ('pending','running','retrying','success');

CREATE INDEX IF NOT EXISTS ix_task_queue_claim
ON task_queue(queue_name, task_type, status, priority, not_before, id);

CREATE TABLE IF NOT EXISTS task_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    run_uid TEXT NOT NULL UNIQUE,
    worker_id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'running',
    started_at TEXT NOT NULL,
    finished_at TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_summary TEXT,
    result_json TEXT NOT NULL DEFAULT '{}',
    FOREIGN KEY(task_id) REFERENCES task_queue(id)
);

CREATE INDEX IF NOT EXISTS ix_task_runs_task ON task_runs(task_id, started_at DESC);

CREATE TABLE IF NOT EXISTS worker_heartbeats (
    worker_id TEXT PRIMARY KEY,
    queue_name TEXT NOT NULL DEFAULT 'default',
    task_type TEXT,
    pid INTEGER,
    hostname TEXT,
    status TEXT NOT NULL DEFAULT 'online',
    started_at TEXT NOT NULL,
    heartbeat_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS scheduler_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_key TEXT NOT NULL UNIQUE,
    task_type TEXT NOT NULL,
    queue_name TEXT NOT NULL DEFAULT 'default',
    cron_expr TEXT,
    interval_seconds INTEGER NOT NULL DEFAULT 86400,
    payload_json TEXT NOT NULL DEFAULT '{}',
    enabled INTEGER NOT NULL DEFAULT 1,
    last_scheduled_at TEXT,
    next_run_at TEXT,
    misfire_policy TEXT NOT NULL DEFAULT 'skip',
    timezone TEXT NOT NULL DEFAULT 'local',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(enabled IN (0,1))
);

CREATE TABLE IF NOT EXISTS scheduler_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    schedule_key TEXT NOT NULL,
    task_id INTEGER,
    status TEXT NOT NULL,
    scheduled_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    note TEXT,
    FOREIGN KEY(task_id) REFERENCES task_queue(id)
);

CREATE TABLE IF NOT EXISTS backup_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    backup_id TEXT NOT NULL UNIQUE,
    backup_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'success',
    environment TEXT,
    database_backend TEXT,
    backup_path TEXT NOT NULL,
    manifest_json TEXT NOT NULL DEFAULT '{}',
    sha256 TEXT,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    error_summary TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS restore_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restore_id TEXT NOT NULL UNIQUE,
    backup_id TEXT,
    status TEXT NOT NULL,
    dry_run INTEGER NOT NULL DEFAULT 1,
    target_path TEXT,
    validation_json TEXT NOT NULL DEFAULT '{}',
    error_summary TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    CHECK(dry_run IN (0,1))
);

CREATE TABLE IF NOT EXISTS system_health_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    snapshot_at TEXT NOT NULL,
    status TEXT NOT NULL,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_health_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    source_key TEXT,
    source_name TEXT,
    lifecycle_status TEXT NOT NULL DEFAULT 'pilot',
    source_grade TEXT NOT NULL DEFAULT 'C',
    health_score INTEGER NOT NULL DEFAULT 0,
    credibility_score INTEGER NOT NULL DEFAULT 0,
    success_rate REAL,
    quality_score REAL,
    last_run_at TEXT,
    needs_attention INTEGER NOT NULL DEFAULT 0,
    metrics_json TEXT NOT NULL DEFAULT '{}',
    calculated_at TEXT NOT NULL,
    UNIQUE(source_id, calculated_at)
);

CREATE TABLE IF NOT EXISTS source_quality_samples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sample_no TEXT NOT NULL UNIQUE,
    source_id INTEGER,
    sample_type TEXT NOT NULL,
    related_table TEXT,
    related_id INTEGER,
    correctness TEXT NOT NULL DEFAULT 'pending',
    error_type TEXT,
    reviewer TEXT,
    note TEXT,
    evidence_ref TEXT,
    created_at TEXT NOT NULL,
    reviewed_at TEXT
);

CREATE TABLE IF NOT EXISTS source_rule_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    rule_key TEXT NOT NULL,
    rule_version TEXT NOT NULL,
    previous_version TEXT,
    current_status TEXT NOT NULL DEFAULT 'draft',
    rule_config_json TEXT NOT NULL DEFAULT '{}',
    changed_by TEXT,
    change_reason TEXT,
    created_at TEXT NOT NULL,
    UNIQUE(source_id, rule_key, rule_version)
);

CREATE TABLE IF NOT EXISTS source_rule_test_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id INTEGER,
    old_rule_version TEXT,
    new_rule_version TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    comparison_json TEXT NOT NULL DEFAULT '{}',
    created_by TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS data_quality_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    metric_key TEXT NOT NULL,
    metric_label TEXT NOT NULL,
    metric_value REAL,
    sample_size INTEGER NOT NULL DEFAULT 0,
    window_start TEXT,
    window_end TEXT,
    source_type TEXT,
    note TEXT,
    calculated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_data_quality_metrics_key
ON data_quality_metrics(metric_key, calculated_at DESC);

CREATE TABLE IF NOT EXISTS quality_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_no TEXT NOT NULL UNIQUE,
    report_type TEXT NOT NULL DEFAULT 'weekly_quality',
    period_start TEXT,
    period_end TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    metrics_json TEXT NOT NULL DEFAULT '{}',
    sample_refs_json TEXT NOT NULL DEFAULT '[]',
    content_markdown TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS performance_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    target TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'success',
    detail_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);
"""


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        target = BACKUP_DIR / f"app_before_v05kl_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(db_path, target)
        backup_path = str(target)
    migrate_v05j(db_path, backup=False)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        _seed_scheduler(conn)
        conn.commit()
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def _seed_scheduler(conn: sqlite3.Connection) -> None:
    now = datetime.now().replace(microsecond=0).isoformat()
    rows = [
        ("due_collection", "collection", 3600, {"due_only": True, "limit": 20}, 1),
        ("daily_backup", "backup", 86400, {"backup_type": "daily"}, 0),
        ("daily_source_health", "source_health_check", 86400, {}, 0),
        ("weekly_quality_report", "quality_sample", 604800, {"report": "weekly_quality"}, 0),
    ]
    for key, task_type, interval, payload, enabled in rows:
        conn.execute(
            """
            INSERT OR IGNORE INTO scheduler_jobs(schedule_key,task_type,interval_seconds,payload_json,enabled,next_run_at,created_at,updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (key, task_type, interval, __import__("json").dumps(payload, ensure_ascii=False), enabled, now, now, now),
        )


def main() -> int:
    result = migrate()
    print("v0.5K-L migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

