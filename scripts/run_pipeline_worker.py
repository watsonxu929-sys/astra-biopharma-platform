from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.pipeline import retry_pipeline, run_pipeline_once
from app.services.pipeline.pipeline_common import db_connection
from scripts.migrate_v05i import migrate


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.5I pipeline worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--source-id", type=int)
    parser.add_argument("--pipeline-run-id", type=int)
    parser.add_argument("--due-only", action="store_true")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--resume-failed", action="store_true")
    parser.add_argument("--pilot", action="store_true")
    parser.add_argument("--confirm", action="store_true", help="Disable dry-run for report/signal stage")
    args = parser.parse_args()
    migrate(backup=False)
    processed = 0
    if args.resume_failed:
        with db_connection() as conn:
            rows = conn.execute("SELECT id FROM v05i_pipeline_runs WHERE status IN ('failed','partial') ORDER BY id LIMIT ?", (max(1, args.limit),)).fetchall()
        for row in rows:
            print(retry_pipeline(int(row["id"]), actor="pipeline_worker"))
            processed += 1
            if args.once:
                break
    else:
        while processed < max(1, args.limit):
            result = run_pipeline_once(source_id=args.source_id, pipeline_run_id=args.pipeline_run_id, created_by="pipeline_worker", pilot=args.pilot, dry_run=not args.confirm)
            print(result)
            processed += int(result.get("processed") or 0)
            if args.once or args.source_id or args.pipeline_run_id or not result.get("processed"):
                break
            time.sleep(1 if args.due_only else 0)
    print(f"pipeline_worker processed={processed}")
    return 0


if __name__ == "__main__":
    os.environ.setdefault("APP_AUTH_DISABLED", "1")
    raise SystemExit(main())
