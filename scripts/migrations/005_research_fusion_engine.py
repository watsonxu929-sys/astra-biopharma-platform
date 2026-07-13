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

MIGRATION_ID = "005_research_fusion_engine"

REQUIRED_TABLES = {
    "research_topics",
    "v05h_generated_reports",
    "v05g_extraction_candidates",
    "raw_intelligence",
    "v04g_source_snapshots",
    "organizations",
    "people",
    "projects",
}

COLUMNS = {
    "research_topics": {
        "research_scope": "TEXT",
        "keywords": "TEXT",
        "subject_scope_json": "TEXT NOT NULL DEFAULT '[]'",
        "responsible_user": "TEXT",
        "pilot_batch_id": "TEXT",
    },
    "v05h_generated_reports": {
        "topic_id": "INTEGER",
        "research_status": "TEXT NOT NULL DEFAULT 'draft'",
        "research_report_type": "TEXT",
        "citation_completeness": "REAL NOT NULL DEFAULT 0",
        "current_version_no": "INTEGER NOT NULL DEFAULT 1",
        "revision_note": "TEXT",
        "published_by": "TEXT",
        "pilot_batch_id": "TEXT",
    },
}

TABLE_SQL = """
CREATE TABLE IF NOT EXISTS p2_3_industry_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_no TEXT NOT NULL UNIQUE,
    legacy_event_id INTEGER,
    title TEXT NOT NULL,
    event_type TEXT NOT NULL,
    occurred_at TEXT,
    published_at TEXT,
    amount_value REAL,
    amount_currency TEXT,
    region TEXT,
    stage TEXT,
    importance INTEGER NOT NULL DEFAULT 3,
    confidence INTEGER NOT NULL DEFAULT 50,
    status TEXT NOT NULL DEFAULT 'draft',
    fusion_method TEXT NOT NULL DEFAULT 'rule',
    source_count INTEGER NOT NULL DEFAULT 0,
    has_conflict INTEGER NOT NULL DEFAULT 0,
    is_pilot INTEGER NOT NULL DEFAULT 0,
    pilot_batch_id TEXT,
    created_by TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(status IN ('draft','pending_review','needs_revision','approved','published','archived')),
    CHECK(importance BETWEEN 1 AND 5),
    CHECK(confidence BETWEEN 0 AND 100),
    CHECK(has_conflict IN (0,1)),
    CHECK(is_pilot IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_p23_event_status_time
ON p2_3_industry_events(status, occurred_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS p2_3_event_subjects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    subject_label TEXT,
    role TEXT NOT NULL DEFAULT 'involved',
    created_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES p2_3_industry_events(id) ON DELETE CASCADE,
    UNIQUE(event_id, subject_type, subject_id, role),
    CHECK(subject_type IN ('organization','person','project','product'))
);
CREATE INDEX IF NOT EXISTS ix_p23_event_subject
ON p2_3_event_subjects(subject_type, subject_id, event_id);

CREATE TABLE IF NOT EXISTS p2_3_event_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    candidate_id INTEGER,
    relation_type TEXT NOT NULL,
    fusion_score REAL NOT NULL DEFAULT 0,
    reason_json TEXT NOT NULL DEFAULT '{}',
    review_status TEXT NOT NULL DEFAULT 'pending',
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES p2_3_industry_events(id) ON DELETE CASCADE,
    FOREIGN KEY(candidate_id) REFERENCES v05g_extraction_candidates(id) ON DELETE RESTRICT,
    UNIQUE(event_id, candidate_id),
    CHECK(relation_type IN ('same_event','related_event','duplicate_report','update_event','conflict','unrelated')),
    CHECK(review_status IN ('pending','approved','rejected','needs_manual_review'))
);

CREATE TABLE IF NOT EXISTS p2_3_event_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id INTEGER NOT NULL,
    snapshot_id INTEGER,
    raw_intelligence_id INTEGER,
    candidate_id INTEGER,
    source_organization TEXT,
    source_title TEXT,
    source_url TEXT,
    published_at TEXT,
    captured_at TEXT,
    evidence_excerpt TEXT NOT NULL,
    char_start INTEGER,
    char_end INTEGER,
    page_number INTEGER,
    table_number TEXT,
    locator_json TEXT NOT NULL DEFAULT '{}',
    evidence_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES p2_3_industry_events(id) ON DELETE CASCADE,
    FOREIGN KEY(snapshot_id) REFERENCES v04g_source_snapshots(id) ON DELETE RESTRICT,
    FOREIGN KEY(raw_intelligence_id) REFERENCES raw_intelligence(id) ON DELETE RESTRICT,
    FOREIGN KEY(candidate_id) REFERENCES v05g_extraction_candidates(id) ON DELETE RESTRICT
);
CREATE INDEX IF NOT EXISTS ix_p23_event_evidence
ON p2_3_event_evidence(event_id, snapshot_id);
CREATE UNIQUE INDEX IF NOT EXISTS ux_p23_event_evidence
ON p2_3_event_evidence(event_id, evidence_hash, COALESCE(snapshot_id,-1));

CREATE TABLE IF NOT EXISTS p2_3_fact_assertions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    assertion_no TEXT NOT NULL UNIQUE,
    event_id INTEGER,
    topic_id INTEGER,
    subject_type TEXT NOT NULL,
    subject_id TEXT NOT NULL,
    subject_label TEXT,
    predicate TEXT NOT NULL,
    object_value TEXT,
    numeric_value REAL,
    unit TEXT,
    valid_time TEXT,
    confidence INTEGER NOT NULL DEFAULT 50,
    review_status TEXT NOT NULL DEFAULT 'pending_review',
    source_count INTEGER NOT NULL DEFAULT 0,
    is_current INTEGER NOT NULL DEFAULT 1,
    is_pilot INTEGER NOT NULL DEFAULT 0,
    pilot_batch_id TEXT,
    created_by TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(event_id) REFERENCES p2_3_industry_events(id) ON DELETE SET NULL,
    FOREIGN KEY(topic_id) REFERENCES research_topics(id) ON DELETE SET NULL,
    CHECK(review_status IN ('pending_review','needs_revision','approved','rejected','superseded')),
    CHECK(confidence BETWEEN 0 AND 100),
    CHECK(is_current IN (0,1)),
    CHECK(is_pilot IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_p23_assertion_subject
ON p2_3_fact_assertions(subject_type, subject_id, predicate, valid_time);

CREATE TABLE IF NOT EXISTS p2_3_assertion_evidence (
    assertion_id INTEGER NOT NULL,
    event_evidence_id INTEGER NOT NULL,
    support_type TEXT NOT NULL DEFAULT 'supports',
    created_at TEXT NOT NULL,
    PRIMARY KEY(assertion_id, event_evidence_id),
    FOREIGN KEY(assertion_id) REFERENCES p2_3_fact_assertions(id) ON DELETE CASCADE,
    FOREIGN KEY(event_evidence_id) REFERENCES p2_3_event_evidence(id) ON DELETE RESTRICT,
    CHECK(support_type IN ('supports','contradicts','context'))
);

CREATE TABLE IF NOT EXISTS p2_3_fact_conflicts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conflict_no TEXT NOT NULL UNIQUE,
    topic_id INTEGER,
    event_id INTEGER,
    subject_type TEXT,
    subject_id TEXT,
    subject_label TEXT,
    field_name TEXT NOT NULL,
    assertion_a_id INTEGER,
    assertion_b_id INTEGER,
    value_a TEXT,
    value_b TEXT,
    evidence_a_json TEXT NOT NULL DEFAULT '[]',
    evidence_b_json TEXT NOT NULL DEFAULT '[]',
    adopted_value TEXT,
    adoption_reason TEXT,
    status TEXT NOT NULL DEFAULT 'unresolved',
    is_simulated INTEGER NOT NULL DEFAULT 0,
    is_pilot INTEGER NOT NULL DEFAULT 0,
    pilot_batch_id TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(topic_id) REFERENCES research_topics(id) ON DELETE SET NULL,
    FOREIGN KEY(event_id) REFERENCES p2_3_industry_events(id) ON DELETE SET NULL,
    FOREIGN KEY(assertion_a_id) REFERENCES p2_3_fact_assertions(id) ON DELETE RESTRICT,
    FOREIGN KEY(assertion_b_id) REFERENCES p2_3_fact_assertions(id) ON DELETE RESTRICT,
    CHECK(status IN ('unresolved','needs_manual_review','resolved','dismissed')),
    CHECK(is_simulated IN (0,1)),
    CHECK(is_pilot IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_p23_conflict_status
ON p2_3_fact_conflicts(status, topic_id, id DESC);

CREATE TABLE IF NOT EXISTS p2_3_research_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER NOT NULL,
    question TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'open',
    answer_summary TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
    CHECK(status IN ('open','investigating','answered','closed'))
);

CREATE TABLE IF NOT EXISTS p2_3_topic_events (
    topic_id INTEGER NOT NULL,
    event_id INTEGER NOT NULL,
    relevance TEXT NOT NULL DEFAULT 'core',
    added_by TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY(topic_id, event_id),
    FOREIGN KEY(topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
    FOREIGN KEY(event_id) REFERENCES p2_3_industry_events(id) ON DELETE RESTRICT,
    CHECK(relevance IN ('core','related','context'))
);

CREATE TABLE IF NOT EXISTS p2_3_research_findings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    finding_no TEXT NOT NULL UNIQUE,
    topic_id INTEGER NOT NULL,
    finding_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    confidence INTEGER,
    status TEXT NOT NULL DEFAULT 'draft',
    generated_by TEXT NOT NULL DEFAULT 'analyst',
    provider TEXT,
    model TEXT,
    prompt_version TEXT,
    output_hash TEXT,
    is_pilot INTEGER NOT NULL DEFAULT 0,
    pilot_batch_id TEXT,
    created_by TEXT,
    reviewed_by TEXT,
    reviewed_at TEXT,
    review_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
    CHECK(finding_type IN ('verified_fact','inference','analyst_opinion','hypothesis','conflict')),
    CHECK(status IN ('draft','pending_review','needs_revision','approved','archived')),
    CHECK(is_pilot IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_p23_finding_topic
ON p2_3_research_findings(topic_id, status, id DESC);

CREATE TABLE IF NOT EXISTS p2_3_finding_assertions (
    finding_id INTEGER NOT NULL,
    assertion_id INTEGER NOT NULL,
    relation_type TEXT NOT NULL DEFAULT 'supports',
    created_at TEXT NOT NULL,
    PRIMARY KEY(finding_id, assertion_id),
    FOREIGN KEY(finding_id) REFERENCES p2_3_research_findings(id) ON DELETE CASCADE,
    FOREIGN KEY(assertion_id) REFERENCES p2_3_fact_assertions(id) ON DELETE RESTRICT,
    CHECK(relation_type IN ('supports','contradicts','context'))
);

CREATE TABLE IF NOT EXISTS p2_3_report_sections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    section_order INTEGER NOT NULL,
    section_type TEXT NOT NULL,
    title TEXT NOT NULL,
    content_markdown TEXT NOT NULL,
    finding_id INTEGER,
    citation_complete INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(report_id) REFERENCES v05h_generated_reports(id) ON DELETE CASCADE,
    FOREIGN KEY(finding_id) REFERENCES p2_3_research_findings(id) ON DELETE SET NULL,
    UNIQUE(report_id, section_order),
    CHECK(section_type IN ('fact','inference','opinion','to_verify','summary','methodology')),
    CHECK(citation_complete IN (0,1))
);

CREATE TABLE IF NOT EXISTS p2_3_report_citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    section_id INTEGER NOT NULL,
    finding_id INTEGER,
    assertion_id INTEGER,
    event_id INTEGER,
    event_evidence_id INTEGER,
    snapshot_id INTEGER,
    source_organization TEXT,
    source_title TEXT,
    published_at TEXT,
    source_url TEXT,
    evidence_excerpt TEXT NOT NULL,
    page_number INTEGER,
    locator_json TEXT NOT NULL DEFAULT '{}',
    captured_at TEXT,
    citation_hash TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(report_id) REFERENCES v05h_generated_reports(id) ON DELETE CASCADE,
    FOREIGN KEY(section_id) REFERENCES p2_3_report_sections(id) ON DELETE CASCADE,
    FOREIGN KEY(finding_id) REFERENCES p2_3_research_findings(id) ON DELETE SET NULL,
    FOREIGN KEY(assertion_id) REFERENCES p2_3_fact_assertions(id) ON DELETE SET NULL,
    FOREIGN KEY(event_id) REFERENCES p2_3_industry_events(id) ON DELETE SET NULL,
    FOREIGN KEY(event_evidence_id) REFERENCES p2_3_event_evidence(id) ON DELETE RESTRICT,
    FOREIGN KEY(snapshot_id) REFERENCES v04g_source_snapshots(id) ON DELETE RESTRICT,
    UNIQUE(section_id, citation_hash)
);
CREATE INDEX IF NOT EXISTS ix_p23_report_citations
ON p2_3_report_citations(report_id, section_id);

CREATE TABLE IF NOT EXISTS p2_3_report_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    report_id INTEGER NOT NULL,
    version_no INTEGER NOT NULL,
    title TEXT NOT NULL,
    summary TEXT,
    content_markdown TEXT,
    sections_json TEXT NOT NULL DEFAULT '[]',
    citations_json TEXT NOT NULL DEFAULT '[]',
    change_note TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(report_id) REFERENCES v05h_generated_reports(id) ON DELETE CASCADE,
    UNIQUE(report_id, version_no)
);

CREATE TABLE IF NOT EXISTS p2_3_research_agent_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_no TEXT NOT NULL UNIQUE,
    topic_id INTEGER NOT NULL,
    report_id INTEGER,
    provider TEXT NOT NULL,
    model TEXT,
    prompt_version TEXT NOT NULL,
    input_fact_ids_json TEXT NOT NULL DEFAULT '[]',
    output_hash TEXT,
    status TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'draft',
    error_type TEXT,
    created_at TEXT NOT NULL,
    finished_at TEXT,
    FOREIGN KEY(topic_id) REFERENCES research_topics(id) ON DELETE CASCADE,
    FOREIGN KEY(report_id) REFERENCES v05h_generated_reports(id) ON DELETE SET NULL,
    CHECK(status IN ('running','success','failed','unavailable')),
    CHECK(review_status IN ('draft','pending_review','needs_revision','approved'))
);
"""


