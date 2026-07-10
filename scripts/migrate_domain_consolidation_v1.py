from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import resolved_db_path

DOMAINS = {
    "intelligence": ["raw_intelligence", "v05e_industry_signals", "v06_intelligence_items"],
    "resources": ["resources", "v04f_club_needs", "v04f_club_offerings", "v06_market_resources"],
    "opportunities": ["v04f_lead_records", "actions", "v04h_recommendations", "v06_contact_intents", "v06_opportunities", "v06_follow_ups", "v06_collab_tasks", "v06_timeline_entries"],
}


def table_count(conn: sqlite3.Connection, table: str) -> int | None:
    exists = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone()
    if not exists:
        return None
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def ensure_mapping_table(conn: sqlite3.Connection) -> None:
    conn.execute("""
        CREATE TABLE IF NOT EXISTS platform_entity_mappings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            domain TEXT NOT NULL,
            source_system TEXT NOT NULL,
            source_entity_type TEXT NOT NULL,
            source_entity_id TEXT NOT NULL,
            canonical_entity_type TEXT NOT NULL,
            canonical_entity_id TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),
            metadata_json TEXT,
            UNIQUE(domain, source_system, source_entity_type, source_entity_id)
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS ix_platform_entity_mappings_canonical ON platform_entity_mappings(domain, canonical_entity_type, canonical_entity_id)")


def backup_database(db_path: Path) -> Path | None:
    if not db_path.exists():
        return None
    backup_dir = ROOT / "data" / "backups" if (ROOT / "data").resolve() in db_path.resolve().parents else db_path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"app_before_domain_consolidation_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(db_path, backup_path)
    with sqlite3.connect(backup_path) as backup:
        integrity = backup.execute("PRAGMA integrity_check").fetchone()[0]
        fk_count = len(backup.execute("PRAGMA foreign_key_check").fetchall())
    print(f"backup={backup_path}")
    print(f"backup_integrity_check={integrity}")
    print(f"backup_foreign_key_check_count={fk_count}")
    return backup_path


def planned_mappings(conn: sqlite3.Connection) -> list[tuple[str, str, str, str, str, str, str]]:
    planned = []
    if table_count(conn, "v06_intelligence_items") is None:
        return planned
    for row in conn.execute("SELECT id, source_name, source_url FROM v06_intelligence_items WHERE source_name='raw_intelligence' AND source_url IS NOT NULL").fetchall():
        raw = conn.execute("SELECT id FROM raw_intelligence WHERE source_url=? LIMIT 1", (row["source_url"],)).fetchone() if table_count(conn, "raw_intelligence") is not None else None
        if raw:
            planned.append(("intelligence", "legacy", "raw_intelligence", str(raw["id"]), "v06_intelligence_items", str(row["id"]), "{}"))
    return planned


def migrate(conn: sqlite3.Connection, apply: bool) -> dict:
    planned = planned_mappings(conn)
    inserted = 0
    if apply:
        ensure_mapping_table(conn)
        for item in planned:
            cur = conn.execute("""
                INSERT OR IGNORE INTO platform_entity_mappings(domain,source_system,source_entity_type,source_entity_id,canonical_entity_type,canonical_entity_id,metadata_json)
                VALUES (?,?,?,?,?,?,?)
            """, item)
            inserted += cur.rowcount if cur.rowcount > 0 else 0
        conn.commit()
    return {"planned_exact_mappings": len(planned), "inserted": inserted if apply else 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    db_path = resolved_db_path()
    if args.apply:
        backup_database(db_path)
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        print(f"database={db_path}")
        for domain, tables in DOMAINS.items():
            print(f"[{domain}]")
            for table in tables:
                count = table_count(conn, table)
                print(f"  {table}: {'missing' if count is None else count}")
        result = migrate(conn, apply=args.apply)
        print(f"mode={'apply' if args.apply else 'dry-run'}")
        print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
