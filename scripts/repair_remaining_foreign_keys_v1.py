from __future__ import annotations

import argparse
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.data_integrity_service import (
    audit_trail,
    backup_database,
    connect,
    current_fk_issues,
    export_issues,
    issue_summary,
    list_registered_issues,
    sync_issues,
    update_issue_status,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Register and safely repair remaining foreign key issues.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--issue-id", type=int)
    parser.add_argument("--status", choices=["waiting_for_source", "ignored_with_reason", "manually_resolved", "archived"])
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    apply = bool(args.apply)
    with connect() as conn:
        before = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        issues = current_fk_issues(conn)
        json_path, csv_path = export_issues(issues)
        print(f"foreign_key_issues_before={before}")
        print(f"audit_json={json_path}")
        print(f"audit_csv={csv_path}")
        deterministic = [issue for issue in issues if issue["issue_type"] == "audit_missing_user"]
        manual = [issue for issue in issues if issue not in deterministic]
        print(f"deterministic_fix_candidates={len(deterministic)}")
        print(f"manual_review_candidates={len(manual)}")
        if not apply:
            print("mode=dry-run")
            return 0
        backup = backup_database(label="v06d_fk_repair")
        print(f"backup_path={backup}")
        if args.issue_id:
            if args.status:
                update_issue_status(conn, args.issue_id, status=args.status, actor="repair_script", note=args.note)
                conn.commit()
                print(f"issue_id={args.issue_id}")
                print(f"status={args.status}")
            else:
                rows = list_registered_issues(conn)
                selected = [row for row in rows if int(row["id"]) == args.issue_id]
                print(f"issue_id={args.issue_id}")
                print(f"selected_count={len(selected)}")
                print("no automatic repair rule for selected issue; use --status with explicit manual action")
        else:
            result = sync_issues(conn, issues, actor="repair_script")
            conn.commit()
            print(f"registered_inserted={result['inserted']}")
            print(f"registered_refreshed={result['refreshed']}")
        after = len(conn.execute("PRAGMA foreign_key_check").fetchall())
        summary = issue_summary(conn)
        print(f"foreign_key_issues_after={after}")
        print(f"open_or_waiting={summary['open_total']}")
        print(f"audit_entries={len(audit_trail(conn))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
