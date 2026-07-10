from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.id_generator import PREFIX_BY_ENTITY, is_valid_system_id  # noqa: E402

DB_PATH = ROOT / "data" / "app.db"

TABLES = {
    "organizations": "ORG",
    "people": "PER",
    "projects": "PRJ",
    "resources": "RES",
    "events": "EVT",
    "relations": "REL",
    "actions": "ACT",
}

COMMON_COLUMNS = {
    "source_url": "TEXT",
    "source_type": "VARCHAR(50)",
    "source_title": "VARCHAR(300)",
    "source_text": "TEXT",
    "captured_at": "DATETIME",
    "analyzed_at": "DATETIME",
    "model_version": "VARCHAR(80)",
    "manually_confirmed": "BOOLEAN DEFAULT 0",
    "auto_generated_fields": "TEXT",
    "confirmed_fields": "TEXT",
    "is_active": "BOOLEAN DEFAULT 1",
    "deactivated_at": "DATETIME",
    "deactivated_reason": "TEXT",
    "subject_match_method": "VARCHAR(50)",
    "subject_matched_at": "DATETIME",
    "subject_manually_confirmed": "BOOLEAN DEFAULT 0",
}

EXTRA_COLUMNS = {
    "projects": {"owner_organization_id": "INTEGER"},
    "resources": {"owner_organization_id": "INTEGER"},
    "events": {"related_organization_id": "INTEGER"},
    "actions": {"target_organization_id": "INTEGER"},
}


def columns(conn: sqlite3.Connection, table: str) -> set[str]:
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}


def ensure_columns(conn: sqlite3.Connection, table: str) -> None:
    existing = columns(conn, table)
    additions = dict(COMMON_COLUMNS)
    additions.update(EXTRA_COLUMNS.get(table, {}))
    for name, ddl in additions.items():
        if name not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")


def next_id(conn: sqlite3.Connection, table: str, prefix: str, day: str, used: set[str]) -> str:
    stem = f"{prefix}-{day}-"
    max_seq = 0
    for (value,) in conn.execute(
        f"SELECT external_id FROM {table} WHERE external_id LIKE ?",
        (f"{stem}%",),
    ):
        if value and str(value).startswith(stem):
            tail = str(value)[len(stem):]
            if tail.isdigit():
                max_seq = max(max_seq, int(tail))
    while True:
        max_seq += 1
        candidate = f"{stem}{max_seq:06d}"
        if candidate not in used:
            used.add(candidate)
            return candidate


def backfill_ids(conn: sqlite3.Connection, table: str, prefix: str) -> int:
    rows = conn.execute(f"SELECT id, external_id, created_at FROM {table} ORDER BY id").fetchall()
    used = {row[1] for row in rows if row[1]}
    changed = 0
    for row_id, external_id, created_at in rows:
        if is_valid_system_id(external_id):
            continue
        day = "20260626"
        if created_at and len(str(created_at)) >= 10:
            day = str(created_at)[:10].replace("-", "")
        new_id = next_id(conn, table, prefix, day, used)
        conn.execute(f"UPDATE {table} SET external_id=? WHERE id=?", (new_id, row_id))
        changed += 1
    return changed


def backfill_project_owner_ids(conn: sqlite3.Connection) -> int:
    if "owner_organization_id" not in columns(conn, "projects"):
        return 0
    changed = 0
    rows = conn.execute(
        "SELECT id, owner_external_id FROM projects WHERE owner_external_id IS NOT NULL "
        "AND owner_external_id != '' AND owner_organization_id IS NULL"
    ).fetchall()
    for project_id, owner_value in rows:
        org = conn.execute(
            "SELECT id, external_id FROM organizations WHERE external_id=? OR standard_name=? ORDER BY id LIMIT 1",
            (owner_value, owner_value),
        ).fetchone()
        if not org:
            continue
        conn.execute(
            "UPDATE projects SET owner_organization_id=?, owner_external_id=?, "
            "subject_match_method='exact', subject_matched_at=datetime('now'), "
            "subject_manually_confirmed=1 WHERE id=?",
            (org[0], org[1], project_id),
        )
        changed += 1
    return changed


def apply_v04b(db_path: Path = DB_PATH) -> dict[str, int]:
    db_path.parent.mkdir(exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        summary: dict[str, int] = {}
        for table, prefix in TABLES.items():
            ensure_columns(conn, table)
            summary[table] = backfill_ids(conn, table, prefix)
            conn.execute(
                f"CREATE UNIQUE INDEX IF NOT EXISTS ux_{table}_external_id ON {table}(external_id)"
            )
        summary["project_owner_links"] = backfill_project_owner_ids(conn)
        conn.commit()
        return summary
    finally:
        conn.close()


if __name__ == "__main__":
    result = apply_v04b()
    for table, count in result.items():
        print(f"{table} 补编号/补关联 {count} 条")
