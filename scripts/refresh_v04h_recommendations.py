from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.recommendation_service import refresh_recommendations


def main() -> int:
    parser = argparse.ArgumentParser(description="Refresh v0.4H recommendations")
    parser.add_argument("--lead-limit", type=int, default=200)
    parser.add_argument("--pair-limit", type=int, default=2500)
    args = parser.parse_args()
    result = refresh_recommendations(
        lead_limit=max(1, min(500, args.lead_limit)),
        pair_limit=max(100, min(10000, args.pair_limit)),
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