def table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def column_names(conn: sqlite3.Connection, table: str) -> set[str]:
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')} if table_exists(conn, table) else set()


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


P23_TABLES = {
    "p2_3_industry_events", "p2_3_event_subjects", "p2_3_event_candidates",
    "p2_3_event_evidence", "p2_3_fact_assertions", "p2_3_assertion_evidence",
    "p2_3_fact_conflicts", "p2_3_research_questions", "p2_3_topic_events",
    "p2_3_research_findings", "p2_3_finding_assertions", "p2_3_report_sections",
    "p2_3_report_citations", "p2_3_report_versions", "p2_3_research_agent_runs",
}


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    existing = table_names(conn)
    return {
        table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
        for table in sorted(P23_TABLES | REQUIRED_TABLES)
        if table in existing
    }


def analyze(conn: sqlite3.Connection) -> dict:
    existing = table_names(conn)
    return {
        "missing_required_tables": sorted(REQUIRED_TABLES - existing),
        "missing_p2_3_tables": sorted(P23_TABLES - existing),
        "missing_columns": {
            table: sorted(set(specs) - column_names(conn, table))
            for table, specs in COLUMNS.items()
            if table in existing
        },
        "counts": counts(conn),
    }


def backup_database(conn: sqlite3.Connection, db_path: Path) -> tuple[Path, str]:
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{db_path.stem}_before_{MIGRATION_ID}_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    with sqlite3.connect(target) as destination:
        conn.backup(destination)
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
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="P2.3 research fusion engine migration")
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
    applying = bool(args.apply)
    uri = str(db_path) if applying else f"file:{db_path.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=not applying) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        before = analyze(conn)
        report = {
            "migration_id": MIGRATION_ID,
            "mode": "apply" if applying else "dry-run",
            "database_name": db_path.name,
            "timestamp": datetime.now().isoformat(),
            "before": before,
        }
        if before["missing_required_tables"]:
            report["error"] = "missing_required_tables"
            write_report(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 3
        if not applying:
            write_report(args.report, report)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0

        backup_path, backup_sha = backup_database(conn, db_path)
        try:
            conn.execute("BEGIN IMMEDIATE")
            apply_schema(conn)
            after = analyze(conn)
            if after["missing_p2_3_tables"] or any(after["missing_columns"].values()):
                raise RuntimeError("schema_verification_failed")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        report.update({
            "backup_name": backup_path.name,
            "backup_sha256": backup_sha,
            "after": after,
            "applied": True,
        })
        write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
