from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.collection_service import create_job, run_worker  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.5F collection jobs.")
    parser.add_argument("--once", action="store_true", help="Process only one job.")
    parser.add_argument("--job-id", type=int, default=None, help="Process one existing job.")
    parser.add_argument("--source-id", type=int, default=None, help="Create and process a job for one source.")
    parser.add_argument("--due-only", action="store_true", help="Only process due pending jobs.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum jobs to process.")
    parser.add_argument("--create-only", action="store_true", help="Create a job for --source-id but do not process it.")
    args = parser.parse_args()

    if args.create_only and not args.source_id:
        parser.error("--create-only requires --source-id")

    if args.create_only:
        job = create_job(args.source_id, trigger_type="command", operator="worker")
        print(f"created job_id={job['id']} run_no={job['run_no']} status={job['status']}")
        return 0

    result = run_worker(
        once=args.once or bool(args.job_id or args.source_id),
        job_id=args.job_id,
        source_id=args.source_id,
        due_only=args.due_only,
        limit=args.limit,
    )
    print(f"processed={result['processed']}")
    for item in result["results"]:
        print(item)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
