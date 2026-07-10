from __future__ import annotations

import json
import re
import sqlite3
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Literal
from urllib.parse import quote

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.v04c_review import db_connection, default_db_path

router = APIRouter(prefix="/review/entities", tags=["v0.4E-A 主体消歧与别名管理"])
MODULE_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = MODULE_DIR / "templates"
templates = Jinja2Templates(directory=str(TEMPLATE_DIR))

SubjectType = Literal["organization", "person", "project", "event", "resource"]
Decision = Literal["pending", "reviewing", "same_entity", "different_entity", "deferred"]

SUBJECT_LABELS = {
    "organization": "机构",
    "person": "人物",
    "project": "项目",
    "event": "事件",
    "resource": "资源",
}

DECISION_LABELS = {
    "pending": "待判断",
    "reviewing": "判断中",
    "same_entity": "确认同一主体",
    "different_entity": "确认不同主体",
    "deferred": "暂缓判断",
}

ENTITY_CONFIG: dict[str, dict[str, Any]] = {
    "organization": {
        "table": "organizations",
        "id_col": "external_id",
        "label_col": "standard_name",
        "detail_cols": ["org_type", "region", "industry_tags", "verification_status", "is_active"],
        "compare_cols": ["org_type", "region", "industry_tags", "resources", "needs", "verification_status"],
    },
    "person": {
        "table": "people",
        "id_col": "external_id",
        "label_col": "name",
        "detail_cols": ["public_role", "organization_network", "ability_tags", "verification_status", "is_active"],
        "compare_cols": ["public_role", "organization_network", "ability_tags", "value_provided", "verification_status"],
    },
    "project": {
        "table": "projects",
        "id_col": "external_id",
        "label_col": "name",
        "detail_cols": ["project_type", "owner_external_id", "stage", "verification_status", "is_active"],
        "compare_cols": ["project_type", "owner_external_id", "stage", "tags", "needs", "verification_status"],
    },
    "event": {
        "table": "events",
        "id_col": "external_id",
        "label_col": "name",
        "detail_cols": ["event_date", "event_type", "related_entity", "verification_status", "is_active"],
        "compare_cols": ["event_date", "event_type", "related_entity", "fact_summary", "verification_status"],
    },
    "resource": {
        "table": "resources",
        "id_col": "external_id",
        "label_col": "description",
        "detail_cols": ["category", "owner_external_id", "region", "verification_status", "is_active"],
        "compare_cols": ["category", "owner_external_id", "region", "applicable_to", "verification_status"],
    },
}

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS v04e_sequence_counters (
    seq_key TEXT PRIMARY KEY,
    seq_date TEXT NOT NULL,
    seq_value INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS v04e_entity_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    alias_no TEXT NOT NULL UNIQUE,
    subject_type TEXT NOT NULL,
    entity_external_id TEXT NOT NULL,
    entity_label TEXT,
    alias TEXT NOT NULL,
    normalized_alias TEXT NOT NULL,
    alias_type TEXT NOT NULL DEFAULT 'other',
    source_url TEXT,
    source_note TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_by TEXT NOT NULL DEFAULT 'manual',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (subject_type IN ('organization','person','project','event','resource')),
    CHECK (alias_type IN ('short_name','former_name','english_name','brand','transliteration','other')),
    CHECK (status IN ('active','inactive'))
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04e_alias_entity
ON v04e_entity_aliases(subject_type, entity_external_id, normalized_alias);

CREATE INDEX IF NOT EXISTS ix_v04e_alias_lookup
ON v04e_entity_aliases(subject_type, normalized_alias, status);

CREATE TABLE IF NOT EXISTS v04e_duplicate_candidates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_no TEXT NOT NULL UNIQUE,
    subject_type TEXT NOT NULL,
    left_external_id TEXT NOT NULL,
    left_label TEXT,
    right_external_id TEXT NOT NULL,
    right_label TEXT,
    normalized_left TEXT NOT NULL,
    normalized_right TEXT NOT NULL,
    similarity_score REAL NOT NULL,
    risk_level TEXT NOT NULL DEFAULT 'medium',
    reasons_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    reviewer TEXT,
    review_note TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    reviewed_at TEXT,
    CHECK (subject_type IN ('organization','person','project','event','resource')),
    CHECK (risk_level IN ('low','medium','high')),
    CHECK (status IN ('pending','reviewing','same_entity','different_entity','deferred')),
    CHECK (left_external_id < right_external_id)
);

