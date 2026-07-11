from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import resolved_db_path

MIGRATION_ID = "004_real_source_quality_evaluation"

COLUMNS = {
    "v04g_monitoring_sources": {
        "wait_selector": "TEXT",
        "request_interval_seconds": "REAL NOT NULL DEFAULT 1.0",
        "backoff_seconds": "REAL NOT NULL DEFAULT 2.0",
        "max_file_bytes": "INTEGER NOT NULL DEFAULT 10485760",
        "last_etag": "TEXT",
        "last_modified_header": "TEXT",
        "next_allowed_at": "TEXT",
    },
    "v04g_monitoring_runs": {
        "duration_ms": "INTEGER",
        "retry_count": "INTEGER NOT NULL DEFAULT 0",
        "parse_failed_count": "INTEGER NOT NULL DEFAULT 0",
        "ai_call_count": "INTEGER NOT NULL DEFAULT 0",
        "ai_failed_count": "INTEGER NOT NULL DEFAULT 0",
        "estimated_cost_usd": "REAL NOT NULL DEFAULT 0",
        "error_stage": "TEXT",
        "next_retry_at": "TEXT",
    },
    "v04g_source_snapshots": {
        "attachment_filename": "TEXT",
        "attachment_hash": "TEXT",
        "parse_status": "TEXT",
        "parse_error_stage": "TEXT",
        "parse_error_type": "TEXT",
        "parse_retryable": "INTEGER NOT NULL DEFAULT 0",
        "sections_json": "TEXT NOT NULL DEFAULT '[]'",
        "tables_json": "TEXT NOT NULL DEFAULT '[]'",
        "quality_status": "TEXT",
        "quality_json": "TEXT NOT NULL DEFAULT '{}'",
        "collection_duration_ms": "INTEGER",
    },
    "raw_intelligence": {
        "quality_status": "TEXT",
        "quality_json": "TEXT NOT NULL DEFAULT '{}'",
        "sections_json": "TEXT NOT NULL DEFAULT '[]'",
        "tables_json": "TEXT NOT NULL DEFAULT '[]'",
    },
    "p2_ai_analysis_runs": {
        "pilot_batch_id": "TEXT",
        "input_hash": "TEXT",
        "output_hash": "TEXT",
        "latency_ms": "INTEGER",
        "estimated_cost_usd": "REAL NOT NULL DEFAULT 0",
        "retry_count": "INTEGER NOT NULL DEFAULT 0",
        "schema_repair_count": "INTEGER NOT NULL DEFAULT 0",
    },
}

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS p2_2_evaluation_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    evaluation_no TEXT NOT NULL UNIQUE,
    pilot_batch_id TEXT NOT NULL,
    provider_mode TEXT NOT NULL,
    sample_count INTEGER NOT NULL,
    metrics_json TEXT NOT NULL,
    latency_ms INTEGER,
    estimated_cost_usd REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_p2_2_eval_batch
ON p2_2_evaluation_runs(pilot_batch_id, provider_mode);

CREATE TABLE IF NOT EXISTS p2_2_fact_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pilot_batch_id TEXT,
    conflict_key TEXT NOT NULL,
    subject_type TEXT,
    subject_label TEXT,
    field_name TEXT NOT NULL,
    left_candidate_id INTEGER,
    right_candidate_id INTEGER,
    left_value TEXT,
    right_value TEXT,
    status TEXT NOT NULL DEFAULT 'needs_manual_review',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    UNIQUE(conflict_key, left_candidate_id, right_candidate_id)
);
CREATE INDEX IF NOT EXISTS ix_p2_2_conflict_status
ON p2_2_fact_conflicts(status, created_at DESC);
"""

REQUIRED_TABLES = set(COLUMNS)


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')} if table_exists(conn, table) else set()


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = sorted(REQUIRED_TABLES | {"p2_2_evaluation_runs", "p2_2_fact_conflicts"})
    return {name: int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]) for name in names if table_exists(conn, name)}


def analyze(conn: sqlite3.Connection) -> dict:
    missing_tables = sorted(name for name in REQUIRED_TABLES if not table_exists(conn, name))
    missing_columns = {name: sorted(set(spec) - column_names(conn, name)) for name, spec in COLUMNS.items() if table_exists(conn, name)}
    return {"missing_required_tables": missing_tables, "missing_columns": missing_columns, "counts": counts(conn)}


def backup_database(conn: sqlite3.Connection, db_path: Path) -> tuple[Path, str]:
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{db_path.stem}_before_{MIGRATION_ID}_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    with sqlite3.connect(target) as backup:
        conn.backup(backup)
    digest = hashlib.sha256(target.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{target.as_posix()}?mode=ro", uri=True) as check:
        if check.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            target.unlink(missing_ok=True)
            raise RuntimeError("backup_integrity_check_failed")
    return target, digest


def apply_schema(conn: sqlite3.Connection) -> None:
    for table, specs in COLUMNS.items():
        existing = column_names(conn, table)
        for name, declaration in specs.items():
            if name not in existing:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {declaration}')
    for statement in TABLE_SQL.split(";"):
        if statement.strip():
            conn.execute(statement)


def write_report(path: Path | None, report: dict) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="P2.2 real-source quality and evaluation migration")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    db_path = (args.db or resolved_db_path()).resolve()
    if not db_path.exists():
        print(json.dumps({"error": "database_not_found"}, ensure_ascii=False))
        return 2
    apply = bool(args.apply)
    uri = str(db_path) if apply else f"file:{db_path.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=not apply) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        before = analyze(conn)
        report = {"migration_id": MIGRATION_ID, "mode": "apply" if apply else "dry-run", "database_name": db_path.name, "timestamp": datetime.now().isoformat(), "before": before}
        if before["missing_required_tables"]:
            report["error"] = "missing_required_tables"
            write_report(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 3
        if not apply:
            write_report(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        backup_path, backup_sha = backup_database(conn, db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            apply_schema(conn)
            after = analyze(conn)
            if after["missing_required_tables"] or any(after["missing_columns"].values()):
                raise RuntimeError("schema_verification_failed")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        report.update({"backup_name": backup_path.name, "backup_sha256": backup_sha, "after": after, "applied": True})
        write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
