from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.v04c_review import db_connection


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Queue historical v05F collection items for v05G processing.")
    parser.add_argument("--limit", type=int, required=True, help="Maximum items to inspect.")
    parser.add_argument("--confirm", action="store_true", help="Actually update item processing_status.")
    parser.add_argument("--include-processed", action="store_true", help="Also include already processed items.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    statuses = ("new", "failed", "needs_review") if not args.include_processed else ("new", "failed", "needs_review", "processed", "ignored")
    with db_connection() as conn:
        rows = conn.execute(
            f"""
            SELECT id, item_no, title, processing_status
            FROM v05f_collection_items
            WHERE processing_status IN ({','.join('?' for _ in statuses)})
            ORDER BY id DESC LIMIT ?
            """,
            (*statuses, max(1, min(int(args.limit), 1000))),
        ).fetchall()
        if args.confirm:
            conn.executemany(
                "UPDATE v05f_collection_items SET processing_status='queued', updated_at=datetime('now','localtime') WHERE id=?",
                [(row["id"],) for row in rows],
            )
    print(f"candidate_items={len(rows)} confirm={bool(args.confirm)}")
    for row in rows[:20]:
        print(f"{row['id']}\t{row['item_no']}\t{row['processing_status']}\t{row['title'] or ''}")
    if not args.confirm:
        print("dry-run only; add --confirm to queue these items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
