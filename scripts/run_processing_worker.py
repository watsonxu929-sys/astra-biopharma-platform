from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.processing import create_processing_job, process_job, run_worker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run v0.5G semantic processing worker.")
    parser.add_argument("--once", action="store_true", help="Process one job then exit.")
    parser.add_argument("--job-id", type=int, default=None, help="Run an existing processing job.")
    parser.add_argument("--item-id", type=int, default=None, help="Create and run a job for one collection item.")
    parser.add_argument("--queued-only", action="store_true", help="Only process queued/needs_review/failed items.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum items per scan.")
    parser.add_argument("--reprocess", action="store_true", help="Allow reprocessing existing items.")
    parser.add_argument("--sleep", type=int, default=30, help="Seconds between scans when not --once.")
    parser.add_argument("--operator", default="processing-worker", help="Audit/display operator name.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.job_id:
        result = process_job(args.job_id)
        print(result)
        return 0 if result.get("status") != "failed" else 1
    if args.item_id:
        job = create_processing_job(
            item_id=args.item_id,
            trigger_type="command",
            operator=args.operator,
            queued_only=args.queued_only,
            reprocess=args.reprocess,
        )
        result = process_job(job["id"])
        print(result)
        return 0 if result.get("status") != "failed" else 1
    while True:
        result = run_worker(
            once=args.once,
            queued_only=args.queued_only or True,
            limit=args.limit,
            reprocess=args.reprocess,
            operator=args.operator,
        )
        print(result)
        if args.once:
            return 0
        time.sleep(max(5, int(args.sleep or 30)))


if __name__ == "__main__":
    raise SystemExit(main())
