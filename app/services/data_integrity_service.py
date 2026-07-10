from __future__ import annotations

import csv
import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.settings import resolved_db_path
from scripts.audit_foreign_keys_v1 import audit

ROOT = Path(__file__).resolve().parents[2]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS data_integrity_issues (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_key TEXT NOT NULL UNIQUE,
    issue_type TEXT NOT NULL,
    table_name TEXT NOT NULL,
    record_id TEXT NOT NULL,
    field_name TEXT NOT NULL,
    invalid_value TEXT,
    target_table TEXT,
    status TEXT NOT NULL DEFAULT 'open',
    severity TEXT NOT NULL DEFAULT 'medium',
    suggested_action TEXT,
    resolution_action TEXT,
    resolution_note TEXT,
    resolved_by TEXT,
    resolved_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK(status IN ('open','auto_resolved','manually_resolved','ignored_with_reason','waiting_for_source','archived'))
);
CREATE INDEX IF NOT EXISTS ix_data_integrity_issues_status ON data_integrity_issues(status, severity, table_name);
CREATE TABLE IF NOT EXISTS data_integrity_issue_audit (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    issue_id INTEGER,
    issue_key TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT,
    note TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(issue_id) REFERENCES data_integrity_issues(id)
);
"""


def db_path() -> Path:
    return resolved_db_path()


def connect(path: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA_SQL)


def backup_database(path: Path | None = None, *, label: str = "v06d_data_integrity") -> Path:
    source = path or db_path()
    data_dir = (ROOT / "data").resolve()
    resolved_source = source.resolve()
    backup_dir = ROOT / "data" / "backups" if data_dir in resolved_source.parents else source.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"app_{label}_{datetime.now():%Y%m%d_%H%M%S}.db"
    shutil.copy2(source, target)
    with sqlite3.connect(target) as conn:
        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity != "ok":
        raise RuntimeError(f"backup integrity check failed: {integrity}")
    return target


def issue_key(issue: dict[str, Any]) -> str:
    return "|".join(str(issue.get(k, "")) for k in ["table", "rowid", "fk_field", "current_fk_value", "parent_table"])


def normalize_issue(issue: dict[str, Any]) -> dict[str, Any]:
    category = issue.get("category") or "foreign_key_orphan"
    severity = "high" if category == "opportunity_child_missing_parent" else "medium"
    return {
        "issue_key": issue_key(issue),
        "issue_type": category,
        "table_name": str(issue.get("table") or ""),
        "record_id": str(issue.get("rowid") or ""),
        "field_name": str(issue.get("fk_field") or ""),
        "invalid_value": None if issue.get("current_fk_value") is None else str(issue.get("current_fk_value")),
        "target_table": str(issue.get("parent_table") or ""),
        "status": "open",
        "severity": severity,
        "suggested_action": issue.get("suggestion") or "manual review before repair",
    }


def current_fk_issues(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [normalize_issue(item) for item in audit(conn)]


def export_issues(issues: list[dict[str, Any]], artifact_dir: Path | None = None) -> tuple[Path, Path]:
    artifact_dir = artifact_dir or (ROOT / "artifacts")
    artifact_dir.mkdir(parents=True, exist_ok=True)
    json_path = artifact_dir / "foreign_key_issues_v06d.json"
    csv_path = artifact_dir / "foreign_key_issues_v06d.csv"
    json_path.write_text(json.dumps(issues, ensure_ascii=False, indent=2), encoding="utf-8")
    fields = ["issue_key", "issue_type", "table_name", "record_id", "field_name", "invalid_value", "target_table", "status", "severity", "suggested_action"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for issue in issues:
            writer.writerow({field: issue.get(field, "") for field in fields})
    return json_path, csv_path


def sync_issues(conn: sqlite3.Connection, issues: list[dict[str, Any]], *, actor: str = "system") -> dict[str, int]:
    ensure_schema(conn)
    now = datetime.now().replace(microsecond=0).isoformat()
    inserted = 0
    refreshed = 0
    active_keys = {issue["issue_key"] for issue in issues}
    for issue in issues:
        existing = conn.execute("SELECT id,status FROM data_integrity_issues WHERE issue_key=?", (issue["issue_key"],)).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE data_integrity_issues
                SET issue_type=?,table_name=?,record_id=?,field_name=?,invalid_value=?,target_table=?,severity=?,suggested_action=?,updated_at=?
                WHERE issue_key=? AND status IN ('open','waiting_for_source')
                """,
                (issue["issue_type"], issue["table_name"], issue["record_id"], issue["field_name"], issue["invalid_value"], issue["target_table"], issue["severity"], issue["suggested_action"], now, issue["issue_key"]),
            )
            refreshed += 1
        else:
            cur = conn.execute(
                """
                INSERT INTO data_integrity_issues(issue_key,issue_type,table_name,record_id,field_name,invalid_value,target_table,status,severity,suggested_action,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (issue["issue_key"], issue["issue_type"], issue["table_name"], issue["record_id"], issue["field_name"], issue["invalid_value"], issue["target_table"], "open", issue["severity"], issue["suggested_action"], now, now),
            )
            conn.execute("INSERT INTO data_integrity_issue_audit(issue_id,issue_key,action,actor,note,created_at) VALUES (?,?,?,?,?,?)", (cur.lastrowid, issue["issue_key"], "registered", actor, "foreign key issue registered", now))
            inserted += 1
    for row in conn.execute("SELECT id,issue_key,status FROM data_integrity_issues WHERE issue_type!='manual_note'").fetchall():
        if row["issue_key"] not in active_keys and row["status"] in {"open", "waiting_for_source"}:
            conn.execute("UPDATE data_integrity_issues SET status='auto_resolved',resolution_action='recheck_clean',resolved_at=?,updated_at=? WHERE id=?", (now, now, row["id"]))
            conn.execute("INSERT INTO data_integrity_issue_audit(issue_id,issue_key,action,actor,note,created_at) VALUES (?,?,?,?,?,?)", (row["id"], row["issue_key"], "auto_resolved", actor, "issue no longer appears in PRAGMA foreign_key_check", now))
    return {"inserted": inserted, "refreshed": refreshed, "active": len(issues)}


def list_registered_issues(conn: sqlite3.Connection, *, status: str = "", table: str = "", severity: str = "") -> list[dict[str, Any]]:
    ensure_schema(conn)
    sql = "SELECT * FROM data_integrity_issues WHERE 1=1"
    params: list[Any] = []
    if status:
        sql += " AND status=?"; params.append(status)
    if table:
        sql += " AND table_name=?"; params.append(table)
    if severity:
        sql += " AND severity=?"; params.append(severity)
    sql += " ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'waiting_for_source' THEN 1 ELSE 2 END, severity DESC, table_name, CAST(record_id AS INTEGER)"
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def issue_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    ensure_schema(conn)
    rows = conn.execute("SELECT status, COUNT(*) AS c FROM data_integrity_issues GROUP BY status").fetchall()
    by_status = {row["status"]: int(row["c"]) for row in rows}
    by_table = {row["table_name"]: int(row["c"]) for row in conn.execute("SELECT table_name, COUNT(*) AS c FROM data_integrity_issues WHERE status IN ('open','waiting_for_source') GROUP BY table_name").fetchall()}
    return {"by_status": by_status, "by_table": by_table, "open_total": sum(by_status.get(s, 0) for s in ["open", "waiting_for_source"])}


def update_issue_status(conn: sqlite3.Connection, issue_id: int, *, status: str, actor: str, note: str = "") -> None:
    ensure_schema(conn)
    if status not in {"open", "manually_resolved", "ignored_with_reason", "waiting_for_source", "archived"}:
        raise ValueError("invalid issue status")
    if status == "ignored_with_reason" and not note.strip():
        raise ValueError("ignore requires reason")
    row = conn.execute("SELECT * FROM data_integrity_issues WHERE id=?", (issue_id,)).fetchone()
    if not row:
        raise ValueError("issue not found")
    now = datetime.now().replace(microsecond=0).isoformat()
    resolved_at = now if status in {"manually_resolved", "ignored_with_reason", "archived"} else None
    conn.execute("UPDATE data_integrity_issues SET status=?,resolution_action=?,resolution_note=?,resolved_by=?,resolved_at=?,updated_at=? WHERE id=?", (status, "manual_status_update", note.strip(), actor, resolved_at, now, issue_id))
    conn.execute("INSERT INTO data_integrity_issue_audit(issue_id,issue_key,action,actor,note,created_at) VALUES (?,?,?,?,?,?)", (issue_id, row["issue_key"], status, actor, note.strip(), now))


def audit_trail(conn: sqlite3.Connection, issue_id: int | None = None) -> list[dict[str, Any]]:
    ensure_schema(conn)
    if issue_id is None:
        rows = conn.execute("SELECT * FROM data_integrity_issue_audit ORDER BY id DESC LIMIT 100").fetchall()
    else:
        rows = conn.execute("SELECT * FROM data_integrity_issue_audit WHERE issue_id=? ORDER BY id DESC", (issue_id,)).fetchall()
    return [dict(row) for row in rows]
