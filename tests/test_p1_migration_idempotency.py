import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_migration(db_path, mode):
    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "migrations" / "001_core_domain_unification.py"),
         "--db-path", str(db_path), mode],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError(f"Migration failed: {result.stderr}")
    return result.stdout


def test_migration_dry_run_on_copy(temp_database):
    run_migration(temp_database, "--dry-run")


def test_migration_apply_on_copy(temp_database):
    run_migration(temp_database, "--apply")


def test_migration_idempotent(temp_database):
    run_migration(temp_database, "--apply")
    before_mappings = count_mappings(temp_database)
    before_conflicts = count_conflicts(temp_database)
    
    run_migration(temp_database, "--apply")
    after_mappings = count_mappings(temp_database)
    after_conflicts = count_conflicts(temp_database)
    
    assert before_mappings == after_mappings, "Mappings count changed on second apply"
    assert before_conflicts == after_conflicts, "Conflicts count changed on second apply"


def count_mappings(db_path):
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM platform_entity_mappings").fetchone()[0]


def count_conflicts(db_path):
    import sqlite3
    with sqlite3.connect(db_path) as conn:
        return conn.execute("SELECT COUNT(*) FROM platform_migration_conflicts").fetchone()[0]
