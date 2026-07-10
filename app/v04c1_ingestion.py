from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Iterator, Literal

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.v04c_review import (
    FACT_LABELS,
    STATUS_LABELS,
    add_evidence,
    create_pending_relation,
    create_review_item,
    db_connection,
    default_db_path,
    ensure_v04c_schema,
)

router = APIRouter(prefix="/review/intake", tags=["v0.4C-1 真实数据接入"])

MODULE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = MODULE_DIR.parent
TEMPLATE_DIR = MODULE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

FactLevel = Literal["fact", "inference", "unknown"]

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS v04c1_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v04c1_ingest_batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_no TEXT NOT NULL UNIQUE,
    source_name TEXT NOT NULL,
    source_type TEXT,
    status TEXT NOT NULL DEFAULT 'processing',
    total_records INTEGER NOT NULL DEFAULT 0,
    success_records INTEGER NOT NULL DEFAULT 0,
    processed_records INTEGER NOT NULL DEFAULT 0,
    duplicate_records INTEGER NOT NULL DEFAULT 0,
    conflict_records INTEGER NOT NULL DEFAULT 0,
    needs_structuring_records INTEGER NOT NULL DEFAULT 0,
    failed_records INTEGER NOT NULL DEFAULT 0,
    raw_payload_json TEXT,
    created_by TEXT NOT NULL DEFAULT 'manual',
    note TEXT,
    created_at TEXT NOT NULL,
    completed_at TEXT,
    CHECK (status IN ('processing','completed','partial','failed'))
);

CREATE TABLE IF NOT EXISTS v04c1_source_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_no TEXT NOT NULL UNIQUE,
    batch_id INTEGER,
    external_key TEXT,
    source_name TEXT NOT NULL,
    source_type TEXT,
    source_grade TEXT,
    source_url TEXT,
    title TEXT,
    published_at TEXT,
    captured_at TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'received',
    candidate_count INTEGER NOT NULL DEFAULT 0,
    error_message TEXT,
    created_at TEXT NOT NULL,
    processed_at TEXT,
    FOREIGN KEY(batch_id) REFERENCES v04c1_ingest_batches(id) ON DELETE SET NULL,
    CHECK (status IN ('received','processed','duplicate','needs_structuring','failed'))
);

CREATE INDEX IF NOT EXISTS ix_v04c1_source_batch
ON v04c1_source_records(batch_id, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_v04c1_source_status
ON v04c1_source_records(status, created_at DESC);

CREATE INDEX IF NOT EXISTS ix_v04c1_source_hash
ON v04c1_source_records(source_name, content_hash);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04c1_source_external_key
ON v04c1_source_records(source_name, external_key)
WHERE external_key IS NOT NULL AND external_key <> '';

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04c1_source_content_hash
ON v04c1_source_records(source_name, content_hash);

CREATE TABLE IF NOT EXISTS v04c1_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_no TEXT NOT NULL UNIQUE,
    source_record_id INTEGER NOT NULL,
    candidate_type TEXT NOT NULL DEFAULT 'field',
    subject_type TEXT NOT NULL,
    subject_key TEXT NOT NULL,
    subject_id TEXT,
    subject_label TEXT,
    field_name TEXT,
    candidate_value TEXT,
    normalized_value TEXT,
    fact_level TEXT NOT NULL DEFAULT 'unknown',
    confidence REAL,
    current_value TEXT,
    comparison_result TEXT NOT NULL,
    review_item_id INTEGER,
    pending_relation_id INTEGER,
    status TEXT NOT NULL DEFAULT 'pending_review',
    metadata_json TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(source_record_id) REFERENCES v04c1_source_records(id) ON DELETE CASCADE,
    FOREIGN KEY(review_item_id) REFERENCES v04c_review_items(id) ON DELETE SET NULL,
    FOREIGN KEY(pending_relation_id) REFERENCES v04c_pending_relations(id) ON DELETE SET NULL,
    CHECK (candidate_type IN ('field','relation')),
    CHECK (fact_level IN ('fact','inference','unknown')),
    CHECK (status IN ('pending_review','waiting_fact','matched','relation_pending','synced','rejected','failed'))
);

CREATE INDEX IF NOT EXISTS ix_v04c1_candidate_review
ON v04c1_candidates(review_item_id, status);

CREATE INDEX IF NOT EXISTS ix_v04c1_candidate_subject
ON v04c1_candidates(subject_type, subject_key, field_name, created_at DESC);

