from __future__ import annotations

import shutil
import sqlite3
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.settings import resolved_db_path
DB_PATH = resolved_db_path()
LOG_PATH = ROOT / "logs" / "migrate_all_latest.log"

MIGRATIONS = [
    ("v0.4C", "scripts/migrate_v04c.py", {"v04c_review_items", "v04c_review_actions"}),
    ("v0.4C-1", "scripts/migrate_v04c1.py", {"v04c1_ingest_batches", "v04c1_canonical_facts"}),
    ("v0.4D", "scripts/migrate_v04d.py", {"v04d_structuring_tasks", "v04d_structure_items"}),
    ("v0.4D-B", "scripts/migrate_v04db.py", {"v04db_extraction_runs", "v04db_candidates"}),
    ("v0.4E", "scripts/migrate_v04e.py", {"v04e_entity_aliases", "v04e_duplicate_candidates"}),
    ("v0.4F", "scripts/migrate_v04f.py", {"v04f_lead_records", "v04f_club_memberships"}),
    ("v0.4G", "scripts/migrate_v04g.py", {"v04g_monitoring_sources", "v04g_update_proposals"}),
    ("v0.4H", "scripts/migrate_v04h.py", {"v04h_recommendations", "v04h_feedback_events"}),
    ("v0.5A", "scripts/migrate_v05a.py", {"v05a_users", "v05a_audit_logs"}),
    ("v0.5B", "scripts/migrate_v05b.py", {"v05b_import_jobs", "v05b_import_drafts", "v05b_media_assets", "v05b_member_contacts"}),
    ("v0.5C", "scripts/migrate_v05c.py", {"v05c_club_event_profiles", "v05c_club_event_registrations", "v05c_club_event_participation", "v05c_member_activity_scores"}),
    ("v0.5D", "scripts/migrate_v05d.py", {"v05d_member_accounts", "v05d_profile_change_requests", "v05d_member_content_requests", "v05d_member_notifications"}),
    ("v0.5E", "scripts/migrate_v05e.py", {"v05e_industry_signals", "v05e_watchlists", "v05e_watchlist_items"}),
    ("v0.5F", "scripts/migrate_v05f.py", {"v05f_collection_items", "v05f_discovered_links", "v05f_content_duplicate_links"}),
    ("v0.5G", "scripts/migrate_v05g.py", {"v05g_processing_jobs", "v05g_extraction_candidates", "v05g_subject_match_candidates"}),
    ("v0.5H", "scripts/migrate_v05h.py", {"v05h_signal_rules", "v05h_signal_evidence", "v05h_report_templates", "v05h_report_jobs", "v05h_generated_reports"}),
    ("v0.5I", "scripts/migrate_v05i.py", {"v05i_pipeline_runs", "v05i_pipeline_stage_runs", "v05i_pipeline_quality_samples", "v05i_pilot_source_results"}),
    ("v0.5J", "scripts/migrate_v05j.py", {"research_topics", "research_topic_subjects", "research_snapshots", "investment_assessments"}),
    ("v0.5K-L", "scripts/migrate_v05kl.py", {"task_queue", "worker_heartbeats", "scheduler_jobs", "backup_records", "source_health_scores", "data_quality_metrics"}),
]


def log(message: str) -> None:
    print(message)
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(message + "\n")


def existing_tables() -> set[str]:
    if not DB_PATH.exists():
        return set()
    conn = sqlite3.connect(DB_PATH)
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def backup_database() -> str:
    if not DB_PATH.exists():
        return ""
    target_dir = ROOT / "data" / "backups"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / f"app_before_migrate_all_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(DB_PATH, target)
    return str(target)


def main() -> int:
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("", encoding="utf-8")
    log("migrate_all started")
    log(f"project={ROOT}")
    backup = backup_database()
    log(f"backup={backup or 'not created'}")

    skipped = 0
    executed = 0
    for name, script, required in MIGRATIONS:
        path = ROOT / script
        if not path.exists():
            log(f"[SKIP] {name}: missing {script}")
            skipped += 1
            continue
        tables = existing_tables()
        if required.issubset(tables):
            log(f"[SKIP] {name}: schema already present")
            skipped += 1
            continue
        log(f"[RUN] {name}: {script}")
        result = subprocess.run([sys.executable, str(path)], cwd=ROOT, text=True, capture_output=True)
        if result.stdout:
            log(result.stdout.rstrip())
        if result.stderr:
            log(result.stderr.rstrip())
        if result.returncode != 0:
            log(f"[FAIL] {name}: exit={result.returncode}")
            return result.returncode
        executed += 1

    log(f"migrate_all completed executed={executed} skipped={skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

