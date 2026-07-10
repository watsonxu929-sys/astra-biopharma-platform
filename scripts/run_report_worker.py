from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.reports import create_report_job, generate_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.5H report generation worker.")
    parser.add_argument("--daily", action="store_true")
    parser.add_argument("--weekly", action="store_true")
    parser.add_argument("--monthly", action="store_true")
    parser.add_argument("--job-id", type=int, default=None)
    parser.add_argument("--report-type", default="")
    parser.add_argument("--period-start", default="")
    parser.add_argument("--period-end", default="")
    args = parser.parse_args()
    if args.job_id:
        print(generate_report(args.job_id))
        return 0
    report_type = args.report_type or ("weekly" if args.weekly else "monthly" if args.monthly else "daily")
    job = create_report_job(report_type=report_type, period_start=args.period_start, period_end=args.period_end, generated_by="report-worker")
    print(generate_report(job["id"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
