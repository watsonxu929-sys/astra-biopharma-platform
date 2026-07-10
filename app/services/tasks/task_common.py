from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from app.v04c_review import db_connection as base_connection, default_db_path
from scripts.migrate_v05kl import migrate


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def dumps(value: Any) -> str:
    return json.dumps(value or {}, ensure_ascii=False, default=str)


def loads(value: str | None, default: Any = None) -> Any:
    try:
        return json.loads(value or "")
    except Exception:
        return {} if default is None else default


def ensure_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    if not allow_migration:
        return path
    migrate(path, backup=False)
    return path


@contextmanager
def db_connection(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    path = ensure_schema(db_path)
    with base_connection(path) as conn:
        yield conn


def next_uid(conn: sqlite3.Connection, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v05kl_sequence_counters(seq_key,seq_date,seq_value,updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date,
          updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, stamp, now()),
    ).fetchone()
    return f"{prefix}-{stamp}-{int(row['seq_value']):05d}"
