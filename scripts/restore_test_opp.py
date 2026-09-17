"""Disabled historical one-off utility. No database is opened, including on import."""
import argparse
from pathlib import Path


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True, help="Explicit target; this retired utility refuses all databases")
    parser.parse_args(argv)
    print("REFUSE: Retired: restoring test Opportunities is not supported. Use isolated fixtures; no data changed.")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
