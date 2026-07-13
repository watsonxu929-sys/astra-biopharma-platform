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

MIGRATION_ID = "007_club_operations_mvp"
REQUIRED_TABLES = {
    "v05a_users", "people", "organizations", "events", "v04f_club_applications",
    "v04f_club_memberships", "v05c_club_event_profiles",
    "v05c_club_event_registrations", "v05c_club_event_participation",
    "v06_market_resources",
}
P4_TABLES = {
    "p4_membership_history", "p4_event_feedback", "p4_checkin_tokens",
    "p4_checkin_audit", "p4_event_relationship_candidates",
    "p4_resource_match_candidates", "p4_club_lead_candidates",
    "p4_domain_events", "p4_operation_audit",
}

TABLE_SQL = r"""
CREATE TABLE IF NOT EXISTS p4_membership_history (
 id INTEGER PRIMARY KEY AUTOINCREMENT, membership_id INTEGER, application_id INTEGER,
 change_type TEXT NOT NULL, old_status TEXT, new_status TEXT, before_json TEXT, after_json TEXT,
 reason TEXT, actor_user_id INTEGER, actor TEXT NOT NULL, pilot_batch_id TEXT,
 created_at TEXT NOT NULL,
 FOREIGN KEY(membership_id) REFERENCES v04f_club_memberships(id) ON DELETE RESTRICT,
 FOREIGN KEY(application_id) REFERENCES v04f_club_applications(id) ON DELETE RESTRICT,
 CHECK(change_type IN ('application_reviewed','membership_activated','member_type_changed','organization_changed','role_changed','validity_changed','suspended','resumed','expired','withdrawn'))
);
CREATE INDEX IF NOT EXISTS ix_p4_membership_history_member ON p4_membership_history(membership_id,id DESC);

CREATE TABLE IF NOT EXISTS p4_event_feedback (
 id INTEGER PRIMARY KEY AUTOINCREMENT, feedback_no TEXT NOT NULL UNIQUE,
 club_event_id INTEGER NOT NULL, registration_id INTEGER NOT NULL, membership_id INTEGER,
 content_score INTEGER, speaker_score INTEGER, organization_score INTEGER, satisfaction_score INTEGER,
 content_feedback TEXT, interested_people TEXT, interested_organizations TEXT,
 cooperation_intent TEXT, new_demand TEXT, new_supply TEXT, suggestions TEXT,
 status TEXT NOT NULL DEFAULT 'submitted', submitted_by_user_id INTEGER,
 pilot_batch_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(club_event_id) REFERENCES v05c_club_event_profiles(id) ON DELETE RESTRICT,
 FOREIGN KEY(registration_id) REFERENCES v05c_club_event_registrations(id) ON DELETE RESTRICT,
 UNIQUE(club_event_id,registration_id),
 CHECK(status IN ('submitted','reviewed','archived'))
);

CREATE TABLE IF NOT EXISTS p4_checkin_tokens (
 id INTEGER PRIMARY KEY AUTOINCREMENT, club_event_id INTEGER NOT NULL,
 registration_id INTEGER NOT NULL, token_hash TEXT NOT NULL UNIQUE, token_hint TEXT NOT NULL,
 valid_from TEXT NOT NULL, valid_until TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'active',
 issued_by_user_id INTEGER, pilot_batch_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(club_event_id) REFERENCES v05c_club_event_profiles(id) ON DELETE RESTRICT,
 FOREIGN KEY(registration_id) REFERENCES v05c_club_event_registrations(id) ON DELETE RESTRICT,
 UNIQUE(club_event_id,registration_id,status),
 CHECK(status IN ('active','used','revoked','expired'))
);

CREATE TABLE IF NOT EXISTS p4_checkin_audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, club_event_id INTEGER NOT NULL,
 registration_id INTEGER, token_id INTEGER, action TEXT NOT NULL, result TEXT NOT NULL,
 method TEXT NOT NULL, detail TEXT, actor_user_id INTEGER, actor TEXT NOT NULL,
 pilot_batch_id TEXT, created_at TEXT NOT NULL,
 FOREIGN KEY(club_event_id) REFERENCES v05c_club_event_profiles(id) ON DELETE RESTRICT,
 CHECK(action IN ('check_in','supplement','undo','invalid_attempt')),
 CHECK(result IN ('success','duplicate','rejected','not_found','expired','wrong_event'))
);
CREATE INDEX IF NOT EXISTS ix_p4_checkin_audit_event ON p4_checkin_audit(club_event_id,id DESC);

CREATE TABLE IF NOT EXISTS p4_event_relationship_candidates (
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_no TEXT NOT NULL UNIQUE,
 club_event_id INTEGER NOT NULL, relationship_type TEXT NOT NULL,
 subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT NOT NULL,
 evidence_json TEXT NOT NULL, confidence REAL NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending',
 p3_candidate_id INTEGER, reviewed_by TEXT, reviewed_at TEXT, review_note TEXT,
 pilot_batch_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(club_event_id) REFERENCES v05c_club_event_profiles(id) ON DELETE RESTRICT,
 UNIQUE(club_event_id,relationship_type,subject_type,subject_id,object_type,object_id),
 CHECK(relationship_type IN ('attended_same_event','met_at_event','expressed_connection_interest','speaker_at_event','organizer_of_event','co_organizer_of_event')),
 CHECK(status IN ('pending','reviewed','accepted','rejected','promoted','closed'))
);

CREATE TABLE IF NOT EXISTS p4_resource_match_candidates (
 id INTEGER PRIMARY KEY AUTOINCREMENT, match_no TEXT NOT NULL UNIQUE,
 demand_resource_id INTEGER NOT NULL, supply_resource_id INTEGER NOT NULL,
 recommended_person_id INTEGER, recommended_organization_id INTEGER,
 score INTEGER NOT NULL, reasons_json TEXT NOT NULL, relationship_path_json TEXT,
 common_contacts_json TEXT, risks_json TEXT, evidence_json TEXT, generation_method TEXT NOT NULL,
 status TEXT NOT NULL DEFAULT 'pending', reviewed_by TEXT, reviewed_at TEXT, review_note TEXT,
 pilot_batch_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(demand_resource_id) REFERENCES v06_market_resources(id) ON DELETE RESTRICT,
 FOREIGN KEY(supply_resource_id) REFERENCES v06_market_resources(id) ON DELETE RESTRICT,
 UNIQUE(demand_resource_id,supply_resource_id),
 CHECK(status IN ('pending','reviewed','accepted','rejected','introduced','converted_to_lead','closed'))
);

CREATE TABLE IF NOT EXISTS p4_club_lead_candidates (
 id INTEGER PRIMARY KEY AUTOINCREMENT, lead_no TEXT NOT NULL UNIQUE, title TEXT NOT NULL,
 source_type TEXT NOT NULL, source_id TEXT, demand_organization_id INTEGER, supply_organization_id INTEGER,
 person_ids_json TEXT, organization_ids_json TEXT, reason TEXT NOT NULL, evidence_json TEXT NOT NULL,
 owner_user_id INTEGER, priority TEXT NOT NULL DEFAULT 'P2', next_action TEXT,
 status TEXT NOT NULL DEFAULT 'pending', legacy_lead_id INTEGER,
 reviewed_by TEXT, reviewed_at TEXT, pilot_batch_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(status IN ('pending','reviewed','accepted','rejected','converted','closed'))
);

CREATE TABLE IF NOT EXISTS p4_domain_events (
 id INTEGER PRIMARY KEY AUTOINCREMENT, event_id TEXT NOT NULL UNIQUE, event_type TEXT NOT NULL,
 aggregate_type TEXT NOT NULL, aggregate_id TEXT NOT NULL, payload_json TEXT NOT NULL,
 actor_user_id INTEGER, occurred_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
 consumed_at TEXT, pilot_batch_id TEXT,
 CHECK(status IN ('pending','consumed','failed','ignored'))
);
CREATE INDEX IF NOT EXISTS ix_p4_domain_events_queue ON p4_domain_events(status,id);

CREATE TABLE IF NOT EXISTS p4_operation_audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, audit_no TEXT NOT NULL UNIQUE, action TEXT NOT NULL,
 target_type TEXT NOT NULL, target_id TEXT NOT NULL, before_json TEXT, after_json TEXT,
 actor_user_id INTEGER, actor TEXT NOT NULL, reason TEXT, result TEXT NOT NULL DEFAULT 'success',
 pilot_batch_id TEXT, created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_p4_operation_audit_target ON p4_operation_audit(target_type,target_id,id DESC);
"""

