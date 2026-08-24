from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = ROOT / "logs" / "verify_all_latest.log"
DB_PATH = ROOT / "data" / "app.db"

COMPILE_TARGETS = [
    "app/main.py",
    "app/v04g_monitoring.py",
    "app/v04h_recommendations.py",
    "app/v05a_security.py",
    "app/security.py",
    "app/services/monitoring_service.py",
    "app/services/recommendation_service.py",
    "app/services/relationship_path_service.py",
    "app/services/search_service.py",
    "app/services/api_subject_service.py",
    "app/services/signal_service.py",
    "app/services/watchlist_service.py",
    "app/services/dashboard_service.py",
    "app/services/intelligence_flow_service.py",
    "app/api/v1/router.py",
    "app/v05e_intelligence.py",
    "app/v05f_collection.py",
    "app/services/collection_service.py",
    "app/api/v1/collection.py",
    "app/v05g_processing.py",
    "app/services/processing/processing_job_service.py",
    "app/api/v1/processing.py",
    "app/navigation.py",
    "app/v05h_reports.py",
    "app/v05i_pipeline.py",
    "app/v05j_research.py",
    "app/services/signals/signal_generation_service.py",
    "app/services/reports/report_generation_service.py",
    "app/services/pipeline/pipeline_service.py",
    "app/services/pipeline/pipeline_state_service.py",
    "app/services/pipeline/pipeline_metrics_service.py",
    "app/services/pipeline/pipeline_quality_service.py",
    "app/api/v1/reports.py",
    "app/api/v1/navigation.py",
    "app/api/v1/pipeline.py",
    "app/api/v1/research.py",
    "app/api/v1/investment_assessments.py",
    "app/services/research/research_service.py",
    "app/services/research/investment_assessment_service.py",
    "app/i18n/helpers.py",
    "app/core/config.py",
    "app/core/database_compat.py",
    "app/v05kl_operations.py",
    "app/api/v1/system.py",
    "app/services/tasks/task_common.py",
    "app/services/tasks/task_dispatcher.py",
    "app/services/tasks/task_registry.py",
    "app/services/tasks/task_heartbeat_service.py",
    "app/services/tasks/task_retry_service.py",
    "app/services/tasks/task_runner.py",
    "app/services/tasks/task_metrics_service.py",
    "app/services/operations/backup_service.py",
    "app/services/operations/restore_service.py",
    "app/services/operations/source_quality_service.py",
    "app/services/operations/system_health_service.py",
    "scripts/migrate_all.py",
    "scripts/verify_all.py",
    "scripts/migrate_v05a.py",
    "scripts/verify_v05a.py",
    "app/v05b_member_import.py",
    "app/services/member_import_service.py",
    "app/services/member_import_parser.py",
    "app/services/member_field_classifier.py",
    "app/services/member_import_normalizer.py",
    "app/services/member_import_validator.py",
    "app/v05c_club_events.py",
    "app/v05d_member_portal.py",
    "scripts/migrate_v05b.py",
    "scripts/verify_v05b.py",
    "scripts/migrate_v05c.py",
    "scripts/verify_v05c.py",
    "scripts/migrate_v05d.py",
    "scripts/verify_v05d.py",
    "scripts/migrate_v05e.py",
    "scripts/verify_v05e.py",
    "scripts/migrate_v05f.py",
    "scripts/verify_v05f.py",
    "scripts/migrate_v05g.py",
    "scripts/verify_v05g.py",
    "scripts/run_processing_worker.py",
    "scripts/migrate_v05h.py",
    "scripts/verify_v05h.py",
    "scripts/migrate_v05i.py",
    "scripts/verify_v05i.py",
    "scripts/migrate_v05j.py",
    "scripts/verify_v05j.py",
    "scripts/migrate_v05kl.py",
    "scripts/verify_v05m.py",
    "scripts/verify_v05kl.py",
    "scripts/run_worker.py",
    "scripts/run_scheduler.py",
    "scripts/restore_backup.py",
    "scripts/migrate_sqlite_to_postgres.py",
    "scripts/run_operational_pilot.py",
    "scripts/check_user_visible_english.py",
    "scripts/pilot_real_sources.py",
    "scripts/run_signal_worker.py",
    "scripts/run_report_worker.py",
    "scripts/run_pipeline_worker.py",
]

PRECHECK_SCRIPTS = [
    ("template precompile", "scripts/check_all_templates.py"),
    ("mojibake scan", "scripts/check_mojibake.py"),
    ("core page smoke", "scripts/verify_core_pages.py"),
]

