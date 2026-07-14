from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from app.v04c_review import db_connection, default_db_path
from app.services.processing.content_quality_service import QUALITY_STATUS_LABELS

EVENT_LABEL_MAP = {
    "regulatory_approval": "监管审批",
    "clinical_progress": "临床进展",
    "financing": "融资事件",
    "merger": "并购交易",
    "cooperation": "许可合作",
    "product_launch": "产品发布",
    "tech_progress": "技术进展",
    "corporate": "企业动态",
    "recruitment": "人事变动",
    "policy": "政策发布",
    "conference": "行业活动",
    "unknown": "其他",
}

IMPORTANCE_LABELS = {1: "低", 2: "中低", 3: "中", 4: "中高", 5: "高"}


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_feedback_table(db_path: str | Path | None = None) -> None:
    path = Path(db_path) if db_path else default_db_path()
    with db_connection(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS v05h_intelligence_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_item_id INTEGER,
                user_id INTEGER,
                user_name TEXT,
                feedback_type TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def get_today_intelligence(db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_feedback_table(db_path)
    path = Path(db_path) if db_path else default_db_path()
    with db_connection(path) as conn:
        today = datetime.now().strftime("%Y-%m-%d")
        stats = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN quality_status='accepted' THEN 1 ELSE 0 END) as accepted,
                SUM(CASE WHEN quality_status='pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN quality_status='duplicate' THEN 1 ELSE 0 END) as duplicate,
                SUM(CASE WHEN quality_status='low_quality' OR quality_status='insufficient_content' THEN 1 ELSE 0 END) as low_quality,
                SUM(CASE WHEN quality_status='irrelevant' THEN 1 ELSE 0 END) as irrelevant,
                SUM(CASE WHEN processing_status='processed' THEN 1 ELSE 0 END) as processed,
                SUM(CASE WHEN processing_status='pending' OR processing_status='queued' THEN 1 ELSE 0 END) as pending_processing,
                SUM(CASE WHEN processing_status='failed' THEN 1 ELSE 0 END) as failed_processing
            FROM v05f_collection_items
            WHERE date(captured_at)=?
            """,
            (today,),
        ).fetchone()
        items = conn.execute(
            """
            SELECT i.*, s.name as source_name, s.source_type, s.url as source_url
            FROM v05f_collection_items i
            LEFT JOIN v04g_monitoring_sources s ON s.id=i.monitoring_source_id
            WHERE date(i.captured_at)=? AND i.quality_status='accepted'
            ORDER BY i.captured_at DESC
            LIMIT 50
            """,
            (today,),
        ).fetchall()
        processed_items = []
        for item in items:
            item_dict = dict(item)
            candidates = conn.execute(
                """
                SELECT * FROM v05g_extraction_candidates
                WHERE collection_item_id=? AND candidate_type IN ('event', 'organization', 'person', 'project')
                ORDER BY confidence_score DESC
                """,
                (item["id"],),
            ).fetchall()
            event_candidates = [c for c in candidates if c["candidate_type"] == "event"]
            entity_candidates = [c for c in candidates if c["candidate_type"] in ("organization", "person", "project")][:5]
            item_dict["event_type"] = event_candidates[0]["normalized_value"] if event_candidates else "其他"
            item_dict["entities"] = [dict(c) for c in entity_candidates]
            item_dict["candidate_count"] = len(candidates)
            item_dict["quality_label"] = QUALITY_STATUS_LABELS.get(item["quality_status"], item["quality_status"])
            processed_items.append(item_dict)
        latest_run = conn.execute(
            """
            SELECT * FROM v04g_monitoring_runs
            ORDER BY started_at DESC LIMIT 1
            """
        ).fetchone()
        return {
            "stats": dict(stats) if stats else {},
            "items": processed_items,
            "today": today,
            "latest_run": dict(latest_run) if latest_run else None,
        }


def get_intelligence_detail(item_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    path = Path(db_path) if db_path else default_db_path()
    with db_connection(path) as conn:
        item = conn.execute(
            """
            SELECT i.*, s.name as source_name, s.source_type, s.url as source_url
            FROM v05f_collection_items i
            LEFT JOIN v04g_monitoring_sources s ON s.id=i.monitoring_source_id
            WHERE i.id=?
            """,
            (item_id,),
        ).fetchone()
        if not item:
            return None
        item_dict = dict(item)
        snapshot = conn.execute("SELECT * FROM v04g_source_snapshots WHERE id=?", (item["snapshot_id"],)).fetchone()
        if snapshot:
            item_dict["snapshot"] = dict(snapshot)
        candidates = conn.execute(
            """
            SELECT * FROM v05g_extraction_candidates
            WHERE collection_item_id=?
            ORDER BY candidate_type, confidence_score DESC
            """,
            (item["id"],),
        ).fetchall()
        item_dict["candidates"] = [dict(c) for c in candidates]
        item_dict["quality_label"] = QUALITY_STATUS_LABELS.get(item["quality_status"], item["quality_status"])
        feedback = conn.execute(
            """
            SELECT * FROM v05h_intelligence_feedback WHERE collection_item_id=? ORDER BY created_at DESC
            """,
            (item["id"],),
        ).fetchall()
        item_dict["feedback"] = [dict(f) for f in feedback]
        return item_dict


def submit_feedback(item_id: int, user_name: str, feedback_type: str, note: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_feedback_table(db_path)
    path = Path(db_path) if db_path else default_db_path()
    ts = now()
    with db_connection(path) as conn:
        cur = conn.execute(
            """
            INSERT INTO v05h_intelligence_feedback(collection_item_id, user_name, feedback_type, note, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (item_id, user_name, feedback_type, note, ts),
        )
        return {"id": int(cur.lastrowid), "item_id": item_id, "feedback_type": feedback_type, "created_at": ts}


def get_quality_dashboard(db_path: str | Path | None = None) -> dict[str, Any]:
    path = Path(db_path) if db_path else default_db_path()
    with db_connection(path) as conn:
        overall = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN quality_status='accepted' THEN 1 ELSE 0 END) as accepted,
                SUM(CASE WHEN quality_status='pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN quality_status='duplicate' THEN 1 ELSE 0 END) as duplicate,
                SUM(CASE WHEN quality_status='low_quality' OR quality_status='insufficient_content' THEN 1 ELSE 0 END) as low_quality,
                SUM(CASE WHEN quality_status='irrelevant' THEN 1 ELSE 0 END) as irrelevant,
                SUM(CASE WHEN quality_status='access_denied' THEN 1 ELSE 0 END) as access_denied,
                SUM(CASE WHEN quality_status='parse_failed' THEN 1 ELSE 0 END) as parse_failed
            FROM v05f_collection_items
            """
        ).fetchone()
        today_stats = conn.execute(
            """
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN quality_status='accepted' THEN 1 ELSE 0 END) as accepted,
                SUM(CASE WHEN processing_status='processed' THEN 1 ELSE 0 END) as processed
            FROM v05f_collection_items
            WHERE date(captured_at)=date('now','localtime')
            """
        ).fetchone()
        candidate_stats = conn.execute(
            """
            SELECT
                COUNT(*) as total_candidates,
                SUM(CASE WHEN candidate_type='event' THEN 1 ELSE 0 END) as event_candidates,
                SUM(CASE WHEN candidate_type='organization' THEN 1 ELSE 0 END) as org_candidates,
                SUM(CASE WHEN candidate_type='person' THEN 1 ELSE 0 END) as person_candidates,
                SUM(CASE WHEN candidate_type='project' THEN 1 ELSE 0 END) as project_candidates,
                SUM(CASE WHEN evidence_excerpt IS NULL OR evidence_excerpt='' THEN 1 ELSE 0 END) as no_evidence_candidates
            FROM v05g_extraction_candidates
            """
        ).fetchone()
        avg_candidates = conn.execute(
            """
            SELECT AVG(cnt) as avg_per_item FROM (
                SELECT COUNT(*) as cnt FROM v05g_extraction_candidates GROUP BY collection_item_id
            )
            """
        ).fetchone()
        feedback_stats = conn.execute(
            """
            SELECT feedback_type, COUNT(*) as count
            FROM v05h_intelligence_feedback
            GROUP BY feedback_type
            """
        ).fetchall()
        return {
            "overall": dict(overall) if overall else {},
            "today": dict(today_stats) if today_stats else {},
            "candidates": dict(candidate_stats) if candidate_stats else {},
            "avg_candidates_per_item": float(avg_candidates["avg_per_item"] or 0),
            "feedback": {f["feedback_type"]: f["count"] for f in feedback_stats},
        }


def generate_summary(item: dict) -> str:
    snapshot = item.get("snapshot")
    if not snapshot:
        return item.get("title", "")[:160]
    text = snapshot.get("cleaned_text") or snapshot.get("raw_content") or ""
    title = snapshot.get("page_title") or item.get("title") or ""
    event_type = item.get("event_type", "")
    sentences = [s.strip() for s in text.split("。") if s.strip()]
    if sentences:
        first_sentence = sentences[0]
        if event_type and event_type != "其他":
            return f"{event_type}：{first_sentence[:120]}"[:160]
        return first_sentence[:160]
    return title[:160]


def generate_watch_reason(item: dict) -> str:
    event_type = item.get("event_type", "")
    entities = item.get("entities", [])
    if event_type in {"监管审批", "临床进展", "融资事件", "并购交易"}:
        return f"涉及{event_type}"
    if entities:
        org_names = [e["subject_label"] for e in entities if e["candidate_type"] == "organization"][:2]
        if org_names:
            return f"涉及{'、'.join(org_names)}"
    return "尚待人工评估"