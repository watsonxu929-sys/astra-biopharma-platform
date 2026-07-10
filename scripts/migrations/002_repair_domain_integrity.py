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

MIGRATION_ID = "002_repair_domain_integrity"


def table_exists(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None


def columns(conn, table):
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')} if table_exists(conn, table) else set()


def backup_database(conn, db_path):
    backup_dir = db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{db_path.stem}_before_{MIGRATION_ID}_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    with sqlite3.connect(backup_path) as target:
        conn.backup(target)
    digest = hashlib.sha256(backup_path.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{backup_path.as_posix()}?mode=ro", uri=True) as check:
        integrity = check.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        backup_path.unlink(missing_ok=True)
        raise RuntimeError(f"backup integrity check failed: {integrity}")
    return backup_path, digest


def analyze_orphan_fks(conn):
    orphans = []
    if table_exists(conn, "v06_timeline_entries") and table_exists(conn, "v06_opportunities"):
        existing_opp_ids = {r["id"] for r in conn.execute("SELECT id FROM v06_opportunities")}
        for row in conn.execute("SELECT id, opportunity_id, event_type, description, created_at FROM v06_timeline_entries"):
            if row["opportunity_id"] not in existing_opp_ids:
                orphans.append({
                    "table": "v06_timeline_entries",
                    "row_id": row["id"],
                    "fk_field": "opportunity_id",
                    "fk_value": row["opportunity_id"],
                    "event_type": row["event_type"],
                    "description": row["description"],
                    "created_at": row["created_at"],
                    "can_auto_repair": False,
                    "reason": "no_matching_opportunity",
                })
    return orphans


def analyze_resource_conflicts(conn):
    conflicts = []
    if table_exists(conn, "platform_migration_conflicts"):
        for row in conn.execute("SELECT * FROM platform_migration_conflicts WHERE status='pending'"):
            conflicts.append({
                "conflict_id": row["id"],
                "migration_id": row["migration_id"],
                "domain": row["domain"],
                "source_entity_type": row["source_entity_type"],
                "source_entity_id": row["source_entity_id"],
                "reason": row["reason"],
                "details_json": row["details_json"],
                "status": row["status"],
                "can_auto_repair": False,
                "analysis": "awaiting_human_review",
            })
    return conflicts


def check_legacy_mappings(conn):
    mappings_count = 0
    if table_exists(conn, "platform_entity_mappings"):
        mappings_count = int(conn.execute("SELECT COUNT(*) FROM platform_entity_mappings").fetchone()[0])
    return mappings_count


def build_report(conn, orphans, conflicts, mappings_count):
    return {
        "migration_id": MIGRATION_ID,
        "timestamp": datetime.now().isoformat(),
        "orphan_foreign_keys": {
            "count": len(orphans),
            "details": orphans,
        },
        "resource_conflicts": {
            "count": len(conflicts),
            "details": conflicts,
        },
        "legacy_mappings": {
            "count": mappings_count,
        },
        "summary": {
            "total_issues": len(orphans) + len(conflicts),
            "auto_repairable": sum(1 for o in orphans if o["can_auto_repair"]) + sum(1 for c in conflicts if c["can_auto_repair"]),
            "requires_human_review": len(orphans) + len(conflicts) - sum(1 for o in orphans if o["can_auto_repair"]) - sum(1 for c in conflicts if c["can_auto_repair"]),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Domain integrity repair migration")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Apply fixes (default is dry-run)")
    mode.add_argument("--dry-run", action="store_true", help="Dry run only (default)")
    parser.add_argument("--db", type=Path, help="Database path")
    parser.add_argument("--report", type=Path, help="Report output path")
    args = parser.parse_args()

    db_path = (args.db or resolved_db_path()).resolve()
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}")
        return 2

    apply = bool(args.apply)
    dry_run = bool(args.dry_run) or not apply
    
    uri = str(db_path) if apply else f"file:{db_path.as_posix()}?mode=ro"
    
    with sqlite3.connect(uri, uri=not apply) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")

        orphans = analyze_orphan_fks(conn)
        conflicts = analyze_resource_conflicts(conn)
        mappings_count = check_legacy_mappings(conn)
        report = build_report(conn, orphans, conflicts, mappings_count)

        report["mode"] = "apply" if apply else "dry-run"

        if not apply:
            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                with open(args.report, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)
            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
            return 0

        backup_path, backup_sha = backup_database(conn, db_path)

        try:
            conn.execute("BEGIN IMMEDIATE")

            for orphan in orphans:
                if orphan["can_auto_repair"]:
                    pass

            for conflict in conflicts:
                if conflict["can_auto_repair"]:
                    pass

            report["backup"] = str(backup_path)
            report["backup_sha256"] = backup_sha
            report["applied"] = True
            report["applied_at"] = datetime.now().isoformat()

            if args.report:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                with open(args.report, "w", encoding="utf-8") as f:
                    json.dump(report, f, ensure_ascii=False, indent=2, sort_keys=True)

            print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))

            if table_exists(conn, "platform_migration_runs"):
                conn.execute(
                    "INSERT INTO platform_migration_runs(migration_id, mode, stats_json, backup_path, backup_sha256) VALUES (?, ?, ?, ?, ?)",
                    (MIGRATION_ID, "apply", json.dumps(report, ensure_ascii=False, sort_keys=True), str(backup_path), backup_sha)
                )

            conn.commit()

        except Exception:
            conn.rollback()
            raise

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
