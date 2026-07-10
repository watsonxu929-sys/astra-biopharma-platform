from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.api_common import Pagination, normalize_page, paginated
from app.v04c_review import db_connection
from scripts.migrate_v05e import SCHEMA_SQL as V05E_SCHEMA_SQL

STATUS_VALUES = {"new", "reviewed", "important", "ignored", "converted", "expired"}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_schema(db_path: str | Path | None = None) -> None:
    with db_connection(db_path) as conn:
        conn.executescript(V05E_SCHEMA_SQL)


def _next_no(conn: sqlite3.Connection, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v05e_sequence_counters(seq_key,seq_date,seq_value,updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date, updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, stamp, now_iso()),
    ).fetchone()
    return f"{prefix}-{stamp}-{int(row['seq_value']):04d}"


def classify_signal(title: str, body: str = "") -> dict[str, Any] | None:
    text = f"{title} {body}".lower()
    rules = [
        ("\u878d\u8d44", "financing", "high", ["\u878d\u8d44", "\u94bb\u5d76\u794f", "\u52df\u8d44", "\u6295\u8d44", "a\u8f6e", "a\u677c", "b\u8f6e", "b\u677c", "pre-a", "series", "funding", "ipo"], "\u878d\u8d44\u6216\u52df\u8d44\u5173\u952e\u8bcd"),
        ("\u6218\u7565\u5408\u4f5c", "strategic_cooperation", "high", ["\u5408\u4f5c", "\u934f\u582a\u7dbd", "\u6218\u7565\u5408\u4f5c", "\u7b7e\u7ea6", "\u5171\u5efa", "\u6388\u6743", "license", "collaboration"], "\u5408\u4f5c\u6216\u7b7e\u7ea6\u5173\u952e\u8bcd"),
        ("\u4e34\u5e8a\u8fdb\u5c55", "clinical_progress", "high", ["\u4e34\u5e8a", "\u6d93\u6751\u7c25", "\u7533\u62a5", "\u83b7\u6279", "\u6ce8\u518c", "\u4e0a\u5e02", "\u8bd5\u9a8c", "\u5165\u7ec4", "ind", "nda"], "\u4e34\u5e8a\u6216\u6ce8\u518c\u8fdb\u5c55\u5173\u952e\u8bcd"),
        ("\u4ea7\u80fd\u5efa\u8bbe", "capacity_expansion", "medium", ["\u4ea7\u80fd", "\u5382\u623f", "\u5b9e\u9a8c\u5ba4", "\u57fa\u5730", "\u6295\u4ea7", "\u6269\u4ea7"], "\u4ea7\u80fd\u3001\u5382\u623f\u6216\u57fa\u5730\u5173\u952e\u8bcd"),
        ("\u9ad8\u7ba1\u53d8\u52a8", "executive_change", "medium", ["\u4efb\u547d", "\u79bb\u4efb", "\u52a0\u5165", "ceo", "cfo", "\u9996\u5e2d"], "\u7ba1\u7406\u5c42\u53d8\u52a8\u5173\u952e\u8bcd"),
        ("\u98ce\u9669", "risk", "critical", ["\u98ce\u9669", "\u51b2\u7a81", "\u903e\u671f", "\u5931\u8d25", "\u7ec8\u6b62", "\u6682\u505c", "\u5931\u6548", "\u5904\u7f5a", "\u8bc9\u8bbc", "\u53ec\u56de"], "\u98ce\u9669\u5173\u952e\u8bcd"),
    ]
    for label, signal_type, level, words, reason in rules:
        if any(word in text for word in words):
            confidence = {"critical": 88, "high": 78, "medium": 65, "low": 50}[level]
            return {"signal_type": signal_type, "signal_label": label, "signal_level": level, "confidence": confidence, "level_reason": reason}
    return None