ADDITIVE_COLUMNS = {
    "v04f_club_applications": {
        "user_id": "INTEGER", "member_type": "TEXT", "professional_direction": "TEXT",
        "application_reason": "TEXT", "source_event_id": "INTEGER", "owner": "TEXT",
        "held_reason": "TEXT", "pilot_batch_id": "TEXT",
    },
    "v04f_club_memberships": {"pilot_batch_id": "TEXT"},
    "v05c_club_event_profiles": {
        "lifecycle_status": "TEXT NOT NULL DEFAULT 'draft'", "topic": "TEXT", "co_organizer": "TEXT", "channel": "TEXT",
        "registration_start": "TEXT", "audience": "TEXT", "review_mode": "TEXT",
        "agenda": "TEXT", "guests": "TEXT", "research_topic_id": "INTEGER",
        "industry_tags": "TEXT", "reviewed_by": "TEXT", "reviewed_at": "TEXT",
        "review_note": "TEXT", "pilot_batch_id": "TEXT",
    },
    "v05c_club_event_registrations": {
        "lifecycle_status": "TEXT NOT NULL DEFAULT 'submitted'", "canonical_membership_id": "INTEGER", "user_id": "INTEGER", "person_id": "INTEGER", "organization_id": "INTEGER",
        "is_guest": "INTEGER NOT NULL DEFAULT 1", "application_reason": "TEXT",
        "interest_direction": "TEXT", "desired_connections": "TEXT",
        "offered_resources": "TEXT", "current_needs": "TEXT", "cancelled_at": "TEXT",
        "pilot_batch_id": "TEXT",
    },
    "v05c_club_event_participation": {"canonical_membership_id": "INTEGER", "pilot_batch_id": "TEXT"},
    "v06_market_resources": {
        "source_event_id": "INTEGER", "target_audience": "TEXT", "reviewed_by": "TEXT",
        "reviewed_at": "TEXT", "review_note": "TEXT", "pilot_batch_id": "TEXT",
    },
}


