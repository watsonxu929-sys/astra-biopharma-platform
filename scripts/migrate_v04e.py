from __future__ import annotations

import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.v04c_review import db_connection, default_db_path  # noqa: E402
from app.v04e_entity_resolution import ensure_v04e_schema  # noqa: E402


def main() -> int:
    db_path = default_db_path()
    if db_path.exists():
        backup_dir = db_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir / f"app_before_v04eA_{datetime.now():%Y%m%d_%H%M%S}.db"
        shutil.copy2(db_path, backup)
        print(f"[BACKUP] {backup}")
    path = ensure_v04e_schema(db_path)
    expected = {
        "v04e_sequence_counters",
        "v04e_entity_aliases",
        "v04e_duplicate_candidates",
        "v04e_resolution_actions",
    }
    with db_connection(path) as conn:
        actual = {row["name"] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v04e_%'"
        ).fetchall()}
    missing = expected - actual
    if missing:
        print(f"[ERROR] Missing tables: {', '.join(sorted(missing))}")
        return 2
    print(f"[OK] v0.4E-A migration completed: {path}")
    print("[SAFE] No entity was merged, deleted, deactivated, or rewritten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
