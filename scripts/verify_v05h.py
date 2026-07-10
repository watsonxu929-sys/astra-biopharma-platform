from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("APP_AUTH_DISABLED", "1")

from app.navigation import navigation_for
from app.services.reports import approve_report, create_report_job, generate_report, list_reports, report_citations, submit_report
from app.services.signals import generate_signals, list_rules, set_rule_enabled, signal_dashboard
from app.v04c_review import db_connection
from scripts.migrate_v05h import migrate


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def table_names(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def seed_core(db_path: Path) -> None:
    with db_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                event_date TEXT,
                name TEXT,
                event_type TEXT,
                related_entity TEXT,
                fact_summary TEXT,
                verification_status TEXT,
                manually_confirmed INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS actions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT,
                task TEXT,
                target_external_id TEXT,
                completion_standard TEXT,
                owner TEXT,
                priority TEXT,
                status TEXT,
                source_type TEXT,
                source_title TEXT,
                source_text TEXT,
                manually_confirmed INTEGER,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                standard_name TEXT,
                is_active INTEGER DEFAULT 1
            );
            """
        )
        conn.execute(
            """
            INSERT INTO events(external_id,event_date,name,event_type,related_entity,fact_summary,verification_status,manually_confirmed,is_active,created_at)
            VALUES ('EVT-20260701-000001','2026-07-01','星河生物完成B轮融资','融资','ORG-20260701-000001','星河生物完成5000万美元B轮融资，用于ADC项目临床推进。','已确认',1,1,datetime('now','localtime'))
            """
        )
        conn.execute(
            """
            INSERT INTO events(external_id,event_date,name,event_type,related_entity,fact_summary,verification_status,manually_confirmed,is_active,created_at)
            VALUES ('EVT-20260701-000002','2026-07-01','未审核融资传闻','融资','ORG-20260701-000001','该记录未确认。','待核验',0,1,datetime('now','localtime'))
            """
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="verify_v05h_") as tmp:
        db_path = Path(tmp) / "app.db"
        migrate(db_path, backup=False)
        migrate(db_path, backup=False)
        seed_core(db_path)
        required = {"v05h_signal_rules", "v05h_signal_evidence", "v05h_report_templates", "v05h_report_jobs", "v05h_generated_reports"}
        check(required.issubset(table_names(db_path)), "migration creates v0.5H signal and report tables")
        with db_connection(db_path) as conn:
            signal_columns = {row[1] for row in conn.execute("PRAGMA table_info(v05e_industry_signals)").fetchall()}
            watch_columns = {row[1] for row in conn.execute("PRAGMA table_info(v05e_watchlist_items)").fetchall()}
        check({"signal_category", "severity", "rule_no", "evidence_hash"}.issubset(signal_columns), "migration extends existing v05E signal table")
        check({"focus_signal_types", "alert_threshold", "include_weekly", "include_monthly"}.issubset(watch_columns), "migration extends existing watchlist items")

        rules = list_rules(db_path=db_path)
        check(len(rules) >= 5 and all("condition_json" in r for r in rules), "signal rules are centrally listed")
        disabled = set_rule_enabled(rules[0]["id"], False, db_path=db_path)
        enabled = set_rule_enabled(rules[0]["id"], True, db_path=db_path)
        check(disabled and disabled["is_enabled"] == 0 and enabled and enabled["is_enabled"] == 1, "signal rule can be enabled and disabled without code execution")

        dry = generate_signals(since="2026-07-01", limit=50, dry_run=True, db_path=db_path)
        check(dry["dry_run"] and dry["candidates"] >= 1 and dry["created"] == 0, "historical signal generation is dry-run by default")
        result = generate_signals(since="2026-07-01", limit=50, dry_run=False, db_path=db_path)
        again = generate_signals(since="2026-07-01", limit=50, dry_run=False, db_path=db_path)
        check(result["created"] >= 1 and again["created"] == 0, "confirmed event creates formal signal once with deduplication")
        with db_connection(db_path) as conn:
            unreviewed = conn.execute("SELECT COUNT(*) FROM v05e_industry_signals WHERE source_id='2'").fetchone()[0]
            action_count = conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        check(unreviewed == 0 and action_count == 0, "unreviewed event does not create signal and signal generation does not create actions")
        stats = signal_dashboard(db_path=db_path)
        check(stats["counts"]["total"] >= 1 and stats["counts"]["high"] >= 1, "signal dashboard counts generated signals")

        job = create_report_job(report_type="daily", period_start="2026-07-01", period_end="2026-07-01", generated_by="verify", db_path=db_path)
        report = generate_report(job["id"], db_path=db_path)
        refs = report_citations(report["id"], db_path=db_path)
        check(report["status"] == "draft" and refs, "daily report draft is generated with citations")
        submitted = submit_report(report["id"], actor="verify", db_path=db_path)
        approved = approve_report(report["id"], actor="verify", db_path=db_path)
        check(submitted["status"] == "under_review" and approved["status"] == "approved", "report submit and approval workflow works")
        reports = list_reports(db_path=db_path)
        check(reports["pagination"]["total"] >= 1, "report list is available")

        nav = navigation_for({"permissions": ["view_internal", "review_data", "edit_data"], "auth_disabled": False}, "/signals/dashboard")
        check(len(nav["primary"]) <= 7 and any(item["key"] == "analysis" for item in nav["primary"]), "navigation has no more than seven primary entries and includes analysis")
        check(nav["secondary"] and any(item["endpoint"] == "/reports" for item in nav["secondary"]), "navigation exposes report center in analysis module")
        viewer_nav = navigation_for({"permissions": ["view_internal"], "auth_disabled": False}, "/reports")
        check(not any(child.get("required_permission") == "review_data" for item in viewer_nav["primary"] for child in item.get("children", [])), "navigation filters review-only entries for viewers")

        check((ROOT / "start_windows.bat").exists() and (ROOT / "run_windows.bat").exists(), "Windows start entries exist")
        check((ROOT / "data" / "app.db") != db_path, "verification used a temporary SQLite database")

    print("v0.5H verification completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
