from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from app.v04c_review import db_connection, default_db_path
from scripts.migrate_v05i import migrate as migrate_v05i


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    if not allow_migration:
        return path
    migrate_v05i(path, backup=False)
    return path


def dumps(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


def loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def next_no(conn: sqlite3.Connection, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v05i_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
            seq_value = CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
            seq_date = excluded.seq_date,
            updated_at = excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, stamp, now()),
    ).fetchone()
    return f"{prefix}-{stamp}-{int(row['seq_value']):05d}"


class StageTimer:
    def __init__(self) -> None:
        self.started = time.perf_counter()

    @property
    def duration_ms(self) -> int:
        return int((time.perf_counter() - self.started) * 1000)


def stage_start(conn: sqlite3.Connection, run_id: int, stage: str, related_table: str = "", related_id: int | None = None) -> None:
    ts = now()
    conn.execute(
        """
        INSERT OR IGNORE INTO v05i_pipeline_stage_runs(
            pipeline_run_id, stage_name, status, related_table, related_id, started_at, created_at, updated_at
        ) VALUES (?, ?, 'pending', ?, ?, ?, ?, ?)
        """,
        (run_id, stage, related_table or None, related_id, ts, ts, ts),
    )
    conn.execute(
        """
        UPDATE v05i_pipeline_stage_runs
        SET status='running', started_at=COALESCE(started_at, ?), updated_at=?
        WHERE pipeline_run_id=? AND stage_name=? AND COALESCE(related_table,'')=COALESCE(?, '') AND COALESCE(related_id,0)=COALESCE(?,0)
        """,
        (ts, ts, run_id, stage, related_table or None, related_id),
    )


def stage_finish(conn: sqlite3.Connection, run_id: int, stage: str, status: str, *, related_table: str = "", related_id: int | None = None, count_value: int = 0, duration_ms: int = 0, error_code: str = "", error_summary: str = "", metadata: dict[str, Any] | None = None) -> None:
    ts = now()
    conn.execute(
        """
        UPDATE v05i_pipeline_stage_runs
        SET status=?, finished_at=?, duration_ms=?, count_value=?, error_code=?, error_summary=?, metadata_json=?, updated_at=?
        WHERE pipeline_run_id=? AND stage_name=? AND COALESCE(related_table,'')=COALESCE(?, '') AND COALESCE(related_id,0)=COALESCE(?,0)
        """,
        (status, ts, int(duration_ms or 0), int(count_value or 0), error_code or None, error_summary[:800] or None, dumps(metadata or {}), ts, run_id, stage, related_table or None, related_id),
    )


__all__ = ["db_connection", "ensure_schema", "now", "dumps", "loads", "next_no", "StageTimer", "stage_start", "stage_finish"]