CREATE TABLE IF NOT EXISTS v04c1_canonical_facts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_no TEXT NOT NULL UNIQUE,
    subject_type TEXT NOT NULL,
    subject_key TEXT NOT NULL,
    subject_id TEXT,
    subject_label TEXT,
    field_name TEXT NOT NULL,
    fact_value TEXT NOT NULL,
    normalized_value TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    is_current INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'active',
    source_review_item_id INTEGER,
    source_record_id INTEGER,
    confirmed_by TEXT,
    confirmed_at TEXT NOT NULL,
    superseded_at TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(source_review_item_id) REFERENCES v04c_review_items(id) ON DELETE SET NULL,
    FOREIGN KEY(source_record_id) REFERENCES v04c1_source_records(id) ON DELETE SET NULL,
    CHECK (is_current IN (0,1)),
    CHECK (status IN ('active','superseded','withdrawn'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04c1_current_fact
ON v04c1_canonical_facts(subject_type, subject_key, field_name)
WHERE is_current = 1 AND status = 'active';

CREATE INDEX IF NOT EXISTS ix_v04c1_fact_subject
ON v04c1_canonical_facts(subject_type, subject_key, field_name, version DESC);

CREATE TABLE IF NOT EXISTS v04c1_fact_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fact_id INTEGER NOT NULL,
    source_record_id INTEGER,
    review_item_id INTEGER,
    source_url TEXT,
    source_title TEXT,
    source_excerpt TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(fact_id) REFERENCES v04c1_canonical_facts(id) ON DELETE CASCADE,
    FOREIGN KEY(source_record_id) REFERENCES v04c1_source_records(id) ON DELETE SET NULL,
    FOREIGN KEY(review_item_id) REFERENCES v04c_review_items(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04c1_fact_evidence_once
ON v04c1_fact_evidence(
    fact_id,
    COALESCE(source_record_id, 0),
    COALESCE(source_url, ''),
    COALESCE(source_excerpt, '')
);

CREATE TABLE IF NOT EXISTS v04c1_canonical_relations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    relation_no TEXT NOT NULL UNIQUE,
    left_type TEXT NOT NULL,
    left_key TEXT NOT NULL,
    left_id TEXT,
    left_label TEXT,
    relation_type TEXT NOT NULL,
    right_type TEXT NOT NULL,
    right_key TEXT NOT NULL,
    right_id TEXT,
    right_label TEXT,
    source_pending_relation_id INTEGER,
    confirmed_by TEXT,
    confirmed_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(source_pending_relation_id) REFERENCES v04c_pending_relations(id) ON DELETE SET NULL
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04c1_canonical_relation
ON v04c1_canonical_relations(left_type, left_key, relation_type, right_type, right_key);

CREATE TABLE IF NOT EXISTS v04c1_sync_mappings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_type TEXT NOT NULL,
    field_name TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_id_column TEXT NOT NULL,
    target_field_column TEXT NOT NULL,
    target_label_column TEXT,
    allow_insert INTEGER NOT NULL DEFAULT 0,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (allow_insert IN (0,1)),
    CHECK (enabled IN (0,1))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04c1_mapping
ON v04c1_sync_mappings(subject_type, field_name, target_table, target_field_column);

CREATE TABLE IF NOT EXISTS v04c1_sync_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    review_item_id INTEGER,
    candidate_id INTEGER,
    sync_target TEXT NOT NULL,
    action TEXT NOT NULL,
    status TEXT NOT NULL,
    before_json TEXT,
    after_json TEXT,
    error_message TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(review_item_id) REFERENCES v04c_review_items(id) ON DELETE SET NULL,
    FOREIGN KEY(candidate_id) REFERENCES v04c1_candidates(id) ON DELETE SET NULL,
    CHECK (status IN ('success','skipped','failed'))
);

CREATE INDEX IF NOT EXISTS ix_v04c1_sync_review
ON v04c1_sync_logs(review_item_id, created_at DESC);
"""

IDENTIFIER_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
RAW_TABLE_HINTS = ("raw", "intel", "intelligence", "import", "source", "clue", "lead")
SYSTEM_TABLE_PREFIXES = ("sqlite_", "v04c_", "v04c1_")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).strip().lower().split())
    return text.replace("，", ",").replace("。", ".")


def _subject_key(subject_id: Any, subject_label: Any, subject_type: Any) -> str:
    raw = subject_id or subject_label or subject_type or "unknown"
    return _normalize_text(raw)


def _content_hash(payload: Any) -> str:
    text = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def ensure_v04c1_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> Path:
    ensure_v04c_schema(db_path, allow_migration=allow_migration)
    path = Path(db_path) if db_path else default_db_path()
    if not allow_migration:
        return path
    with db_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
        _ensure_column(conn, "v04c1_ingest_batches", "success_records", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "v04c1_ingest_batches", "conflict_records", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "v04c1_ingest_batches", "needs_structuring_records", "INTEGER NOT NULL DEFAULT 0")
        _ensure_column(conn, "v04c1_ingest_batches", "raw_payload_json", "TEXT")
    return path


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
    existing = {row["name"] for row in conn.execute(f'PRAGMA table_info("{table}")').fetchall()}
    if column not in existing:
        conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}')


def _next_number(conn: sqlite3.Connection, prefix: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    now = utc_now()
    # 单条 UPSERT 原子递增，避免并发接入时生成重复编号。
    row = conn.execute(
        """
        INSERT INTO v04c1_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
            seq_value = CASE
                WHEN v04c1_sequence_counters.seq_date = excluded.seq_date
                THEN v04c1_sequence_counters.seq_value + 1
                ELSE 1
            END,
            seq_date = excluded.seq_date,
            updated_at = excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, today, now),
    ).fetchone()
    value = int(row["seq_value"])
    return f"{prefix}-{today}-{value:04d}"