def table_names(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def analyze(conn: sqlite3.Connection) -> dict:
    names = table_names(conn)
    return {
        "missing_required_tables": sorted(REQUIRED_TABLES - names),
        "missing_p4_tables": sorted(P4_TABLES - names),
        "p3_available": "p3_relationship_candidates" in names,
        "counts": {
            name: int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0])
            for name in sorted(P4_TABLES | {"people", "organizations", "v04f_club_memberships", "v06_market_resources"})
            if name in names
        },
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
    for statement in TABLE_SQL.split(";"):
        if statement.strip():
            conn.execute(statement)
    for table, columns in ADDITIVE_COLUMNS.items():
        existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        for name, definition in columns.items():
            if name not in existing:
                conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{name}" {definition}')


def write_report(path: Path | None, report: dict) -> None:
    if path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="P4 Q-BAY club operations MVP migration")
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
            "migration_id": MIGRATION_ID, "mode": "apply" if applying else "dry-run",
            "database_name": db_path.name, "timestamp": datetime.now().isoformat(), "before": before,
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
            if after["missing_p4_tables"]:
                raise RuntimeError("schema_verification_failed")
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        report.update({
            "backup_name": backup_path.name, "backup_sha256": backup_sha,
            "after": after, "applied": True,
        })
        write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
