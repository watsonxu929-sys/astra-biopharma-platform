from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Literal
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.v04c_review import db_connection, default_db_path
from app.v04c1_ingestion import (
    ensure_v04c1_schema,
    ingest_payload,
    process_field_candidate,
    process_relation_candidate,
)

router = APIRouter(prefix="/review/structure", tags=["v0.4D 原始情报结构化"])

MODULE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = MODULE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

TaskStatus = Literal["draft", "ready", "returned", "submitted", "partial", "cancelled"]
ItemType = Literal["field", "relation", "event"]
FactLevel = Literal["fact", "inference", "unknown"]

TASK_STATUS_LABELS = {
    "draft": "草稿",
    "ready": "待结构化复核",
    "returned": "退回修改",
    "submitted": "已送数据审核",
    "partial": "部分送审",
    "cancelled": "已取消",
}
ITEM_TYPE_LABELS = {"field": "字段候选", "relation": "关系候选", "event": "事件候选"}
ITEM_STATUS_LABELS = {"draft": "草稿", "submitted": "已送审", "failed": "送审失败"}
FACT_LEVEL_LABELS = {"fact": "事实陈述", "inference": "推测", "unknown": "待判定"}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS v04d_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v04d_structuring_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_no TEXT NOT NULL UNIQUE,
    source_record_id INTEGER NOT NULL UNIQUE,
    raw_intelligence_id INTEGER,
    status TEXT NOT NULL DEFAULT 'draft',
    assigned_to TEXT,
    reviewer TEXT,
    review_note TEXT,
    created_by TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    ready_at TEXT,
    submitted_at TEXT,
    completed_at TEXT,
    FOREIGN KEY(source_record_id) REFERENCES v04c1_source_records(id) ON DELETE RESTRICT,
    CHECK (status IN ('draft','ready','returned','submitted','partial','cancelled'))
);

CREATE INDEX IF NOT EXISTS ix_v04d_tasks_status
ON v04d_structuring_tasks(status, updated_at DESC);

CREATE INDEX IF NOT EXISTS ix_v04d_tasks_raw
ON v04d_structuring_tasks(raw_intelligence_id);

CREATE TABLE IF NOT EXISTS v04d_structure_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    item_no TEXT NOT NULL UNIQUE,
    task_id INTEGER NOT NULL,
    item_type TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,

    subject_type TEXT,
    subject_id TEXT,
    subject_label TEXT,
    field_name TEXT,
    candidate_value TEXT,

    left_type TEXT,
    left_id TEXT,
    left_label TEXT,
    relation_type TEXT,
    right_type TEXT,
    right_id TEXT,
    right_label TEXT,

    event_name TEXT,
    event_date TEXT,
    event_type TEXT,
    related_entity TEXT,
    event_summary TEXT,

    fact_level TEXT NOT NULL DEFAULT 'unknown',
    confidence REAL,
    evidence_excerpt TEXT,
    source_url TEXT,
    status TEXT NOT NULL DEFAULT 'draft',
    review_item_id INTEGER,
    pending_relation_id INTEGER,
    candidate_id INTEGER,
    submission_json TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,

    FOREIGN KEY(task_id) REFERENCES v04d_structuring_tasks(id) ON DELETE CASCADE,
    FOREIGN KEY(review_item_id) REFERENCES v04c_review_items(id) ON DELETE SET NULL,
    FOREIGN KEY(pending_relation_id) REFERENCES v04c_pending_relations(id) ON DELETE SET NULL,
    FOREIGN KEY(candidate_id) REFERENCES v04c1_candidates(id) ON DELETE SET NULL,
    CHECK (item_type IN ('field','relation','event')),
    CHECK (fact_level IN ('fact','inference','unknown')),
    CHECK (status IN ('draft','submitted','failed'))
);

CREATE INDEX IF NOT EXISTS ix_v04d_items_task
ON v04d_structure_items(task_id, sort_order, id);

CREATE INDEX IF NOT EXISTS ix_v04d_items_status
ON v04d_structure_items(status, updated_at DESC);

