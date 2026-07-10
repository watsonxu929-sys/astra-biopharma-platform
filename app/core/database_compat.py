from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .config import Settings, get_settings


def sqlite_connection(path: str | Path | None = None) -> sqlite3.Connection:
    settings = get_settings()
    db_path = Path(path) if path else settings.sqlite_path
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=5000")
    try:
        conn.execute("PRAGMA journal_mode=WAL")
    except sqlite3.Error:
        pass
    return conn


def database_health(settings: Settings | None = None) -> dict[str, Any]:
    settings = settings or get_settings()
    result: dict[str, Any] = {
        "backend": settings.db_backend,
        "database_url": settings.sanitized_database_url(),
        "ok": False,
        "message": "",
    }
    if settings.db_backend == "sqlite":
        try:
            with sqlite_connection(settings.sqlite_path) as conn:
                conn.execute("SELECT 1").fetchone()
                mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
            result.update({"ok": True, "journal_mode": mode, "path": str(settings.sqlite_path)})
        except sqlite3.Error as exc:
            result.update({"message": f"SQLite 连接失败：{exc}"})
        return result
    try:
        import psycopg  # type: ignore  # noqa: F401

        result.update({"ok": True, "message": "PostgreSQL 驱动可用；未在健康检查中执行高成本查询"})
    except Exception:
        result.update({"ok": False, "message": "PostgreSQL 驱动不可用或未配置连接测试环境"})
    return result