def _clamp_confidence(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return None


def _fact_level(value: Any) -> FactLevel:
    normalized = _normalize_text(value)
    aliases = {
        "fact": "fact",
        "事实": "fact",
        "confirmed": "fact",
        "inference": "inference",
        "推测": "inference",
        "estimate": "inference",
        "unknown": "unknown",
        "待判定": "unknown",
        "": "unknown",
    }
    return aliases.get(normalized, "unknown")  # type: ignore[return-value]


def _source_evidence(record: dict[str, Any], field: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_url": record.get("source_url") or field.get("source_url"),
        "source_type": record.get("source_type") or field.get("source_type"),
        "source_grade": record.get("source_grade") or field.get("source_grade"),
        "source_title": record.get("title") or field.get("source_title"),
        "source_value": field.get("value") or field.get("object_value") or field.get("proposed_value"),
        "source_excerpt": field.get("excerpt") or field.get("basis") or record.get("excerpt"),
        "published_at": record.get("published_at") or field.get("published_at"),
        "captured_at": record.get("captured_at") or utc_now(),
        "is_primary": bool(field.get("is_primary", False)),
        "supports_fact": _fact_level(field.get("fact_level") or field.get("claim_type")) == "fact",
        "metadata": field.get("metadata") or {},
    }


def _find_current_fact(
    conn: sqlite3.Connection,
    subject_type: str,
    subject_key: str,
    field_name: str,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT * FROM v04c1_canonical_facts
        WHERE subject_type = ? AND subject_key = ? AND field_name = ?
          AND is_current = 1 AND status = 'active'
        LIMIT 1
        """,
        (subject_type, subject_key, field_name),
    ).fetchone()


def _attach_fact_evidence(
    conn: sqlite3.Connection,
    *,
    fact_id: int,
    source_record_id: int | None,
    review_item_id: int | None = None,
    source_url: str | None = None,
    source_title: str | None = None,
    source_excerpt: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT OR IGNORE INTO v04c1_fact_evidence(
            fact_id, source_record_id, review_item_id, source_url,
            source_title, source_excerpt, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fact_id,
            source_record_id,
            review_item_id,
            source_url or None,
            source_title or None,
            source_excerpt or None,
            utc_now(),
        ),
    )


def _find_open_reviews(
    conn: sqlite3.Connection,
    subject_type: str,
    subject_id: str | None,
    subject_label: str | None,
    field_name: str,
) -> list[sqlite3.Row]:
    where_subject = "subject_id = ?" if subject_id else "COALESCE(subject_label,'') = ?"
    subject_value = subject_id if subject_id else (subject_label or "")
    return conn.execute(
        f"""
        SELECT * FROM v04c_review_items
        WHERE subject_type = ? AND {where_subject} AND field_name = ?
          AND status IN ('pending','in_review','deferred')
        ORDER BY id ASC
        """,
        (subject_type, subject_value, field_name),
    ).fetchall()


def _evidence_exists(conn: sqlite3.Connection, review_item_id: int, evidence: dict[str, Any]) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM v04c_review_evidence
        WHERE review_item_id = ?
          AND COALESCE(source_url,'') = ?
          AND COALESCE(source_value,'') = ?
          AND COALESCE(source_excerpt,'') = ?
        LIMIT 1
        """,
        (
            review_item_id,
            evidence.get("source_url") or "",
            str(evidence.get("source_value") or ""),
            evidence.get("source_excerpt") or "",
        ),
    ).fetchone()
    return row is not None


def _attach_evidence_once(review_item_id: int, evidence: dict[str, Any], db_path: str | Path | None) -> None:
    with db_connection(db_path) as conn:
        exists = _evidence_exists(conn, review_item_id, evidence)
    if not exists:
        add_evidence(review_item_id, evidence, actor="v04c1_ingestion", db_path=db_path)


def _insert_candidate(
    conn: sqlite3.Connection,
    *,
    source_record_id: int,
    candidate_type: str,
    subject_type: str,
    subject_key: str,
    subject_id: str | None,
    subject_label: str | None,
    field_name: str | None,
    candidate_value: str | None,
    fact_level: FactLevel,
    confidence: float | None,
    current_value: str | None,
    comparison_result: str,
    review_item_id: int | None,
    pending_relation_id: int | None,
    status: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = utc_now()
    candidate_no = _next_number(conn, "CND")
    cursor = conn.execute(
        """
        INSERT INTO v04c1_candidates(
            candidate_no, source_record_id, candidate_type, subject_type,
            subject_key, subject_id, subject_label, field_name, candidate_value,
            normalized_value, fact_level, confidence, current_value,
            comparison_result, review_item_id, pending_relation_id, status,
            metadata_json, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            candidate_no,
            source_record_id,
            candidate_type,
            subject_type,
            subject_key,
            subject_id or None,
            subject_label or None,
            field_name or None,
            candidate_value or None,
            _normalize_text(candidate_value),
            fact_level,
            confidence,
            current_value or None,
            comparison_result,
            review_item_id,
            pending_relation_id,
            status,
            _json_dumps(metadata or {}),
            now,
            now,
        ),
    )
    row = conn.execute("SELECT * FROM v04c1_candidates WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return dict(row)


def _iter_field_candidates(record: dict[str, Any]) -> Iterator[dict[str, Any]]:
    def normalize_fields(subject: dict[str, Any], fields: Any) -> Iterator[dict[str, Any]]:
        if isinstance(fields, dict):
            fields = [{"name": key, "value": value} for key, value in fields.items()]
        if not isinstance(fields, list):
            return
        for raw in fields:
            if not isinstance(raw, dict):
                continue
            field_name = raw.get("name") or raw.get("field_name") or raw.get("predicate")
            value = raw.get("value")
            if value is None:
                value = raw.get("object_value")
            if value is None:
                value = raw.get("proposed_value")
            if not field_name or value is None:
                continue
            yield {
                **raw,
                "subject_type": subject.get("subject_type") or subject.get("type") or record.get("subject_type") or "unknown",
                "subject_id": subject.get("subject_id") or subject.get("id") or record.get("subject_id"),
                "subject_label": subject.get("subject_label") or subject.get("label") or subject.get("name") or record.get("subject_label"),
                "field_name": str(field_name),
                "value": str(value),
            }

    subjects = record.get("subjects")
    if isinstance(subjects, list):
        for subject in subjects:
            if not isinstance(subject, dict):
                continue
            yield from normalize_fields(subject, subject.get("fields") or subject.get("claims") or [])

    if record.get("fields") is not None or record.get("claims") is not None:
        subject = {
            "subject_type": record.get("subject_type") or "unknown",
            "subject_id": record.get("subject_id"),
            "subject_label": record.get("subject_label") or record.get("subject_name"),
        }
        yield from normalize_fields(subject, record.get("fields") or record.get("claims") or [])


def _iter_relation_candidates(record: dict[str, Any]) -> Iterator[dict[str, Any]]:
    relations = record.get("relations") or []
    if not isinstance(relations, list):
        return
    for relation in relations:
        if not isinstance(relation, dict):
            continue
        relation_type = relation.get("relation_type") or relation.get("type")
        left_type = relation.get("left_type") or relation.get("source_type")
        right_type = relation.get("right_type") or relation.get("target_type")
        if not relation_type or not left_type or not right_type:
            continue
        yield relation


def process_field_candidate(
    source_record_id: int,
    record: dict[str, Any],
    field: dict[str, Any],
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04c1_schema(db_path)
    subject_type = str(field.get("subject_type") or "unknown").strip() or "unknown"
    subject_id = str(field.get("subject_id") or "").strip() or None
    subject_label = str(field.get("subject_label") or "").strip() or None
    field_name = str(field.get("field_name") or "").strip()
    candidate_value = str(field.get("value") or "").strip()
    fact_level = _fact_level(field.get("fact_level") or field.get("claim_type"))
    confidence = _clamp_confidence(field.get("confidence"))
    subject_key = _subject_key(subject_id, subject_label, subject_type)
    normalized = _normalize_text(candidate_value)
    evidence = _source_evidence(record, field)

    with db_connection(db_path) as conn:
        current_fact = _find_current_fact(conn, subject_type, subject_key, field_name)
        open_reviews = _find_open_reviews(conn, subject_type, subject_id, subject_label, field_name)

    current_value = current_fact["fact_value"] if current_fact else None
    comparison_result = "new_pending"
    item_type = "fact_check"
    review_item: dict[str, Any] | None = None
    status = "pending_review"

    if current_fact and _normalize_text(current_fact["fact_value"]) == normalized:
        comparison_result = "matched_fact"
        status = "matched"
        with db_connection(db_path) as conn:
            _attach_fact_evidence(
                conn,
                fact_id=int(current_fact["id"]),
                source_record_id=source_record_id,
                source_url=evidence.get("source_url"),
                source_title=evidence.get("source_title"),
                source_excerpt=evidence.get("source_excerpt"),
            )
    else:
        matching_open = next(
            (row for row in open_reviews if _normalize_text(row["proposed_value"]) == normalized),
            None,
        )
        different_open = next(
            (row for row in open_reviews if _normalize_text(row["proposed_value"]) != normalized),
            None,
        )

        if fact_level == "inference":
            comparison_result = "inference_pending"
            item_type = "fact_check"
        elif fact_level == "unknown":
            comparison_result = "unknown_pending"
            item_type = "fact_check"
        elif current_fact:
            comparison_result = "conflict_fact"
            item_type = "conflict"
        elif different_open:
            comparison_result = "conflict_candidate"
            item_type = "conflict"
            current_value = different_open["proposed_value"]
        elif matching_open:
            comparison_result = "duplicate_candidate"
        else:
            comparison_result = "new_pending"

        if matching_open:
            review_item = dict(matching_open)
            _attach_evidence_once(int(review_item["id"]), evidence, db_path)
        else:
            review_item = create_review_item(
                item_type=item_type,
                subject_type=subject_type,
                subject_id=subject_id,
                subject_label=subject_label,
                field_name=field_name,
                current_value=current_value,
                proposed_value=candidate_value,
                fact_level=fact_level,
                priority=None,
                created_by="v04c1_ingestion",
                evidence=[evidence],
                db_path=db_path,
            )
            _attach_evidence_once(int(review_item["id"]), evidence, db_path)

    with db_connection(db_path) as conn:
        candidate = _insert_candidate(
            conn,
            source_record_id=source_record_id,
            candidate_type="field",
            subject_type=subject_type,
            subject_key=subject_key,
            subject_id=subject_id,
            subject_label=subject_label,
            field_name=field_name,
            candidate_value=candidate_value,
            fact_level=fact_level,
            confidence=confidence,
            current_value=current_value,
            comparison_result=comparison_result,
            review_item_id=int(review_item["id"]) if review_item else None,
            pending_relation_id=None,
            status=status,
            metadata={"excerpt": field.get("excerpt") or field.get("basis"), "raw": field},
        )
    return candidate


def process_relation_candidate(
    source_record_id: int,
    record: dict[str, Any],
    relation: dict[str, Any],
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    left_type = str(relation.get("left_type") or relation.get("source_type") or "unknown")
    left_id = str(relation.get("left_id") or relation.get("source_id") or "").strip() or None
    left_label = str(relation.get("left_label") or relation.get("source_label") or "").strip() or None
    relation_type = str(relation.get("relation_type") or relation.get("type") or "关联")
    right_type = str(relation.get("right_type") or relation.get("target_type") or "unknown")
    right_id = str(relation.get("right_id") or relation.get("target_id") or "").strip() or None
    right_label = str(relation.get("right_label") or relation.get("target_label") or "").strip() or None
    fact_level = _fact_level(relation.get("fact_level") or relation.get("claim_type") or "inference")
    if fact_level == "fact":
        # 自动识别出的关联仍先按推测进入队列，人工通过后才成为事实。
        fact_level = "inference"
    confidence = _clamp_confidence(relation.get("confidence"))
    basis = relation.get("basis") or relation.get("excerpt") or record.get("excerpt")
    source_url = relation.get("source_url") or record.get("source_url")

    pending_relation = create_pending_relation(
        left_type=left_type,
        left_id=left_id,
        left_label=left_label,
        relation_type=relation_type,
        right_type=right_type,
        right_id=right_id,
        right_label=right_label,
        confidence=confidence,
        basis=str(basis or ""),
        source_url=str(source_url or "") or None,
        fact_level=fact_level,
        db_path=db_path,
    )

    relation_text = f"{left_label or left_id or left_type} —{relation_type}→ {right_label or right_id or right_type}"
    with db_connection(db_path) as conn:
        candidate = _insert_candidate(
            conn,
            source_record_id=source_record_id,
            candidate_type="relation",
            subject_type=left_type,
            subject_key=_subject_key(left_id, left_label, left_type),
            subject_id=left_id,
            subject_label=left_label,
            field_name=relation_type,
            candidate_value=relation_text,
            fact_level="inference",
            confidence=confidence,
            current_value=None,
            comparison_result="relation_pending",
            review_item_id=int(pending_relation["source_review_item_id"]) if pending_relation.get("source_review_item_id") else None,
            pending_relation_id=int(pending_relation["id"]),
            status="relation_pending",
            metadata={"raw": relation},
        )
    return candidate


def ingest_record(
    record: dict[str, Any],
    *,
    batch_id: int | None,
    default_source_name: str,
    default_source_type: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04c1_schema(db_path)
    source_name = str(record.get("source_name") or default_source_name or "manual").strip() or "manual"
    external_key = str(record.get("external_key") or record.get("id") or "").strip() or None
    content_hash = _content_hash(record)
    now = utc_now()

    with db_connection(db_path) as conn:
        if external_key:
            duplicate = conn.execute(
                "SELECT * FROM v04c1_source_records WHERE source_name = ? AND external_key = ? ORDER BY id DESC LIMIT 1",
                (source_name, external_key),
            ).fetchone()
        else:
            duplicate = conn.execute(
                "SELECT * FROM v04c1_source_records WHERE source_name = ? AND content_hash = ? ORDER BY id DESC LIMIT 1",
                (source_name, content_hash),
            ).fetchone()
        if duplicate:
            return {"record": dict(duplicate), "duplicate": True, "candidates": []}

        record_no = _next_number(conn, "SRC")
        cursor = conn.execute(
            """
            INSERT INTO v04c1_source_records(
                record_no, batch_id, external_key, source_name, source_type,
                source_grade, source_url, title, published_at, captured_at,
                content_hash, payload_json, status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'received', ?)
            """,
            (
                record_no,
                batch_id,
                external_key,
                source_name,
                record.get("source_type") or default_source_type,
                record.get("source_grade"),
                record.get("source_url"),
                record.get("title"),
                record.get("published_at"),
                record.get("captured_at") or now,
                content_hash,
                _json_dumps(record),
                now,
            ),
        )
        source_record_id = int(cursor.lastrowid)

    candidates: list[dict[str, Any]] = []
    error_message: str | None = None
    try:
        for field in _iter_field_candidates(record):
            candidates.append(process_field_candidate(source_record_id, record, field, db_path=db_path))
        for relation in _iter_relation_candidates(record):
            candidates.append(process_relation_candidate(source_record_id, record, relation, db_path=db_path))
        final_status = "processed" if candidates else "needs_structuring"
    except Exception as exc:
        final_status = "failed"
        error_message = str(exc)

    with db_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE v04c1_source_records
            SET status = ?, candidate_count = ?, error_message = ?, processed_at = ?
            WHERE id = ?
            """,
            (final_status, len(candidates), error_message, utc_now(), source_record_id),
        )
        row = conn.execute("SELECT * FROM v04c1_source_records WHERE id = ?", (source_record_id,)).fetchone()

    if error_message:
        raise ValueError(error_message)
    return {"record": dict(row), "duplicate": False, "candidates": candidates}


def ingest_payload(
    payload: dict[str, Any] | list[Any],
    *,
    created_by: str = "manual",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04c1_schema(db_path)
    if isinstance(payload, list):
        payload = {"records": payload}
    if not isinstance(payload, dict):
        raise ValueError("JSON 顶层必须是对象或记录数组")

    batch_meta = payload.get("batch") if isinstance(payload.get("batch"), dict) else {}
    source_name = str(batch_meta.get("source_name") or payload.get("source_name") or "manual-json").strip() or "manual-json"
    source_type = str(batch_meta.get("source_type") or payload.get("source_type") or "json").strip() or "json"
    note = batch_meta.get("note") or payload.get("note")
    records = payload.get("records")
    if records is None:
        records = [payload]
    if not isinstance(records, list):
        raise ValueError("records 必须是数组")

    now = utc_now()
    with db_connection(db_path) as conn:
        batch_no = _next_number(conn, "BAT")
        cursor = conn.execute(
            """
            INSERT INTO v04c1_ingest_batches(
                batch_no, source_name, source_type, status, total_records,
                raw_payload_json, created_by, note, created_at
            ) VALUES (?, ?, ?, 'processing', ?, ?, ?, ?, ?)
            """,
            (
                batch_no,
                source_name,
                source_type,
                len(records),
                _json_dumps(payload),
                created_by or "manual",
                note,
                now,
            ),
        )
        batch_id = int(cursor.lastrowid)

    processed = 0
    duplicates = 0
    conflicts = 0
    needs_structuring = 0
    failed = 0
    results: list[dict[str, Any]] = []
    for raw in records:
        if not isinstance(raw, dict):
            failed += 1
            results.append({"error": "记录不是 JSON 对象"})
            continue
        try:
            result = ingest_record(
                raw,
                batch_id=batch_id,
                default_source_name=source_name,
                default_source_type=source_type,
                db_path=db_path,
            )
            results.append(result)
            if result["duplicate"]:
                duplicates += 1
            else:
                processed += 1
                record_status = result["record"].get("status")
                if record_status == "needs_structuring":
                    needs_structuring += 1
                if any(
                    str(candidate.get("comparison_result", "")).startswith("conflict")
                    for candidate in result.get("candidates", [])
                ):
                    conflicts += 1
        except Exception as exc:
            failed += 1
            results.append({"error": str(exc)})

    status = "completed" if failed == 0 else ("partial" if processed or duplicates else "failed")
    with db_connection(db_path) as conn:
        conn.execute(
            """
            UPDATE v04c1_ingest_batches
            SET status = ?, success_records = ?, processed_records = ?, duplicate_records = ?,
                conflict_records = ?, needs_structuring_records = ?, failed_records = ?, completed_at = ?
            WHERE id = ?
            """,
            (
                status,
                processed,
                processed,
                duplicates,
                conflicts,
                needs_structuring,
                failed,
                utc_now(),
                batch_id,
            ),
        )
        batch = conn.execute("SELECT * FROM v04c1_ingest_batches WHERE id = ?", (batch_id,)).fetchone()

    return {"batch": dict(batch), "results": results}


def discover_tables(db_path: str | Path | None = None) -> list[dict[str, Any]]:
    ensure_v04c1_schema(db_path)
    with db_connection(db_path) as conn:
        names = [
            row["name"]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            ).fetchall()
            if not row["name"].startswith(SYSTEM_TABLE_PREFIXES)
        ]
        result: list[dict[str, Any]] = []
        for name in names:
            if not IDENTIFIER_RE.match(name):
                continue
            columns = [row["name"] for row in conn.execute(f'PRAGMA table_info("{name}")').fetchall()]
            lower = name.lower()
            score = sum(1 for hint in RAW_TABLE_HINTS if hint in lower)
            result.append({"name": name, "columns": columns, "raw_score": score})
    return sorted(result, key=lambda row: (-row["raw_score"], row["name"]))


def _pick_column(columns: Iterable[str], candidates: Iterable[str]) -> str | None:
    by_lower = {column.lower(): column for column in columns}
    for candidate in candidates:
        if candidate.lower() in by_lower:
            return by_lower[candidate.lower()]
    return None


def import_existing_table(
    table_name: str,
    *,
    limit: int = 100,
    source_name: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    tables = {item["name"]: item for item in discover_tables(db_path)}
    if table_name not in tables:
        raise ValueError("表不存在或不允许导入")
    if not IDENTIFIER_RE.match(table_name):
        raise ValueError("非法表名")

    columns = tables[table_name]["columns"]
    id_col = _pick_column(columns, ("id", "raw_id", "intel_id", "intelligence_id"))
    title_col = _pick_column(columns, ("title", "name", "subject", "headline"))
    url_col = _pick_column(columns, ("source_url", "url", "link"))
    source_col = _pick_column(columns, ("source_name", "source", "platform"))
    grade_col = _pick_column(columns, ("source_grade", "grade"))
    published_col = _pick_column(columns, ("published_at", "event_date", "date", "occurred_at"))
    payload_col = _pick_column(columns, ("payload_json", "raw_json", "data_json", "json_data", "metadata_json"))
    content_col = _pick_column(columns, ("content", "summary", "description", "body", "raw_text", "text"))

    with db_connection(db_path) as conn:
        rows = conn.execute(f'SELECT * FROM "{table_name}" ORDER BY rowid DESC LIMIT ?', (max(1, min(int(limit), 1000)),)).fetchall()

    records: list[dict[str, Any]] = []
    for row in rows:
        row_dict = dict(row)
        parsed: dict[str, Any] = {}
        if payload_col and row_dict.get(payload_col):
            try:
                loaded = json.loads(row_dict[payload_col])
                if isinstance(loaded, dict):
                    parsed = loaded
            except (TypeError, json.JSONDecodeError):
                parsed = {}
        record = {
            **parsed,
            "external_key": f"{table_name}:{row_dict.get(id_col) if id_col else row_dict.get('rowid', _content_hash(row_dict)[:12])}",
            "source_name": row_dict.get(source_col) if source_col else (source_name or table_name),
            "source_type": f"database:{table_name}",
            "source_grade": row_dict.get(grade_col) if grade_col else None,
            "source_url": row_dict.get(url_col) if url_col else None,
            "title": row_dict.get(title_col) if title_col else None,
            "published_at": row_dict.get(published_col) if published_col else None,
            "excerpt": row_dict.get(content_col) if content_col else None,
            "legacy_row": row_dict,
        }
        records.append(record)

    return ingest_payload(
        {
            "batch": {
                "source_name": source_name or table_name,
                "source_type": f"database:{table_name}",
                "note": f"从现有数据表 {table_name} 导入",
            },
            "records": records,
        },
        created_by="existing-table-import",
        db_path=db_path,
    )


def _safe_identifier(value: str, label: str) -> str:
    if not IDENTIFIER_RE.match(value or ""):
        raise ValueError(f"{label}不是安全的数据库标识符")
    return value


def create_sync_mapping(
    *,
    subject_type: str,
    field_name: str,
    target_table: str,
    target_id_column: str,
    target_field_column: str,
    target_label_column: str | None = None,
    allow_insert: bool = False,
    enabled: bool = True,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04c1_schema(db_path)
    target_table = _safe_identifier(target_table, "目标表")
    target_id_column = _safe_identifier(target_id_column, "ID列")
    target_field_column = _safe_identifier(target_field_column, "字段列")
    if target_label_column:
        target_label_column = _safe_identifier(target_label_column, "名称列")

    catalog = {item["name"]: set(item["columns"]) for item in discover_tables(db_path)}
    if target_table not in catalog:
        raise ValueError("目标表不存在")
    required = {target_id_column, target_field_column}
    if target_label_column:
        required.add(target_label_column)
    missing = required - catalog[target_table]
    if missing:
        raise ValueError(f"目标表缺少列：{', '.join(sorted(missing))}")

    now = utc_now()
    with db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO v04c1_sync_mappings(
                subject_type, field_name, target_table, target_id_column,
                target_field_column, target_label_column, allow_insert,
                enabled, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(subject_type, field_name, target_table, target_field_column)
            DO UPDATE SET target_id_column = excluded.target_id_column,
                          target_label_column = excluded.target_label_column,
                          allow_insert = excluded.allow_insert,
                          enabled = excluded.enabled,
                          updated_at = excluded.updated_at
            """,
            (
                subject_type.strip(),
                field_name.strip(),
                target_table,
                target_id_column,
                target_field_column,
                target_label_column or None,
                1 if allow_insert else 0,
                1 if enabled else 0,
                now,
                now,
            ),
        )
        row = conn.execute(
            """
            SELECT * FROM v04c1_sync_mappings
            WHERE subject_type = ? AND field_name = ? AND target_table = ? AND target_field_column = ?
            """,
            (subject_type.strip(), field_name.strip(), target_table, target_field_column),
        ).fetchone()
    return dict(row)


def _log_sync(
    conn: sqlite3.Connection,
    *,
    review_item_id: int | None,
    candidate_id: int | None,
    sync_target: str,
    action: str,
    status: str,
    before: Any = None,
    after: Any = None,
    error: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO v04c1_sync_logs(
            review_item_id, candidate_id, sync_target, action, status,
            before_json, after_json, error_message, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            review_item_id,
            candidate_id,
            sync_target,
            action,
            status,
            _json_dumps(before) if before is not None else None,
            _json_dumps(after) if after is not None else None,
            error,
            utc_now(),
        ),
    )


def _upsert_canonical_fact(
    conn: sqlite3.Connection,
    *,
    review: sqlite3.Row,
    candidate: sqlite3.Row,
    fact_value: str,
    actor: str,
) -> tuple[str, dict[str, Any]]:
    subject_type = candidate["subject_type"]
    subject_key = candidate["subject_key"]
    field_name = candidate["field_name"]
    normalized = _normalize_text(fact_value)
    current = _find_current_fact(conn, subject_type, subject_key, field_name)

    if current and current["normalized_value"] == normalized:
        source = conn.execute(
            "SELECT source_url, title, payload_json FROM v04c1_source_records WHERE id = ?",
            (candidate["source_record_id"],),
        ).fetchone()
        source_excerpt = None
        if source and source["payload_json"]:
            try:
                payload = json.loads(source["payload_json"])
                source_excerpt = payload.get("excerpt") if isinstance(payload, dict) else None
            except json.JSONDecodeError:
                source_excerpt = None
        _attach_fact_evidence(
            conn,
            fact_id=int(current["id"]),
            source_record_id=candidate["source_record_id"],
            review_item_id=review["id"],
            source_url=source["source_url"] if source else None,
            source_title=source["title"] if source else None,
            source_excerpt=source_excerpt,
        )
        return "unchanged", dict(current)

    version = int(current["version"]) + 1 if current else 1
    now = utc_now()
    if current:
        conn.execute(
            """
            UPDATE v04c1_canonical_facts
            SET is_current = 0, status = 'superseded', superseded_at = ?
            WHERE id = ?
            """,
            (now, current["id"]),
        )
    fact_no = _next_number(conn, "FCT")
    cursor = conn.execute(
        """
        INSERT INTO v04c1_canonical_facts(
            fact_no, subject_type, subject_key, subject_id, subject_label,
            field_name, fact_value, normalized_value, version, is_current,
            status, source_review_item_id, source_record_id, confirmed_by,
            confirmed_at, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, 'active', ?, ?, ?, ?, ?)
        """,
        (
            fact_no,
            subject_type,
            subject_key,
            candidate["subject_id"],
            candidate["subject_label"],
            field_name,
            fact_value,
            normalized,
            version,
            review["id"],
            candidate["source_record_id"],
            actor,
            now,
            now,
        ),
    )
    row = conn.execute("SELECT * FROM v04c1_canonical_facts WHERE id = ?", (cursor.lastrowid,)).fetchone()
    _attach_fact_evidence(
        conn,
        fact_id=int(row["id"]),
        source_record_id=candidate["source_record_id"],
        review_item_id=review["id"],
    )
    return ("updated" if current else "inserted"), dict(row)


def _apply_mapping(
    conn: sqlite3.Connection,
    *,
    mapping: sqlite3.Row,
    candidate: sqlite3.Row,
    fact_value: str,
    review_item_id: int,
) -> None:
    table = _safe_identifier(mapping["target_table"], "目标表")
    id_col = _safe_identifier(mapping["target_id_column"], "ID列")
    field_col = _safe_identifier(mapping["target_field_column"], "字段列")
    label_col = mapping["target_label_column"]
    if label_col:
        label_col = _safe_identifier(label_col, "名称列")

    subject_id = candidate["subject_id"]
    if not subject_id:
        _log_sync(
            conn,
            review_item_id=review_item_id,
            candidate_id=candidate["id"],
            sync_target=f"{table}.{field_col}",
            action="mapping",
            status="skipped",
            error="候选记录没有 subject_id，无法定位业务表记录",
        )
        return

    matches = conn.execute(
        f'SELECT * FROM "{table}" WHERE CAST("{id_col}" AS TEXT) = ? LIMIT 2',
        (str(subject_id),),
    ).fetchall()
    if len(matches) > 1:
        _log_sync(
            conn,
            review_item_id=review_item_id,
            candidate_id=candidate["id"],
            sync_target=f"{table}.{field_col}",
            action="mapping",
            status="skipped",
            error="target object is not unique",
        )
        return
    existing = matches[0] if matches else None
    if existing:
        before = dict(existing)
        conn.execute(
            f'UPDATE "{table}" SET "{field_col}" = ? WHERE CAST("{id_col}" AS TEXT) = ?',
            (fact_value, str(subject_id)),
        )
        after = conn.execute(
            f'SELECT * FROM "{table}" WHERE CAST("{id_col}" AS TEXT) = ? LIMIT 1',
            (str(subject_id),),
        ).fetchone()
        _log_sync(
            conn,
            review_item_id=review_item_id,
            candidate_id=candidate["id"],
            sync_target=f"{table}.{field_col}",
            action="update",
            status="success",
            before=before,
            after=dict(after) if after else None,
        )
        return

    if not mapping["allow_insert"]:
        _log_sync(
            conn,
            review_item_id=review_item_id,
            candidate_id=candidate["id"],
            sync_target=f"{table}.{field_col}",
            action="insert",
            status="skipped",
            error="目标记录不存在，且该映射禁止自动新增",
        )
        return

    columns = [id_col, field_col]
    values: list[Any] = [subject_id, fact_value]
    if label_col and candidate["subject_label"]:
        columns.append(label_col)
        values.append(candidate["subject_label"])
    column_sql = ", ".join(f'"{column}"' for column in columns)
    placeholder_sql = ", ".join("?" for _ in values)
    conn.execute(f'INSERT INTO "{table}" ({column_sql}) VALUES ({placeholder_sql})', values)
    _log_sync(
        conn,
        review_item_id=review_item_id,
        candidate_id=candidate["id"],
        sync_target=f"{table}.{field_col}",
        action="insert",
        status="success",
        after={column: value for column, value in zip(columns, values)},
    )


def sync_approved_reviews(
    *,
    actor: str = "manual-sync",
    limit: int = 200,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04c1_schema(db_path)
    with db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT c.*, r.status AS review_status, r.fact_level AS review_fact_level,
                   r.resolved_value, r.proposed_value, r.resolution_note,
                   r.id AS linked_review_id
            FROM v04c1_candidates c
            JOIN v04c_review_items r ON r.id = c.review_item_id
            WHERE c.candidate_type = 'field'
              AND c.status IN ('pending_review','waiting_fact')
              AND r.status IN ('approved','rejected')
            ORDER BY r.resolved_at ASC, c.id ASC
            LIMIT ?
            """,
            (max(1, min(int(limit), 1000)),),
        ).fetchall()

    grouped: dict[int, list[sqlite3.Row]] = {}
    for row in rows:
        grouped.setdefault(int(row["linked_review_id"]), []).append(row)

    synced: list[int] = []
    rejected: list[int] = []
    waiting_fact: list[int] = []
    failed: list[dict[str, Any]] = []

    for review_id, candidates in grouped.items():
        first = candidates[0]
        if first["review_status"] == "rejected":
            with db_connection(db_path) as conn:
                ids = [row["id"] for row in candidates]
                conn.executemany(
                    "UPDATE v04c1_candidates SET status = 'rejected', updated_at = ? WHERE id = ?",
                    [(utc_now(), candidate_id) for candidate_id in ids],
                )
            rejected.append(review_id)
            continue

        if first["review_fact_level"] != "fact":
            with db_connection(db_path) as conn:
                conn.executemany(
                    "UPDATE v04c1_candidates SET status = 'waiting_fact', updated_at = ? WHERE id = ?",
                    [(utc_now(), row["id"]) for row in candidates],
                )
            waiting_fact.append(review_id)
            continue

        fact_value = str(first["resolved_value"] or first["proposed_value"] or first["candidate_value"] or "").strip()
        if not fact_value:
            failed.append({"review_id": review_id, "error": "审核通过但没有最终值"})
            continue

        try:
            with db_connection(db_path) as conn:
                review = conn.execute("SELECT * FROM v04c_review_items WHERE id = ?", (review_id,)).fetchone()
                candidate = conn.execute("SELECT * FROM v04c1_candidates WHERE id = ?", (first["id"],)).fetchone()
                action, fact = _upsert_canonical_fact(
                    conn,
                    review=review,
                    candidate=candidate,
                    fact_value=fact_value,
                    actor=actor,
                )
                _log_sync(
                    conn,
                    review_item_id=review_id,
                    candidate_id=candidate["id"],
                    sync_target="v04c1_canonical_facts",
                    action=action,
                    status="success",
                    after=fact,
                )
                mappings = conn.execute(
                    """
                    SELECT * FROM v04c1_sync_mappings
                    WHERE enabled = 1 AND subject_type = ? AND field_name = ?
                    ORDER BY id
                    """,
                    (candidate["subject_type"], candidate["field_name"]),
                ).fetchall()
                for mapping in mappings:
                    try:
                        _apply_mapping(
                            conn,
                            mapping=mapping,
                            candidate=candidate,
                            fact_value=fact_value,
                            review_item_id=review_id,
                        )
                    except Exception as mapping_exc:
                        _log_sync(
                            conn,
                            review_item_id=review_id,
                            candidate_id=candidate["id"],
                            sync_target=f"{mapping['target_table']}.{mapping['target_field_column']}",
                            action="mapping",
                            status="failed",
                            error=str(mapping_exc),
                        )
                conn.executemany(
                    "UPDATE v04c1_candidates SET status = 'synced', updated_at = ? WHERE id = ?",
                    [(utc_now(), row["id"]) for row in candidates],
                )
            synced.append(review_id)
        except Exception as exc:
            failed.append({"review_id": review_id, "error": str(exc)})

    relation_result = sync_approved_relations(actor=actor, db_path=db_path)
    return {
        "synced": synced,
        "rejected": rejected,
        "waiting_fact": waiting_fact,
        "failed": failed,
        "relations": relation_result,
    }


def sync_approved_relations(
    *,
    actor: str = "manual-sync",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04c1_schema(db_path)
    inserted: list[int] = []
    skipped: list[int] = []
    with db_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM v04c_pending_relations
            WHERE status = 'approved' AND fact_level = 'fact'
            ORDER BY reviewed_at ASC, id ASC
            """
        ).fetchall()
        for row in rows:
            left_key = _subject_key(row["left_id"], row["left_label"], row["left_type"])
            right_key = _subject_key(row["right_id"], row["right_label"], row["right_type"])
            existing = conn.execute(
                """
                SELECT id FROM v04c1_canonical_relations
                WHERE left_type = ? AND left_key = ? AND relation_type = ?
                  AND right_type = ? AND right_key = ?
                """,
                (row["left_type"], left_key, row["relation_type"], row["right_type"], right_key),
            ).fetchone()
            if existing:
                skipped.append(int(row["id"]))
                continue
            relation_no = _next_number(conn, "CRL")
            conn.execute(
                """
                INSERT INTO v04c1_canonical_relations(
                    relation_no, left_type, left_key, left_id, left_label,
                    relation_type, right_type, right_key, right_id, right_label,
                    source_pending_relation_id, confirmed_by, confirmed_at, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    relation_no,
                    row["left_type"],
                    left_key,
                    row["left_id"],
                    row["left_label"],
                    row["relation_type"],
                    row["right_type"],
                    right_key,
                    row["right_id"],
                    row["right_label"],
                    row["id"],
                    actor,
                    utc_now(),
                    utc_now(),
                ),
            )
            conn.execute(
                "UPDATE v04c1_candidates SET status = 'synced', updated_at = ? WHERE pending_relation_id = ?",
                (utc_now(), row["id"]),
            )
            inserted.append(int(row["id"]))
    return {"inserted": inserted, "skipped": skipped}


def dashboard_data(db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04c1_schema(db_path)
    with db_connection(db_path) as conn:
        counts = {
            "batches": conn.execute("SELECT COUNT(*) AS c FROM v04c1_ingest_batches").fetchone()["c"],
            "sources": conn.execute("SELECT COUNT(*) AS c FROM v04c1_source_records").fetchone()["c"],
            "candidates": conn.execute("SELECT COUNT(*) AS c FROM v04c1_candidates").fetchone()["c"],
            "open_reviews": conn.execute("SELECT COUNT(*) AS c FROM v04c_review_items WHERE status IN ('pending','in_review','deferred')").fetchone()["c"],
            "facts": conn.execute("SELECT COUNT(*) AS c FROM v04c1_canonical_facts WHERE is_current=1 AND status='active'").fetchone()["c"],
            "waiting_sync": conn.execute(
                """
                SELECT COUNT(DISTINCT c.review_item_id) AS c
                FROM v04c1_candidates c JOIN v04c_review_items r ON r.id=c.review_item_id
                WHERE c.status IN ('pending_review','waiting_fact') AND r.status='approved'
                """
            ).fetchone()["c"],
        }
        batches = [dict(row) for row in conn.execute("SELECT * FROM v04c1_ingest_batches ORDER BY id DESC LIMIT 20").fetchall()]
        sources = [dict(row) for row in conn.execute("SELECT * FROM v04c1_source_records ORDER BY id DESC LIMIT 50").fetchall()]
        candidates = [
            dict(row)
            for row in conn.execute(
                """
                SELECT c.*, r.review_no, r.status AS review_status
                FROM v04c1_candidates c
                LEFT JOIN v04c_review_items r ON r.id=c.review_item_id
                ORDER BY c.id DESC LIMIT 100
                """
            ).fetchall()
        ]
        facts = [dict(row) for row in conn.execute("SELECT * FROM v04c1_canonical_facts WHERE is_current=1 AND status='active' ORDER BY id DESC LIMIT 100").fetchall()]
        relations = [dict(row) for row in conn.execute("SELECT * FROM v04c1_canonical_relations ORDER BY id DESC LIMIT 100").fetchall()]
        mappings = [dict(row) for row in conn.execute("SELECT * FROM v04c1_sync_mappings ORDER BY id DESC").fetchall()]
        sync_logs = [dict(row) for row in conn.execute("SELECT * FROM v04c1_sync_logs ORDER BY id DESC LIMIT 50").fetchall()]
    return {
        "counts": counts,
        "batches": batches,
        "sources": sources,
        "candidates": candidates,
        "facts": facts,
        "relations": relations,
        "mappings": mappings,
        "sync_logs": sync_logs,
        "tables": discover_tables(db_path),
    }


def _redirect(message: str, level: str = "ok", tab: str = "overview") -> RedirectResponse:
    from urllib.parse import quote

    return RedirectResponse(
        url=f"/review/intake?message={quote(message)}&level={quote(level)}&tab={quote(tab)}",
        status_code=303,
    )


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def intake_dashboard(
    request: Request,
    message: str | None = None,
    level: str = "ok",
    tab: str = "overview",
):
    return templates.TemplateResponse(
        request=request,
        name="v04c1_ingestion.html",
        context={
            **dashboard_data(),
            "message": message,
            "message_level": level,
            "active_tab": tab,
            "status_labels": STATUS_LABELS,
            "fact_labels": FACT_LABELS,
            "db_path": str(default_db_path()),
        },
    )


@router.post("/json")
def ui_ingest_json(
    payload_json: str = Form(...),
    created_by: str = Form("manual"),
):
    try:
        payload = json.loads(payload_json)
        result = ingest_payload(payload, created_by=created_by or "manual")
        batch = result["batch"]
        return _redirect(
            f"批次 {batch['batch_no']} 完成：处理 {batch['processed_records']}、重复 {batch['duplicate_records']}、失败 {batch['failed_records']}",
            "error" if batch["failed_records"] else "ok",
            "sources",
        )
    except Exception as exc:
        return _redirect(f"JSON 接入失败：{exc}", "error", "ingest")


@router.post("/import-table")
def ui_import_table(
    table_name: str = Form(...),
    limit: int = Form(100),
    source_name: str = Form(""),
):
    try:
        result = import_existing_table(table_name, limit=limit, source_name=source_name or None)
        batch = result["batch"]
        return _redirect(
            f"已从 {table_name} 导入：处理 {batch['processed_records']}、重复 {batch['duplicate_records']}、失败 {batch['failed_records']}。无结构化字段的记录会标记为“待结构化”。",
            "error" if batch["failed_records"] else "ok",
            "sources",
        )
    except Exception as exc:
        return _redirect(f"现有表导入失败：{exc}", "error", "ingest")


@router.post("/sync-approved")
def ui_sync_approved(
    actor: str = Form("manual-sync"),
    limit: int = Form(200),
):
    try:
        result = sync_approved_reviews(actor=actor or "manual-sync", limit=limit)
        message = (
            f"同步完成：事实 {len(result['synced'])} 条，驳回归档 {len(result['rejected'])} 条，"
            f"等待定为事实 {len(result['waiting_fact'])} 条，关系 {len(result['relations']['inserted'])} 条"
        )
        if result["failed"]:
            message += f"，失败 {len(result['failed'])} 条"
        return _redirect(message, "error" if result["failed"] else "ok", "facts")
    except Exception as exc:
        return _redirect(f"同步失败：{exc}", "error", "facts")


@router.post("/mappings")
def ui_create_mapping(
    subject_type: str = Form(...),
    field_name: str = Form(...),
    target_table: str = Form(...),
    target_id_column: str = Form(...),
    target_field_column: str = Form(...),
    target_label_column: str = Form(""),
    allow_insert: bool = Form(False),
    enabled: bool = Form(False),
):
    try:
        mapping = create_sync_mapping(
            subject_type=subject_type,
            field_name=field_name,
            target_table=target_table,
            target_id_column=target_id_column,
            target_field_column=target_field_column,
            target_label_column=target_label_column or None,
            allow_insert=allow_insert,
            enabled=enabled,
        )
        return _redirect(f"映射已保存：{mapping['subject_type']}.{mapping['field_name']} → {mapping['target_table']}.{mapping['target_field_column']}", "ok", "mappings")
    except Exception as exc:
        return _redirect(f"映射保存失败：{exc}", "error", "mappings")


@router.post("/api/ingest")
async def api_ingest(request: Request):
    try:
        payload = await request.json()
        return JSONResponse(ingest_payload(payload, created_by="api"))
    except (ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/sync-approved")
def api_sync_approved(actor: str = "api-sync", limit: int = 200):
    return JSONResponse(sync_approved_reviews(actor=actor, limit=limit))


@router.get("/api/source/{source_record_id}")
def api_source_detail(source_record_id: int):
    ensure_v04c1_schema()
    with db_connection() as conn:
        source = conn.execute("SELECT * FROM v04c1_source_records WHERE id = ?", (source_record_id,)).fetchone()
        if not source:
            raise HTTPException(status_code=404, detail="来源记录不存在")
        candidates = [dict(row) for row in conn.execute("SELECT * FROM v04c1_candidates WHERE source_record_id = ? ORDER BY id", (source_record_id,)).fetchall()]
    result = dict(source)
    try:
        result["payload"] = json.loads(result["payload_json"])
    except json.JSONDecodeError:
        result["payload"] = result["payload_json"]
    return JSONResponse({"source": result, "candidates": candidates})


@router.get("/health")
def v04c1_health():
    path = ensure_v04c1_schema()
    with db_connection(path) as conn:
        table_count = conn.execute("SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v04c1_%'").fetchone()["c"]
        sources = conn.execute("SELECT COUNT(*) AS c FROM v04c1_source_records").fetchone()["c"]
        candidates = conn.execute("SELECT COUNT(*) AS c FROM v04c1_candidates").fetchone()["c"]
        facts = conn.execute("SELECT COUNT(*) AS c FROM v04c1_canonical_facts WHERE is_current=1 AND status='active'").fetchone()["c"]
    return {
        "ok": table_count >= 8,
        "version": "0.4C-1",
        "database": str(path),
        "v04c1_table_count": table_count,
        "source_records": sources,
        "candidates": candidates,
        "canonical_facts": facts,
    }
