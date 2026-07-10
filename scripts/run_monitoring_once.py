from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.monitoring_service import due_sources, ensure_schema, run_source  # noqa: E402
from app.v04c_review import db_connection  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.4G monitoring sources once.")
    parser.add_argument("--source-id", type=int, default=0)
    parser.add_argument("--due-only", action="store_true")
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()

    ensure_schema()
    if args.source_id:
        ids = [args.source_id]
    else:
        with db_connection() as conn:
            ids = [row["id"] for row in due_sources(conn, due_only=args.due_only, limit=max(1, args.limit))]

    ok = 0
    failed = 0
    for source_id in ids:
        result = run_source(source_id)
        print(f"source_id={source_id} status={result.get('status')} proposals={result.get('created_proposal_count', 0)}")
        if result.get("status") == "failed":
            failed += 1
        else:
            ok += 1
    print(f"completed ok={ok} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