CREATE UNIQUE INDEX IF NOT EXISTS ux_v04e_duplicate_pair
ON v04e_duplicate_candidates(subject_type, left_external_id, right_external_id);

CREATE INDEX IF NOT EXISTS ix_v04e_duplicate_status
ON v04e_duplicate_candidates(status, similarity_score DESC, id DESC);

CREATE TABLE IF NOT EXISTS v04e_resolution_actions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    action_no TEXT NOT NULL UNIQUE,
    action_type TEXT NOT NULL,
    subject_type TEXT,
    entity_external_id TEXT,
    candidate_id INTEGER,
    actor TEXT NOT NULL DEFAULT 'manual',
    detail_json TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(candidate_id) REFERENCES v04e_duplicate_candidates(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS ix_v04e_actions_entity
ON v04e_resolution_actions(subject_type, entity_external_id, created_at DESC);
"""

LEGAL_SUFFIXES = (
    "有限责任公司", "股份有限公司", "有限公司", "集团股份有限公司", "集团有限公司",
    "控股有限公司", "生物医药", "生物科技", "医药科技", "制药", "科技", "集团", "公司",
    "incorporated", "corporation", "company limited", "limited", "holdings", "holding", "corp", "inc", "ltd", "llc",
)
PUNCT_RE = re.compile(r"[\s\-—_·•,，.。()（）\[\]【】'\"“”‘’/\\]+")


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _load_json(value: Any, default: Any = None) -> Any:
    if value in (None, ""):
        return default if default is not None else {}
    try:
        return json.loads(str(value))
    except (TypeError, json.JSONDecodeError):
        return default if default is not None else {}


def _text(value: Any, limit: int | None = None) -> str:
    result = "" if value is None else str(value).strip()
    return result[:limit] if limit else result


def normalize_name(value: Any) -> str:
    text = unicodedata.normalize("NFKC", _text(value)).casefold()
    text = PUNCT_RE.sub("", text)
    return text


def compact_name(value: Any, subject_type: str) -> str:
    text = normalize_name(value)
    if subject_type == "organization":
        changed = True
        while changed and text:
            changed = False
            for suffix in LEGAL_SUFFIXES:
                normalized = normalize_name(suffix)
                if normalized and text.endswith(normalized) and len(text) > len(normalized) + 1:
                    text = text[: -len(normalized)]
                    changed = True
                    break
    return text


def _next_number(conn: sqlite3.Connection, prefix: str) -> str:
    today = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04e_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
            seq_value = CASE WHEN v04e_sequence_counters.seq_date=excluded.seq_date
                             THEN v04e_sequence_counters.seq_value+1 ELSE 1 END,
            seq_date=excluded.seq_date,
            updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, today, utc_now()),
    ).fetchone()
    return f"{prefix}-{today}-{int(row['seq_value']):04d}"


def ensure_v04e_schema(db_path: str | Path | None = None) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    with db_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
    return path


def _table_exists(conn: sqlite3.Connection, table: str) -> bool:
    return conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
    ).fetchone() is not None


def _entity_config(subject_type: str) -> dict[str, Any]:
    config = ENTITY_CONFIG.get(_text(subject_type).lower())
    if not config:
        raise ValueError("不支持的主体类型")
    return config


def _entity_row(conn: sqlite3.Connection, subject_type: str, external_id: str) -> sqlite3.Row:
    config = _entity_config(subject_type)
    row = conn.execute(
        f'SELECT * FROM "{config["table"]}" WHERE "{config["id_col"]}"=? LIMIT 1',
        (_text(external_id),),
    ).fetchone()
    if not row:
        raise ValueError("主体不存在")
    return row


def list_entities(conn: sqlite3.Connection, subject_type: str, active_only: bool = True) -> list[sqlite3.Row]:
    config = _entity_config(subject_type)
    if not _table_exists(conn, config["table"]):
        return []
    where = "WHERE COALESCE(is_active,1)=1" if active_only else ""
    return conn.execute(
        f'SELECT * FROM "{config["table"]}" {where} ORDER BY "{config["label_col"]}", "{config["id_col"]}"'
    ).fetchall()


def add_alias(
    subject_type: str,
    entity_external_id: str,
    alias: str,
    *,
    alias_type: str = "other",
    source_url: str = "",
    source_note: str = "",
    actor: str = "manual",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04e_schema(db_path)
    subject_type = _text(subject_type).lower()
    alias = _text(alias, 500)
    normalized = normalize_name(alias)
    if len(normalized) < 2:
        raise ValueError("别名过短或无有效字符")
    if alias_type not in {"short_name", "former_name", "english_name", "brand", "transliteration", "other"}:
        raise ValueError("别名类型不正确")
    with db_connection(db_path) as conn:
        entity = _entity_row(conn, subject_type, entity_external_id)
        config = _entity_config(subject_type)
        primary_label = _text(entity[config["label_col"]])
        if normalize_name(primary_label) == normalized:
            raise ValueError("该别名与主体标准名称完全相同，无需重复添加")
        now = utc_now()
        existing = conn.execute(
            """
            SELECT * FROM v04e_entity_aliases
            WHERE subject_type=? AND entity_external_id=? AND normalized_alias=?
            """,
            (subject_type, entity_external_id, normalized),
        ).fetchone()
        if existing:
            conn.execute(
                """
                UPDATE v04e_entity_aliases
                SET alias=?, alias_type=?, source_url=?, source_note=?, status='active', updated_at=?
                WHERE id=?
                """,
                (alias, alias_type, source_url or None, source_note or None, now, existing["id"]),
            )
            alias_row = conn.execute("SELECT * FROM v04e_entity_aliases WHERE id=?", (existing["id"],)).fetchone()
            action = "reactivate_alias"
        else:
            alias_no = _next_number(conn, "ALS")
            cursor = conn.execute(
                """
                INSERT INTO v04e_entity_aliases(
                    alias_no, subject_type, entity_external_id, entity_label,
                    alias, normalized_alias, alias_type, source_url, source_note,
                    status, created_by, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?)
                """,
                (
                    alias_no, subject_type, entity_external_id, primary_label,
                    alias, normalized, alias_type, source_url or None, source_note or None,
                    actor or "manual", now, now,
                ),
            )
            alias_row = conn.execute("SELECT * FROM v04e_entity_aliases WHERE id=?", (cursor.lastrowid,)).fetchone()
            action = "add_alias"
        conn.execute(
            """
            INSERT INTO v04e_resolution_actions(
                action_no, action_type, subject_type, entity_external_id,
                actor, detail_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (_next_number(conn, "ERA"), action, subject_type, entity_external_id, actor or "manual", _json(dict(alias_row)), now),
        )
    return dict(alias_row)


def deactivate_alias(alias_id: int, *, actor: str = "manual", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04e_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v04e_entity_aliases WHERE id=?", (alias_id,)).fetchone()
        if not row:
            raise ValueError("别名不存在")
        now = utc_now()
        conn.execute("UPDATE v04e_entity_aliases SET status='inactive', updated_at=? WHERE id=?", (now, alias_id))
        updated = conn.execute("SELECT * FROM v04e_entity_aliases WHERE id=?", (alias_id,)).fetchone()
        conn.execute(
            """
            INSERT INTO v04e_resolution_actions(
                action_no, action_type, subject_type, entity_external_id, actor, detail_json, created_at
            ) VALUES (?, 'deactivate_alias', ?, ?, ?, ?, ?)
            """,
            (_next_number(conn, "ERA"), row["subject_type"], row["entity_external_id"], actor or "manual", _json(dict(updated)), now),
        )
    return dict(updated)


def _field_similarity(left: sqlite3.Row, right: sqlite3.Row, columns: Iterable[str]) -> tuple[float, list[str]]:
    score_bonus = 0.0
    reasons: list[str] = []
    for column in columns:
        if column not in left.keys() or column not in right.keys():
            continue
        lv, rv = _text(left[column]), _text(right[column])
        if lv and rv and normalize_name(lv) == normalize_name(rv):
            score_bonus += 0.025
            reasons.append(f"{column}一致")
    return min(score_bonus, 0.10), reasons


def score_pair(subject_type: str, left: sqlite3.Row, right: sqlite3.Row) -> tuple[float, list[str]]:
    config = _entity_config(subject_type)
    left_label = _text(left[config["label_col"]])
    right_label = _text(right[config["label_col"]])
    n_left, n_right = normalize_name(left_label), normalize_name(right_label)
    c_left, c_right = compact_name(left_label, subject_type), compact_name(right_label, subject_type)
    reasons: list[str] = []
    if not n_left or not n_right:
        return 0.0, ["名称为空"]
    if n_left == n_right:
        base = 0.96
        reasons.append("标准化名称完全一致")
    elif c_left and c_left == c_right:
        base = 0.91
        reasons.append("去除常见机构后缀后名称一致")
    else:
        ratio = SequenceMatcher(None, n_left, n_right).ratio()
        compact_ratio = SequenceMatcher(None, c_left, c_right).ratio() if c_left and c_right else 0.0
        base = max(ratio, compact_ratio)
        reasons.append(f"名称相似度 {base:.2f}")
    bonus, field_reasons = _field_similarity(left, right, config["compare_cols"])
    reasons.extend(field_reasons)
    score = min(0.999, base + bonus)
    if subject_type == "person" and n_left == n_right:
        has_identity_evidence = any(
            reason.startswith("public_role") or reason.startswith("organization_network")
            for reason in field_reasons
        )
        if not has_identity_evidence:
            score = min(score, 0.82)
            reasons.append("人物同名但缺少共同任职或网络证据，保持谨慎")
    return round(score, 4), reasons


def scan_duplicates(
    subject_type: str = "all",
    *,
    threshold: float = 0.76,
    actor: str = "system-scan",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_v04e_schema(db_path)
    threshold = max(0.55, min(float(threshold), 0.99))
    types = list(ENTITY_CONFIG) if subject_type == "all" else [_text(subject_type).lower()]
    created = updated = skipped = 0
    scanned_pairs = 0
    with db_connection(db_path) as conn:
        for current_type in types:
            config = _entity_config(current_type)
            rows = list_entities(conn, current_type, active_only=True)
            for index, left in enumerate(rows):
                for right in rows[index + 1 :]:
                    scanned_pairs += 1
                    score, reasons = score_pair(current_type, left, right)
                    if score < threshold:
                        skipped += 1
                        continue
                    left_id, right_id = sorted([_text(left[config["id_col"]]), _text(right[config["id_col"]])])
                    left_row = left if _text(left[config["id_col"]]) == left_id else right
                    right_row = right if left_row is left else left
                    risk = "high" if score >= 0.93 else ("medium" if score >= 0.84 else "low")
                    existing = conn.execute(
                        """
                        SELECT * FROM v04e_duplicate_candidates
                        WHERE subject_type=? AND left_external_id=? AND right_external_id=?
                        """,
                        (current_type, left_id, right_id),
                    ).fetchone()
                    now = utc_now()
                    if existing:
                        conn.execute(
                            """
                            UPDATE v04e_duplicate_candidates
                            SET left_label=?, right_label=?, normalized_left=?, normalized_right=?,
                                similarity_score=?, risk_level=?, reasons_json=?, updated_at=?
                            WHERE id=?
                            """,
                            (
                                left_row[config["label_col"]], right_row[config["label_col"]],
                                normalize_name(left_row[config["label_col"]]), normalize_name(right_row[config["label_col"]]),
                                score, risk, _json(reasons), now, existing["id"],
                            ),
                        )
                        updated += 1
                    else:
                        conn.execute(
                            """
                            INSERT INTO v04e_duplicate_candidates(
                                candidate_no, subject_type, left_external_id, left_label,
                                right_external_id, right_label, normalized_left, normalized_right,
                                similarity_score, risk_level, reasons_json, status, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                            """,
                            (
                                _next_number(conn, "DUP"), current_type,
                                left_id, left_row[config["label_col"]], right_id, right_row[config["label_col"]],
                                normalize_name(left_row[config["label_col"]]), normalize_name(right_row[config["label_col"]]),
                                score, risk, _json(reasons), now, now,
                            ),
                        )
                        created += 1
        conn.execute(
            """
            INSERT INTO v04e_resolution_actions(action_no, action_type, actor, detail_json, created_at)
            VALUES (?, 'scan_duplicates', ?, ?, ?)
            """,
            (_next_number(conn, "ERA"), actor or "system-scan", _json({"subject_type": subject_type, "threshold": threshold, "pairs": scanned_pairs, "created": created, "updated": updated}), utc_now()),
        )
    return {"subject_type": subject_type, "threshold": threshold, "pairs": scanned_pairs, "created": created, "updated": updated, "skipped": skipped}


def decide_candidate(
    candidate_id: int,
    decision: Decision,
    *,
    reviewer: str = "manual",
    note: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if decision not in DECISION_LABELS:
        raise ValueError("判断结果不正确")
    if decision in {"same_entity", "different_entity"} and not _text(note):
        raise ValueError("确认同一或不同主体时必须填写判断依据")
    ensure_v04e_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v04e_duplicate_candidates WHERE id=?", (candidate_id,)).fetchone()
        if not row:
            raise ValueError("重复候选不存在")
        now = utc_now()
        reviewed_at = now if decision in {"same_entity", "different_entity", "deferred"} else None
        conn.execute(
            """
            UPDATE v04e_duplicate_candidates
            SET status=?, reviewer=?, review_note=?, reviewed_at=?, updated_at=? WHERE id=?
            """,
            (decision, reviewer or "manual", _text(note, 4000) or None, reviewed_at, now, candidate_id),
        )
        updated = conn.execute("SELECT * FROM v04e_duplicate_candidates WHERE id=?", (candidate_id,)).fetchone()
        conn.execute(
            """
            INSERT INTO v04e_resolution_actions(
                action_no, action_type, subject_type, candidate_id, actor, detail_json, created_at
            ) VALUES (?, 'decide_duplicate', ?, ?, ?, ?, ?)
            """,
            (_next_number(conn, "ERA"), row["subject_type"], candidate_id, reviewer or "manual", _json(dict(updated)), now),
        )
    return dict(updated)


def search_entities(
    subject_type: str,
    q: str,
    *,
    limit: int = 20,
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    ensure_v04e_schema(db_path)
    subject_type = _text(subject_type).lower()
    config = _entity_config(subject_type)
    normalized_q = normalize_name(q)
    limit = max(1, min(int(limit), 50))
    if not normalized_q:
        return []
    results: dict[str, dict[str, Any]] = {}
    with db_connection(db_path) as conn:
        rows = conn.execute(
            f'''SELECT "{config["id_col"]}" AS subject_id, "{config["label_col"]}" AS subject_label
                FROM "{config["table"]}"
                WHERE COALESCE(is_active,1)=1 AND (
                    CAST("{config["id_col"]}" AS TEXT) LIKE ? OR
                    COALESCE(CAST("{config["label_col"]}" AS TEXT),'') LIKE ?
                ) LIMIT ?''',
            (f"%{q}%", f"%{q}%", limit),
        ).fetchall()
        for row in rows:
            match_type = "primary_exact" if normalize_name(row["subject_label"]) == normalized_q else "primary_partial"
            results[_text(row["subject_id"])] = {
                "subject_type": subject_type,
                "subject_id": row["subject_id"],
                "subject_label": row["subject_label"] or row["subject_id"],
                "match_type": match_type,
                "matched_text": row["subject_label"],
            }
        alias_rows = conn.execute(
            """
            SELECT * FROM v04e_entity_aliases
            WHERE subject_type=? AND status='active'
              AND (normalized_alias=? OR alias LIKE ?)
            ORDER BY CASE WHEN normalized_alias=? THEN 0 ELSE 1 END, id DESC LIMIT ?
            """,
            (subject_type, normalized_q, f"%{q}%", normalized_q, limit),
        ).fetchall()
        for row in alias_rows:
            entity = _entity_row(conn, subject_type, row["entity_external_id"])
            results.setdefault(
                row["entity_external_id"],
                {
                    "subject_type": subject_type,
                    "subject_id": row["entity_external_id"],
                    "subject_label": entity[config["label_col"]] or row["entity_external_id"],
                    "match_type": "alias_exact" if row["normalized_alias"] == normalized_q else "alias_partial",
                    "matched_text": row["alias"],
                },
            )
    order = {"primary_exact": 0, "alias_exact": 1, "primary_partial": 2, "alias_partial": 3}
    return sorted(results.values(), key=lambda item: (order.get(item["match_type"], 9), _text(item["subject_label"])))[:limit]


def entity_detail(subject_type: str, external_id: str, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04e_schema(db_path)
    subject_type = _text(subject_type).lower()
    config = _entity_config(subject_type)
    with db_connection(db_path) as conn:
        entity = _entity_row(conn, subject_type, external_id)
        aliases = [dict(row) for row in conn.execute(
            "SELECT * FROM v04e_entity_aliases WHERE subject_type=? AND entity_external_id=? ORDER BY status, id DESC",
            (subject_type, external_id),
        ).fetchall()]
        candidates = [dict(row) for row in conn.execute(
            """
            SELECT * FROM v04e_duplicate_candidates
            WHERE subject_type=? AND (left_external_id=? OR right_external_id=?)
            ORDER BY similarity_score DESC, id DESC
            """,
            (subject_type, external_id, external_id),
        ).fetchall()]
        actions = [dict(row) for row in conn.execute(
            """
            SELECT * FROM v04e_resolution_actions
            WHERE subject_type=? AND entity_external_id=?
            ORDER BY id DESC LIMIT 50
            """,
            (subject_type, external_id),
        ).fetchall()]
    return {
        "entity": dict(entity),
        "entity_label": entity[config["label_col"]],
        "entity_external_id": entity[config["id_col"]],
        "subject_type": subject_type,
        "subject_label": SUBJECT_LABELS[subject_type],
        "detail_cols": config["detail_cols"],
        "aliases": aliases,
        "candidates": candidates,
        "actions": actions,
    }


def candidate_detail(candidate_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04e_schema(db_path)
    with db_connection(db_path) as conn:
        candidate = conn.execute("SELECT * FROM v04e_duplicate_candidates WHERE id=?", (candidate_id,)).fetchone()
        if not candidate:
            raise ValueError("重复候选不存在")
        subject_type = candidate["subject_type"]
        config = _entity_config(subject_type)
        left = _entity_row(conn, subject_type, candidate["left_external_id"])
        right = _entity_row(conn, subject_type, candidate["right_external_id"])
        left_aliases = [dict(row) for row in conn.execute(
            "SELECT * FROM v04e_entity_aliases WHERE subject_type=? AND entity_external_id=? AND status='active' ORDER BY id DESC",
            (subject_type, candidate["left_external_id"]),
        ).fetchall()]
        right_aliases = [dict(row) for row in conn.execute(
            "SELECT * FROM v04e_entity_aliases WHERE subject_type=? AND entity_external_id=? AND status='active' ORDER BY id DESC",
            (subject_type, candidate["right_external_id"]),
        ).fetchall()]
    comparisons = []
    for column in [config["label_col"], *config["compare_cols"], "source_title", "source_url", "created_at"]:
        if column in left.keys() or column in right.keys():
            lv = left[column] if column in left.keys() else None
            rv = right[column] if column in right.keys() else None
            comparisons.append({"field": column, "left": lv, "right": rv, "same": normalize_name(lv) == normalize_name(rv) if lv or rv else True})
    result = dict(candidate)
    result["reasons"] = _load_json(candidate["reasons_json"], [])
    return {
        "candidate": result,
        "left": dict(left),
        "right": dict(right),
        "left_aliases": left_aliases,
        "right_aliases": right_aliases,
        "comparisons": comparisons,
        "subject_label": SUBJECT_LABELS[subject_type],
    }


def dashboard_data(status: str = "", subject_type: str = "", q: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_v04e_schema(db_path)
    status, subject_type, q = _text(status), _text(subject_type), _text(q)
    with db_connection(db_path) as conn:
        counts = {
            "aliases": conn.execute("SELECT COUNT(*) AS c FROM v04e_entity_aliases WHERE status='active'").fetchone()["c"],
            "pending": conn.execute("SELECT COUNT(*) AS c FROM v04e_duplicate_candidates WHERE status IN ('pending','reviewing')").fetchone()["c"],
            "same_entity": conn.execute("SELECT COUNT(*) AS c FROM v04e_duplicate_candidates WHERE status='same_entity'").fetchone()["c"],
            "different_entity": conn.execute("SELECT COUNT(*) AS c FROM v04e_duplicate_candidates WHERE status='different_entity'").fetchone()["c"],
            "deferred": conn.execute("SELECT COUNT(*) AS c FROM v04e_duplicate_candidates WHERE status='deferred'").fetchone()["c"],
        }
        clauses: list[str] = []
        params: list[Any] = []
        if status:
            clauses.append("status=?")
            params.append(status)
        if subject_type:
            clauses.append("subject_type=?")
            params.append(subject_type)
        if q:
            clauses.append("(candidate_no LIKE ? OR left_label LIKE ? OR right_label LIKE ? OR left_external_id LIKE ? OR right_external_id LIKE ?)")
            token = f"%{q}%"
            params.extend([token] * 5)
        where = "WHERE " + " AND ".join(clauses) if clauses else ""
        candidates = [dict(row) for row in conn.execute(
            f"SELECT * FROM v04e_duplicate_candidates {where} ORDER BY similarity_score DESC, id DESC LIMIT 150",
            params,
        ).fetchall()]
        aliases = [dict(row) for row in conn.execute(
            "SELECT * FROM v04e_entity_aliases ORDER BY id DESC LIMIT 80"
        ).fetchall()]
        actions = [dict(row) for row in conn.execute(
            "SELECT * FROM v04e_resolution_actions ORDER BY id DESC LIMIT 50"
        ).fetchall()]
    for candidate in candidates:
        candidate["reasons"] = _load_json(candidate["reasons_json"], [])
    return {"counts": counts, "candidates": candidates, "aliases": aliases, "actions": actions}


def _redirect(message: str, level: str = "ok", target: str = "/review/entities") -> RedirectResponse:
    separator = "&" if "?" in target else "?"
    return RedirectResponse(url=f"{target}{separator}message={quote(message)}&level={quote(level)}", status_code=303)


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def entities_dashboard(
    request: Request,
    status: str = Query(""),
    subject_type: str = Query(""),
    q: str = Query(""),
    message: str | None = None,
    level: str = "ok",
):
    return templates.TemplateResponse(
        request=request,
        name="v04e_entity_resolution.html",
        context={
            "mode": "dashboard",
            **dashboard_data(status, subject_type, q),
            "filters": {"status": status, "subject_type": subject_type, "q": q},
            "message": message,
            "message_level": level,
            "subject_labels": SUBJECT_LABELS,
            "decision_labels": DECISION_LABELS,
        },
    )


@router.post("/scan")
def ui_scan_duplicates(
    subject_type: str = Form("all"),
    threshold: float = Form(0.76),
    actor: str = Form("manual"),
):
    try:
        result = scan_duplicates(subject_type, threshold=threshold, actor=actor)
        return _redirect(f"扫描完成：比较 {result['pairs']} 对，新增 {result['created']}，更新 {result['updated']}")
    except Exception as exc:
        return _redirect(f"扫描失败：{exc}", "error")


@router.post("/aliases")
def ui_add_alias(
    subject_type: str = Form(...),
    entity_external_id: str = Form(...),
    alias: str = Form(...),
    alias_type: str = Form("other"),
    source_url: str = Form(""),
    source_note: str = Form(""),
    actor: str = Form("manual"),
):
    target = f"/review/entities/entity/{subject_type}/{quote(entity_external_id, safe='')}"
    try:
        row = add_alias(subject_type, entity_external_id, alias, alias_type=alias_type, source_url=source_url, source_note=source_note, actor=actor)
        return _redirect(f"别名 {row['alias']} 已保存", target=target)
    except Exception as exc:
        return _redirect(f"别名保存失败：{exc}", "error", target=target)


@router.post("/aliases/{alias_id}/deactivate")
def ui_deactivate_alias(alias_id: int, actor: str = Form("manual")):
    try:
        row = deactivate_alias(alias_id, actor=actor)
        target = f"/review/entities/entity/{row['subject_type']}/{quote(row['entity_external_id'], safe='')}"
        return _redirect("别名已停用", target=target)
    except Exception as exc:
        return _redirect(f"停用失败：{exc}", "error")


@router.get("/entity/{subject_type}/{external_id}", response_class=HTMLResponse)
def entity_page(subject_type: str, external_id: str, request: Request, message: str | None = None, level: str = "ok"):
    try:
        detail = entity_detail(subject_type, external_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request=request,
        name="v04e_entity_resolution.html",
        context={
            "mode": "entity",
            **detail,
            "message": message,
            "message_level": level,
            "subject_labels": SUBJECT_LABELS,
            "decision_labels": DECISION_LABELS,
        },
    )


@router.get("/candidate/{candidate_id}", response_class=HTMLResponse)
def candidate_page(candidate_id: int, request: Request, message: str | None = None, level: str = "ok"):
    try:
        detail = candidate_detail(candidate_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return templates.TemplateResponse(
        request=request,
        name="v04e_entity_resolution.html",
        context={
            "mode": "candidate",
            **detail,
            "message": message,
            "message_level": level,
            "subject_labels": SUBJECT_LABELS,
            "decision_labels": DECISION_LABELS,
        },
    )


@router.post("/candidate/{candidate_id}/decision")
def ui_decide_candidate(
    candidate_id: int,
    decision: str = Form(...),
    reviewer: str = Form("manual"),
    note: str = Form(""),
):
    target = f"/review/entities/candidate/{candidate_id}"
    try:
        row = decide_candidate(candidate_id, decision, reviewer=reviewer, note=note)  # type: ignore[arg-type]
        return _redirect(f"已更新为：{DECISION_LABELS[row['status']]}", target=target)
    except Exception as exc:
        return _redirect(f"保存判断失败：{exc}", "error", target=target)


@router.get("/api/search")
def api_search(subject_type: str, q: str, limit: int = 20):
    try:
        return JSONResponse({"items": search_entities(subject_type, q, limit=limit)})
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/health")
def v04e_health():
    path = ensure_v04e_schema()
    with db_connection(path) as conn:
        tables = conn.execute(
            "SELECT COUNT(*) AS c FROM sqlite_master WHERE type='table' AND name LIKE 'v04e_%'"
        ).fetchone()["c"]
        aliases = conn.execute("SELECT COUNT(*) AS c FROM v04e_entity_aliases WHERE status='active'").fetchone()["c"]
        pending = conn.execute("SELECT COUNT(*) AS c FROM v04e_duplicate_candidates WHERE status IN ('pending','reviewing')").fetchone()["c"]
    return {"ok": tables >= 4, "version": "0.4E-A", "database": str(path), "v04e_table_count": tables, "active_aliases": aliases, "pending_duplicates": pending, "merge_execution_enabled": False}
