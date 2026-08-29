from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.golden_loop_service import GoldenLoopService
from app.services.unified_resource_service import UnifiedResourceService


ROOT = Path(__file__).resolve().parents[1]


def _session(database: Path) -> Session:
    engine = create_engine(
        f"sqlite:///{database.as_posix()}", connect_args={"check_same_thread": False}
    )
    return Session(engine)


def test_r4_matching_is_explained_owner_safe_and_respects_rejection(
    temp_database: Path,
) -> None:
    with _session(temp_database) as db:
        actor_id = int(db.execute(text(
            "SELECT id FROM v05a_users WHERE status='active' ORDER BY id LIMIT 1"
        )).scalar_one())
        organization_ids = [int(row[0]) for row in db.execute(text(
            "SELECT id FROM organizations WHERE COALESCE(is_active,1)=1 ORDER BY id LIMIT 2"
        )).all()]
        assert len(organization_ids) == 2
        resources = UnifiedResourceService(db)
        demand = resources.create(actor_user_id=actor_id, fields={
            "title": "R4验收需求",
            "direction": "demand",
            "resource_type": "R4确定性匹配",
            "summary": "寻找生物医药研发合作伙伴",
            "organization_id": organization_ids[0],
            "status": "published",
        })
        supply = resources.create(actor_user_id=actor_id, fields={
            "title": "R4验收供给",
            "direction": "supply",
            "resource_type": "R4确定性匹配",
            "summary": "提供生物医药研发合作能力",
            "organization_id": organization_ids[1],
            "status": "published",
        })
        same_owner = resources.create(actor_user_id=actor_id, fields={
            "title": "R4同主体供给",
            "direction": "supply",
            "resource_type": "R4确定性匹配",
            "summary": "同主体资源不应推荐",
            "organization_id": organization_ids[0],
            "status": "published",
        })

        candidates = resources.match(demand.id)
        by_id = {int(item["resource"].id): item for item in candidates}
        assert int(supply.id) in by_id
        assert int(same_owner.id) not in by_id
        assert by_id[int(supply.id)]["owner_label"] != "主体信息待补充"
        assert any("资源类别一致" in reason for reason in by_id[int(supply.id)]["reasons"])
        assert any("有效状态" in reason for reason in by_id[int(supply.id)]["reasons"])

        golden = GoldenLoopService(db)
        match = golden.confirm_match(
            demand_resource_id=int(demand.id),
            supply_resource_id=int(supply.id),
            actor_user_id=actor_id,
        )
        golden.set_match_intention(
            int(match["id"]), actor_user_id=actor_id,
            intention="not_interested", reason_code="conditions_not_met",
        )
        assert int(supply.id) not in {
            int(item["resource"].id) for item in resources.match(demand.id)
        }


def test_r4_formal_pages_use_business_language_and_no_manual_id_fields() -> None:
    intelligence = (ROOT / "app/templates/platform/intelligence_detail.html").read_text(encoding="utf-8")
    resource = (ROOT / "app/templates/platform/resource_detail.html").read_text(encoding="utf-8")
    match = (ROOT / "app/templates/platform/golden_match_detail.html").read_text(encoding="utf-8")
    opportunity = (ROOT / "app/templates/platform/opportunity_detail.html").read_text(encoding="utf-8")
    compatibility = (ROOT / "app/templates/platform/golden_loop.html").read_text(encoding="utf-8")
    opportunities = (ROOT / "app/templates/platform/opportunities.html").read_text(encoding="utf-8")

    assert "人工确认正式主体" in intelligence
    assert "建立跟进" in intelligence and "相关资源" in intelligence
    assert "匹配候选" in resource and "推荐理由" in resource
    assert "确认匹配" in resource and "暂不匹配" in resource
    assert "转为合作机会" in match
    assert "合作双方" in opportunity and "机会来源" in opportunity
    assert "还没有跟进记录" in opportunity
    assert "Golden Loop" not in "\n".join((intelligence, resource, match, opportunity, compatibility))
    assert "Step 1" not in compatibility and "Step 2" not in compatibility
    assert "/opportunities/new" not in opportunities
    for source in (intelligence, resource, match, opportunity):
        assert 'type="number" name="subject_id"' not in source
        assert 'type="number" name="resource_id"' not in source
        assert 'type="number" name="match_id"' not in source
        assert 'type="number" name="opportunity_id"' not in source
