from __future__ import annotations

from pathlib import Path

from app.main import app, legacy_dashboard_alias
from app.platform.capability_registry import MVP_PRODUCT_KEYS, filter_capabilities, validate_registry
from app.routes_platform import legacy_resource_demand, legacy_resource_matching, legacy_resource_supply
from app.security import ROLE_PERMISSIONS
from app.services.navigation_service import get_client_navigation
from app.v05d_member_portal import member_home


ROOT = Path(__file__).resolve().parents[1]


def test_non_admin_product_surface_is_exactly_fifteen_capabilities() -> None:
    assert validate_registry() == []
    for role in ("viewer", "operator", "reviewer"):
        visible = filter_capabilities(set(ROLE_PERMISSIONS[role]), client="web")
        assert {item["capability_key"] for item in visible} == MVP_PRODUCT_KEYS
        assert len(visible) == 15


def test_primary_navigation_is_the_five_business_domains() -> None:
    for role in ("viewer", "operator", "reviewer", "admin"):
        context = {"permissions": sorted(ROLE_PERMISSIONS[role])}
        labels = [item["label"] for item in get_client_navigation(context, path="/platform")["primary"]]
        assert labels == ["工作台", "情报", "关系", "资源", "协作"]


def test_legacy_product_entries_redirect_without_new_business_pages() -> None:
    expected = {
        legacy_resource_demand: "/resources?direction=demand",
        legacy_resource_supply: "/resources?direction=supply",
        legacy_resource_matching: "/resources",
        legacy_dashboard_alias: "/platform",
    }
    for endpoint, location in expected.items():
        response = endpoint()
        assert response.status_code == 303
        assert response.headers["location"] == location
    assert member_home(None).headers["location"] == "/club"

    routes: set[str] = set()
    for route in app.routes:
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            routes.update(getattr(context, "path", "") for context in contexts())
        else:
            routes.add(getattr(route, "path", ""))
    assert {"/dashboard", "/resources/demand", "/resources/supply", "/resources/matching", "/member"} <= routes


def test_formal_templates_hide_legacy_and_engineering_surface_terms() -> None:
    base = (ROOT / "app/templates/base.html").read_text(encoding="utf-8-sig")
    assert 'href="/help"' not in base

    formal_templates = [
        "platform/home.html",
        "platform/intelligence.html",
        "platform/intelligence_detail.html",
        "platform/network.html",
        "platform/resources.html",
        "platform/resource_detail.html",
        "platform/opportunities.html",
    ]
    combined = "\n".join((ROOT / "app/templates" / name).read_text(encoding="utf-8") for name in formal_templates)
    for term in ("黄金业务闭环", "人脉推荐", "专题研究", "我的订阅"):
        assert term not in combined
    assert "运营场景：Q-BAY" in (ROOT / "app/templates/v04f_club.html").read_text(encoding="utf-8")
