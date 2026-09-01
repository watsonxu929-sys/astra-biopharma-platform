from __future__ import annotations

from pathlib import Path

from app.platform.capability_registry import MVP_PRODUCT_KEYS, filter_capabilities
from app.routes_platform import workspace
from app.security import ROLE_PERMISSIONS, required_permission
from app.services.navigation_service import get_client_navigation, get_secondary_navigation
from app.v05h_reports import report_detail, router as report_router


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_PRIMARY = ["工作台", "情报", "企业与人物", "俱乐部", "跟进"]


def test_rc1_2b_primary_and_secondary_navigation_are_frozen() -> None:
    for role in ("viewer", "operator", "reviewer", "admin"):
        context = {"permissions": sorted(ROLE_PERMISSIONS[role])}
        assert [item["label"] for item in get_client_navigation(context, path="/platform")["primary"]] == EXPECTED_PRIMARY
    admin_context = {"permissions": sorted(ROLE_PERMISSIONS["admin"])}
    assert [item["label"] for item in get_secondary_navigation(admin_context, "intelligence", "/intelligence")] == [
        "情报首页", "采集与数据源", "报告", "我的订阅",
    ]
    operator_context = {"permissions": sorted(ROLE_PERMISSIONS["operator"])}
    assert [item["label"] for item in get_secondary_navigation(operator_context, "intelligence", "/collection")] == [
        "情报首页", "采集与数据源", "报告", "我的订阅",
    ]
    source_navigation = get_client_navigation(operator_context, path="/collection/sources")["secondary"]
    assert next(item for item in source_navigation if item["label"] == "采集与数据源")["active"] is True
    viewer_context = {"permissions": sorted(ROLE_PERMISSIONS["viewer"])}
    assert "采集与数据源" not in [
        item["label"] for item in get_secondary_navigation(viewer_context, "intelligence", "/intelligence")
    ]
    assert [item["label"] for item in get_secondary_navigation(admin_context, "club", "/club")] == [
        "俱乐部首页", "会员", "活动", "供需与匹配",
    ]


def test_rc1_2b_product_surface_keeps_contextual_capabilities_without_primary_nav() -> None:
    visible = filter_capabilities(set(ROLE_PERMISSIONS["viewer"]), client="web")
    visible_keys = {item["capability_key"] for item in visible}
    assert visible_keys <= MVP_PRODUCT_KEYS
    assert {"resources", "resources.demand", "resources.supply"} <= visible_keys
    assert "resources" not in {item["key"] for item in get_client_navigation(
        {"permissions": sorted(ROLE_PERMISSIONS["viewer"])}, path="/resources"
    )["primary"]}


def test_workspace_is_compatibility_redirect_and_club_writes_remain_protected() -> None:
    response = workspace(None, None)
    assert response.status_code == 302
    assert response.headers["location"] == "/platform"
    assert required_permission("/club/members", "GET") == "view_internal"
    assert required_permission("/club/matches", "GET") == "view_internal"
    assert required_permission("/club/members", "POST") == "manage_club"
    assert required_permission("/club/matches", "POST") == "manage_club"


def test_report_detail_route_is_bound_to_report_handler() -> None:
    matching = [
        route for route in report_router.routes
        if getattr(route, "path", "") == "/reports/{report_id:int}"
    ]
    assert len(matching) == 1
    assert matching[0].endpoint is report_detail


def test_shared_shell_separates_product_and_admin_surfaces() -> None:
    shell = (ROOT / "app/templates/base.html").read_text(encoding="utf-8-sig")
    assert "surface-admin" in shell
    assert "管理控制台" in shell
    assert "返回业务产品" in shell
    assert "path.startswith('/admin') or path.startswith('/system') or path.startswith('/collection')" not in shell
    collection = (ROOT / "app/templates/v05f_collection.html").read_text(encoding="utf-8")
    for label in ("采集概览", "采集来源", "采集任务", "原始情报"):
        assert label in collection
    processing = (ROOT / "app/templates/v05g_processing.html").read_text(encoding="utf-8")
    assert "管理员工具" in processing
    assert "管理控制台" in processing
