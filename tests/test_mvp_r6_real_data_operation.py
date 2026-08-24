from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.golden_loop_service import GoldenLoopService
from app.services.intelligence_product_service import IntelligenceProductService
from app.services.intelligence_review_service import IntelligenceReviewService
from app.services.processing.content_quality_service import check_content_quality
from app.services.processing.entity_extraction_service import _is_bad_heading
from app.services.product_recovery_service import run_inline_intelligence_flow


ROOT = Path(__file__).resolve().parents[1]


def _session(database: Path) -> Session:
    engine = create_engine(
        f"sqlite:///{database.as_posix()}", connect_args={"check_same_thread": False}
    )
    return Session(engine)


def _real_rule_flow(database: Path) -> tuple[int, int]:
    html = """
    <html><head><title>R6真实生物科技有限公司药物获监管批准</title></head><body><main>
    <h1>R6真实生物科技有限公司药物获监管批准</h1>
    <p>R6真实生物科技有限公司宣布其创新生物药获得监管机构批准，产品将用于临床治疗。</p>
    <p>该批准基于完整临床试验和药品安全数据，公司正在评估后续生产、注册与产业合作需求。</p>
    <p>公开信息同时说明研发团队将继续开展药物真实世界研究并更新医学证据。</p>
    </main></body></html>
    """
    flow = run_inline_intelligence_flow(
        html=html,
        title="R6真实监管来源",
        db_path=database,
        operator="r6-test",
    )
    assert flow["processed_jobs"] and flow["processed_jobs"][0]["status"] in {"success", "needs_review"}
    with sqlite3.connect(database) as conn:
        conn.row_factory = sqlite3.Row
        candidate = conn.execute(
            """
            SELECT * FROM v05g_extraction_candidates
            WHERE collection_item_id=? AND candidate_type='event'
            ORDER BY confidence_score DESC,id LIMIT 1
            """,
            (flow["collection_item_id"],),
        ).fetchone()
        assert candidate is not None
        evidence_count = conn.execute(
            "SELECT COUNT(*) FROM p2_fact_candidate_evidence WHERE candidate_id=?",
            (candidate["id"],),
        ).fetchone()[0]
        assert evidence_count == 1
        assert candidate["pipeline_review_status"] == "pending"
        return int(candidate["id"]), int(flow["collection_item_id"])


def test_r6_rule_candidate_uses_existing_evidence_review_and_canonical_publication(
    temp_database: Path,
) -> None:
    candidate_id, _ = _real_rule_flow(temp_database)
    IntelligenceReviewService(temp_database).review_candidate(
        candidate_id,
        decision="approved",
        actor="r6-reviewer",
        permissions={"review_data"},
    )
    service = IntelligenceProductService(temp_database)
    product = service.publish_candidate(
        candidate_id,
        actor="r6-reviewer",
        permissions={"review_data"},
        visibility="organization",
    )
    assert product["source_name"] == "R6真实监管来源"
    assert product["source_url"].startswith("inline:")
    assert product["event_type"] == "approval"
    assert product["intel_type"] == "监管审批"
    assert product["importance"] == 4
    assert service.publish_candidate(
        candidate_id,
        actor="r6-reviewer",
        permissions={"review_data"},
    )["id"] == product["id"]


def test_r6_subject_candidate_is_manual_confirm_or_ignore_only(temp_database: Path) -> None:
    candidate_id, collection_item_id = _real_rule_flow(temp_database)
    IntelligenceReviewService(temp_database).review_candidate(
        candidate_id,
        decision="approved",
        actor="r6-reviewer",
        permissions={"review_data"},
    )
    product = IntelligenceProductService(temp_database).publish_candidate(
        candidate_id,
        actor="r6-reviewer",
        permissions={"review_data"},
    )
    with sqlite3.connect(temp_database) as conn:
        stamp = "2026-08-24T12:00:00"
        org_id = conn.execute(
            """
            INSERT INTO organizations(
                external_id,standard_name,visibility,verification_status,is_active,created_at)
            VALUES ('ORG-R6-TEST','R6真实生物科技有限公司','内部','已确认',1,?)
            """,
            (stamp,),
        ).lastrowid
        org_candidate = conn.execute(
            """
            SELECT id FROM v05g_extraction_candidates
            WHERE collection_item_id=? AND candidate_type='organization'
            ORDER BY id LIMIT 1
            """,
            (collection_item_id,),
        ).fetchone()
        assert org_candidate is not None
        conn.execute(
            """
            UPDATE v05g_subject_match_candidates
            SET matched_subject_type='organization',matched_subject_id='ORG-R6-TEST',
                matched_subject_label='R6真实生物科技有限公司',match_method='exact_name',
                match_score=92,status='confirmed',ambiguity_count=0
            WHERE extraction_candidate_id=?
            """,
            (org_candidate[0],),
        )
        actor_id = conn.execute(
            "SELECT id FROM v05a_users WHERE status='active' ORDER BY id LIMIT 1"
        ).fetchone()[0]
        conn.commit()

    with _session(temp_database) as db:
        golden = GoldenLoopService(db)
        candidates = golden.subject_candidates(int(product["id"]))
        assert [(row["subject_label"], row["confidence"]) for row in candidates] == [
            ("R6真实生物科技有限公司", "高")
        ]
        golden.ignore_subject_candidate(
            int(product["id"]),
            subject_type="organization",
            subject_id=int(org_id),
            actor_user_id=int(actor_id),
        )
        assert golden.subject_candidates(int(product["id"])) == []
        db.execute(text(
            "DELETE FROM core_intelligence_workflow_events WHERE intelligence_item_id=:id AND action='subject_candidate_ignored'"
        ), {"id": int(product["id"])})
        db.commit()
        golden.link_subject(
            int(product["id"]),
            subject_type="organization",
            subject_id=int(org_id),
            actor_user_id=int(actor_id),
        )
        assert golden.subject_candidates(int(product["id"])) == []
        assert golden.subjects(int(product["id"]))[0]["subject_label"] == "R6真实生物科技有限公司"


def test_r6_intelligence_detail_exposes_explainable_candidate_actions() -> None:
    template = (ROOT / "app/templates/platform/intelligence_detail.html").read_text(encoding="utf-8")
    assert "为什么值得关注" in template
    assert "可能涉及" in template
    assert "确认关联" in template and "忽略" in template
    assert "/golden-loop/intelligence/{{ item.id }}/subjects" in template
    assert "AI" not in template


def test_r6_quality_gate_rejects_generic_site_pages_and_sentence_entities() -> None:
    generic = check_content_quality(
        "Roche | Contact Roche Continents",
        "\n".join([
            "Clinical trials and pharmaceutical research information for healthcare professionals.",
            "Biotechnology medicines, drug development and regulatory approval resources.",
            "Contact offices and general information for healthcare support.",
        ]),
        "https://www.roche.com/contact",
    )
    assert generic["quality_status"] == "low_quality"
    assert generic["quality_reason"] == "栏目页或通用页面"
    assert _is_bad_heading("另一方面助力钱塘区生物医药企业赴沪设立研发中心")
    assert _is_bad_heading("theRocheInstituteofMolecularBio")
    assert not _is_bad_heading("R6真实生物科技有限公司")


def test_r6_search_template_uses_mapping_items_key() -> None:
    template = (ROOT / "app/templates/platform/search_results.html").read_text(encoding="utf-8")
    assert 'group["items"]|length' in template
    assert 'group.items|length' not in template
    assert 'for item in group["items"]' in template