CREATE TABLE IF NOT EXISTS v04d_task_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'manual',
    comment TEXT,
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(task_id) REFERENCES v04d_structuring_tasks(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_v04d_actions_task
ON v04d_task_actions(task_id, created_at DESC);
"""

SUBJECT_TABLES = {
    "organization": ("organizations", "external_id", "standard_name"),
    "org": ("organizations", "external_id", "standard_name"),
    "person": ("people", "external_id", "name"),
    "project": ("projects", "external_id", "name"),
    "event": ("events", "external_id", "name"),
    "resource": ("resources", "external_id", "description"),
}


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _text(value: Any, limit: int | None = None) -> str:
    result = "" if value is None else str(value).strip()
    if limit is not None:
        result = result[:limit]
    return result


def _optional(value: Any, limit: int | None = None) -> str | None:
    value_text = _text(value, limit)
    return value_text or None


def _confidence(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _fact_level(value: Any) -> FactLevel:
    normalized = _text(value).lower()
    if normalized in {"fact", "事实", "事实陈述"}:
        return "fact"
    if normalized in {"inference", "推测", "估计"}:
        return "inference"
    return "unknown"


def ensure_v04d_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> Path:
    path = ensure_v04c1_schema(db_path, allow_migration=allow_migration)
    if not allow_migration:
        return path
    with db_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
    return path


def _next_number(conn: sqlite3.Connection, prefix: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04d_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
            seq_value = CASE
                WHEN v04d_sequence_counters.seq_date = excluded.seq_date
                THEN v04d_sequence_counters.seq_value + 1
                ELSE 1
            END,
            seq_date = excluded.seq_date,
            updated_at = excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, today, utc_now()),
    ).fetchone()
    return f"{prefix}-{today}-{int(row['seq_value']):04d}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _load_json(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not value:
        return {}
    try:
        loaded = json.loads(str(value))
        return loaded if isinstance(loaded, dict) else {"value": loaded}
    except (TypeError, json.JSONDecodeError):
        return {"raw": str(value)}


def _extract_source_text(payload: dict[str, Any]) -> str:
    keys = ("content", "excerpt", "raw_text", "body", "summary", "description", "text")
    for key in keys:
        value = payload.get(key)
        if value not in (None, ""):
            return str(value)
    legacy = payload.get("legacy_row")
    if isinstance(legacy, dict):
        for key in keys:
            value = legacy.get(key)
            if value not in (None, ""):
                return str(value)
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def _log_action(
    conn: sqlite3.Connection,
    task_id: int,
    action: str,
    *,
    actor: str = "manual",
    comment: str | None = None,
    before: Any = None,
    after: Any = None,
) -> None:
    conn.execute(
        """
        INSERT INTO v04d_task_actions(
            task_id, action, actor, comment, before_json, after_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            task_id,
            action,
            actor or "manual",
            comment or None,
            _json(before) if before is not None else None,
            _json(after) if after is not None else None,
            utc_now(),
        ),
    )


def _get_source(conn: sqlite3.Connection, source_record_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM v04c1_source_records WHERE id = ?", (source_record_id,)
    ).fetchone()
    if not row:
        raise ValueError("来源记录不存在")
    return row


