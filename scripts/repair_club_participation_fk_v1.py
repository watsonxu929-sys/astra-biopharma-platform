"""CLOSEOUT-03 CONTINUE: explicit upgrade of the sole remaining chain FK.

Stop writers and take a consistent PRE backup before --apply. Already-correct
registration/check-in tables are never rebuilt. Imports do not open a database.
"""
import argparse
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.repair_club_registration_fk_v1 import PARTICIPATION, repair


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(repair(args.db, apply=args.apply, table=PARTICIPATION), ensure_ascii=False))


if __name__ == '__main__':
    main()
