import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def run_integrity_repair(db_path, mode, report_path=None):
    args = [
        sys.executable,
        str(ROOT / "scripts" / "migrations" / "002_repair_domain_integrity.py"),
        "--db", str(db_path),
        mode,
    ]
    if report_path:
        args.extend(["--report", str(report_path)])
    
    result = subprocess.run(args, cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(f"Integrity repair failed: {result.stderr}")
    return json.loads(result.stdout)


def test_dry_run_default(temp_database):
    result = run_integrity_repair(temp_database, "--dry-run")
    assert result["mode"] == "dry-run"
    assert "applied" not in result or result.get("applied") is False


def test_dry_run_does_not_modify_db(temp_database):
    import sqlite3
    with sqlite3.connect(temp_database) as conn:
        initial_count = conn.execute("SELECT COUNT(*) FROM v06_timeline_entries").fetchone()[0]
    
    run_integrity_repair(temp_database, "--dry-run")
    
    with sqlite3.connect(temp_database) as conn:
        final_count = conn.execute("SELECT COUNT(*) FROM v06_timeline_entries").fetchone()[0]
    
    assert initial_count == final_count


def test_apply_mode(temp_database):
    result = run_integrity_repair(temp_database, "--apply")
    assert result["mode"] == "apply"
    assert result.get("applied") is True
    assert "backup" in result
    assert "backup_sha256" in result


def test_apply_idempotent(temp_database):
    run_integrity_repair(temp_database, "--apply")
    first_result = run_integrity_repair(temp_database, "--apply")
    
    second_result = run_integrity_repair(temp_database, "--apply")
    
    assert first_result["orphan_foreign_keys"]["count"] == second_result["orphan_foreign_keys"]["count"]
    assert first_result["resource_conflicts"]["count"] == second_result["resource_conflicts"]["count"]


def test_ambiguous_records_not_auto_repaired(temp_database):
    result = run_integrity_repair(temp_database, "--apply")
    summary = result["summary"]
    assert summary["auto_repairable"] == 0
    assert summary["requires_human_review"] > 0


def test_report_output(temp_database, tmp_path):
    report_path = tmp_path / "integrity_report.json"
    result = run_integrity_repair(temp_database, "--dry-run", report_path)
    
    assert report_path.exists()
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)
    assert report["mode"] == "dry-run"
    assert "orphan_foreign_keys" in report
    assert "resource_conflicts" in report
