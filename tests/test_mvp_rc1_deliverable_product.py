from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.security import ROLE_PERMISSIONS
from app.services.golden_loop_service import GoldenLoopService
from app.services.navigation_service import get_client_navigation
from app.services.processing.entity_extraction_service import extract_candidates


def _session(database: Path) -> Session:
    engine = create_engine(
        f"sqlite:///{database.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    return Session(engine)


def test_rc1_primary_navigation_is_product_first() -> None:
    for role in ("viewer", "operator", "reviewer", "admin"):
        navigation = get_client_navigation(
            {"permissions": sorted(ROLE_PERMISSIONS[role])}, path="/platform"
        )
        assert [item["label"] for item in navigation["primary"]] == [
            "工作台", "情报", "企业与人物", "跟进",
        ]


def test_rc1_ema_and_eismea_are_not_projects() -> None:
    rows = extract_candidates(
        {
            "text": (
                "European Medicines Agency (EMA) and the European Innovation Council "
                "reported an update with EISMEA. ABC-123 remains a development project."
            ),
            "index": 0,
        },
        "news_event",
        {"source_url": "https://example.invalid", "source_title": "Regulatory update"},
    )
    projects = {row["subject_label"] for row in rows if row["candidate_type"] == "project"}
    organizations = {row["subject_label"] for row in rows if row["candidate_type"] == "organization"}
    assert "EMA" not in projects
    assert "EISMEA" not in projects
    assert "ABC-123" in projects
    assert any("Agency" in name or "Council" in name for name in organizations)


def test_rc1_reading_view_preserves_original_and_labels_manual_sample(
    temp_database: Path,
) -> None:
    with _session(temp_database) as db:
        item_id = int(db.execute(text(
            "SELECT id FROM v06_intelligence_items WHERE status='published' ORDER BY id LIMIT 1"
        )).scalar())
        db.execute(
            text(
                """UPDATE v06_intelligence_items
                   SET title='English regulatory source',summary='Original evidence remains.',
                       analysis_notes=:notes WHERE id=:id"""
            ),
            {
                "id": item_id,
                "notes": json.dumps(
                    {
                        "translation": {
                            "mode": "MANUAL_CURATED_ACCEPTANCE_SAMPLE",
                            "title_zh": "监管动态中文验收样本",
                            "summary_zh": "中文内容仅用于隔离验收，原文仍作为证据保留。",
                        }
                    },
                    ensure_ascii=False,
                ),
            },
        )
        db.commit()
        view = GoldenLoopService(db).reading_view(item_id)
    assert view["display_title"] == "监管动态中文验收样本"
    assert view["translation_mode"] == "MANUAL_CURATED_ACCEPTANCE_SAMPLE"
    assert view["original_title"] == "English regulatory source"


def test_rc1_today_queue_excludes_old_and_supports_per_user_restore(
    temp_database: Path,
) -> None:
    with _session(temp_database) as db:
        db.execute(text(
            """CREATE TABLE IF NOT EXISTS v05h_intelligence_feedback (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                collection_item_id INTEGER,
                user_id INTEGER,
                user_name TEXT,
                feedback_type TEXT NOT NULL,
                note TEXT,
                created_at TEXT NOT NULL
            )"""
        ))
        user_id = int(db.execute(text(
            "SELECT id FROM v05a_users WHERE status='active' ORDER BY id LIMIT 1"
        )).scalar())
        item = db.execute(text(
            """SELECT id FROM v06_intelligence_items
               WHERE status='published' ORDER BY id LIMIT 1"""
        )).mappings().first()
        collection_id = int(db.execute(text(
            "SELECT id FROM v05f_collection_items ORDER BY id LIMIT 1"
        )).scalar())
        item_id = int(item["id"])
        db.execute(
            text(
                """UPDATE v06_intelligence_items
                   SET source_record_type='v05f_collection_items',source_record_id=:collection_id,
                       published_at=:recent,is_demo=0 WHERE id=:id"""
            ),
            {
                "collection_id": collection_id,
                "recent": (datetime.now() - timedelta(days=1)).replace(microsecond=0),
                "id": item_id,
            },
        )
        old_id = int(db.execute(text(
            """SELECT id FROM v06_intelligence_items
               WHERE status='published' AND id<>:id ORDER BY id LIMIT 1"""
        ), {"id": item_id}).scalar())
        db.execute(
            text("UPDATE v06_intelligence_items SET published_at=:old,is_demo=0 WHERE id=:id"),
            {"old": datetime.now() - timedelta(days=45), "id": old_id},
        )
        db.commit()
        service = GoldenLoopService(db)
        assert item_id in {row["id"] for row in service.priority_feed(limit=20, user_id=user_id)}
        assert old_id not in {row["id"] for row in service.priority_feed(limit=20, user_id=user_id)}
        service.set_today_disposition(item_id, actor_user_id=user_id, dismissed=True)
        assert item_id not in {row["id"] for row in service.priority_feed(limit=20, user_id=user_id)}
        assert item_id in {row["id"] for row in service.dismissed_today(user_id)}
        service.set_today_disposition(item_id, actor_user_id=user_id, dismissed=False)
        assert item_id in {row["id"] for row in service.priority_feed(limit=20, user_id=user_id)}


def test_rc1_follow_up_is_canonical_traceable_persistent_and_idempotent(
    temp_database: Path,
) -> None:
    with _session(temp_database) as db:
        user_id = int(db.execute(text(
            "SELECT id FROM v05a_users WHERE status='active' ORDER BY id LIMIT 1"
        )).scalar())
        item_id = int(db.execute(text(
            "SELECT id FROM v06_intelligence_items WHERE status='published' ORDER BY id LIMIT 1"
        )).scalar())
        service = GoldenLoopService(db)
        fields = {
            "actor_user_id": user_id,
            "object_name": "真实验收主体",
            "matter": "核实公开动态",
            "reason": "与当前产业运营相关",
            "next_action": "联系现有负责人核对",
            "next_follow_at": (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M"),
        }
        first = service.create_follow_up_from_intelligence(item_id, **fields)
        second = service.create_follow_up_from_intelligence(item_id, **fields)
        persisted = db.execute(text(
            """SELECT f.id,o.source_intelligence_id,o.opp_type,o.owner_id
               FROM v06_follow_ups f JOIN v06_opportunities o ON o.id=f.opportunity_id
               WHERE f.id=:id"""
        ), {"id": int(first["id"])}).mappings().one()
        todo_ids = {row["id"] for row in service.current_user_follow_ups(user_id)}
    assert persisted["source_intelligence_id"] == item_id
    assert persisted["opp_type"] == "follow_up"
    assert persisted["owner_id"] == user_id
    assert second["id"] == first["id"]
    assert second["created"] is False
    assert first["id"] in todo_ids


def test_rc1_viewer_writes_remain_forbidden() -> None:
    with pytest.raises(HTTPException) as error:
        GoldenLoopService.require_writer("viewer")
    assert error.value.status_code == 403


def test_rc1_formal_copy_has_exact_empty_states_and_no_engineering_pipeline() -> None:
    root = Path(__file__).resolve().parents[1]
    home = (root / "app/templates/platform/home.html").read_text(encoding="utf-8")
    detail = (root / "app/templates/platform/intelligence_detail.html").read_text(encoding="utf-8")
    entity = (root / "app/templates/p3_network.html").read_text(encoding="utf-8")
    assert "今天暂时没有需要优先处理的产业动态。" in home
    assert "当前未发现直接关系" in detail
    assert "暂无相关资源" in detail
    assert "暂无进行中的跟进" in entity
    for term in ("Collection Pipeline", "Processing", "Candidate", "Recommendation"):
        assert term not in home + detail
