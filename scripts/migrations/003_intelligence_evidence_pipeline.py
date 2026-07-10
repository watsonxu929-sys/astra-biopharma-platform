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

MIGRATION_ID = "003_intelligence_evidence_pipeline"

REQUIRED_TABLES = {
    "v04g_monitoring_sources",
    "v04g_monitoring_runs",
    "v04g_source_snapshots",
    "raw_intelligence",
    "v05g_extraction_candidates",
    "v06_intelligence_items",
}

COLUMNS = {
    "v04g_monitoring_sources": {
        "rss_url": "TEXT",
        "source_credibility": "INTEGER NOT NULL DEFAULT 3",
        "health_status": "TEXT NOT NULL DEFAULT 'unknown'",
    },
    "v04g_monitoring_runs": {
        "parent_job_id": "INTEGER",
    },
    "v04g_source_snapshots": {
        "attachment_path": "TEXT",
        "attachment_page_count": "INTEGER",
        "evidence_status": "TEXT NOT NULL DEFAULT 'captured'",
        "is_pilot": "INTEGER NOT NULL DEFAULT 0",
        "pilot_batch_id": "TEXT",
        "immutable_at": "TEXT",
    },
    "raw_intelligence": {
        "evidence_snapshot_id": "INTEGER",
        "content_hash": "TEXT",
        "published_at": "TEXT",
        "language": "TEXT",
        "content_type": "TEXT",
        "processing_status": "TEXT NOT NULL DEFAULT 'normalized'",
        "is_pilot": "INTEGER NOT NULL DEFAULT 0",
        "pilot_batch_id": "TEXT",
    },
    "v05g_extraction_candidates": {
        "generated_by": "TEXT NOT NULL DEFAULT 'rule'",
        "provider": "TEXT",
        "model": "TEXT",
        "prompt_version": "TEXT",
        "result_hash": "TEXT",
        "pipeline_review_status": "TEXT NOT NULL DEFAULT 'pending'",
        "rejection_reason": "TEXT",
        "merged_into_candidate_id": "INTEGER",
        "is_pilot": "INTEGER NOT NULL DEFAULT 0",
        "pilot_batch_id": "TEXT",
    },
    "v06_intelligence_items": {
        "is_pilot": "INTEGER NOT NULL DEFAULT 0",
        "pilot_batch_id": "TEXT",
    },
}

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS p2_fact_candidate_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id INTEGER NOT NULL,
    snapshot_id INTEGER NOT NULL,
    evidence_excerpt TEXT NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    page_number INTEGER,
    table_number TEXT,
    locator_json TEXT NOT NULL DEFAULT '{}',
    evidence_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(candidate_id) REFERENCES v05g_extraction_candidates(id) ON DELETE CASCADE,
    FOREIGN KEY(snapshot_id) REFERENCES v04g_source_snapshots(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_p2_candidate_evidence_snapshot ON p2_fact_candidate_evidence(snapshot_id, candidate_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_p2_candidate_evidence
ON p2_fact_candidate_evidence(candidate_id, snapshot_id, evidence_hash, COALESCE(char_start,-1), COALESCE(char_end,-1), COALESCE(page_number,-1), COALESCE(table_number,''));

CREATE TABLE IF NOT EXISTS p2_intelligence_product_candidates (
    product_id INTEGER NOT NULL,
    candidate_id INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY(product_id, candidate_id),
    FOREIGN KEY(product_id) REFERENCES v06_intelligence_items(id) ON DELETE CASCADE,
    FOREIGN KEY(candidate_id) REFERENCES v05g_extraction_candidates(id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS p2_intelligence_product_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER NOT NULL,
    snapshot_id INTEGER NOT NULL,
    candidate_id INTEGER,
    evidence_excerpt TEXT NOT NULL,
    locator_json TEXT NOT NULL DEFAULT '{}',
    evidence_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(product_id) REFERENCES v06_intelligence_items(id) ON DELETE CASCADE,
    FOREIGN KEY(snapshot_id) REFERENCES v04g_source_snapshots(id) ON DELETE RESTRICT,
    FOREIGN KEY(candidate_id) REFERENCES v05g_extraction_candidates(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_p2_product_evidence_snapshot ON p2_intelligence_product_evidence(snapshot_id, product_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_p2_product_evidence
ON p2_intelligence_product_evidence(product_id, snapshot_id, evidence_hash, COALESCE(candidate_id,-1));

CREATE TABLE IF NOT EXISTS p2_ai_analysis_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_no TEXT NOT NULL UNIQUE,
    processing_job_id INTEGER,
    snapshot_id INTEGER,
    raw_intelligence_id INTEGER,
    provider TEXT NOT NULL,
    model TEXT,
    prompt_version TEXT NOT NULL,
    generated_by TEXT NOT NULL,
    status TEXT NOT NULL,
    token_usage_json TEXT,
    result_hash TEXT,
    raw_result TEXT,
    error_type TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY(processing_job_id) REFERENCES v05g_processing_jobs(id) ON DELETE SET NULL,
    FOREIGN KEY(snapshot_id) REFERENCES v04g_source_snapshots(id) ON DELETE RESTRICT,
    FOREIGN KEY(raw_intelligence_id) REFERENCES raw_intelligence(id) ON DELETE SET NULL,
    CHECK(status IN ('running','success','failed','unavailable'))
);

CREATE TABLE IF NOT EXISTS p2_pilot_batches (
    batch_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'planned',
    source_manifest_json TEXT NOT NULL DEFAULT '[]',
    sample_limit INTEGER NOT NULL DEFAULT 20,
    created_by TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    cleanup_note TEXT,
    CHECK(sample_limit BETWEEN 1 AND 20)
);

CREATE TABLE IF NOT EXISTS p2_intelligence_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    entity_type TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    note TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_p2_audit_entity ON p2_intelligence_audit_log(entity_type, entity_id, created_at DESC);
"""


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')} if table_exists(conn, table) else set()


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    names = sorted(REQUIRED_TABLES | {"p2_fact_candidate_evidence", "p2_intelligence_product_candidates", "p2_intelligence_product_evidence", "p2_ai_analysis_runs", "p2_pilot_batches", "p2_intelligence_audit_log"})
    return {name: int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]) for name in names if table_exists(conn, name)}


def analyze(conn: sqlite3.Connection) -> dict:
    missing_tables = sorted(table for table in REQUIRED_TABLES if not table_exists(conn, table))
    missing_columns = {table: sorted(set(spec) - column_names(conn, table)) for table, spec in COLUMNS.items() if table_exists(conn, table)}
    conflicts = []
    if table_exists(conn, "v04g_source_snapshots"):
        duplicate_rows = conn.execute("SELECT monitoring_source_id, content_hash, COUNT(*) n FROM v04g_source_snapshots GROUP BY monitoring_source_id, content_hash HAVING n>1").fetchall()
        conflicts.extend({"type": "duplicate_snapshot_hash", "source_id": row[0], "content_hash": row[1], "count": row[2]} for row in duplicate_rows)
    return {"missing_required_tables": missing_tables, "missing_columns": missing_columns, "conflicts": conflicts, "counts": counts(conn)}


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
    conn.execute("""
    CREATE TRIGGER IF NOT EXISTS trg_p2_snapshot_immutable
    BEFORE UPDATE OF url, original_url, normalized_url, raw_content, raw_html, content_hash, captured_at
    ON v04g_source_snapshots
    WHEN OLD.url IS NOT NEW.url OR OLD.original_url IS NOT NEW.original_url
      OR OLD.normalized_url IS NOT NEW.normalized_url OR OLD.raw_content IS NOT NEW.raw_content
      OR OLD.raw_html IS NOT NEW.raw_html OR OLD.content_hash IS NOT NEW.content_hash
      OR OLD.captured_at IS NOT NEW.captured_at
    BEGIN SELECT RAISE(ABORT, 'evidence_snapshot_is_immutable'); END
    """)


def write_report(path: Path | None, report: dict) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="P2.1 intelligence evidence pipeline migration")
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
