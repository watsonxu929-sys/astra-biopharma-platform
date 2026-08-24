from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.v04c_review import db_connection
from app.core.similarity import similarity_ratio

EVENT_RELATIONS = {
    "same_event", "related_event", "duplicate_report", "update_event", "conflict", "unrelated"
}
APPROVED_EVENT_STATUSES = {"approved", "published"}


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _text(value: Any) -> str:
    return " ".join(str(value or "").casefold().split())


def _tokens(value: Any) -> set[str]:
    return {
        token for token in re.split(r"[^\w\u4e00-\u9fff]+", _text(value))
        if len(token) >= 2
    }


def _set(value: Any) -> set[str]:
    if isinstance(value, (list, tuple, set)):
        return {_text(item) for item in value if _text(item)}
    return {_text(item) for item in re.split(r"[,;，；|]", str(value or "")) if _text(item)}


def _date(value: Any) -> date | None:
    text = str(value or "").strip()[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _jaccard(left: set[str], right: set[str]) -> float:
    if not left and not right:
        return 0.0
    return len(left & right) / len(left | right) if left | right else 0.0


def classify_event_relation(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    left_subjects = _set(left.get("subjects") or left.get("subject_id") or left.get("subject_label"))
    right_subjects = _set(right.get("subjects") or right.get("subject_id") or right.get("subject_label"))
    subject_score = _jaccard(left_subjects, right_subjects)
    type_score = 1.0 if _text(left.get("event_type")) and _text(left.get("event_type")) == _text(right.get("event_type")) else 0.0
    product_score = _jaccard(
        _set(left.get("products") or left.get("product")),
        _set(right.get("products") or right.get("product")),
    )
    title_score = similarity_ratio(_text(left.get("title")), _text(right.get("title")))
    content_score = _jaccard(_tokens(left.get("content")), _tokens(right.get("content")))
    left_date, right_date = _date(left.get("occurred_at") or left.get("event_date")), _date(right.get("occurred_at") or right.get("event_date"))
    day_gap = abs((left_date - right_date).days) if left_date and right_date else None
    date_score = 1.0 if day_gap is not None and day_gap <= 3 else 0.6 if day_gap is not None and day_gap <= 30 else 0.0
    region_score = 1.0 if _text(left.get("region")) and _text(left.get("region")) == _text(right.get("region")) else 0.0
    score = round(
        subject_score * 0.30 + type_score * 0.20 + product_score * 0.15
        + date_score * 0.15 + title_score * 0.10 + content_score * 0.07
        + region_score * 0.03,
        4,
    )

    conflicts: list[str] = []
    if subject_score > 0 and type_score:
        for field in ("amount_value", "stage", "occurred_at"):
            lval, rval = left.get(field), right.get(field)
            if lval not in (None, "") and rval not in (None, "") and _text(lval) != _text(rval):
                if field != "occurred_at" or (
                    day_gap is not None and day_gap > 3 and title_score >= 0.80
                ):
                    conflicts.append(field)

    update_terms = {"update", "progress", "follow-up", "最新", "进展", "后续"}
    has_update_term = bool(_tokens(left.get("title")) & update_terms or _tokens(right.get("title")) & update_terms)
    if conflicts and score >= 0.45:
        relation = "conflict"
    elif title_score >= 0.97 and content_score >= 0.90:
        relation = "duplicate_report"
    elif score >= 0.72 or (
        subject_score > 0 and type_score and day_gap is not None and day_gap <= 3
        and title_score >= 0.55
    ):
        relation = "same_event"
    elif subject_score > 0 and type_score and day_gap is not None and 4 <= day_gap <= 180 and has_update_term:
        relation = "update_event"
    elif score >= 0.38 or (subject_score > 0 and (type_score or product_score > 0)):
        relation = "related_event"
    else:
        relation = "unrelated"
    return {
        "relation_type": relation,
        "fusion_score": score,
        "features": {
            "subject": subject_score, "event_type": type_score, "product": product_score,
            "date": date_score, "title": round(title_score, 4),
            "content": round(content_score, 4), "region": region_score, "day_gap": day_gap,
        },
        "conflict_fields": conflicts,
        "requires_manual_review": relation in {"same_event", "update_event", "conflict"},
    }


def ensure_schema(db_path: str | Path | None = None) -> None:
    with db_connection(db_path) as conn:
        if not conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='p2_3_industry_events'"
        ).fetchone():
            raise RuntimeError("p2_3_schema_required")


def _no(prefix: str) -> str:
    return f"{prefix}-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:10].upper()}"


def create_industry_event(
    *,
    title: str,
    event_type: str,
    occurred_at: str = "",
    published_at: str = "",
    amount_value: float | None = None,
    amount_currency: str = "",
    region: str = "",
    stage: str = "",
    importance: int = 3,
    confidence: int = 50,
    created_by: str = "manual",
    fusion_method: str = "rule",
    is_pilot: bool = False,
    pilot_batch_id: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_schema(db_path)
    if not title.strip() or not event_type.strip():
        raise ValueError("event_title_and_type_required")
    ts = now()
    with db_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO p2_3_industry_events(
               event_no,title,event_type,occurred_at,published_at,amount_value,amount_currency,
               region,stage,importance,confidence,status,fusion_method,is_pilot,pilot_batch_id,
               created_by,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,'draft',?,?,?,?,?,?)""",
            (
                _no("IEV"), title.strip(), event_type.strip(), occurred_at or None,
                published_at or None, amount_value, amount_currency or None, region or None,
                stage or None, max(1, min(int(importance), 5)),
                max(0, min(int(confidence), 100)), fusion_method, int(is_pilot),
                pilot_batch_id, created_by, ts, ts,
            ),
        )
        return dict(conn.execute("SELECT * FROM p2_3_industry_events WHERE id=?", (cur.lastrowid,)).fetchone())


def add_event_subject(
    event_id: int,
    *,
    subject_type: str,
    subject_id: str,
    subject_label: str = "",
    role: str = "involved",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if subject_type not in {"organization", "person", "project", "product"}:
        raise ValueError("unsupported_subject_type")
    with db_connection(db_path) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO p2_3_event_subjects(
               event_id,subject_type,subject_id,subject_label,role,created_at)
               VALUES (?,?,?,?,?,?)""",
            (event_id, subject_type, subject_id, subject_label or None, role, now()),
        )
        row = conn.execute(
            "SELECT * FROM p2_3_event_subjects WHERE event_id=? AND subject_type=? AND subject_id=? AND role=?",
            (event_id, subject_type, subject_id, role),
        ).fetchone()
        if not row:
            raise ValueError("event_not_found")
        return dict(row)


def add_event_evidence(
    event_id: int,
    *,
    evidence_excerpt: str,
    snapshot_id: int | None = None,
    raw_intelligence_id: int | None = None,
    candidate_id: int | None = None,
    source_organization: str = "",
    source_title: str = "",
    source_url: str = "",
    published_at: str = "",
    captured_at: str = "",
    char_start: int | None = None,
    char_end: int | None = None,
    page_number: int | None = None,
    table_number: str | None = None,
    locator: dict[str, Any] | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    excerpt = evidence_excerpt.strip()
    if not excerpt:
        raise ValueError("evidence_excerpt_required")
    digest = hashlib.sha256(excerpt.encode("utf-8")).hexdigest()
    with db_connection(db_path) as conn:
        conn.execute(
            """INSERT OR IGNORE INTO p2_3_event_evidence(
               event_id,snapshot_id,raw_intelligence_id,candidate_id,source_organization,
               source_title,source_url,published_at,captured_at,evidence_excerpt,char_start,
               char_end,page_number,table_number,locator_json,evidence_hash,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                event_id, snapshot_id, raw_intelligence_id, candidate_id,
                source_organization or None, source_title or None, source_url or None,
                published_at or None, captured_at or None, excerpt, char_start, char_end,
                page_number, table_number, json.dumps(locator or {}, ensure_ascii=False),
                digest, now(),
            ),
        )
        row = conn.execute(
            """SELECT * FROM p2_3_event_evidence
               WHERE event_id=? AND evidence_hash=? AND COALESCE(snapshot_id,-1)=COALESCE(?,-1)""",
            (event_id, digest, snapshot_id),
        ).fetchone()
        conn.execute(
            """UPDATE p2_3_industry_events SET source_count=(
               SELECT COUNT(DISTINCT COALESCE(snapshot_id, source_url, id))
               FROM p2_3_event_evidence WHERE event_id=?),updated_at=? WHERE id=?""",
            (event_id, now(), event_id),
        )
        return dict(row)


def link_candidate(
    event_id: int,
    candidate_id: int,
    *,
    relation_type: str,
    fusion_score: float,
    reasons: dict[str, Any],
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if relation_type not in EVENT_RELATIONS:
        raise ValueError("invalid_event_relation")
    review_status = "needs_manual_review" if relation_type in {"same_event", "update_event", "conflict"} else "pending"
    with db_connection(db_path) as conn:
        conn.execute(
            """INSERT INTO p2_3_event_candidates(
               event_id,candidate_id,relation_type,fusion_score,reason_json,review_status,created_at)
               VALUES (?,?,?,?,?,?,?)
               ON CONFLICT(event_id,candidate_id) DO UPDATE SET
               relation_type=excluded.relation_type,fusion_score=excluded.fusion_score,
               reason_json=excluded.reason_json,review_status=excluded.review_status""",
            (event_id, candidate_id, relation_type, float(fusion_score), json.dumps(reasons, ensure_ascii=False), review_status, now()),
        )
        if relation_type == "conflict":
            conn.execute("UPDATE p2_3_industry_events SET has_conflict=1,updated_at=? WHERE id=?", (now(), event_id))
        return dict(conn.execute(
            "SELECT * FROM p2_3_event_candidates WHERE event_id=? AND candidate_id=?",
            (event_id, candidate_id),
        ).fetchone())


def submit_event(event_id: int, *, actor: str, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        event = conn.execute("SELECT * FROM p2_3_industry_events WHERE id=?", (event_id,)).fetchone()
        if not event:
            raise ValueError("event_not_found")
        if int(event["source_count"] or 0) < 1:
            raise ValueError("event_evidence_required")
        conn.execute(
            "UPDATE p2_3_industry_events SET status='pending_review',review_note=?,updated_at=? WHERE id=?",
            (f"submitted_by:{actor}", now(), event_id),
        )
        return dict(conn.execute("SELECT * FROM p2_3_industry_events WHERE id=?", (event_id,)).fetchone())


def review_event(
    event_id: int,
    *,
    decision: str,
    actor: str,
    note: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if decision not in {"approved", "needs_revision", "archived"}:
        raise ValueError("invalid_event_review_decision")
    if not actor.strip():
        raise ValueError("reviewer_required")
    with db_connection(db_path) as conn:
        event = conn.execute("SELECT * FROM p2_3_industry_events WHERE id=?", (event_id,)).fetchone()
        if not event:
            raise ValueError("event_not_found")
        if event["status"] != "pending_review":
            raise ValueError("event_not_pending_review")
        unresolved = conn.execute(
            "SELECT COUNT(*) FROM p2_3_fact_conflicts WHERE event_id=? AND status IN ('unresolved','needs_manual_review')",
            (event_id,),
        ).fetchone()[0]
        if decision == "approved" and unresolved:
            raise ValueError("event_has_unresolved_conflict")
        conn.execute(
            """UPDATE p2_3_industry_events SET status=?,reviewed_by=?,reviewed_at=?,
               review_note=?,updated_at=? WHERE id=?""",
            (decision, actor, now(), note or None, now(), event_id),
        )
        return dict(conn.execute("SELECT * FROM p2_3_industry_events WHERE id=?", (event_id,)).fetchone())


def create_assertion(
    *,
    subject_type: str,
    subject_id: str,
    predicate: str,
    object_value: str = "",
    numeric_value: float | None = None,
    unit: str = "",
    valid_time: str = "",
    subject_label: str = "",
    event_id: int | None = None,
    topic_id: int | None = None,
    confidence: int = 50,
    created_by: str = "manual",
    is_pilot: bool = False,
    pilot_batch_id: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO p2_3_fact_assertions(
               assertion_no,event_id,topic_id,subject_type,subject_id,subject_label,predicate,
               object_value,numeric_value,unit,valid_time,confidence,review_status,is_pilot,
               pilot_batch_id,created_by,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?, 'pending_review',?,?,?,?,?)""",
            (
                _no("FAS"), event_id, topic_id, subject_type, subject_id,
                subject_label or None, predicate, object_value or None, numeric_value,
                unit or None, valid_time or None, max(0, min(int(confidence), 100)),
                int(is_pilot), pilot_batch_id, created_by, now(), now(),
            ),
        )
        return dict(conn.execute("SELECT * FROM p2_3_fact_assertions WHERE id=?", (cur.lastrowid,)).fetchone())


def link_assertion_evidence(
    assertion_id: int,
    event_evidence_id: int,
    *,
    support_type: str = "supports",
    db_path: str | Path | None = None,
) -> None:
    if support_type not in {"supports", "contradicts", "context"}:
        raise ValueError("invalid_support_type")
    with db_connection(db_path) as conn:
        conn.execute(
            "INSERT OR IGNORE INTO p2_3_assertion_evidence(assertion_id,event_evidence_id,support_type,created_at) VALUES (?,?,?,?)",
            (assertion_id, event_evidence_id, support_type, now()),
        )
        conn.execute(
            """UPDATE p2_3_fact_assertions SET source_count=(
               SELECT COUNT(*) FROM p2_3_assertion_evidence WHERE assertion_id=?),updated_at=? WHERE id=?""",
            (assertion_id, now(), assertion_id),
        )


def review_assertion(
    assertion_id: int,
    *,
    decision: str,
    actor: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if decision not in {"approved", "rejected", "needs_revision"}:
        raise ValueError("invalid_assertion_review_decision")
    with db_connection(db_path) as conn:
        assertion = conn.execute("SELECT * FROM p2_3_fact_assertions WHERE id=?", (assertion_id,)).fetchone()
        if not assertion:
            raise ValueError("assertion_not_found")
        if decision == "approved" and int(assertion["source_count"] or 0) < 1:
            raise ValueError("assertion_evidence_required")
        conn.execute(
            "UPDATE p2_3_fact_assertions SET review_status=?,reviewed_by=?,reviewed_at=?,updated_at=? WHERE id=?",
            (decision, actor, now(), now(), assertion_id),
        )
        return dict(conn.execute("SELECT * FROM p2_3_fact_assertions WHERE id=?", (assertion_id,)).fetchone())


def register_conflict(
    *,
    field_name: str,
    value_a: str,
    value_b: str,
    evidence_a: list[dict[str, Any]],
    evidence_b: list[dict[str, Any]],
    topic_id: int | None = None,
    event_id: int | None = None,
    subject_type: str = "",
    subject_id: str = "",
    subject_label: str = "",
    assertion_a_id: int | None = None,
    assertion_b_id: int | None = None,
    is_simulated: bool = False,
    is_pilot: bool = False,
    pilot_batch_id: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if _text(value_a) == _text(value_b):
        raise ValueError("conflict_values_must_differ")
    ts = now()
    with db_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO p2_3_fact_conflicts(
               conflict_no,topic_id,event_id,subject_type,subject_id,subject_label,field_name,
               assertion_a_id,assertion_b_id,value_a,value_b,evidence_a_json,evidence_b_json,
               status,is_simulated,is_pilot,pilot_batch_id,created_at,updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,'needs_manual_review',?,?,?,?,?)""",
            (
                _no("CFL"), topic_id, event_id, subject_type or None, subject_id or None,
                subject_label or None, field_name, assertion_a_id, assertion_b_id,
                value_a, value_b, json.dumps(evidence_a, ensure_ascii=False),
                json.dumps(evidence_b, ensure_ascii=False), int(is_simulated), int(is_pilot),
                pilot_batch_id, ts, ts,
            ),
        )
        if event_id:
            conn.execute("UPDATE p2_3_industry_events SET has_conflict=1,updated_at=? WHERE id=?", (ts, event_id))
        return dict(conn.execute("SELECT * FROM p2_3_fact_conflicts WHERE id=?", (cur.lastrowid,)).fetchone())


def resolve_conflict(
    conflict_id: int,
    *,
    adopted_value: str,
    reason: str,
    actor: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if not adopted_value.strip() or not reason.strip() or not actor.strip():
        raise ValueError("conflict_resolution_fields_required")
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM p2_3_fact_conflicts WHERE id=?", (conflict_id,)).fetchone()
        if not row:
            raise ValueError("conflict_not_found")
        conn.execute(
            """UPDATE p2_3_fact_conflicts SET adopted_value=?,adoption_reason=?,status='resolved',
               reviewed_by=?,reviewed_at=?,updated_at=? WHERE id=?""",
            (adopted_value, reason, actor, now(), now(), conflict_id),
        )
        if row["event_id"]:
            remaining = conn.execute(
                "SELECT COUNT(*) FROM p2_3_fact_conflicts WHERE event_id=? AND id<>? AND status IN ('unresolved','needs_manual_review')",
                (row["event_id"], conflict_id),
            ).fetchone()[0]
            if not remaining:
                conn.execute("UPDATE p2_3_industry_events SET has_conflict=0,updated_at=? WHERE id=?", (now(), row["event_id"]))
        return dict(conn.execute("SELECT * FROM p2_3_fact_conflicts WHERE id=?", (conflict_id,)).fetchone())


def list_conflicts(
    *,
    topic_id: int | None = None,
    status: str = "",
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    clauses, params = ["1=1"], []
    if topic_id:
        clauses.append("topic_id=?")
        params.append(topic_id)
    if status:
        clauses.append("status=?")
        params.append(status)
    with db_connection(db_path) as conn:
        return [dict(row) for row in conn.execute(
            f"SELECT * FROM p2_3_fact_conflicts WHERE {' AND '.join(clauses)} ORDER BY id DESC",
            params,
        )]


def link_topic_event(
    topic_id: int,
    event_id: int,
    *,
    relevance: str = "core",
    actor: str = "manual",
    db_path: str | Path | None = None,
) -> None:
    with db_connection(db_path) as conn:
        event = conn.execute("SELECT status FROM p2_3_industry_events WHERE id=?", (event_id,)).fetchone()
        if not event or event["status"] not in APPROVED_EVENT_STATUSES:
            raise ValueError("only_approved_event_can_enter_topic")
        conn.execute(
            "INSERT OR IGNORE INTO p2_3_topic_events(topic_id,event_id,relevance,added_by,created_at) VALUES (?,?,?,?,?)",
            (topic_id, event_id, relevance, actor, now()),
        )


def event_timeline(
    *,
    topic_id: int | None = None,
    subject_type: str = "",
    subject_id: str = "",
    event_type: str = "",
    db_path: str | Path | None = None,
) -> list[dict[str, Any]]:
    clauses = ["e.status IN ('approved','published')"]
    params: list[Any] = []
    joins = []
    if topic_id:
        joins.append("JOIN p2_3_topic_events te ON te.event_id=e.id")
        clauses.append("te.topic_id=?")
        params.append(topic_id)
    if subject_type or subject_id:
        joins.append("JOIN p2_3_event_subjects es ON es.event_id=e.id")
        if subject_type:
            clauses.append("es.subject_type=?")
            params.append(subject_type)
        if subject_id:
            clauses.append("es.subject_id=?")
            params.append(subject_id)
    if event_type:
        clauses.append("e.event_type=?")
        params.append(event_type)
    query = f"""SELECT DISTINCT e.* FROM p2_3_industry_events e {' '.join(joins)}
                WHERE {' AND '.join(clauses)} ORDER BY COALESCE(e.occurred_at,e.published_at,e.created_at) DESC,e.id DESC"""
    with db_connection(db_path) as conn:
        rows = []
        for row in conn.execute(query, params):
            item = dict(row)
            item["evidence_count"] = conn.execute(
                "SELECT COUNT(*) FROM p2_3_event_evidence WHERE event_id=?", (row["id"],)
            ).fetchone()[0]
            rows.append(item)
        return rows


def get_event(event_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM p2_3_industry_events WHERE id=?", (event_id,)).fetchone()
        if not row:
            return None
        item = dict(row)
        item["subjects"] = [dict(r) for r in conn.execute("SELECT * FROM p2_3_event_subjects WHERE event_id=?", (event_id,))]
        item["evidence"] = [dict(r) for r in conn.execute("SELECT * FROM p2_3_event_evidence WHERE event_id=? ORDER BY id", (event_id,))]
        item["candidate_links"] = [dict(r) for r in conn.execute("SELECT * FROM p2_3_event_candidates WHERE event_id=?", (event_id,))]
        item["conflicts"] = [dict(r) for r in conn.execute("SELECT * FROM p2_3_fact_conflicts WHERE event_id=? ORDER BY id", (event_id,))]
        return item
