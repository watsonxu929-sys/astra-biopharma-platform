from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.routes_platform import STATUS_LABELS, _templates, status_label
from app.security import ROLE_PERMISSIONS
from app.p3_network import templates as network_templates
from app.services.golden_loop_service import GoldenLoopService
from app.services.navigation_service import get_client_navigation
from app.services.unified_intelligence_service import UnifiedIntelligenceService
from app.services.unified_opportunity_service import UnifiedOpportunityService
from app.services.unified_resource_service import UnifiedResourceService


ROOT = Path(__file__).resolve().parents[1]


def _session(database: Path) -> Session:
    engine = create_engine(
        f"sqlite:///{database.as_posix()}",
        connect_args={"check_same_thread": False},
    )
    return Session(engine)


def test_workbench_metrics_are_canonical_and_click_filters_match(temp_database: Path) -> None:
    with _session(temp_database) as db:
        metrics = GoldenLoopService(db).workbench()["home_metrics"]
        assert {
            "today_intelligence",
            "pending_judgement",
            "pending_subjects",
            "active_demands",
            "active_supplies",
            "pending_matches",
            "active_opportunities",
            "today_followups",
            "overdue_followups",
            "won_this_month",
            "recent_relationships",
        } <= metrics.keys()
        pending_subject = UnifiedIntelligenceService(db).list(workflow="pending_subject")
        assert pending_subject["total"] == metrics["pending_subjects"]
        assert all(item.status == "published" for item in pending_subject["items"])
        demands = UnifiedResourceService(db).list(direction="demand", status="published")
        supplies = UnifiedResourceService(db).list(direction="supply", status="published")
        assert demands["total"] == metrics["active_demands"]
        assert supplies["total"] == metrics["active_supplies"]


def test_resource_and_opportunity_product_filters_are_real(temp_database: Path) -> None:
    with _session(temp_database) as db:
        resources = UnifiedResourceService(db)
        published = resources.list(status="published", include_legacy=False)
        all_states = resources.list(status="all", include_legacy=False)
        assert all_states["total"] >= published["total"]
        opportunities = UnifiedOpportunityService(db)
        active = opportunities.list(user_id=None, is_admin=True, status="active")
        all_states = opportunities.list(user_id=None, is_admin=True, status="all")
        owners = db.execute(text("SELECT id,username FROM v05a_users WHERE status='active' ORDER BY username")).all()
        assert owners

        assert all_states["total"] >= active["total"]
        assert all(row.status == "active" for row in active["items"])


def test_rule_guidance_covers_each_canonical_object(temp_database: Path) -> None:
    with _session(temp_database) as db:
        service = GoldenLoopService(db)
        intelligence_id = db.execute(text("SELECT id FROM v06_intelligence_items WHERE status='published' ORDER BY id LIMIT 1")).scalar()
        resource_id = db.execute(text("SELECT id FROM v06_market_resources ORDER BY id LIMIT 1")).scalar()
        opportunity_id = db.execute(text("SELECT id FROM v06_opportunities ORDER BY id LIMIT 1")).scalar()
        assert set(service.trace(intelligence_id)["guidance"]) == {"current_state", "next_action"}
        assert set(service.resource_trace(resource_id)["guidance"]) == {"current_state", "next_action"}
        assert set(service.opportunity_trace(opportunity_id)["guidance"]) == {"current_state", "next_action"}


def test_user_visible_statuses_and_templates_are_product_facing() -> None:
    assert status_label("active") == "跟进中"
    assert status_label("lost") == "未成交"
    assert status_label("unknown_internal_enum") == "待确认"
    assert STATUS_LABELS["won"] == "已达成"
    templates = [
        "platform/home.html",
        "platform/intelligence.html",
        "platform/intelligence_detail.html",
        "platform/resources.html",
        "platform/resource_detail.html",
        "platform/opportunities.html",
        "platform/opportunity_detail.html",
    ]
    for name in templates:
        _templates.env.get_template(name)
    network_templates.env.get_template("p3_network.html")
    golden = (ROOT / "app/templates/platform/golden_loop.html").read_text(encoding="utf-8")
    opportunity = (ROOT / "app/templates/platform/opportunity_detail.html").read_text(encoding="utf-8")
    assert "正式主体 ID" not in golden
    assert "viewer" not in golden
    assert "MVP-RC1" not in golden
    assert "补充合作证据" in opportunity
    assert "来源情报 #" not in opportunity


def test_five_formal_navigation_labels_are_exact() -> None:
    navigation = get_client_navigation(
        {"permissions": sorted(ROLE_PERMISSIONS["admin"])}, path="/platform"
    )
    assert [item["label"] for item in navigation["primary"]] == [
        "工作台", "情报", "企业与人物", "俱乐部", "跟进",
    ]
