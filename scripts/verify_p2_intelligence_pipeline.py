from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.platform.capability_registry import list_capabilities
from app.settings import resolved_db_path

REQUIRED_TABLES = {
    "p2_fact_candidate_evidence",
    "p2_intelligence_product_candidates",
    "p2_intelligence_product_evidence",
    "p2_ai_analysis_runs",
    "p2_pilot_batches",
    "p2_intelligence_audit_log",
}


def verify(db_path: Path) -> dict:
    digest_before = hashlib.sha256(db_path.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        tables = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        missing = sorted(REQUIRED_TABLES - tables)
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        all_foreign_key_issues = [dict(row) for row in conn.execute("PRAGMA foreign_key_check")]
        foreign_key_issues = [row for row in all_foreign_key_issues if row["table"] in REQUIRED_TABLES]
        counts = {table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]) for table in sorted(REQUIRED_TABLES & tables)}
        snapshot_trigger = bool(conn.execute("SELECT 1 FROM sqlite_master WHERE type='trigger' AND name='trg_p2_snapshot_immutable'").fetchone())
    intelligence_children = [item for item in list_capabilities() if item.get("parent_key") == "intelligence"]
    routes = [item["web_route"] for item in intelligence_children]
    keys = [item["capability_key"] for item in intelligence_children]
    digest_after = hashlib.sha256(db_path.read_bytes()).hexdigest()
    checks = {
        "schema_complete": not missing,
        "sqlite_integrity": integrity == "ok",
        "foreign_keys_clean": not foreign_key_issues,
        "snapshot_immutable_trigger": snapshot_trigger,
        "navigation_keys_unique": len(keys) == len(set(keys)),
        "navigation_routes_unique": len(routes) == len(set(routes)),
        "database_unchanged_by_verifier": digest_before == digest_after,
    }
    return {
        "ok": all(checks.values()),
        "database_name": db_path.name,
        "sha256_before": digest_before,
        "sha256_after": digest_after,
        "checks": checks,
        "missing_tables": missing,
        "foreign_key_issues": foreign_key_issues,
        "known_legacy_foreign_key_issue_count": len(all_foreign_key_issues) - len(foreign_key_issues),
        "counts": counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Read-only P2.1 intelligence pipeline verification")
    parser.add_argument("--db", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    result = verify((args.db or resolved_db_path()).resolve())
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