VERIFY_SCRIPTS = [
    ("current", "scripts/verify_intelligence_full_chain.py"),
    ("current", "scripts/verify_v05m.py"),
    ("current", "scripts/verify_v05kl.py"),
    ("current", "scripts/verify_v05e.py"),
    ("current", "scripts/verify_v05j.py"),
    ("current", "scripts/verify_v05i.py"),
    ("current", "scripts/verify_v05h.py"),
    ("current", "scripts/verify_v05g.py"),
    ("current", "scripts/verify_v05f.py"),
    ("current", "scripts/verify_v05d.py"),
    ("current", "scripts/verify_v05c.py"),
    ("current", "scripts/verify_v05b.py"),
    ("security", "scripts/verify_v05a.py"),
    ("current", "scripts/verify_v04h.py"),
    ("current", "scripts/verify_v04g.py"),
    ("core", "scripts/verify_v04d_search.py"),
    ("core", "scripts/verify_v04e.py"),
    ("core", "scripts/verify_v04f.py"),
    ("history", "scripts/verify_v04c.py"),
    ("history", "scripts/verify_v04c1.py"),
    ("history", "scripts/verify_v04d.py"),
    ("history", "scripts/verify_manual_ingestion.py"),
    ("history", "scripts/verify_v04db.py"),
    ("history", "scripts/verify_v04d3_batch_people.py"),
    ("history", "scripts/verify_v04d4_links_and_review.py"),
]


def log(message: str) -> None:
    print(message)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(message + "\n")


def run_step(label: str, args: list[str], *, auth_disabled: bool = False) -> bool:
    log(f"[RUN] {label}")
    env = os.environ.copy()
    if auth_disabled:
        env["APP_AUTH_DISABLED"] = "1"
    else:
        env.pop("APP_AUTH_DISABLED", None)
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True, env=env)
    if result.stdout:
        log(result.stdout.rstrip())
    if result.stderr:
        log(result.stderr.rstrip())
    if result.returncode != 0:
        log(f"[FAIL] {label}: exit={result.returncode}")
        return False
    log(f"[PASS] {label}")
    return True


def check_database_schema() -> bool:
    required = {"organizations", "people", "projects", "v04g_monitoring_sources", "v04g_update_proposals", "v04h_recommendations", "v04h_feedback_events", "v05a_users", "v05a_audit_logs", "v05b_import_jobs", "v05b_import_drafts", "v05b_media_assets", "v05b_member_contacts", "v05c_club_event_profiles", "v05c_club_event_registrations", "v05c_club_event_participation", "v05c_member_activity_scores", "v05d_member_accounts", "v05d_profile_change_requests", "v05d_member_content_requests", "v05d_member_notifications", "v05e_industry_signals", "v05e_watchlists", "v05e_watchlist_items", "v05f_collection_items", "v05f_discovered_links", "v05f_content_duplicate_links", "v05g_processing_jobs", "v05g_extraction_candidates", "v05g_subject_match_candidates", "v05h_signal_rules", "v05h_report_templates", "v05h_generated_reports", "v05i_pipeline_runs", "v05i_pipeline_stage_runs", "v05i_pipeline_quality_samples", "v05i_pilot_source_results", "research_topics", "research_topic_subjects", "research_snapshots", "investment_assessments", "task_queue", "task_runs", "worker_heartbeats", "scheduler_jobs", "backup_records", "restore_records", "source_health_scores", "source_quality_samples", "source_rule_versions", "source_rule_test_runs", "data_quality_metrics", "quality_reports", "performance_events"}
    if not DB_PATH.exists():
        log("[FAIL] database missing")
        return False
    conn = sqlite3.connect(DB_PATH)
    try:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()
    missing = required - tables
    if missing:
        log(f"[FAIL] missing tables: {', '.join(sorted(missing))}")
        return False
    log("[PASS] database schema check")
    return True


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")
    passed = failed = skipped = 0

    existing_compile = [str(ROOT / item) for item in COMPILE_TARGETS if (ROOT / item).exists()]
    if run_step("python compile check", [sys.executable, "-m", "py_compile", *existing_compile]):
        passed += 1
    else:
        failed += 1

    if check_database_schema():
        passed += 1
    else:
        failed += 1

    for category, script in VERIFY_SCRIPTS:
        path = ROOT / script
        if not path.exists():
            log(f"[SKIP] {category}: {script} not found")
            skipped += 1
            continue
        if run_step(f"{category}: {script}", [sys.executable, str(path)], auth_disabled=(script != "scripts/verify_v05a.py")):
            passed += 1
        else:
            failed += 1

    log(f"verify_all completed passed={passed} failed={failed} skipped={skipped}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())

