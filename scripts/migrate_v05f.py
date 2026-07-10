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

from scripts.migrate_v04g import SCHEMA_SQL as V04G_SCHEMA_SQL

DB_PATH = resolved_db_path()
BACKUP_DIR = DB_PATH.parent / "backups" if (ROOT / "data").resolve() not in DB_PATH.resolve().parents else ROOT / "data" / "backups"


TABLE_SQL = """
CREATE TABLE IF NOT EXISTS v05f_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v05f_discovered_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_no TEXT NOT NULL UNIQUE,
    monitoring_source_id INTEGER NOT NULL,
    monitoring_run_id INTEGER,
    parent_snapshot_id INTEGER,
    source_url TEXT NOT NULL,
    normalized_url TEXT NOT NULL,
    canonical_url TEXT,
    link_text TEXT,
    title_candidate TEXT,
    published_at_candidate TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    reason TEXT,
    depth INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(monitoring_source_id) REFERENCES v04g_monitoring_sources(id),
    FOREIGN KEY(monitoring_run_id) REFERENCES v04g_monitoring_runs(id),
    FOREIGN KEY(parent_snapshot_id) REFERENCES v04g_source_snapshots(id),
    CHECK(status IN ('new','queued','fetched','duplicate','skipped','failed'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05f_link_source_url
ON v05f_discovered_links(monitoring_source_id, normalized_url);

CREATE INDEX IF NOT EXISTS ix_v05f_link_status
ON v05f_discovered_links(status, created_at DESC);

CREATE TABLE IF NOT EXISTS v05f_collection_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_no TEXT NOT NULL UNIQUE,
    monitoring_source_id INTEGER NOT NULL,
    monitoring_run_id INTEGER NOT NULL,
    snapshot_id INTEGER,
    discovered_link_id INTEGER,
    title TEXT,
    original_url TEXT,
    normalized_url TEXT,
    canonical_url TEXT,
    published_at TEXT,
    captured_at TEXT NOT NULL,
    content_type TEXT,
    page_structure TEXT,
    language TEXT,
    dedup_status TEXT NOT NULL DEFAULT 'new',
    change_status TEXT NOT NULL DEFAULT 'new',
    processing_status TEXT NOT NULL DEFAULT 'queued',
    priority TEXT NOT NULL DEFAULT 'medium',
    subject_type_candidate TEXT,
    subject_id_candidate TEXT,
    content_hash TEXT,
    structure_hash TEXT,
    duplicate_of_item_id INTEGER,
    warning_json TEXT,
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(monitoring_source_id) REFERENCES v04g_monitoring_sources(id),
    FOREIGN KEY(monitoring_run_id) REFERENCES v04g_monitoring_runs(id),
    FOREIGN KEY(snapshot_id) REFERENCES v04g_source_snapshots(id),
    FOREIGN KEY(discovered_link_id) REFERENCES v05f_discovered_links(id),
    FOREIGN KEY(duplicate_of_item_id) REFERENCES v05f_collection_items(id),
    CHECK(dedup_status IN ('new','duplicate','near_duplicate','reprint','unchanged','changed')),
    CHECK(change_status IN ('new','unchanged','changed','failed','skipped')),
    CHECK(processing_status IN ('new','queued','processing','processed','needs_review','ignored','failed')),
    CHECK(priority IN ('critical','high','medium','low'))
);

CREATE INDEX IF NOT EXISTS ix_v05f_item_source_time
ON v05f_collection_items(monitoring_source_id, captured_at DESC);

CREATE INDEX IF NOT EXISTS ix_v05f_item_status
ON v05f_collection_items(processing_status, dedup_status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_v05f_item_url
ON v05f_collection_items(normalized_url);

CREATE INDEX IF NOT EXISTS ix_v05f_item_hash
ON v05f_collection_items(content_hash);

CREATE TABLE IF NOT EXISTS v05f_content_duplicate_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    primary_item_id INTEGER NOT NULL,
    duplicate_item_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL DEFAULT 'duplicate',
    similarity_score INTEGER NOT NULL DEFAULT 100,
    reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(primary_item_id) REFERENCES v05f_collection_items(id),
    FOREIGN KEY(duplicate_item_id) REFERENCES v05f_collection_items(id),
    CHECK(relation_type IN ('duplicate','near_duplicate','reprint','same_url'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05f_duplicate_pair
ON v05f_content_duplicate_links(primary_item_id, duplicate_item_id, relation_type);

CREATE TABLE IF NOT EXISTS v05f_collection_job_locks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    monitoring_source_id INTEGER NOT NULL UNIQUE,
    monitoring_run_id INTEGER,
    lock_token TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'locked',
    acquired_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    released_at TEXT,
    note TEXT,
    FOREIGN KEY(monitoring_source_id) REFERENCES v04g_monitoring_sources(id),
    FOREIGN KEY(monitoring_run_id) REFERENCES v04g_monitoring_runs(id),
    CHECK(status IN ('locked','released','expired'))
);

CREATE TABLE IF NOT EXISTS v05f_collection_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_no TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    source_type TEXT NOT NULL,
    collection_mode TEXT NOT NULL,
    description TEXT,
    config_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""

SOURCE_COLUMNS = {
    "allowed_domains": "TEXT",
    "collection_source_type": "TEXT",
    "collection_mode": "TEXT",
    "content_kind": "TEXT",
    "min_interval_seconds": "INTEGER NOT NULL DEFAULT 60",
    "request_timeout_seconds": "INTEGER NOT NULL DEFAULT 15",
    "max_retries": "INTEGER NOT NULL DEFAULT 2",
    "max_pages": "INTEGER NOT NULL DEFAULT 1",
    "max_links": "INTEGER NOT NULL DEFAULT 20",
    "crawl_detail_pages": "INTEGER NOT NULL DEFAULT 0",
    "save_raw_html": "INTEGER NOT NULL DEFAULT 1",
    "robots_status": "TEXT",
    "robots_checked_at": "TEXT",
    "robots_summary": "TEXT",
    "compliance_note": "TEXT",
    "auto_paused": "INTEGER NOT NULL DEFAULT 0",
    "last_pause_reason": "TEXT",
}

RUN_COLUMNS = {
    "job_type": "TEXT",
    "trigger_type": "TEXT",
    "priority": "TEXT NOT NULL DEFAULT 'medium'",
    "scheduled_at": "TEXT",
    "attempt_count": "INTEGER NOT NULL DEFAULT 0",
    "max_retries": "INTEGER NOT NULL DEFAULT 2",
    "discovered_link_count": "INTEGER NOT NULL DEFAULT 0",
    "fetched_success_count": "INTEGER NOT NULL DEFAULT 0",
    "new_content_count": "INTEGER NOT NULL DEFAULT 0",
    "duplicate_content_count": "INTEGER NOT NULL DEFAULT 0",
    "changed_content_count": "INTEGER NOT NULL DEFAULT 0",
    "failed_content_count": "INTEGER NOT NULL DEFAULT 0",
    "skipped_content_count": "INTEGER NOT NULL DEFAULT 0",
    "snapshot_count": "INTEGER NOT NULL DEFAULT 0",
    "queued_item_count": "INTEGER NOT NULL DEFAULT 0",
    "operator_username": "TEXT",
}

SNAPSHOT_COLUMNS = {
    "original_url": "TEXT",
    "normalized_url": "TEXT",
    "canonical_url": "TEXT",
    "published_at": "TEXT",
    "http_status": "INTEGER",
    "response_headers_json": "TEXT",
    "raw_html": "TEXT",
    "cleaned_html": "TEXT",
    "structure_hash": "TEXT",
    "encoding": "TEXT",
    "content_type": "TEXT",
    "content_length": "INTEGER NOT NULL DEFAULT 0",
    "is_truncated": "INTEGER NOT NULL DEFAULT 0",
    "is_changed": "INTEGER NOT NULL DEFAULT 0",
    "previous_snapshot_id": "INTEGER",
    "diff_summary": "TEXT",
}


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _add_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    for name, definition in columns.items():
        if not _has_column(conn, table, name):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _seed_templates(conn: sqlite3.Connection) -> None:
    ts = datetime.now().replace(microsecond=0).isoformat()
    templates = [
        ("TPL-RSS", "RSS source", "rss", "rss", "Generic RSS or Atom feed"),
        ("TPL-WEB", "Article page", "webpage", "http", "Single static article page"),
        ("TPL-LIST", "News list page", "list_page", "http", "Static list page with detail links"),
        ("TPL-TEAM", "Team page", "webpage", "http", "Management or team profile page"),
        ("TPL-PIPE", "Product pipeline page", "webpage", "http", "Product or pipeline page"),
        ("TPL-GOV", "Government news list", "list_page", "http", "Government, park or association news"),
        ("TPL-DYN", "Dynamic list page", "dynamic_page", "playwright", "Optional dynamic page mode"),
    ]
    for template_no, name, source_type, mode, description in templates:
        conn.execute(
            """
            INSERT OR IGNORE INTO v05f_collection_templates(
                template_no, name, source_type, collection_mode, description, config_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, '{}', ?, ?)
            """,
            (template_no, name, source_type, mode, description, ts, ts),
        )


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        target = BACKUP_DIR / f"app_before_v05f_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(db_path, target)
        backup_path = str(target)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(V04G_SCHEMA_SQL)
        conn.executescript(TABLE_SQL)
        _add_columns(conn, "v04g_monitoring_sources", SOURCE_COLUMNS)
        _add_columns(conn, "v04g_monitoring_runs", RUN_COLUMNS)
        _add_columns(conn, "v04g_source_snapshots", SNAPSHOT_COLUMNS)
        _seed_templates(conn)
        conn.commit()
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("v0.5F migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

