from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
import gc
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.test_db_utils import temporary_database


def check(results: list[bool], name: str, condition: bool, detail: str = "") -> None:
    print(("PASS" if condition else "FAIL"), name, detail)
    results.append(bool(condition))


def run_script(db_path: Path, *args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["APP_DB_PATH"] = str(db_path)
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    return subprocess.run([sys.executable, *args], cwd=ROOT, env=env, text=True, capture_output=True)


def make_orphan(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute("CREATE TABLE di_parent(id INTEGER PRIMARY KEY)")
        conn.execute("CREATE TABLE di_child(id INTEGER PRIMARY KEY, parent_id INTEGER NOT NULL, note TEXT, FOREIGN KEY(parent_id) REFERENCES di_parent(id))")
        conn.execute("INSERT INTO di_child(id,parent_id,note) VALUES (1,99,'verify orphan')")
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    results: list[bool] = []
    with temporary_database("di_workflow_") as db_path:
        make_orphan(db_path)
        before_mtime = db_path.stat().st_mtime_ns
        dry = run_script(db_path, "scripts/repair_remaining_foreign_keys_v1.py", "--dry-run")
        after_mtime = db_path.stat().st_mtime_ns
        check(results, "foreign key audit dry-run", dry.returncode == 0 and "foreign_key_issues_before=1" in dry.stdout, dry.stdout + dry.stderr)
        check(results, "dry-run does not modify database", before_mtime == after_mtime, f"{before_mtime}->{after_mtime}")
        apply = run_script(db_path, "scripts/repair_remaining_foreign_keys_v1.py", "--apply")
        check(results, "apply registers issue and creates backup", apply.returncode == 0 and "backup_path=" in apply.stdout and "registered_inserted=1" in apply.stdout, apply.stdout + apply.stderr)
        second = run_script(db_path, "scripts/repair_remaining_foreign_keys_v1.py", "--apply")
        check(results, "repeat apply is idempotent", second.returncode == 0 and "registered_inserted=0" in second.stdout, second.stdout + second.stderr)
        conn = sqlite3.connect(db_path)
        try:
            conn.row_factory = sqlite3.Row
            row = conn.execute("SELECT id,status FROM data_integrity_issues LIMIT 1").fetchone()
            audit_count = conn.execute("SELECT COUNT(*) FROM data_integrity_issue_audit").fetchone()[0]
            fk_count = len(conn.execute("PRAGMA foreign_key_check").fetchall())
            issue_id = int(row["id"])
        finally:
            conn.close()
        check(results, "all changes write audit", audit_count >= 1, str(audit_count))
        manual = run_script(db_path, "scripts/repair_remaining_foreign_keys_v1.py", "--issue-id", str(issue_id), "--status", "waiting_for_source", "--note", "verify waiting", "--apply")
        check(results, "single manual handling available", manual.returncode == 0 and "status=waiting_for_source" in manual.stdout, manual.stdout + manual.stderr)
        check(results, "unresolved issue is not auto-deleted", fk_count == 1, str(fk_count))
        check(results, "foreign_key_check result is real", "foreign_key_issues_after=1" in apply.stdout, apply.stdout)
        gc.collect()
        time.sleep(0.3)
    print(f"verify_data_integrity_workflow_v1 passed={sum(results)} failed={len(results)-sum(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

