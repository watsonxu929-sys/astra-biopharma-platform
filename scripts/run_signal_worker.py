from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.signals import generate_signals


def main() -> int:
    parser = argparse.ArgumentParser(description="Run v0.5H signal generation rules.")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--since", default="")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--confirm", action="store_true")
    args = parser.parse_args()
    result = generate_signals(since=args.since, limit=args.limit, dry_run=not args.confirm)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
