from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.golden_loop_service import GoldenLoopService
from app.services.intelligence_flow_service import schedule_due_collection_jobs
from app.services.intelligence_product_service import IntelligenceProductService
from app.services.processing.entity_extraction_service import extract_candidates
from app.services.processing.subject_matching_service import match_subject


ROOT = Path(__file__).resolve().parents[1]


def _session(database: Path) -> Session:
    engine = create_engine(
        f"sqlite:///{database.as_posix()}", connect_args={"check_same_thread": False}
    )
    return Session(engine)


def test_r7_organization_alias_matches_existing_subject_and_people_stay_ambiguous(
    temp_database: Path,
) -> None:
    stamp = datetime.now().replace(microsecond=0).isoformat()
    with sqlite3.connect(temp_database) as conn:
        conn.row_factory = sqlite3.Row
        conn.execute(
            """INSERT INTO organizations(
                external_id,standard_name,name,short_name,visibility,verification_status,is_active,created_at)
                VALUES ('ORG-R7-ALIAS','利博治疗有限公司','LIB Therapeutics B.V.','LIBTherapeutics',
                        '内部','已确认',1,?)""",
            (stamp,),
        )
        for external_id in ("PER-R7-A", "PER-R7-B"):
            conn.execute(
                """INSERT INTO people(
                    external_id,name,visibility,verification_status,is_active,created_at)
                    VALUES (?,'Alex Lee','内部','待核验',1,?)""",
                (external_id, stamp),
            )
        alias = match_subject(conn, "organization", "LIBTherapeutics")
        same_name = match_subject(conn, "person", "Alex Lee")

    assert alias["status"] == "confirmed"
    assert alias["method"] == "exact_alias"
    assert alias["matches"][0]["external_id"] == "ORG-R7-ALIAS"
    assert same_name["status"] == "ambiguous"
    assert same_name["ambiguity_count"] == 2


def test_r7_english_person_action_is_candidate_not_automatic_subject() -> None:
    text_value = (
        "Ivo Claassen joined EMA in 2018. "
        "Melanie Carr has been assigned Deputy Executive Director duties."
    )
    candidates = extract_candidates(
        {"text": text_value, "evidence_excerpt": text_value},
        "news_event",
        {"source_url": "https://example.invalid/news", "source_title": "EMA news"},
    )
    people = [row for row in candidates if row["candidate_type"] == "person"]
    assert [row["subject_label"] for row in people] == ["Ivo Claassen", "Melanie Carr"]
    assert all(row["extraction_rule"] == "person_role_en" for row in people)
    assert all(row["confidence_score"] < 85 for row in people)


def test_r7_policy_title_wins_over_generic_clinical_word_in_body() -> None:
    candidates = extract_candidates(
        {"text": "本措施支持外资企业开展临床研究并建设研发中心。"},
        "product_pipeline",
        {
            "source_url": "https://example.invalid/policy",
            "source_title": "关于支持生物医药外资企业项目落地的若干措施",
        },
    )
    events = [row for row in candidates if row["candidate_type"] == "event"]
    assert events[0]["normalized_value"] == "政策发布"
    assert events[0]["payload"]["event_type"] == "policy"


def test_r7_value_class_requires_confirmed_business_record(temp_database: Path) -> None:
    stamp = datetime.now().replace(microsecond=0).isoformat()
    with sqlite3.connect(temp_database) as conn:
        item_id = conn.execute(
            """INSERT INTO v06_intelligence_items(
                title,summary,intel_type,event_type,importance,source_name,source_url,
                visibility,status,is_demo,created_at,updated_at)
                VALUES ('R7监管事件','公开监管事实','监管审批','approval',4,'官方来源',
                        'https://example.invalid/regulatory','organization','published',0,?,?)""",
            (stamp, stamp),
        ).lastrowid
        conn.commit()

    with _session(temp_database) as db:
        service = GoldenLoopService(db)
        before = service.event_insight(int(item_id))
        assert before["value_class"] == "WATCH"
        assert before["business_opportunity"] is False
        db.execute(
            text(
                """INSERT INTO v06_market_resources(
                    title,direction,resource_type,summary,publisher_id,status,visibility,is_demo,
                    source_intelligence_id,created_at,updated_at)
                    VALUES ('R7真实需求','demand','产业合作','经人工确认的实际需求',1,
                            'published','organization',0,:item_id,:stamp,:stamp)"""
            ),
            {"item_id": int(item_id), "stamp": stamp},
        )
        db.commit()
        after = service.event_insight(int(item_id))
        metrics = service.workbench()["home_metrics"]

    assert after["value_class"] == "ACTIONABLE"
    assert after["business_opportunity"] is False
    assert after["business_opportunity_label"] == "尚未形成业务机会"
    assert metrics["actionable_intelligence"] >= 1


def test_r7_disabled_sources_are_not_scheduled(temp_database: Path) -> None:
    stamp = datetime.now().replace(microsecond=0).isoformat()
    with sqlite3.connect(temp_database) as conn:
        source_id = conn.execute(
            """INSERT INTO v04g_monitoring_sources(
                source_no,name,source_type,url,check_frequency,is_enabled,auto_paused,
                fetch_mode,created_at,updated_at)
                VALUES ('SRC-R7-DISABLED','R7 disabled','website','https://example.invalid/disabled',
                        'daily',0,0,'web',?,?)""",
            (stamp, stamp),
        ).lastrowid
        conn.commit()
    result = schedule_due_collection_jobs(
        limit=200, db_path=temp_database, operator="r7-test"
    )
    assert all(int(row["monitoring_source_id"]) != int(source_id) for row in result["jobs"])


def test_r7_product_update_clears_rejected_subject_names(temp_database: Path) -> None:
    stamp = datetime.now().replace(microsecond=0).isoformat()
    with sqlite3.connect(temp_database) as conn:
        product_id = conn.execute(
            """INSERT INTO v06_intelligence_items(
                title,intel_type,companies,people_involved,visibility,status,is_demo,created_at,updated_at)
                VALUES ('R7 subject cleanup','政策发布','false org','false person','organization','published',0,?,?)""",
            (stamp, stamp),
        ).lastrowid
        conn.commit()
    product = IntelligenceProductService(temp_database).update_product(
        int(product_id), {"companies": None, "people_involved": None}, actor="r7-test"
    )
    assert product["companies"] is None
    assert product["people_involved"] is None
    service_source = (ROOT / "app/services/intelligence_product_service.py").read_text(encoding="utf-8")
    assert "pipeline_review_status" in service_source and "('approved','applied')" in service_source


def test_r7_intelligence_detail_uses_business_language_and_existing_review_path() -> None:
    template = (ROOT / "app/templates/platform/intelligence_detail.html").read_text(
        encoding="utf-8"
    )
    assert "发生了什么" in template and "为什么值得关注" in template
    assert "原文可能提及" in template
    assert "人工确认正式主体" in template
    assert "/processing/candidates/" not in template
    assert "与我们的关系" in template
