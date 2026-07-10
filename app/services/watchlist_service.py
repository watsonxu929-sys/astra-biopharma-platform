from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.api_common import Pagination, normalize_page, paginated
from app.services.api_subject_service import subject_exists
from app.services.signal_service import _next_no, ensure_schema
from app.v04c_review import db_connection

WATCHLIST_CATEGORIES = {"key_organization", "key_person", "key_project", "key_track", "investment_target", "investment_observation", "cooperation_opportunity", "risk_observation", "custom"}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _visible_clause(user: dict[str, Any], alias: str = "") -> tuple[str, list[Any]]:
    prefix = f"{alias}." if alias else ""
    if user.get("role") == "admin":
        return f"{prefix}status='active'", []
    return f"{prefix}status='active' AND ({prefix}visibility='team' OR {prefix}owner_user_id=?)", [int(user.get("id") or 0)]


def list_watchlists(user: dict[str, Any], *, page: int = 1, page_size: int = 20, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    page, page_size = normalize_page(page, page_size)
    where, params = _visible_clause(user)
    with db_connection(db_path) as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM v05e_watchlists WHERE {where}", params).fetchone()[0])
        rows = [dict(r) for r in conn.execute(
            f"SELECT * FROM v05e_watchlists WHERE {where} ORDER BY updated_at DESC,id DESC LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()]
    return paginated(rows, Pagination(page, page_size, total))


def create_watchlist(user: dict[str, Any], *, name: str, category: str, description: str = "", visibility: str = "private", db_path: str | Path | None = None) -> dict[str, Any]:
    if category not in WATCHLIST_CATEGORIES:
        raise ValueError("invalid_category")
    if visibility not in {"private", "team"}:
        raise ValueError("invalid_visibility")
    ensure_schema(db_path)
    ts = now_iso()
    with db_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO v05e_watchlists(watchlist_no,name,category,description,owner_user_id,owner_username,visibility,status,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,'active',?,?)
            """,
            (_next_no(conn, "WL"), name.strip()[:200], category, description.strip()[:1000] or None, int(user.get("id") or 0), user.get("username"), visibility, ts, ts),
        )
        return dict(conn.execute("SELECT * FROM v05e_watchlists WHERE id=?", (cur.lastrowid,)).fetchone())


def add_item(user: dict[str, Any], *, watchlist_id: int, subject_type: str, subject_id: str, priority: str = "medium", reason: str = "", note: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    if priority not in {"critical", "high", "medium", "low"}:
        raise ValueError("invalid_priority")
    ensure_schema(db_path)
    ts = now_iso()
    with db_connection(db_path) as conn:
        where, params = _visible_clause(user)
        wl = conn.execute(f"SELECT * FROM v05e_watchlists WHERE id=? AND {where}", [watchlist_id, *params]).fetchone()
        if not wl:
            return {"created": False, "reason": "watchlist_not_found"}
        if not subject_exists(conn, subject_type, subject_id):
            return {"created": False, "reason": "subject_not_found"}
        existing = conn.execute("SELECT * FROM v05e_watchlist_items WHERE watchlist_id=? AND subject_type=? AND subject_id=? AND status='active'", (watchlist_id, subject_type, subject_id)).fetchone()
        if existing:
            return {"created": False, "idempotent": True, "item": dict(existing)}
        cur = conn.execute(
            """
            INSERT INTO v05e_watchlist_items(watchlist_id,subject_type,subject_id,priority,reason,owner_user_id,owner_username,added_at,status,note)
            VALUES (?,?,?,?,?,?,?,?,'active',?)
            """,
            (watchlist_id, subject_type, subject_id, priority, reason.strip()[:1000] or None, int(user.get("id") or 0), user.get("username"), ts, note.strip()[:1000] or None),
        )
        conn.execute("UPDATE v05e_watchlists SET updated_at=? WHERE id=?", (ts, watchlist_id))
        return {"created": True, "item": dict(conn.execute("SELECT * FROM v05e_watchlist_items WHERE id=?", (cur.lastrowid,)).fetchone())}


def list_items(user: dict[str, Any], watchlist_id: int, *, page: int = 1, page_size: int = 20, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    page, page_size = normalize_page(page, page_size)
    with db_connection(db_path) as conn:
        where, params = _visible_clause(user)
        wl = conn.execute(f"SELECT * FROM v05e_watchlists WHERE id=? AND {where}", [watchlist_id, *params]).fetchone()
        if not wl:
            return paginated([], Pagination(page, page_size, 0), {"watchlist_found": False})
        total = int(conn.execute("SELECT COUNT(*) FROM v05e_watchlist_items WHERE watchlist_id=? AND status='active'", (watchlist_id,)).fetchone()[0])
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM v05e_watchlist_items WHERE watchlist_id=? AND status='active' ORDER BY added_at DESC,id DESC LIMIT ? OFFSET ?",
            (watchlist_id, page_size, (page - 1) * page_size),
        ).fetchall()]
    return paginated(rows, Pagination(page, page_size, total), {"watchlist": dict(wl)})


def remove_item(user: dict[str, Any], item_id: int, db_path: str | Path | None = None) -> bool:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        where, params = _visible_clause(user, "w")
        row = conn.execute(
            f"SELECT i.* FROM v05e_watchlist_items i JOIN v05e_watchlists w ON w.id=i.watchlist_id WHERE i.id=? AND {where}",
            [item_id, *params],
        ).fetchone()
        if not row:
            return False
        conn.execute("UPDATE v05e_watchlist_items SET status='removed',removed_at=? WHERE id=?", (now_iso(), item_id))
        return True
