from __future__ import annotations

import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import resolved_db_path
DB_PATH = resolved_db_path()
BACKUP_DIR = DB_PATH.parent / "backups" if (ROOT / "data").resolve() not in DB_PATH.resolve().parents else ROOT / "data" / "backups"

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS v04h_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v04h_recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_no TEXT NOT NULL UNIQUE,
    recommendation_key TEXT NOT NULL UNIQUE,
    category TEXT NOT NULL,
    subject_type TEXT,
    subject_id TEXT,
    secondary_subject_type TEXT,
    secondary_subject_id TEXT,
    title TEXT NOT NULL,
    summary TEXT,
    score INTEGER NOT NULL DEFAULT 0,
    grade TEXT NOT NULL DEFAULT 'C',
    reasons_json TEXT,
    risks_json TEXT,
    missing_json TEXT,
    path_json TEXT,
    metadata_json TEXT,
    source_type TEXT,
    source_id TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    owner TEXT,
    decision_reason TEXT,
    snoozed_until TEXT,
    action_id INTEGER,
    generated_at TEXT NOT NULL,
    decided_at TEXT,
    updated_at TEXT NOT NULL,
    CHECK(category IN ('lead','club_match','resource','data_quality','relationship')),
    CHECK(status IN ('new','accepted','rejected','snoozed','converted','expired')),
    CHECK(score BETWEEN 0 AND 100),
    CHECK(grade IN ('S','A','B','C'))
);

CREATE INDEX IF NOT EXISTS ix_v04h_recommendation_status_score
ON v04h_recommendations(status, score DESC, updated_at DESC);

CREATE INDEX IF NOT EXISTS ix_v04h_recommendation_category
ON v04h_recommendations(category, score DESC, updated_at DESC);

CREATE INDEX IF NOT EXISTS ix_v04h_recommendation_subject
ON v04h_recommendations(subject_type, subject_id, status);

CREATE TABLE IF NOT EXISTS v04h_feedback_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recommendation_id INTEGER NOT NULL,
    old_status TEXT,
    new_status TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'manual',
    reason TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(recommendation_id) REFERENCES v04h_recommendations(id)
);

CREATE INDEX IF NOT EXISTS ix_v04h_feedback_recommendation
ON v04h_feedback_events(recommendation_id, created_at DESC);
"""


def migrate(db_path: Path = DB_PATH, backup: bool = True) -> dict[str, str]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = ""
    if backup and db_path.exists():
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = BACKUP_DIR / f"app_before_v04h_{stamp}.db"
        shutil.copy2(db_path, target)
        backup_path = str(target)
    conn = sqlite3.connect(db_path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.commit()
    finally:
        conn.close()
    return {"database": str(db_path), "backup": backup_path}


def main() -> int:
    result = migrate()
    print("v0.4H migration completed")
    print(f"database={result['database']}")
    print(f"backup={result['backup'] or 'not created'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

