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

from scripts.migrate_v05e import migrate as migrate_v05e
from scripts.migrate_v05g import migrate as migrate_v05g

DB_PATH = resolved_db_path()
BACKUP_DIR = DB_PATH.parent / "backups" if (ROOT / "data").resolve() not in DB_PATH.resolve().parents else ROOT / "data" / "backups"

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS v05h_signal_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    rule_no TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    signal_type TEXT NOT NULL,
    signal_category TEXT NOT NULL,
    source_scope TEXT NOT NULL,
    condition_json TEXT NOT NULL DEFAULT '{}',
    time_window_days INTEGER NOT NULL DEFAULT 30,
    min_confidence INTEGER NOT NULL DEFAULT 60,
    severity_rule TEXT NOT NULL DEFAULT 'medium',
    dedupe_window_days INTEGER NOT NULL DEFAULT 30,
    is_enabled INTEGER NOT NULL DEFAULT 1,
    description TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(is_enabled IN (0,1))
);

CREATE TABLE IF NOT EXISTS v05h_signal_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT,
    snapshot_id INTEGER,
    event_id INTEGER,
    candidate_id INTEGER,
    evidence_hash TEXT NOT NULL,
    evidence_excerpt TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(signal_id) REFERENCES v05e_industry_signals(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v05h_signal_evidence
ON v05h_signal_evidence(signal_id, source_type, COALESCE(source_id,''), evidence_hash);

CREATE TABLE IF NOT EXISTS v05h_report_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    template_no TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    report_type TEXT NOT NULL,
    description TEXT,
    config_json TEXT NOT NULL DEFAULT '{}',
    is_enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(is_enabled IN (0,1))
);

CREATE TABLE IF NOT EXISTS v05h_report_jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    job_no TEXT NOT NULL UNIQUE,
    report_type TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    template_id INTEGER,
    filters_json TEXT NOT NULL DEFAULT '{}',
    generated_by TEXT,
    started_at TEXT,
    finished_at TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(template_id) REFERENCES v05h_report_templates(id),
    CHECK(status IN ('pending','running','generated','failed','cancelled'))
);

CREATE TABLE IF NOT EXISTS v05h_generated_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_no TEXT NOT NULL UNIQUE,
    report_job_id INTEGER,
    title TEXT NOT NULL,
    report_type TEXT NOT NULL,
    period_start TEXT,
    period_end TEXT,
    summary TEXT,
    content_html TEXT,
    content_markdown TEXT,
    citations_json TEXT NOT NULL DEFAULT '[]',
    version INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'draft',
    created_by TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    published_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(report_job_id) REFERENCES v05h_report_jobs(id),
    CHECK(status IN ('draft','generated','under_review','approved','published','archived','failed'))
);

CREATE INDEX IF NOT EXISTS ix_v05h_report_status
ON v05h_generated_reports(status, report_type, created_at DESC);
"""

SIGNAL_COLUMNS = {
    "signal_category": "TEXT",
    "severity": "TEXT",
    "related_subjects": "TEXT",
    "snapshot_id": "INTEGER",
    "event_id": "INTEGER",
    "owner": "TEXT",
    "is_important": "INTEGER NOT NULL DEFAULT 0",
    "rule_no": "TEXT",
    "rule_explanation": "TEXT",
    "missing_data_json": "TEXT",
    "conflict_json": "TEXT",
    "expires_at": "TEXT",
    "evidence_hash": "TEXT",
}

WATCHLIST_COLUMNS = {
    "focus_signal_types": "TEXT",
    "alert_threshold": "TEXT",
    "next_review_at": "TEXT",
    "auto_summary_enabled": "INTEGER NOT NULL DEFAULT 1",
    "include_weekly": "INTEGER NOT NULL DEFAULT 1",
    "include_monthly": "INTEGER NOT NULL DEFAULT 1",
}


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    return any(row[1] == column for row in conn.execute(f"PRAGMA table_info({table})").fetchall())


def _add_columns(conn: sqlite3.Connection, table: str, columns: dict[str, str]) -> None:
    for name, definition in columns.items():
        if not _has_column(conn, table, name):
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {definition}")


def _next_seed_no(conn: sqlite3.Connection, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(f"SELECT COUNT(*) FROM v05h_signal_rules WHERE rule_no LIKE ?", (f"{prefix}-{stamp}-%",)).fetchone()
    return f"{prefix}-{stamp}-{int(row[0]) + 1:04d}"


def _seed(conn: sqlite3.Connection) -> None:
    ts = datetime.now().replace(microsecond=0).isoformat()
    rules = [
        ("Financing Signal", "financing", "company_development", "confirmed_event", "high", "Confirmed financing and investment events"),
        ("Strategic Cooperation", "strategic_cooperation", "company_development", "confirmed_event", "high", "Partnership, licensing, authorization, and co-development events"),
        ("Clinical Progress", "clinical_progress", "rd_product", "confirmed_event", "high", "Clinical, filing, approval, registration, and launch events"),
        ("Resource Need", "resource_need", "project_attraction", "approved_candidate", "medium", "Reviewed resource, demand, and attraction opportunities"),
        ("Risk Exception", "risk", "risk_exception", "approved_candidate", "critical", "Conflict, failure, suspension, termination, overdue, and other risk events"),
    ]
    for name, signal_type, category, scope, severity, description in rules:
        exists = conn.execute("SELECT 1 FROM v05h_signal_rules WHERE signal_type=? AND source_scope=?", (signal_type, scope)).fetchone()
        if exists:
            continue
        conn.execute(
            """
            INSERT INTO v05h_signal_rules(rule_no,name,signal_type,signal_category,source_scope,condition_json,time_window_days,min_confidence,severity_rule,dedupe_window_days,is_enabled,description,created_at,updated_at)
            VALUES (?,?,?,?,?,'{}',30,60,?,30,1,?,?,?)
            """,
            (_next_seed_no(conn, "RULE"), name, signal_type, category, scope, severity, description, ts, ts),
        )
    templates = [
        ("Daily Brief", "daily", "Daily intelligence brief"),
        ("Weekly Report", "weekly", "Weekly industry intelligence report"),
        ("Monthly Report", "monthly", "Monthly industry intelligence report"),
        ("Subject Report", "subject", "Key subject tracking report"),
        ("Track Report", "track", "Track trend report"),
        ("Q-BAY Report", "qbay", "Q-BAY resources and needs report"),
    ]
    for name, report_type, description in templates:
        exists = conn.execute("SELECT 1 FROM v05h_report_templates WHERE report_type=?", (report_type,)).fetchone()
        if exists:
            continue
        conn.execute(
            """
            INSERT INTO v05h_report_templates(template_no,name,report_type,description,config_json,is_enabled,created_at,updated_at)
            VALUES (?,?,?,?, '{}', 1, ?, ?)
            """,
            (f"RPTTPL-{report_type.upper()}", name, report_type, description, ts, ts),
        )


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        target = BACKUP_DIR / f"app_before_v05h_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(db_path, target)
        backup_path = str(target)
    migrate_v05g(db_path, backup=False)
    migrate_v05e(db_path, backup=False)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(TABLE_SQL)
        _add_columns(conn, "v05e_industry_signals", SIGNAL_COLUMNS)
        _add_columns(conn, "v05e_watchlist_items", WATCHLIST_COLUMNS)
        _seed(conn)
        conn.commit()
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("v0.5H migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

