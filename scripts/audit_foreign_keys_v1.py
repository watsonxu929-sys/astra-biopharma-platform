from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import resolved_db_path


def backup_database(db_path: Path) -> Path:
    backup_dir = ROOT / "data" / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"app_v06c_fk_audit_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(db_path, target)
    with sqlite3.connect(target) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        fk = conn.execute("PRAGMA foreign_key_check").fetchall()
    print(f"backup_path={target}")
    print(f"backup_integrity_check={integrity}")
    print(f"backup_foreign_key_check_count={len(fk)}")
    if integrity != "ok":
        raise SystemExit("backup integrity_check failed")
    return target


def fk_meta(conn: sqlite3.Connection, table: str, fkid: int) -> dict:
    rows = conn.execute(f"PRAGMA foreign_key_list('{table}')").fetchall()
    for row in rows:
        if int(row[0]) == int(fkid):
            return {"from": row[3], "parent": row[2], "to": row[4], "on_delete": row[6]}
    return {"from": "", "parent": "", "to": "", "on_delete": ""}


def classify(table: str, column: str, parent: str) -> tuple[str, str]:
    if table == "v05a_audit_logs" and column == "actor_user_id":
        return "audit_missing_user", "set actor_user_id NULL and keep actor_username snapshot"
    if table in {"v06_follow_ups", "v06_collab_tasks", "v06_timeline_entries"}:
        return "opportunity_child_missing_parent", "do not delete automatically unless confirmed demo data"
    if table in {"v05b_member_contacts", "membership_person_link_audit", "membership_user_link_audit"}:
        return "membership_legacy_reference", "repair only with reliable membership id mapping"
    if "event" in table and parent and "event" in parent:
        return "event_archive_missing_parent", "preserve archive; restore parent or document manual handling"
    return "generic_fk_orphan", "manual review before repair"


def audit(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    issues = []
    for table, rowid, parent, fkid in rows:
        meta = fk_meta(conn, table, fkid)
        category, suggestion = classify(table, meta.get("from", ""), parent)
        current_value = None
        if meta.get("from"):
            try:
                r = conn.execute(f"SELECT {meta['from']} FROM {table} WHERE rowid=?", (rowid,)).fetchone()
                current_value = r[0] if r else None
            except sqlite3.Error:
                current_value = None
        is_test = any(token in str(current_value or "").lower() for token in ["test", "demo", "e2e", "verify"])
        issues.append({"table": table, "rowid": rowid, "fk_field": meta.get("from", ""), "current_fk_value": current_value, "parent_table": parent, "category": category, "suggestion": suggestion, "suspected_test_data": is_test, "suspected_business_data": not is_test})
    return issues


def apply_fixes(conn: sqlite3.Connection, issues: list[dict]) -> tuple[int, int]:
    fixed = 0
    deferred = 0
    for issue in issues:
        if issue["category"] == "audit_missing_user" and issue["fk_field"] == "actor_user_id":
            conn.execute("UPDATE v05a_audit_logs SET actor_user_id=NULL WHERE rowid=?", (issue["rowid"],))
            fixed += 1
        else:
            deferred += 1
    return fixed, deferred


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    db_path = resolved_db_path()
    if not db_path.exists():
        print(f"ERROR: database not found: {db_path}")
        return 1
    backup_database(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
        issues = audit(conn)
        print(f"database={db_path}")
        print(f"integrity_check={integrity}")
        print(f"foreign_key_issues={len(issues)}")
        for issue in issues:
            print(issue)
        if args.apply:
            fixed, deferred = apply_fixes(conn, issues)
            conn.commit()
            after = audit(conn)
            print(f"applied_fixes={fixed}")
            print(f"deferred_manual={deferred}")
            print(f"foreign_key_issues_after={len(after)}")
            if after:
                print("remaining_manual_items:")
                for issue in after:
                    print(issue)
        else:
            print("mode=dry-run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
