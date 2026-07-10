from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def log(message: str) -> None:
    print(message)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def _tables(db_path: Path) -> set[str]:
    conn = sqlite3.connect(db_path)
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


def verify_migration(db_path: Path) -> None:
    from scripts.migrate_v05kl import migrate

    migrate(db_path, backup=False)
    migrate(db_path, backup=False)
    required = {
        "task_queue",
        "task_runs",
        "worker_heartbeats",
        "scheduler_jobs",
        "backup_records",
        "restore_records",
        "system_health_snapshots",
        "source_health_scores",
        "source_quality_samples",
        "source_rule_versions",
        "source_rule_test_runs",
        "data_quality_metrics",
        "quality_reports",
        "performance_events",
    }
    missing = required - _tables(db_path)
    assert_true(not missing, f"missing v05kl tables: {sorted(missing)}")
    log("[PASS] migration is idempotent and creates required tables")


def verify_config(db_path: Path) -> None:
    from app.core.config import Settings
    from app.core.database_compat import database_health

    dev = Settings(app_env="development", database_url=f"sqlite:///{db_path}")
    assert_true(not dev.validate(), "development config should validate")
    prod = Settings(app_env="production", database_url=f"sqlite:///{db_path}")
    errors = prod.validate()
    assert_true(any("SECRET_KEY" in item for item in errors), "production validation should require secrets")
    health = database_health(dev)
    assert_true(health["ok"], "sqlite database health should pass")
    log("[PASS] configuration and database compatibility checks")


def verify_tasks(db_path: Path) -> None:
    from app.services.tasks import create_task, list_tasks, task_metrics
    from app.services.tasks.task_runner import run_once

    task = create_task("cleanup", payload={"scope": "verify"}, db_path=db_path, idempotency_key="verify-cleanup")
    duplicate = create_task("cleanup", payload={"scope": "verify"}, db_path=db_path, idempotency_key="verify-cleanup")
    assert_true(task["id"] == duplicate["id"], "idempotency key should reuse existing task")
    result = run_once(worker_id="verify-worker", db_path=db_path)
    assert_true(result["processed"] == 1 and result["status"] == "success", "cleanup task should run successfully")
    rows = list_tasks(db_path=db_path)
    metrics = task_metrics(db_path=db_path)
    assert_true(rows["pagination"]["total"] >= 1, "task list should include created task")
    assert_true(sum(int(value) for value in metrics["counts"].values()) >= 1, "task metrics should count tasks")
    log("[PASS] task queue, idempotency, worker run and metrics")


def verify_backup_restore(db_path: Path, work_dir: Path) -> None:
    from app.services.operations.backup_service import create_backup
    from app.services.operations.restore_service import restore_backup, validate_backup

    backup = create_backup(backup_type="verify", created_by="verify", db_path=db_path, target_dir=work_dir / "backups")
    validation = validate_backup(backup["backup_id"], db_path=db_path)
    assert_true(validation["ok"], "backup package should validate")
    target = work_dir / "restore-target.db"
    shutil.copy2(db_path, target)
    dry = restore_backup(backup["backup_id"], target_path=target, dry_run=True, created_by="verify", db_path=db_path)
    assert_true(dry["status"] == "validated", "dry-run restore should validate only")
    restored = restore_backup(backup["backup_id"], target_path=target, dry_run=False, confirm=True, created_by="verify", db_path=db_path)
    assert_true(restored["status"] == "restored" and target.exists(), "confirmed restore should write target database")
    log("[PASS] backup package validation and dry-run/confirmed restore")


def verify_source_quality(db_path: Path) -> None:
    from app.services.operations import calculate_source_health_scores, create_quality_report, health_snapshot, quality_metrics, readiness
    from app.services.tasks.task_common import db_connection, now

    with db_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO v04g_monitoring_sources(source_no,name,source_type,url,check_frequency,is_enabled,fetch_mode,created_at,updated_at)
            VALUES ('SRC-VERIFY-0001','验证来源','webpage','https://example.com','manual',1,'web',?,?)
            """,
            (now(), now()),
        )
        conn.execute(
            """
            INSERT INTO v04g_monitoring_runs(run_no,monitoring_source_id,status,started_at,finished_at,http_status,content_length,changed,error_message,created_at)
            VALUES ('RUN-VERIFY-0001', ?, 'success', ?, ?, 200, 128, 1, '', ?)
            """,
            (cur.lastrowid, now(), now(), now()),
        )
    health = calculate_source_health_scores(db_path=db_path)
    metrics = quality_metrics(db_path=db_path)
    report = create_quality_report(created_by="verify", db_path=db_path)
    snapshot = health_snapshot(db_path=db_path, detailed=True)
    ready_code, ready = readiness(db_path=db_path)
    assert_true(health["created"] >= 1, "source health score should be calculated")
    assert_true(metrics["source_total"] >= 1, "quality metrics should count source")
    assert_true(report["report_no"].startswith("QREP-"), "quality report should have report number")
    assert_true(snapshot["status"] in {"healthy", "degraded"}, "health snapshot should have known status")
    assert_true(ready_code in {200, 503} and "checks" in ready, "readiness should return status and checks")
    log("[PASS] source health, quality metrics, report and system readiness")


def verify_postgres_tool(db_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "migrate_sqlite_to_postgres.py"), "--dry-run"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    assert_true(result.returncode == 0, result.stderr or result.stdout)
    assert_true("DRY-RUN" in result.stdout or "dry-run" in result.stdout.lower(), "postgres migration tool should stay in dry-run")
    log("[PASS] SQLite to PostgreSQL migration tool dry-run")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v05kl_verify_", ignore_cleanup_errors=True) as tmp:
        work_dir = Path(tmp)
        db_path = work_dir / "app.db"
        os.environ["APP_DB_PATH"] = str(db_path)
        os.environ["APP_AUTH_DISABLED"] = "1"
        os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
        verify_migration(db_path)
        verify_config(db_path)
        verify_tasks(db_path)
        verify_backup_restore(db_path, work_dir)
        verify_source_quality(db_path)
        verify_postgres_tool(db_path)
    log("verify_v05kl completed passed=6 failed=0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