def generate_from_confirmed_events(*, limit: int = 50, db_path: str | Path | None = None) -> dict[str, int]:
    ensure_schema(db_path)
    created = skipped = 0
    with db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id,external_id,event_date,name,event_type,related_entity,fact_summary,verification_status,source_title,source_url,created_at
            FROM events
            WHERE COALESCE(is_active,1)=1
              AND (verification_status LIKE '%确认%' OR manually_confirmed=1)
            ORDER BY id DESC LIMIT ?
            """,
            (max(1, min(limit, 200)),),
        ).fetchall()
        for row in rows:
            info = classify_signal(row["name"] or "", row["fact_summary"] or "")
            if not info:
                skipped += 1
                continue
            exists = conn.execute(
                """
                SELECT id FROM v05e_industry_signals
                WHERE source_type='event' AND source_id=? AND signal_type=?
                  AND COALESCE(subject_type,'')=COALESCE(?, '') AND COALESCE(subject_id,'')=COALESCE(?, '')
                """,
                (str(row["id"]), info["signal_type"], "organization" if row["related_entity"] else None, row["related_entity"]),
            ).fetchone()
            if exists:
                skipped += 1
                continue
            title = f"{info['signal_label']}：{row['name']}"
            ts = now_iso()
            conn.execute(
                """
                INSERT INTO v05e_industry_signals(
                  signal_no,signal_type,signal_level,title,summary,subject_type,subject_id,occurred_at,discovered_at,
                  source_type,source_id,evidence_excerpt,confidence,level_reason,status,is_read,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,'new',0,?,?)
                """,
                (
                    _next_no(conn, "SIG"),
                    info["signal_type"],
                    info["signal_level"],
                    title[:300],
                    (row["fact_summary"] or row["event_type"] or "")[:1000],
                    "organization" if row["related_entity"] else None,
                    row["related_entity"],
                    row["event_date"] or row["created_at"],
                    ts,
                    "event",
                    str(row["id"]),
                    (row["fact_summary"] or row["name"] or "")[:1000],
                    info["confidence"],
                    info["level_reason"],
                    ts,
                    ts,
                ),
            )
            created += 1
    return {"created": created, "skipped": skipped}


def list_signals(
    *,
    page: int = 1,
    page_size: int = 20,
    signal_type: str = "",
    signal_level: str = "",
    status: str = "",
    subject_type: str = "",
    subject_id: str = "",
    q: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_schema(db_path)
    page, page_size = normalize_page(page, page_size)
    clauses = ["1=1"]
    params: list[Any] = []
    for field, value in [("signal_type", signal_type), ("signal_level", signal_level), ("status", status), ("subject_type", subject_type), ("subject_id", subject_id)]:
        if value:
            clauses.append(f"{field}=?")
            params.append(value)
    if q.strip():
        clauses.append("(title LIKE ? OR COALESCE(summary,'') LIKE ? OR COALESCE(evidence_excerpt,'') LIKE ?)")
        like = f"%{q.strip()}%"
        params.extend([like, like, like])
    where = " AND ".join(clauses)
    with db_connection(db_path) as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM v05e_industry_signals WHERE {where}", params).fetchone()[0])
        rows = [dict(r) for r in conn.execute(
            f"SELECT * FROM v05e_industry_signals WHERE {where} ORDER BY discovered_at DESC,id DESC LIMIT ? OFFSET ?",
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()]
    for row in rows:
        row["api_url"] = f"/api/v1/signals/{row['id']}"
        row["web_url"] = f"/signals/{row['id']}"
    return paginated(rows, Pagination(page, page_size, total), {"filters": {"signal_type": signal_type, "signal_level": signal_level, "status": status}})


def get_signal(signal_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05e_industry_signals WHERE id=?", (signal_id,)).fetchone()
        return dict(row) if row else None


def update_signal_status(signal_id: int, status: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    if status not in STATUS_VALUES:
        raise ValueError("invalid_status")
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05e_industry_signals WHERE id=?", (signal_id,)).fetchone()
        if not row:
            return None
        conn.execute("UPDATE v05e_industry_signals SET status=?,is_read=1,updated_at=? WHERE id=?", (status, now_iso(), signal_id))
        return dict(conn.execute("SELECT * FROM v05e_industry_signals WHERE id=?", (signal_id,)).fetchone())


def convert_signal_to_action(signal_id: int, *, owner: str = "manual", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        signal = conn.execute("SELECT * FROM v05e_industry_signals WHERE id=?", (signal_id,)).fetchone()
        if not signal:
            return {"created": False, "reason": "not_found"}
        if signal["converted_action_id"]:
            return {"created": False, "idempotent": True, "action_id": signal["converted_action_id"]}
        ts = now_iso()
        action_no = _next_no(conn, "ACTSIG")
        cur = conn.execute(
            """
            INSERT INTO actions(external_id,task,target_external_id,completion_standard,owner,priority,status,source_type,source_title,source_text,manually_confirmed,created_at)
            VALUES (?,?,?,?,?,'P1','\u672a\u5f00\u59cb','industry_signal',?,?,1,?)
            """,
            (
                action_no,
                f"\u8ddf\u8fdb\u4ea7\u4e1a\u4fe1\u53f7\uff1a{signal['title']}",
                signal["subject_id"],
                signal["summary"] or "\u4eba\u5de5\u786e\u8ba4\u4fe1\u53f7\u5e76\u5b8c\u6210\u540e\u7eed\u8ddf\u8fdb\u3002",
                owner,
                signal["title"],
                json.dumps({"signal_id": signal_id}, ensure_ascii=False),
                ts,
            ),
        )
        action_id = int(cur.lastrowid)
        conn.execute("UPDATE v05e_industry_signals SET status='converted',converted_action_id=?,is_read=1,updated_at=? WHERE id=?", (action_id, ts, signal_id))
    return {"created": True, "action_id": action_id}
