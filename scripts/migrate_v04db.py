from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    try:
        from app.v04d_structuring import ensure_v04d_schema  # noqa: F401
    except Exception as exc:
        print(f"[ERROR] v0.4D-A is not available: {exc}")
        print("Install and verify app/v04d_structuring.py before v0.4D-B.")
        return 3

    from app.v04c_review import db_connection, default_db_path
    from app.v04db_prestructure import ensure_v04db_schema

    db_path = default_db_path()
    if db_path.exists():
        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"app_before_v04db_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(db_path, backup)
        print(f"[BACKUP] {backup}")

    path = ensure_v04db_schema(db_path)
    expected = {
        "v04db_sequence_counters",
        "v04db_rules",
        "v04db_extraction_runs",
        "v04db_candidates",
    }
    with db_connection(path) as conn:
        actual = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v04db_%'"
            ).fetchall()
        }
        rule_count = conn.execute("SELECT COUNT(*) AS c FROM v04db_rules").fetchone()["c"]
    missing = expected - actual
    if missing:
        print(f"[ERROR] Missing tables: {', '.join(sorted(missing))}")
        return 2
    print(f"[OK] v0.4D-B migration completed: {path}")
    print(f"[OK] Default offline rules: {rule_count}")
    print("[SAFE] Existing business data was not deleted or rebuilt.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
