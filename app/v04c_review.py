from __future__ import annotations

import hashlib
import json
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from app.settings import resolved_db_path

router = APIRouter(prefix="/review", tags=["v0.4C 鏁版嵁瀹℃牳"])

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
TEMPLATE_DIR = MODULE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

ReviewStatus = Literal["pending", "in_review", "approved", "rejected", "deferred"]
FactLevel = Literal["fact", "inference", "unknown"]
Priority = Literal["low", "medium", "high", "critical"]

STATUS_LABELS = {
    "pending": "pending",
    "in_review": "in_review",
    "approved": "approved",
    "rejected": "rejected",
    "deferred": "deferred",
}
FACT_LABELS = {"fact": "fact", "inference": "inference", "unknown": "unknown"}
PRIORITY_LABELS = {
    "low": "low",
    "medium": "medium",
    "high": "high",
    "critical": "critical",
}
ITEM_TYPE_LABELS = {
    "conflict": "conflict",
    "pending_relation": "pending_relation",
    "fact_check": "fact_check",
    "high_risk": "high_risk",
    "duplicate": "duplicate",
    "other": "other",
}

HIGH_RISK_KEYWORDS = {
    "amount",
    "financing",
    "clinical_stage",
    "registration_result",
    "approval",
    "risk",
    "safety",
}
SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS v04c_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v04c_review_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_no TEXT NOT NULL UNIQUE,
    item_type TEXT NOT NULL DEFAULT 'fact_check',
    subject_type TEXT NOT NULL DEFAULT 'unknown',
    subject_id TEXT,
    subject_label TEXT,
    field_name TEXT,
    current_value TEXT,
    proposed_value TEXT,
    fact_level TEXT NOT NULL DEFAULT 'unknown',
    status TEXT NOT NULL DEFAULT 'pending',
    priority TEXT NOT NULL DEFAULT 'medium',
    risk_level TEXT NOT NULL DEFAULT 'normal',
    source_count INTEGER NOT NULL DEFAULT 0,
    assigned_to TEXT,
    due_at TEXT,
    batch_tag TEXT,
    dedupe_key TEXT,
    resolution_note TEXT,
    resolved_value TEXT,
    created_by TEXT NOT NULL DEFAULT 'system',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    resolved_at TEXT,
    CHECK (fact_level IN ('fact', 'inference', 'unknown')),
    CHECK (status IN ('pending', 'in_review', 'approved', 'rejected', 'deferred')),
    CHECK (priority IN ('low', 'medium', 'high', 'critical'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04c_review_dedupe
ON v04c_review_items(dedupe_key)
WHERE dedupe_key IS NOT NULL AND dedupe_key <> '' AND status IN ('pending', 'in_review', 'deferred');

CREATE INDEX IF NOT EXISTS ix_v04c_review_status_priority
ON v04c_review_items(status, priority, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_v04c_review_subject
ON v04c_review_items(subject_type, subject_id);

CREATE TABLE IF NOT EXISTS v04c_review_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_item_id INTEGER NOT NULL,
    source_url TEXT,
    source_type TEXT,
    source_grade TEXT,
    source_title TEXT,
    source_value TEXT,
    source_excerpt TEXT,
    published_at TEXT,
    captured_at TEXT NOT NULL,
    is_primary INTEGER NOT NULL DEFAULT 0,
    supports_fact INTEGER NOT NULL DEFAULT 1,
    metadata_json TEXT,
    FOREIGN KEY(review_item_id) REFERENCES v04c_review_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_v04c_evidence_item
ON v04c_review_evidence(review_item_id, source_grade);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04c_evidence_source_once
ON v04c_review_evidence(
    review_item_id,
    COALESCE(source_url, ''),
    COALESCE(source_value, ''),
    COALESCE(source_excerpt, '')
);

CREATE TABLE IF NOT EXISTS v04c_review_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_item_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'manual',
    comment TEXT,
    before_json TEXT,
    after_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(review_item_id) REFERENCES v04c_review_items(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS ix_v04c_actions_item
ON v04c_review_actions(review_item_id, created_at DESC);

CREATE TABLE IF NOT EXISTS v04c_pending_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relation_no TEXT NOT NULL UNIQUE,
    left_type TEXT NOT NULL,
    left_id TEXT,
    left_label TEXT,
    relation_type TEXT NOT NULL,
    right_type TEXT NOT NULL,
    right_id TEXT,
    right_label TEXT,
    confidence REAL,
    fact_level TEXT NOT NULL DEFAULT 'inference',
    status TEXT NOT NULL DEFAULT 'pending',
    basis TEXT,
    source_url TEXT,
    reviewer TEXT,
    review_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reviewed_at TEXT,
    source_review_item_id INTEGER,
    CHECK (fact_level IN ('fact', 'inference', 'unknown')),
    CHECK (status IN ('pending', 'approved', 'rejected', 'deferred')),
    FOREIGN KEY(source_review_item_id) REFERENCES v04c_review_items(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_v04c_relation_status
ON v04c_pending_relations(status, confidence DESC, created_at DESC);

CREATE TABLE IF NOT EXISTS v04c_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    claim_no TEXT NOT NULL UNIQUE,
    subject_type TEXT NOT NULL,
    subject_id TEXT,
    subject_label TEXT,
    predicate TEXT NOT NULL,
    object_value TEXT NOT NULL,
    claim_type TEXT NOT NULL DEFAULT 'unknown',
    confidence REAL,
    status TEXT NOT NULL DEFAULT 'pending',
    source_url TEXT,
    source_grade TEXT,
    basis TEXT,
    created_by TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    confirmed_at TEXT,
    CHECK (claim_type IN ('fact', 'inference', 'unknown')),
    CHECK (status IN ('pending', 'approved', 'rejected', 'deferred'))
);

CREATE INDEX IF NOT EXISTS ix_v04c_claim_subject
ON v04c_claims(subject_type, subject_id, predicate, claim_type);
"""


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def default_db_path() -> Path:
    return resolved_db_path()


@contextmanager
def db_connection(db_path: str | Path | None = None) -> Iterator[sqlite3.Connection]:
    path = Path(db_path) if db_path else default_db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    conn.execute("PRAGMA journal_mode = WAL")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def ensure_v04c_schema(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    with db_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
    return path


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row is not None else None


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return " ".join(str(value).strip().lower().split())


def build_dedupe_key(
    item_type: str,
    subject_type: str,
    subject_id: str | None,
    field_name: str | None,
    current_value: str | None,
    proposed_value: str | None,
) -> str:
    payload = "|".join(
        _normalize_text(part)
        for part in (
            item_type,
            subject_type,
            subject_id,
            field_name,
            current_value,
            proposed_value,
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def infer_risk(field_name: str | None, item_type: str | None = None) -> tuple[str, Priority]:
    haystack = f"{field_name or ''} {item_type or ''}".lower()
    if any(keyword.lower() in haystack for keyword in HIGH_RISK_KEYWORDS):
        return "high", "high"
    if item_type == "conflict":
        return "elevated", "high"
    if item_type == "pending_relation":
        return "normal", "medium"
    return "normal", "medium"


def next_number(conn: sqlite3.Connection, prefix: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    now = utc_now()
    conn.execute("BEGIN IMMEDIATE")
    row = conn.execute(
        "SELECT seq_date, seq_value FROM v04c_sequence_counters WHERE seq_key = ?",
        (prefix,),
    ).fetchone()
    if row is None:
        value = 1
        conn.execute(
            "INSERT INTO v04c_sequence_counters(seq_key, seq_date, seq_value, updated_at) VALUES (?, ?, ?, ?)",
            (prefix, today, value, now),
        )
    else:
        value = int(row["seq_value"]) + 1 if row["seq_date"] == today else 1
        conn.execute(
            "UPDATE v04c_sequence_counters SET seq_date = ?, seq_value = ?, updated_at = ? WHERE seq_key = ?",
            (today, value, now, prefix),
        )
    return f"{prefix}-{today}-{value:04d}"


def create_review_item(
    *,
    item_type: str,
    subject_type: str,
    subject_id: str | None = None,
    subject_label: str | None = None,
    field_name: str | None = None,
    current_value: str | None = None,
    proposed_value: str | None = None,
    fact_level: FactLevel = "unknown",
    priority: Priority | None = None,
    assigned_to: str | None = None,
    batch_tag: str | None = None,
    created_by: str = "manual",
    evidence: Iterable[dict[str, Any]] | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04c_schema(db_path)
    risk_level, inferred_priority = infer_risk(field_name, item_type)
    priority = priority or inferred_priority
    dedupe_key = build_dedupe_key(
        item_type, subject_type, subject_id, field_name, current_value, proposed_value
    )
    now = utc_now()
    evidence_list = list(evidence or [])

    with db_connection(db_path) as conn:
        existing = conn.execute(
            """
            SELECT * FROM v04c_review_items
            WHERE dedupe_key = ? AND status IN ('pending', 'in_review', 'deferred')
            ORDER BY id DESC LIMIT 1
            """,
            (dedupe_key,),
        ).fetchone()
        if existing:
            return dict(existing)

        review_no = next_number(conn, "RVW")
        cursor = conn.execute(
            """
            INSERT INTO v04c_review_items(
                review_no, item_type, subject_type, subject_id, subject_label,
                field_name, current_value, proposed_value, fact_level, status,
                priority, risk_level, source_count, assigned_to, batch_tag,
                dedupe_key, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                review_no,
                item_type,
                subject_type,
                subject_id or None,
                subject_label or None,
                field_name or None,
                current_value or None,
                proposed_value or None,
                fact_level,
                priority,
                risk_level,
                len(evidence_list),
                assigned_to or None,
                batch_tag or None,
                dedupe_key,
                created_by,
                now,
                now,
            ),
        )
        item_id = int(cursor.lastrowid)
        for source in evidence_list:
            _insert_evidence(conn, item_id, source)
        _log_action(
            conn,
            item_id,
            "created",
            created_by,
            "瀹℃牳椤瑰凡鍒涘缓",
            None,
            {"review_no": review_no, "status": "pending"},
        )
        row = conn.execute("SELECT * FROM v04c_review_items WHERE id = ?", (item_id,)).fetchone()
        return dict(row)


def _insert_evidence(conn: sqlite3.Connection, item_id: int, source: dict[str, Any]) -> int:
    existing = conn.execute(
        """
        SELECT id FROM v04c_review_evidence
        WHERE review_item_id = ?
          AND COALESCE(source_url,'') = ?
          AND COALESCE(source_value,'') = ?
          AND COALESCE(source_excerpt,'') = ?
        LIMIT 1
        """,
        (
            item_id,
            source.get("source_url") or "",
            str(source.get("source_value") or ""),
            source.get("source_excerpt") or "",
        ),
    ).fetchone()
    if existing:
        return int(existing["id"])
    cursor = conn.execute(
        """
        INSERT INTO v04c_review_evidence(
            review_item_id, source_url, source_type, source_grade, source_title,
            source_value, source_excerpt, published_at, captured_at,
            is_primary, supports_fact, metadata_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_id,
            source.get("source_url") or None,
            source.get("source_type") or None,
            source.get("source_grade") or None,
            source.get("source_title") or None,
            source.get("source_value") or None,
            source.get("source_excerpt") or None,
            source.get("published_at") or None,
            source.get("captured_at") or utc_now(),
            1 if source.get("is_primary") else 0,
            1 if source.get("supports_fact", True) else 0,
            json.dumps(source.get("metadata") or {}, ensure_ascii=False),
        ),
    )
    return int(cursor.lastrowid)


def add_evidence(
    review_item_id: int,
    source: dict[str, Any],
    *,
    actor: str = "manual",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04c_schema(db_path)
    with db_connection(db_path) as conn:
        item = conn.execute(
            "SELECT * FROM v04c_review_items WHERE id = ?", (review_item_id,)
        ).fetchone()
        if not item:
            raise ValueError(f"瀹℃牳椤逛笉瀛樺湪: {review_item_id}")
        before_count = int(item["source_count"] or 0)
        evidence_id = _insert_evidence(conn, review_item_id, source)
        actual_count = conn.execute(
            "SELECT COUNT(*) AS c FROM v04c_review_evidence WHERE review_item_id = ?",
            (review_item_id,),
        ).fetchone()["c"]
        conn.execute(
            "UPDATE v04c_review_items SET source_count = ?, updated_at = ? WHERE id = ?",
            (actual_count, utc_now(), review_item_id),
        )
        _log_action(
            conn,
            review_item_id,
            "evidence_added",
            actor,
            source.get("source_title") or source.get("source_url") or "鏂板璇佹嵁",
            None,
            {"evidence_id": evidence_id},
        )
        row = conn.execute(
            "SELECT * FROM v04c_review_evidence WHERE id = ?", (evidence_id,)
        ).fetchone()
        return dict(row)


def _log_action(
    conn: sqlite3.Connection,
    item_id: int,
    action: str,
    actor: str,
    comment: str | None,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    conn.execute(
        """
        INSERT INTO v04c_review_actions(
            review_item_id, action, actor, comment, before_json, after_json, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            item_id,
            action,
            actor or "manual",
            comment or None,
            json.dumps(before, ensure_ascii=False, default=str) if before else None,
            json.dumps(after, ensure_ascii=False, default=str) if after else None,
            utc_now(),
        ),
    )


def resolve_review_item(
    review_item_id: int,
    *,
    decision: ReviewStatus,
    actor: str,
    note: str,
    resolved_value: str | None = None,
    fact_level: FactLevel | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if decision not in {"in_review", "approved", "rejected", "deferred"}:
        raise ValueError("涓嶆敮鎸佺殑瀹℃牳鍐冲畾")
    if decision in {"approved", "rejected"} and not note.strip():
        raise ValueError("閫氳繃鎴栭┏鍥炴椂蹇呴』濉啓瀹℃牳璇存槑")

    ensure_v04c_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM v04c_review_items WHERE id = ?", (review_item_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"瀹℃牳椤逛笉瀛樺湪: {review_item_id}")
        before = dict(row)
        now = utc_now()
        resolved_at = now if decision in {"approved", "rejected"} else None
        new_fact_level = fact_level or row["fact_level"]
        conn.execute(
            """
            UPDATE v04c_review_items
            SET status = ?, resolution_note = ?, resolved_value = ?, fact_level = ?,
                updated_at = ?, resolved_at = ?
            WHERE id = ?
            """,
            (
                decision,
                note.strip() or None,
                resolved_value or None,
                new_fact_level,
                now,
                resolved_at,
                review_item_id,
            ),
        )
        after_row = conn.execute(
            "SELECT * FROM v04c_review_items WHERE id = ?", (review_item_id,)
        ).fetchone()
        after = dict(after_row)
        _log_action(conn, review_item_id, decision, actor, note, before, after)
        return after


def batch_resolve(
    item_ids: Iterable[int],
    *,
    decision: ReviewStatus,
    actor: str,
    note: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ids = sorted({int(item_id) for item_id in item_ids})
    if not ids:
        raise ValueError("??????")
    if decision not in {"approved", "rejected", "deferred", "in_review"}:
        raise ValueError("????????")
    if decision in {"approved", "rejected"} and not note.strip():
        raise ValueError("???????????????")

    ensure_v04c_schema(db_path)
    succeeded: list[int] = []
    failed: list[dict[str, Any]] = []
    now = utc_now()
    with db_connection(db_path) as conn:
        for item_id in ids:
            row = conn.execute(
                "SELECT * FROM v04c_review_items WHERE id = ?",
                (item_id,),
            ).fetchone()
            if not row:
                failed.append({"id": item_id, "error": "review item not found"})
                continue
            before = dict(row)
            resolved_at = now if decision in {"approved", "rejected"} else None
            resolved_value = row["resolved_value"] or row["proposed_value"]
            conn.execute(
                """
                UPDATE v04c_review_items
                SET status = ?, resolution_note = ?, resolved_value = ?,
                    updated_at = ?, resolved_at = ?
                WHERE id = ?
                """,
                (
                    decision,
                    f"[batch] {note.strip()}".strip(),
                    resolved_value,
                    now,
                    resolved_at,
                    item_id,
                ),
            )
            after = conn.execute(
                "SELECT * FROM v04c_review_items WHERE id = ?",
                (item_id,),
            ).fetchone()
            _log_action(conn, item_id, decision, actor, note, before, dict(after))
            succeeded.append(item_id)
    return {"succeeded": succeeded, "failed": failed}

def create_pending_relation(
    *,
    left_type: str,
    left_id: str | None,
    left_label: str | None,
    relation_type: str,
    right_type: str,
    right_id: str | None,
    right_label: str | None,
    confidence: float | None,
    basis: str | None,
    source_url: str | None = None,
    fact_level: FactLevel = "inference",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04c_schema(db_path)
    confidence_value = None if confidence is None else max(0.0, min(1.0, float(confidence)))
    now = utc_now()
    # 鍏堟彁浜ゅ叧鑱旇褰曪紝鍐嶅垱寤哄搴斿鏍搁」锛岄伩鍏?SQLite 宓屽鍐欒繛鎺ラ€犳垚閿佸畾銆?
    with db_connection(db_path) as conn:
        relation_no = next_number(conn, "REL")
        cursor = conn.execute(
            """
            INSERT INTO v04c_pending_relations(
                relation_no, left_type, left_id, left_label, relation_type,
                right_type, right_id, right_label, confidence, fact_level,
                status, basis, source_url, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)
            """,
            (
                relation_no,
                left_type,
                left_id or None,
                left_label or None,
                relation_type,
                right_type,
                right_id or None,
                right_label or None,
                confidence_value,
                fact_level,
                basis or None,
                source_url or None,
                now,
                now,
            ),
        )
        relation_id = int(cursor.lastrowid)

    review_item = create_review_item(
        item_type="pending_relation",
        subject_type=left_type,
        subject_id=left_id,
        subject_label=left_label,
        field_name=relation_type,
        current_value="not_linked",
        proposed_value=f"{left_label or left_id or left_type} --{relation_type}-> {right_label or right_id or right_type}",
        fact_level=fact_level,
        priority="medium",
        created_by="relation_queue",
        db_path=db_path,
    )
    with db_connection(db_path) as conn:
        conn.execute(
            "UPDATE v04c_pending_relations SET source_review_item_id = ? WHERE id = ?",
            (review_item["id"], relation_id),
        )
        row = conn.execute(
            "SELECT * FROM v04c_pending_relations WHERE id = ?", (relation_id,)
        ).fetchone()
        return dict(row)


def decide_pending_relation(
    relation_id: int,
    *,
    decision: Literal["approved", "rejected", "deferred"],
    reviewer: str,
    note: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if decision in {"approved", "rejected"} and not note.strip():
        raise ValueError("纭鎴栭┏鍥炲叧鑱旀椂蹇呴』濉啓璇存槑")
    ensure_v04c_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM v04c_pending_relations WHERE id = ?", (relation_id,)
        ).fetchone()
        if not row:
            raise ValueError(f"寰呯‘璁ゅ叧鑱斾笉瀛樺湪: {relation_id}")
        source_review_item_id = row["source_review_item_id"]
        now = utc_now()
        conn.execute(
            """
            UPDATE v04c_pending_relations
            SET status = ?, reviewer = ?, review_note = ?, reviewed_at = ?, updated_at = ?,
                fact_level = CASE WHEN ? = 'approved' THEN 'fact' ELSE fact_level END
            WHERE id = ?
            """,
            (decision, reviewer or "manual", note.strip() or None, now, now, decision, relation_id),
        )

    # 鍏宠仈璁板綍鎻愪氦鍚庯紝鍐嶅悓姝ュ搴斿鏍搁」锛岄伩鍏嶅祵濂楀啓杩炴帴銆?
    if source_review_item_id:
        resolve_review_item(
            int(source_review_item_id),
            decision=decision,
            actor=reviewer or "manual",
            note=note,
            fact_level="fact" if decision == "approved" else None,
            db_path=db_path,
        )
    with db_connection(db_path) as conn:
        updated = conn.execute(
            "SELECT * FROM v04c_pending_relations WHERE id = ?", (relation_id,)
        ).fetchone()
        return dict(updated)


def register_claim(
    *,
    subject_type: str,
    subject_id: str | None,
    subject_label: str | None,
    predicate: str,
    object_value: str,
    claim_type: FactLevel,
    confidence: float | None = None,
    source_url: str | None = None,
    source_grade: str | None = None,
    basis: str | None = None,
    created_by: str = "manual",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04c_schema(db_path)
    now = utc_now()
    confidence_value = None if confidence is None else max(0.0, min(1.0, float(confidence)))
    # 鍏堢櫥璁颁富寮狅紝鍐嶅崟鐙垱寤哄鏍搁」锛岄伩鍏嶅祵濂楀啓杩炴帴銆?
    with db_connection(db_path) as conn:
        claim_no = next_number(conn, "CLM")
        cursor = conn.execute(
            """
            INSERT INTO v04c_claims(
                claim_no, subject_type, subject_id, subject_label, predicate,
                object_value, claim_type, confidence, status, source_url,
                source_grade, basis, created_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)
            """,
            (
                claim_no,
                subject_type,
                subject_id or None,
                subject_label or None,
                predicate,
                object_value,
                claim_type,
                confidence_value,
                source_url or None,
                source_grade or None,
                basis or None,
                created_by,
                now,
                now,
            ),
        )
        claim_id = int(cursor.lastrowid)

    # 鎺ㄦ祴姘镐笉鑷姩褰撲綔浜嬪疄锛涗簨瀹炰篃鍏堣繘鍏ュ鏍搁槦鍒椼€?
    create_review_item(
        item_type="fact_check",
        subject_type=subject_type,
        subject_id=subject_id,
        subject_label=subject_label,
        field_name=predicate,
        current_value=None,
        proposed_value=object_value,
        fact_level=claim_type,
        priority=None,
        created_by="claim_registry",
        evidence=[
            {
                "source_url": source_url,
                "source_grade": source_grade,
                "source_value": object_value,
                "source_excerpt": basis,
                "supports_fact": claim_type == "fact",
            }
        ]
        if source_url or basis
        else [],
        db_path=db_path,
    )
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v04c_claims WHERE id = ?", (claim_id,)).fetchone()
        return dict(row)


def dashboard_data(
    *,
    status: str | None = None,
    item_type: str | None = None,
    priority: str | None = None,
    q: str | None = None,
    limit: int = 200,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04c_schema(db_path)
    where: list[str] = []
    params: list[Any] = []
    if status:
        where.append("status = ?")
        params.append(status)
    if item_type:
        where.append("item_type = ?")
        params.append(item_type)
    if priority:
        where.append("priority = ?")
        params.append(priority)
    if q:
        where.append(
            "(review_no LIKE ? OR subject_label LIKE ? OR subject_id LIKE ? OR field_name LIKE ? OR proposed_value LIKE ?)"
        )
        term = f"%{q.strip()}%"
        params.extend([term, term, term, term, term])
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with db_connection(db_path) as conn:
        items = [
            dict(row)
            for row in conn.execute(
                f"""
                SELECT * FROM v04c_review_items
                {where_sql}
                ORDER BY
                    CASE priority WHEN 'critical' THEN 1 WHEN 'high' THEN 2 WHEN 'medium' THEN 3 ELSE 4 END,
                    CASE status WHEN 'pending' THEN 1 WHEN 'in_review' THEN 2 WHEN 'deferred' THEN 3 ELSE 4 END,
                    created_at DESC
                LIMIT ?
                """,
                (*params, max(1, min(int(limit), 500))),
            ).fetchall()
        ]
        counts = {
            row["status"]: row["count"]
            for row in conn.execute(
                "SELECT status, COUNT(*) AS count FROM v04c_review_items GROUP BY status"
            ).fetchall()
        }
        type_counts = {
            row["item_type"]: row["count"]
            for row in conn.execute(
                "SELECT item_type, COUNT(*) AS count FROM v04c_review_items WHERE status IN ('pending','in_review','deferred') GROUP BY item_type"
            ).fetchall()
        }
        relations = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM v04c_pending_relations ORDER BY CASE status WHEN 'pending' THEN 1 ELSE 2 END, confidence DESC, created_at DESC LIMIT 100"
            ).fetchall()
        ]
        claims = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM v04c_claims ORDER BY CASE status WHEN 'pending' THEN 1 ELSE 2 END, created_at DESC LIMIT 100"
            ).fetchall()
        ]
    return {
        "items": items,
        "counts": counts,
        "type_counts": type_counts,
        "relations": relations,
        "claims": claims,
    }


def review_detail(review_item_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04c_schema(db_path)
    with db_connection(db_path) as conn:
        item = conn.execute(
            "SELECT * FROM v04c_review_items WHERE id = ?", (review_item_id,)
        ).fetchone()
        if not item:
            raise ValueError(f"瀹℃牳椤逛笉瀛樺湪: {review_item_id}")
        evidence = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM v04c_review_evidence WHERE review_item_id = ? ORDER BY is_primary DESC, source_grade, id",
                (review_item_id,),
            ).fetchall()
        ]
        actions = [
            dict(row)
            for row in conn.execute(
                "SELECT * FROM v04c_review_actions WHERE review_item_id = ? ORDER BY created_at DESC, id DESC",
                (review_item_id,),
            ).fetchall()
        ]
    return {"item": dict(item), "evidence": evidence, "actions": actions}


def _redirect_with_message(message: str, level: str = "ok") -> RedirectResponse:
    from urllib.parse import quote

    return RedirectResponse(
        url=f"/review?message={quote(message)}&level={quote(level)}",
        status_code=303,
    )


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def review_dashboard(
    request: Request,
    status: str | None = None,
    item_type: str | None = None,
    priority: str | None = None,
    q: str | None = None,
    message: str | None = None,
    level: str = "ok",
):
    data = dashboard_data(status=status, item_type=item_type, priority=priority, q=q)
    return templates.TemplateResponse(
        request=request,
        name="v04c_review_queue.html",
        context={
            **data,
            "filters": {"status": status or "", "item_type": item_type or "", "priority": priority or "", "q": q or ""},
            "message": message,
            "message_level": level,
            "status_labels": STATUS_LABELS,
            "fact_labels": FACT_LABELS,
            "priority_labels": PRIORITY_LABELS,
            "item_type_labels": ITEM_TYPE_LABELS,
            "db_path": str(default_db_path()),
        },
    )


@router.get("/api/items/{review_item_id}")
def api_review_detail(review_item_id: int):
    try:
        return JSONResponse(review_detail(review_item_id))
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/items")
def ui_create_review_item(
    item_type: str = Form(...),
    subject_type: str = Form(...),
    subject_id: str = Form(""),
    subject_label: str = Form(""),
    field_name: str = Form(""),
    current_value: str = Form(""),
    proposed_value: str = Form(""),
    fact_level: FactLevel = Form("unknown"),
    priority: Priority | None = Form(None),
    created_by: str = Form("manual"),
):
    try:
        item = create_review_item(
            item_type=item_type,
            subject_type=subject_type,
            subject_id=subject_id,
            subject_label=subject_label,
            field_name=field_name,
            current_value=current_value,
            proposed_value=proposed_value,
            fact_level=fact_level,
            priority=priority,
            created_by=created_by or "manual",
        )
        return _redirect_with_message(f"宸插垱寤?瀹氫綅瀹℃牳椤?{item['review_no']}")
    except Exception as exc:
        return _redirect_with_message(f"failed: {exc}", "error")


@router.post("/items/{review_item_id}/evidence")
def ui_add_evidence(
    review_item_id: int,
    source_url: str = Form(""),
    source_type: str = Form(""),
    source_grade: str = Form(""),
    source_title: str = Form(""),
    source_value: str = Form(""),
    source_excerpt: str = Form(""),
    actor: str = Form("manual"),
):
    try:
        add_evidence(
            review_item_id,
            {
                "source_url": source_url,
                "source_type": source_type,
                "source_grade": source_grade,
                "source_title": source_title,
                "source_value": source_value,
                "source_excerpt": source_excerpt,
            },
            actor=actor,
        )
        return _redirect_with_message("ok")
    except Exception as exc:
        return _redirect_with_message(f"failed: {exc}", "error")


@router.post("/items/{review_item_id}/resolve")
def ui_resolve_review_item(
    review_item_id: int,
    decision: ReviewStatus = Form(...),
    actor: str = Form("manual"),
    note: str = Form(""),
    resolved_value: str = Form(""),
    fact_level: FactLevel | None = Form(None),
):
    try:
        item = resolve_review_item(
            review_item_id,
            decision=decision,
            actor=actor or "manual",
            note=note,
            resolved_value=resolved_value,
            fact_level=fact_level,
        )
        return _redirect_with_message(
            f"{item['review_no']} 宸叉洿鏂颁负 {STATUS_LABELS.get(item['status'], item['status'])}"
        )
    except Exception as exc:
        return _redirect_with_message(f"failed: {exc}", "error")


@router.post("/batch")
def ui_batch_resolve(
    selected_ids: list[int] = Form(default=[]),
    decision: ReviewStatus = Form(...),
    actor: str = Form("manual"),
    note: str = Form(""),
):
    try:
        result = batch_resolve(
            selected_ids,
            decision=decision,
            actor=actor or "manual",
            note=note,
        )
        message = f"batch resolved: success={len(result['succeeded'])} failed={len(result['failed'])}"
        return _redirect_with_message(message, "error" if result["failed"] else "ok")
    except Exception as exc:
        return _redirect_with_message(f"failed: {exc}", "error")

@router.post("/relations")
def ui_create_relation(
    left_type: str = Form(...),
    left_id: str = Form(""),
    left_label: str = Form(""),
    relation_type: str = Form(...),
    right_type: str = Form(...),
    right_id: str = Form(""),
    right_label: str = Form(""),
    confidence: float | None = Form(None),
    basis: str = Form(""),
    source_url: str = Form(""),
):
    try:
        relation = create_pending_relation(
            left_type=left_type,
            left_id=left_id,
            left_label=left_label,
            relation_type=relation_type,
            right_type=right_type,
            right_id=right_id,
            right_label=right_label,
            confidence=confidence,
            basis=basis,
            source_url=source_url,
        )
        return _redirect_with_message(f"relation {relation['relation_no']} created")
    except Exception as exc:
        return _redirect_with_message(f"failed: {exc}", "error")


@router.post("/relations/{relation_id}/decide")
def ui_decide_relation(
    relation_id: int,
    decision: Literal["approved", "rejected", "deferred"] = Form(...),
    reviewer: str = Form("manual"),
    note: str = Form(""),
):
    try:
        relation = decide_pending_relation(
            relation_id,
            decision=decision,
            reviewer=reviewer or "manual",
            note=note,
        )
        return _redirect_with_message(
            f"{relation['relation_no']} 宸叉洿鏂颁负 {STATUS_LABELS.get(relation['status'], relation['status'])}"
        )
    except Exception as exc:
        return _redirect_with_message(f"failed: {exc}", "error")


@router.post("/claims")
def ui_register_claim(
    subject_type: str = Form(...),
    subject_id: str = Form(""),
    subject_label: str = Form(""),
    predicate: str = Form(...),
    object_value: str = Form(...),
    claim_type: FactLevel = Form(...),
    confidence: float | None = Form(None),
    source_url: str = Form(""),
    source_grade: str = Form(""),
    basis: str = Form(""),
    created_by: str = Form("manual"),
):
    try:
        claim = register_claim(
            subject_type=subject_type,
            subject_id=subject_id,
            subject_label=subject_label,
            predicate=predicate,
            object_value=object_value,
            claim_type=claim_type,
            confidence=confidence,
            source_url=source_url,
            source_grade=source_grade,
            basis=basis,
            created_by=created_by or "manual",
        )
        return _redirect_with_message(
            f"涓诲紶 {claim['claim_no']} 宸茬櫥璁帮紱{FACT_LABELS.get(claim_type, claim_type)}涓嶄細鑷姩瑕嗙洊姝ｅ紡鏁版嵁"
        )
    except Exception as exc:
        return _redirect_with_message(f"failed: {exc}", "error")


@router.get("/health")
def v04c_health():
    path = ensure_v04c_schema()
    with db_connection(path) as conn:
        table_count = conn.execute(
            "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v04c_%'"
        ).fetchone()["c"]
        pending = conn.execute(
            "SELECT COUNT(*) AS c FROM v04c_review_items WHERE status IN ('pending','in_review','deferred')"
        ).fetchone()["c"]
    return {
        "ok": table_count >= 6,
        "version": "0.4C",
        "database": str(path),
        "v04c_table_count": table_count,
        "open_review_items": pending,
    }