def get_or_create_task(
    source_record_id: int,
    *,
    raw_intelligence_id: int | None = None,
    created_by: str = "manual",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04d_schema(db_path)
    with db_connection(db_path) as conn:
        _get_source(conn, source_record_id)
        existing = conn.execute(
            "SELECT * FROM v04d_structuring_tasks WHERE source_record_id = ?",
            (source_record_id,),
        ).fetchone()
        if existing:
            return dict(existing)
        now = utc_now()
        task_no = _next_number(conn, "STR")
        cursor = conn.execute(
            """
            INSERT INTO v04d_structuring_tasks(
                task_no, source_record_id, raw_intelligence_id, status,
                created_by, created_at, updated_at
            ) VALUES (?, ?, ?, 'draft', ?, ?, ?)
            """,
            (task_no, source_record_id, raw_intelligence_id, created_by or "manual", now, now),
        )
        task_id = int(cursor.lastrowid)
        row = conn.execute(
            "SELECT * FROM v04d_structuring_tasks WHERE id = ?", (task_id,)
        ).fetchone()
        _log_action(conn, task_id, "create", actor=created_by, after=dict(row))
        return dict(row)


def ensure_source_from_raw_intelligence(
    raw_intelligence_id: int,
    *,
    actor: str = "manual",
    db_path: str | Path | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    ensure_v04d_schema(db_path)
    external_key = f"raw_intelligence:{int(raw_intelligence_id)}"
    with db_connection(db_path) as conn:
        raw = conn.execute(
            "SELECT * FROM raw_intelligence WHERE id = ?", (raw_intelligence_id,)
        ).fetchone()
        if not raw:
            raise ValueError("原始情报不存在")
        existing = conn.execute(
            """
            SELECT * FROM v04c1_source_records
            WHERE source_name = 'raw_intelligence' AND external_key = ?
            ORDER BY id DESC LIMIT 1
            """,
            (external_key,),
        ).fetchone()

    if existing:
        source = dict(existing)
    else:
        payload = {
            "batch": {
                "source_name": "raw_intelligence",
                "source_type": "database:raw_intelligence",
                "note": f"由 v0.4D 从原始情报 #{raw_intelligence_id} 建立结构化任务",
            },
            "records": [
                {
                    "external_key": external_key,
                    "source_name": "raw_intelligence",
                    "source_type": raw["source_type"] or "人工录入",
                    "source_url": raw["source_url"],
                    "title": raw["title"],
                    "captured_at": str(raw["created_at"] or utc_now()),
                    "content": raw["content"],
                    "excerpt": raw["content"],
                    "legacy_raw_intelligence_id": raw_intelligence_id,
                }
            ],
        }
        result = ingest_payload(payload, created_by=f"v04d:{actor}", db_path=db_path)
        first = result["results"][0]
        if "record" not in first:
            raise ValueError(first.get("error") or "来源接入失败")
        source = first["record"]

    task = get_or_create_task(
        int(source["id"]),
        raw_intelligence_id=raw_intelligence_id,
        created_by=actor,
        db_path=db_path,
    )
    with db_connection(db_path) as conn:
        conn.execute(
            "UPDATE raw_intelligence SET review_status = '结构化中' WHERE id = ?",
            (raw_intelligence_id,),
        )
    return source, task


def _task_row(conn: sqlite3.Connection, task_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM v04d_structuring_tasks WHERE id = ?", (task_id,)
    ).fetchone()
    if not row:
        raise ValueError("结构化任务不存在")
    return row


def _item_row(conn: sqlite3.Connection, item_id: int) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM v04d_structure_items WHERE id = ?", (item_id,)
    ).fetchone()
    if not row:
        raise ValueError("结构化条目不存在")
    return row


def _assert_task_editable(task: sqlite3.Row) -> None:
    if task["status"] not in {"draft", "returned", "partial"}:
        raise ValueError("当前任务状态不可编辑；请先退回修改，或新建修订任务")


def _item_payload(values: dict[str, Any]) -> dict[str, Any]:
    item_type = _text(values.get("item_type")).lower()
    if item_type not in ITEM_TYPE_LABELS:
        raise ValueError("条目类型不正确")
    return {
        "item_type": item_type,
        "subject_type": _optional(values.get("subject_type"), 50),
        "subject_id": _optional(values.get("subject_id"), 120),
        "subject_label": _optional(values.get("subject_label"), 300),
        "field_name": _optional(values.get("field_name"), 200),
        "candidate_value": _optional(values.get("candidate_value"), 10000),
        "left_type": _optional(values.get("left_type"), 50),
        "left_id": _optional(values.get("left_id"), 120),
        "left_label": _optional(values.get("left_label"), 300),
        "relation_type": _optional(values.get("relation_type"), 150),
        "right_type": _optional(values.get("right_type"), 50),
        "right_id": _optional(values.get("right_id"), 120),
        "right_label": _optional(values.get("right_label"), 300),
        "event_name": _optional(values.get("event_name"), 400),
        "event_date": _optional(values.get("event_date"), 100),
        "event_type": _optional(values.get("event_type"), 150),
        "related_entity": _optional(values.get("related_entity"), 300),
        "event_summary": _optional(values.get("event_summary"), 10000),
        "fact_level": _fact_level(values.get("fact_level")),
        "confidence": _confidence(values.get("confidence")),
        "evidence_excerpt": _optional(values.get("evidence_excerpt"), 20000),
        "source_url": _optional(values.get("source_url"), 2000),
    }


def create_task_item(
    task_id: int,
    *,
    actor: str = "manual",
    db_path: str | Path | None = None,
    **values: Any,
) -> dict[str, Any]:
    ensure_v04d_schema(db_path)
    payload = _item_payload(values)
    now = utc_now()
    with db_connection(db_path) as conn:
        task = _task_row(conn, task_id)
        _assert_task_editable(task)
        max_sort = conn.execute(
            "SELECT COALESCE(MAX(sort_order), 0) AS n FROM v04d_structure_items WHERE task_id = ?",
            (task_id,),
        ).fetchone()["n"]
        item_no = _next_number(conn, "STI")
        columns = ["item_no", "task_id", "sort_order", *payload.keys(), "status", "created_at", "updated_at"]
        values_list = [item_no, task_id, int(max_sort) + 10, *payload.values(), "draft", now, now]
        placeholders = ",".join("?" for _ in columns)
        cursor = conn.execute(
            f"INSERT INTO v04d_structure_items({','.join(columns)}) VALUES ({placeholders})",
            values_list,
        )
        item = conn.execute(
            "SELECT * FROM v04d_structure_items WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        conn.execute(
            "UPDATE v04d_structuring_tasks SET status = 'draft', updated_at = ? WHERE id = ?",
            (now, task_id),
        )
        _log_action(conn, task_id, "add_item", actor=actor, after=dict(item))
        return dict(item)


def update_task_item(
    item_id: int,
    *,
    actor: str = "manual",
    db_path: str | Path | None = None,
    **values: Any,
) -> dict[str, Any]:
    ensure_v04d_schema(db_path)
    payload = _item_payload(values)
    with db_connection(db_path) as conn:
        item = _item_row(conn, item_id)
        task = _task_row(conn, int(item["task_id"]))
        _assert_task_editable(task)
        if item["status"] == "submitted":
            raise ValueError("已送审条目不可直接修改")
        before = dict(item)
        assignments = ",".join(f"{key} = ?" for key in payload)
        conn.execute(
            f"UPDATE v04d_structure_items SET {assignments}, status='draft', error_message=NULL, updated_at=? WHERE id=?",
            [*payload.values(), utc_now(), item_id],
        )
        updated = _item_row(conn, item_id)
        conn.execute(
            "UPDATE v04d_structuring_tasks SET status='draft', updated_at=? WHERE id=?",
            (utc_now(), task["id"]),
        )
        _log_action(conn, int(task["id"]), "update_item", actor=actor, before=before, after=dict(updated))
        return dict(updated)


def delete_task_item(
    item_id: int,
    *,
    actor: str = "manual",
    db_path: str | Path | None = None,
) -> None:
    ensure_v04d_schema(db_path)
    with db_connection(db_path) as conn:
        item = _item_row(conn, item_id)
        task = _task_row(conn, int(item["task_id"]))
        _assert_task_editable(task)
        if item["status"] == "submitted":
            raise ValueError("已送审条目不能删除")
        before = dict(item)
        conn.execute("DELETE FROM v04d_structure_items WHERE id = ?", (item_id,))
        conn.execute(
            "UPDATE v04d_structuring_tasks SET status='draft', updated_at=? WHERE id=?",
            (utc_now(), task["id"]),
        )
        _log_action(conn, int(task["id"]), "delete_item", actor=actor, before=before)


def update_task_meta(
    task_id: int,
    *,
    assigned_to: str = "",
    review_note: str = "",
    actor: str = "manual",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04d_schema(db_path)
    with db_connection(db_path) as conn:
        task = _task_row(conn, task_id)
        before = dict(task)
        conn.execute(
            """
            UPDATE v04d_structuring_tasks
            SET assigned_to=?, review_note=?, updated_at=? WHERE id=?
            """,
            (_optional(assigned_to, 120), _optional(review_note, 4000), utc_now(), task_id),
        )
        updated = _task_row(conn, task_id)
        _log_action(conn, task_id, "update_meta", actor=actor, before=before, after=dict(updated))
        return dict(updated)


def validate_item(item: sqlite3.Row | dict[str, Any]) -> list[str]:
    row = dict(item)
    errors: list[str] = []
    if not _text(row.get("evidence_excerpt")):
        errors.append("必须绑定原文证据摘录")
    if row.get("item_type") == "field":
        if not _text(row.get("subject_type")):
            errors.append("字段候选缺少主体类型")
        if not (_text(row.get("subject_id")) or _text(row.get("subject_label"))):
            errors.append("字段候选必须填写主体ID或主体名称")
        if not _text(row.get("field_name")):
            errors.append("字段候选缺少字段名")
        if not _text(row.get("candidate_value")):
            errors.append("字段候选缺少候选值")
    elif row.get("item_type") == "relation":
        for label, keys in (
            ("左侧主体", ("left_id", "left_label")),
            ("右侧主体", ("right_id", "right_label")),
        ):
            if not any(_text(row.get(key)) for key in keys):
                errors.append(f"关系候选缺少{label}")
        if not _text(row.get("left_type")) or not _text(row.get("right_type")):
            errors.append("关系候选必须填写左右主体类型")
        if not _text(row.get("relation_type")):
            errors.append("关系候选缺少关系类型")
    elif row.get("item_type") == "event":
        if not _text(row.get("event_name")):
            errors.append("事件候选缺少事件名称")
        if not _text(row.get("event_summary")):
            errors.append("事件候选缺少事件摘要")
    else:
        errors.append("未知条目类型")
    return errors


def validate_task(task_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04d_schema(db_path)
    with db_connection(db_path) as conn:
        _task_row(conn, task_id)
        items = conn.execute(
            "SELECT * FROM v04d_structure_items WHERE task_id=? ORDER BY sort_order,id",
            (task_id,),
        ).fetchall()
    errors: list[dict[str, Any]] = []
    if not items:
        errors.append({"item_no": None, "errors": ["至少需要添加一条结构化候选"]})
    for item in items:
        item_errors = validate_item(item)
        if item_errors:
            errors.append({"item_no": item["item_no"], "errors": item_errors})
    return {"ok": not errors, "errors": errors, "item_count": len(items)}


def mark_task_ready(
    task_id: int,
    *,
    actor: str = "manual",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    validation = validate_task(task_id, db_path)
    if not validation["ok"]:
        joined = "；".join(
            f"{entry['item_no'] or '任务'}：{'、'.join(entry['errors'])}" for entry in validation["errors"]
        )
        raise ValueError(joined)
    with db_connection(db_path) as conn:
        task = _task_row(conn, task_id)
        _assert_task_editable(task)
        before = dict(task)
        now = utc_now()
        conn.execute(
            "UPDATE v04d_structuring_tasks SET status='ready', ready_at=?, updated_at=? WHERE id=?",
            (now, now, task_id),
        )
        updated = _task_row(conn, task_id)
        _log_action(conn, task_id, "mark_ready", actor=actor, before=before, after=dict(updated))
        return dict(updated)


def return_task_for_editing(
    task_id: int,
    *,
    reviewer: str = "manual",
    note: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if not _text(note):
        raise ValueError("退回修改必须填写原因")
    ensure_v04d_schema(db_path)
    with db_connection(db_path) as conn:
        task = _task_row(conn, task_id)
        if task["status"] != "ready":
            raise ValueError("只有待结构化复核任务可以退回")
        before = dict(task)
        now = utc_now()
        conn.execute(
            """
            UPDATE v04d_structuring_tasks
            SET status='returned', reviewer=?, review_note=?, updated_at=? WHERE id=?
            """,
            (_optional(reviewer, 120), _optional(note, 4000), now, task_id),
        )
        updated = _task_row(conn, task_id)
        _log_action(conn, task_id, "return", actor=reviewer, comment=note, before=before, after=dict(updated))
        return dict(updated)


def _source_record_context(source: sqlite3.Row) -> dict[str, Any]:
    payload = _load_json(source["payload_json"])
    return {
        **payload,
        "source_name": source["source_name"],
        "source_type": source["source_type"],
        "source_grade": source["source_grade"],
        "source_url": source["source_url"],
        "title": source["title"],
        "published_at": source["published_at"],
        "captured_at": source["captured_at"],
    }


def _submit_field(
    source_record_id: int,
    source_context: dict[str, Any],
    item: sqlite3.Row,
    db_path: str | Path | None,
) -> list[dict[str, Any]]:
    candidate = process_field_candidate(
        source_record_id,
        source_context,
        {
            "subject_type": item["subject_type"],
            "subject_id": item["subject_id"],
            "subject_label": item["subject_label"],
            "field_name": item["field_name"],
            "value": item["candidate_value"],
            "fact_level": item["fact_level"],
            "confidence": item["confidence"],
            "excerpt": item["evidence_excerpt"],
            "source_url": item["source_url"] or source_context.get("source_url"),
            "metadata": {"v04d_item_no": item["item_no"]},
        },
        db_path=db_path,
    )
    return [candidate]


def _submit_relation(
    source_record_id: int,
    source_context: dict[str, Any],
    item: sqlite3.Row,
    db_path: str | Path | None,
) -> list[dict[str, Any]]:
    candidate = process_relation_candidate(
        source_record_id,
        source_context,
        {
            "left_type": item["left_type"],
            "left_id": item["left_id"],
            "left_label": item["left_label"],
            "relation_type": item["relation_type"],
            "right_type": item["right_type"],
            "right_id": item["right_id"],
            "right_label": item["right_label"],
            "fact_level": item["fact_level"],
            "confidence": item["confidence"],
            "basis": item["evidence_excerpt"],
            "source_url": item["source_url"] or source_context.get("source_url"),
            "metadata": {"v04d_item_no": item["item_no"]},
        },
        db_path=db_path,
    )
    return [candidate]


def _submit_event(
    source_record_id: int,
    source_context: dict[str, Any],
    task: sqlite3.Row,
    item: sqlite3.Row,
    db_path: str | Path | None,
) -> list[dict[str, Any]]:
    subject_id = item["subject_id"] or f"event-draft:{task['task_no']}:{item['item_no']}"
    subject_label = item["event_name"]
    fields: list[tuple[str, str | None]] = [
        ("事件名称", item["event_name"]),
        ("事件日期", item["event_date"]),
        ("事件类型", item["event_type"]),
        ("相关主体", item["related_entity"]),
        ("事件摘要", item["event_summary"]),
    ]
    results: list[dict[str, Any]] = []
    for field_name, value in fields:
        if not _text(value):
            continue
        results.append(
            process_field_candidate(
                source_record_id,
                source_context,
                {
                    "subject_type": "event",
                    "subject_id": subject_id,
                    "subject_label": subject_label,
                    "field_name": field_name,
                    "value": value,
                    "fact_level": item["fact_level"],
                    "confidence": item["confidence"],
                    "excerpt": item["evidence_excerpt"],
                    "source_url": item["source_url"] or source_context.get("source_url"),
                    "metadata": {
                        "v04d_item_no": item["item_no"],
                        "event_candidate": True,
                    },
                },
                db_path=db_path,
            )
        )
    return results


def submit_task_to_review(
    task_id: int,
    *,
    actor: str = "manual",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04d_schema(db_path)
    validation = validate_task(task_id, db_path)
    if not validation["ok"]:
        raise ValueError("任务仍有未完成字段，不能送审")

    with db_connection(db_path) as conn:
        task = _task_row(conn, task_id)
        if task["status"] != "ready":
            raise ValueError("只有“待结构化复核”任务可以送入数据审核队列")
        source = _get_source(conn, int(task["source_record_id"]))
        items = conn.execute(
            "SELECT * FROM v04d_structure_items WHERE task_id=? ORDER BY sort_order,id",
            (task_id,),
        ).fetchall()
        source_context = _source_record_context(source)

    succeeded: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for item in items:
        if item["status"] == "submitted":
            continue
        try:
            if item["item_type"] == "field":
                results = _submit_field(int(source["id"]), source_context, item, db_path)
            elif item["item_type"] == "relation":
                results = _submit_relation(int(source["id"]), source_context, item, db_path)
            else:
                results = _submit_event(int(source["id"]), source_context, task, item, db_path)
            if not results:
                raise ValueError("未生成任何候选")
            primary = results[0]
            with db_connection(db_path) as conn:
                conn.execute(
                    """
                    UPDATE v04d_structure_items
                    SET status='submitted', candidate_id=?, review_item_id=?, pending_relation_id=?,
                        submission_json=?, error_message=NULL, updated_at=?
                    WHERE id=?
                    """,
                    (
                        primary.get("id"),
                        primary.get("review_item_id"),
                        primary.get("pending_relation_id"),
                        _json(results),
                        utc_now(),
                        item["id"],
                    ),
                )
            succeeded.append({"item_no": item["item_no"], "results": results})
        except Exception as exc:
            with db_connection(db_path) as conn:
                conn.execute(
                    "UPDATE v04d_structure_items SET status='failed', error_message=?, updated_at=? WHERE id=?",
                    (str(exc), utc_now(), item["id"]),
                )
            failed.append({"item_no": item["item_no"], "error": str(exc)})

    final_status = "submitted" if not failed else "partial"
    now = utc_now()
    with db_connection(db_path) as conn:
        before = dict(_task_row(conn, task_id))
        candidate_count = conn.execute(
            "SELECT COUNT(*) AS c FROM v04c1_candidates WHERE source_record_id=?",
            (source["id"],),
        ).fetchone()["c"]
        source_status = "processed" if not failed else "needs_structuring"
        source_error = None if not failed else f"v0.4D 部分送审失败：{len(failed)} 条"
        conn.execute(
            """
            UPDATE v04c1_source_records
            SET status=?, candidate_count=?, error_message=?, processed_at=? WHERE id=?
            """,
            (source_status, candidate_count, source_error, now, source["id"]),
        )
        conn.execute(
            """
            UPDATE v04d_structuring_tasks
            SET status=?, reviewer=?, submitted_at=?, completed_at=?, updated_at=? WHERE id=?
            """,
            (final_status, _optional(actor, 120), now, now if not failed else None, now, task_id),
        )
        if task["raw_intelligence_id"]:
            conn.execute(
                "UPDATE raw_intelligence SET review_status=? WHERE id=?",
                ("待审核" if not failed else "需补证", task["raw_intelligence_id"]),
            )
        after = dict(_task_row(conn, task_id))
        _log_action(
            conn,
            task_id,
            "submit_to_review",
            actor=actor,
            comment=f"成功 {len(succeeded)}，失败 {len(failed)}",
            before=before,
            after=after,
        )
    return {"task": after, "succeeded": succeeded, "failed": failed}


def task_detail(task_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04d_schema(db_path)
    with db_connection(db_path) as conn:
        task = _task_row(conn, task_id)
        source = _get_source(conn, int(task["source_record_id"]))
        items = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM v04d_structure_items WHERE task_id=? ORDER BY sort_order,id",
                (task_id,),
            ).fetchall()
        ]
        actions = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM v04d_task_actions WHERE task_id=? ORDER BY id DESC LIMIT 50",
                (task_id,),
            ).fetchall()
        ]
    source_dict = dict(source)
    payload = _load_json(source["payload_json"])
    source_dict["payload"] = payload
    source_dict["display_text"] = _extract_source_text(payload)
    return {
        "task": dict(task),
        "source": source_dict,
        "items": items,
        "actions": actions,
        "validation": validate_task(task_id, db_path),
    }


def dashboard_data(
    *,
    status: str = "",
    q: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04d_schema(db_path)
    status = _text(status)
    q = _text(q)
    with db_connection(db_path) as conn:
        counts = {
            "needs_structuring": conn.execute(
                "SELECT COUNT(*) AS c FROM v04c1_source_records WHERE status='needs_structuring'"
            ).fetchone()["c"],
            "draft_tasks": conn.execute(
                "SELECT COUNT(*) AS c FROM v04d_structuring_tasks WHERE status IN ('draft','returned','partial')"
            ).fetchone()["c"],
            "ready_tasks": conn.execute(
                "SELECT COUNT(*) AS c FROM v04d_structuring_tasks WHERE status='ready'"
            ).fetchone()["c"],
            "submitted_tasks": conn.execute(
                "SELECT COUNT(*) AS c FROM v04d_structuring_tasks WHERE status='submitted'"
            ).fetchone()["c"],
            "draft_items": conn.execute(
                "SELECT COUNT(*) AS c FROM v04d_structure_items WHERE status IN ('draft','failed')"
            ).fetchone()["c"],
        }
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("t.status=?")
            params.append(status)
        if q:
            clauses.append("(t.task_no LIKE ? OR s.record_no LIKE ? OR s.title LIKE ? OR s.source_name LIKE ?)")
            keyword = f"%{q}%"
            params.extend([keyword, keyword, keyword, keyword])
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        tasks = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT t.*, s.record_no, s.title AS source_title, s.source_name,
                       s.status AS source_status,
                       (SELECT COUNT(*) FROM v04d_structure_items i WHERE i.task_id=t.id) AS item_count,
                       (SELECT COUNT(*) FROM v04d_structure_items i WHERE i.task_id=t.id AND i.status='failed') AS failed_count
                FROM v04d_structuring_tasks t
                JOIN v04c1_source_records s ON s.id=t.source_record_id
                {where}
                ORDER BY t.updated_at DESC, t.id DESC LIMIT 100
                """,
                params,
            ).fetchall()
        ]
        sources = [
            dict(row)
            for row in conn.execute(
                """
                SELECT s.*, t.id AS task_id, t.task_no, t.status AS task_status
                FROM v04c1_source_records s
                LEFT JOIN v04d_structuring_tasks t ON t.source_record_id=s.id
                WHERE s.status='needs_structuring'
                ORDER BY s.id DESC LIMIT 100
                """
            ).fetchall()
        ]
        raw_table_exists = conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='raw_intelligence'"
        ).fetchone() is not None
        if raw_table_exists:
            raw_items = [
                dict(row)
                for row in conn.execute(
                    """
                    SELECT r.*, s.id AS source_record_id, t.id AS task_id, t.task_no, t.status AS task_status
                    FROM raw_intelligence r
                    LEFT JOIN v04c1_source_records s
                      ON s.source_name='raw_intelligence'
                     AND s.external_key=('raw_intelligence:' || r.id)
                    LEFT JOIN v04d_structuring_tasks t ON t.source_record_id=s.id
                    ORDER BY r.id DESC LIMIT 100
                    """
                ).fetchall()
            ]
        else:
            raw_items = []
    return {"counts": counts, "tasks": tasks, "sources": sources, "raw_items": raw_items}


def search_subjects(
    subject_type: str,
    q: str = "",
    *,
    limit: int = 20,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    ensure_v04d_schema(db_path)
    subject_type = _text(subject_type).lower()
    mapping = SUBJECT_TABLES.get(subject_type)
    if not mapping:
        return []
    table, id_col, label_col = mapping
    limit = max(1, min(int(limit), 50))
    with db_connection(db_path) as conn:
        if q:
            rows = conn.execute(
                f'SELECT "{id_col}" AS subject_id, "{label_col}" AS subject_label FROM "{table}" '
                f'WHERE CAST("{id_col}" AS TEXT) LIKE ? OR COALESCE(CAST("{label_col}" AS TEXT),\'\') LIKE ? '
                f'ORDER BY "{label_col}" LIMIT ?',
                (f"%{q}%", f"%{q}%", limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f'SELECT "{id_col}" AS subject_id, "{label_col}" AS subject_label FROM "{table}" '
                f'ORDER BY "{label_col}" LIMIT ?',
                (limit,),
            ).fetchall()
    return [
        {
            "subject_type": subject_type,
            "subject_id": row["subject_id"],
            "subject_label": row["subject_label"] or row["subject_id"],
        }
        for row in rows
    ]


def _redirect(message: str, level: str = "ok", *, task_id: int | None = None) -> RedirectResponse:
    target = f"/review/structure/tasks/{task_id}" if task_id else "/review/structure"
    separator = "&" if "?" in target else "?"
    return RedirectResponse(
        url=f"{target}{separator}message={quote(message)}&level={quote(level)}",
        status_code=303,
    )


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def structure_dashboard(
    request: Request,
    status: str = Query(""),
    q: str = Query(""),
    message: str | None = None,
    level: str = "ok",
):
    return templates.TemplateResponse(
        request=request,
        name="v04d_structuring.html",
        context={
            "mode": "dashboard",
            **dashboard_data(status=status, q=q),
            "filters": {"status": status, "q": q},
            "message": message,
            "message_level": level,
            "task_status_labels": TASK_STATUS_LABELS,
            "db_path": str(default_db_path()),
        },
    )


@router.post("/sources/{source_record_id}/start")
def ui_start_source(
    source_record_id: int,
    actor: str = Form("manual"),
):
    try:
        task = get_or_create_task(source_record_id, created_by=actor or "manual")
        return _redirect(f"已进入结构化任务 {task['task_no']}", task_id=int(task["id"]))
    except Exception as exc:
        return _redirect(f"创建任务失败：{exc}", "error")


@router.post("/raw/{raw_intelligence_id}/start")
def ui_start_raw(
    raw_intelligence_id: int,
    actor: str = Form("manual"),
):
    try:
        _, task = ensure_source_from_raw_intelligence(raw_intelligence_id, actor=actor or "manual")
        return _redirect(f"已进入结构化任务 {task['task_no']}", task_id=int(task["id"]))
    except Exception as exc:
        return _redirect(f"建立原始情报任务失败：{exc}", "error")


@router.get("/tasks/{task_id}", response_class=HTMLResponse)
def structure_editor(
    task_id: int,
    request: Request,
    message: str | None = None,
    level: str = "ok",
):
    try:
        detail = task_detail(task_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request=request,
        name="v04d_structuring.html",
        context={
            "mode": "editor",
            **detail,
            "message": message,
            "message_level": level,
            "task_status_labels": TASK_STATUS_LABELS,
            "item_type_labels": ITEM_TYPE_LABELS,
            "item_status_labels": ITEM_STATUS_LABELS,
            "fact_level_labels": FACT_LEVEL_LABELS,
            "editable": detail["task"]["status"] in {"draft", "returned", "partial"},
        },
    )


@router.post("/tasks/{task_id}/meta")
def ui_update_meta(
    task_id: int,
    assigned_to: str = Form(""),
    review_note: str = Form(""),
    actor: str = Form("manual"),
):
    try:
        update_task_meta(
            task_id,
            assigned_to=assigned_to,
            review_note=review_note,
            actor=actor or "manual",
        )
        return _redirect("任务信息已保存", task_id=task_id)
    except Exception as exc:
        return _redirect(f"保存失败：{exc}", "error", task_id=task_id)


@router.post("/tasks/{task_id}/items")
def ui_add_item(
    task_id: int,
    item_type: str = Form(...),
    subject_type: str = Form(""),
    subject_id: str = Form(""),
    subject_label: str = Form(""),
    field_name: str = Form(""),
    candidate_value: str = Form(""),
    left_type: str = Form(""),
    left_id: str = Form(""),
    left_label: str = Form(""),
    relation_type: str = Form(""),
    right_type: str = Form(""),
    right_id: str = Form(""),
    right_label: str = Form(""),
    event_name: str = Form(""),
    event_date: str = Form(""),
    event_type: str = Form(""),
    related_entity: str = Form(""),
    event_summary: str = Form(""),
    fact_level: str = Form("unknown"),
    confidence: str = Form(""),
    evidence_excerpt: str = Form(""),
    source_url: str = Form(""),
    actor: str = Form("manual"),
):
    try:
        values = {
            "item_type": item_type,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "subject_label": subject_label,
            "field_name": field_name,
            "candidate_value": candidate_value,
            "left_type": left_type,
            "left_id": left_id,
            "left_label": left_label,
            "relation_type": relation_type,
            "right_type": right_type,
            "right_id": right_id,
            "right_label": right_label,
            "event_name": event_name,
            "event_date": event_date,
            "event_type": event_type,
            "related_entity": related_entity,
            "event_summary": event_summary,
            "fact_level": fact_level,
            "confidence": confidence,
            "evidence_excerpt": evidence_excerpt,
            "source_url": source_url,
        }
        item = create_task_item(task_id, actor=actor or "manual", **values)
        return _redirect(f"已添加 {item['item_no']}", task_id=task_id)
    except Exception as exc:
        return _redirect(f"添加失败：{exc}", "error", task_id=task_id)


@router.post("/items/{item_id}/update")
def ui_update_item(
    item_id: int,
    item_type: str = Form(...),
    subject_type: str = Form(""),
    subject_id: str = Form(""),
    subject_label: str = Form(""),
    field_name: str = Form(""),
    candidate_value: str = Form(""),
    left_type: str = Form(""),
    left_id: str = Form(""),
    left_label: str = Form(""),
    relation_type: str = Form(""),
    right_type: str = Form(""),
    right_id: str = Form(""),
    right_label: str = Form(""),
    event_name: str = Form(""),
    event_date: str = Form(""),
    event_type: str = Form(""),
    related_entity: str = Form(""),
    event_summary: str = Form(""),
    fact_level: str = Form("unknown"),
    confidence: str = Form(""),
    evidence_excerpt: str = Form(""),
    source_url: str = Form(""),
    actor: str = Form("manual"),
):
    try:
        with db_connection() as conn:
            task_id = int(_item_row(conn, item_id)["task_id"])
        values = {
            "item_type": item_type,
            "subject_type": subject_type,
            "subject_id": subject_id,
            "subject_label": subject_label,
            "field_name": field_name,
            "candidate_value": candidate_value,
            "left_type": left_type,
            "left_id": left_id,
            "left_label": left_label,
            "relation_type": relation_type,
            "right_type": right_type,
            "right_id": right_id,
            "right_label": right_label,
            "event_name": event_name,
            "event_date": event_date,
            "event_type": event_type,
            "related_entity": related_entity,
            "event_summary": event_summary,
            "fact_level": fact_level,
            "confidence": confidence,
            "evidence_excerpt": evidence_excerpt,
            "source_url": source_url,
        }
        update_task_item(item_id, actor=actor or "manual", **values)
        return _redirect("条目已保存", task_id=task_id)
    except Exception as exc:
        task_id_value = locals().get("task_id")
        return _redirect(f"保存失败：{exc}", "error", task_id=task_id_value)


@router.post("/items/{item_id}/delete")
def ui_delete_item(
    item_id: int,
    actor: str = Form("manual"),
):
    try:
        with db_connection() as conn:
            task_id = int(_item_row(conn, item_id)["task_id"])
        delete_task_item(item_id, actor=actor or "manual")
        return _redirect("条目已删除", task_id=task_id)
    except Exception as exc:
        task_id_value = locals().get("task_id")
        return _redirect(f"删除失败：{exc}", "error", task_id=task_id_value)


@router.post("/tasks/{task_id}/ready")
def ui_mark_ready(
    task_id: int,
    actor: str = Form("manual"),
):
    try:
        task = mark_task_ready(task_id, actor=actor or "manual")
        return _redirect(f"{task['task_no']} 已提交结构化复核", task_id=task_id)
    except Exception as exc:
        return _redirect(f"提交复核失败：{exc}", "error", task_id=task_id)


@router.post("/tasks/{task_id}/return")
def ui_return_task(
    task_id: int,
    reviewer: str = Form("manual"),
    note: str = Form(...),
):
    try:
        task = return_task_for_editing(task_id, reviewer=reviewer or "manual", note=note)
        return _redirect(f"{task['task_no']} 已退回修改", task_id=task_id)
    except Exception as exc:
        return _redirect(f"退回失败：{exc}", "error", task_id=task_id)


@router.post("/tasks/{task_id}/submit")
def ui_submit_task(
    task_id: int,
    actor: str = Form("manual"),
):
    try:
        result = submit_task_to_review(task_id, actor=actor or "manual")
        message = f"送审完成：成功 {len(result['succeeded'])} 条"
        if result["failed"]:
            message += f"，失败 {len(result['failed'])} 条"
        return _redirect(message, "error" if result["failed"] else "ok", task_id=task_id)
    except Exception as exc:
        return _redirect(f"送审失败：{exc}", "error", task_id=task_id)


@router.get("/api/subjects")
def api_subjects(
    subject_type: str,
    q: str = "",
    limit: int = 20,
):
    return JSONResponse({"items": search_subjects(subject_type, q, limit=limit)})


@router.get("/api/tasks/{task_id}/validate")
def api_validate_task(task_id: int):
    try:
        return JSONResponse(validate_task(task_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/health")
def v04d_health():
    path = ensure_v04d_schema()
    with db_connection(path) as conn:
        tables = conn.execute(
            "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v04d_%'"
        ).fetchone()["c"]
        tasks = conn.execute("SELECT COUNT(*) AS c FROM v04d_structuring_tasks").fetchone()["c"]
        items = conn.execute("SELECT COUNT(*) AS c FROM v04d_structure_items").fetchone()["c"]
    return {
        "ok": tables >= 4,
        "version": "0.4D-A",
        "database": str(path),
        "v04d_table_count": tables,
        "tasks": tasks,
        "items": items,
    }
