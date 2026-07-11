from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

VALID_CATEGORIES = {"workspace", "network", "intelligence", "resources", "club", "admin", "account"}
VALID_CLIENTS = {"web", "app", "miniprogram", "admin"}
VALID_STATUS = {"active", "beta", "planned", "disabled"}


@dataclass(frozen=True)
class Capability:
    capability_key: str
    name: str
    short_name: str
    description: str
    category: str
    parent_key: str | None
    web_route: str
    api_prefix: str
    icon_key: str
    required_permission: str
    required_context: str
    client_support: tuple[str, ...]
    status: str
    order: int
    legacy_routes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["client_support"] = list(self.client_support)
        data["legacy_routes"] = list(self.legacy_routes)
        return data


def cap(key: str, name: str, short: str, desc: str, category: str, parent: str | None, route: str, api: str, icon: str, perm: str = "view_internal", ctx: str = "", clients: tuple[str, ...] = ("web", "app", "miniprogram"), status: str = "active", order: int = 100, legacy: tuple[str, ...] = ()) -> Capability:
    return Capability(key, name, short, desc, category, parent, route, api, icon, perm, ctx, clients, status, order, legacy)


CAPABILITIES: tuple[Capability, ...] = (
    cap("workspace", "工作台", "工作台", "业务概览、待办、跟进、收藏和最近访问", "workspace", None, "/platform", "/api/v1/client/bootstrap", "layout-dashboard", order=10, legacy=("/workspace",)),
    cap("workspace.overview", "业务概览", "概览", "平台业务摘要", "workspace", "workspace", "/platform", "/api/v1/client/bootstrap", "activity", order=11),
    cap("workspace.todos", "我的待办", "待办", "当前用户协作任务", "workspace", "workspace", "/workspace?tab=todos", "/api/v1/opportunities", "list-checks", order=12),
    cap("workspace.recent_followups", "最近跟进", "跟进", "最近商务跟进", "workspace", "workspace", "/workspace?tab=followups", "/api/v1/opportunities", "message-square", order=13),
    cap("workspace.favorites", "我的收藏", "收藏", "收藏和关注", "workspace", "workspace", "/workspace?tab=favorites", "/api/v1/collection", "bookmark", order=14),
    cap("workspace.recent", "最近访问", "访问", "最近访问记录", "workspace", "workspace", "/workspace?tab=recent", "/api/v1/client/bootstrap", "history", order=15),

    cap("network", "产业关系", "关系", "人物、机构、身份和产业关系", "network", None, "/network", "/api/v1/network", "network", order=20),
    cap("network.people_admin", "人物库", "人物库", "人物主数据管理", "network", "network", "/admin/people", "/api/v1/subjects/people", "users-round", "edit_data", clients=("web", "admin"), order=21),
    cap("network.organizations_admin", "机构库", "机构库", "机构主数据管理", "network", "network", "/admin/organizations", "/api/v1/organizations", "building-2", "edit_data", clients=("web", "admin"), order=22),
    cap("network.people", "人物发现", "人物", "产业人物发现", "network", "network", "/network/people", "/api/v1/network/people", "users", order=23, legacy=("/people",)),
    cap("network.organizations", "机构发现", "机构", "公开机构发现", "network", "network", "/network/organizations", "/api/v1/organizations", "building", "organization.view_self", order=24, legacy=("/organizations",)),
    cap("network.recommendations", "人脉推荐", "推荐", "推荐人脉和连接理由", "network", "network", "/network?tab=recommendations", "/api/v1/network/recommendations/people", "sparkles", "use_recommendations", order=25),
    cap("network.contact_intents", "联系意向", "联系", "联系请求和处理", "network", "network", "/network?tab=intents", "/api/v1/network/contact-intents", "send", order=26),
    cap("network.graph", "关系图谱", "图谱", "主体关系图谱", "network", "network", "/network?tab=graph", "/api/v1/relationships", "share-2", order=27),
    cap("network.identity", "我的产业身份", "身份", "当前用户产业身份", "network", "network", "/me/industry-profile", "/api/v1/me/person-link", "badge-check", "identity.view_self", "person", order=28),

    cap("intelligence", "情报中心", "情报", "情报动态、订阅、研究和运营", "intelligence", None, "/intelligence", "/api/v1/intelligence", "newspaper", order=30),
    cap("intelligence.feed", "情报动态", "动态", "已发布情报流", "intelligence", "intelligence", "/intelligence", "/api/v1/intelligence", "rss", order=31),
    cap("intelligence.subscriptions", "我的订阅", "订阅", "情报订阅", "intelligence", "intelligence", "/intelligence/subscriptions", "/api/v1/intelligence/subscriptions", "bell", order=32),
    cap("intelligence.favorites", "我的收藏", "收藏", "收藏的情报", "intelligence", "intelligence", "/workspace?tab=intelligence_favorites", "/api/v1/collection", "bookmark", order=33),
    cap("intelligence.company_updates", "企业动态", "企业", "重点企业关注和变化跟踪", "intelligence", "intelligence", "/watchlists", "/api/v1/watchlists", "pulse", order=34, legacy=("/signals/watchlists",)),
    cap("intelligence.research", "专题研究", "研究", "专题研究和报告", "intelligence", "intelligence", "/research", "/api/v1/research", "flask-conical", order=35),
    cap("intelligence.operations", "情报运营", "运营", "情报采集、加工、审核和发布总览", "intelligence", "intelligence", "/intelligence/operations", "/api/v1/collection", "activity", "manage_monitoring", clients=("web", "admin"), order=36),
    cap("intelligence.auto_collection", "自动采集", "采集", "从数据源创建并执行采集任务", "intelligence", "intelligence", "/collection", "/api/v1/collection", "download", "manage_monitoring", clients=("web", "admin"), order=37),
    cap("intelligence.collection_jobs", "采集任务", "任务", "采集运行记录、结果数量和失败原因", "intelligence", "intelligence", "/collection/jobs", "/api/v1/collection/jobs", "list-tree", "manage_monitoring", clients=("web", "admin"), order=38),
    cap("intelligence.raw_items", "原始情报", "原始", "采集到的标题、正文、来源链接和快照", "intelligence", "intelligence", "/collection/items", "/api/v1/collection/items", "file-search", clients=("web", "admin"), order=39, legacy=("/collection/snapshots",)),
    cap("intelligence.processing", "数据处理", "处理", "清洗、结构化和实体识别", "intelligence", "intelligence", "/processing/jobs", "/api/v1/processing", "workflow", clients=("web", "admin"), order=40),
    cap("intelligence.candidates", "候选匹配", "候选", "实体、字段和主体候选匹配", "intelligence", "intelligence", "/processing/candidates", "/api/v1/processing/candidates", "git-compare", clients=("web", "admin"), order=41, legacy=("/processing/subject-matches",)),
    cap("intelligence.review", "情报审核", "审核", "候选审核和发布", "intelligence", "intelligence", "/processing/review-queue", "/api/v1/intelligence", "shield-check", clients=("web", "admin"), order=42, legacy=("/review",)),
    cap("intelligence.signals", "产业信号", "信号", "产业信号", "intelligence", "intelligence", "/signals", "/api/v1/signals", "activity", clients=("web", "admin"), order=43),
    cap("intelligence.reports", "报告中心", "报告", "报告和研究", "intelligence", "intelligence", "/reports", "/api/v1/reports", "file-text", clients=("web", "admin"), order=44),
    cap("intelligence.sources", "数据源管理", "来源", "监测和采集来源", "intelligence", "intelligence", "/collection/sources", "/api/v1/collection/sources", "database", "manage_monitoring", clients=("web", "admin"), order=45),

    cap("resources", "业务协同", "协同", "资源、意向、机会、跟进和任务", "resources", None, "/resources", "/api/v1/resources", "handshake", order=50),
    cap("resources.supply", "资源供给", "供给", "供给资源", "resources", "resources", "/resources?direction=supply", "/api/v1/resources", "package-plus", order=51),
    cap("resources.demand", "资源需求", "需求", "需求资源", "resources", "resources", "/resources?direction=demand", "/api/v1/resources", "package-search", order=52),
    cap("resources.match", "资源匹配", "匹配", "供需匹配", "resources", "resources", "/resources?tab=match", "/api/v1/resources", "git-compare", order=53),
    cap("resources.intents", "联系意向", "意向", "联系和合作意向", "resources", "resources", "/network?tab=intents", "/api/v1/network/contact-intents", "send", order=54),
    cap("resources.opportunities", "合作机会", "机会", "合作机会", "resources", "resources", "/opportunities", "/api/v1/opportunities", "handshake", order=55),
    cap("resources.followups", "商务跟进", "跟进", "商务跟进记录", "resources", "resources", "/opportunities?tab=followups", "/api/v1/opportunities", "message-square", order=56, legacy=("/actions",)),
    cap("resources.tasks", "协作任务", "任务", "协作任务", "resources", "resources", "/workspace?tab=tasks", "/api/v1/opportunities", "list-checks", order=57),
    cap("resources.timeline", "项目时间线", "时间线", "项目和机会时间线", "resources", "resources", "/opportunities?tab=timeline", "/api/v1/opportunities", "clock", order=58),

    cap("club", "俱乐部", "俱乐部", "Q-BAY俱乐部、会员和活动", "club", None, "/club", "/api/v1/me/club-context", "landmark", order=60),
    cap("club.home", "俱乐部首页", "首页", "俱乐部门户", "club", "club", "/club", "/api/v1/me/club-context", "home", order=61),
    cap("club.member_center", "会员中心", "会员", "会员身份", "club", "club", "/member", "/api/v1/me/membership-context", "id-card", "membership.view_self", "membership", order=62),
    cap("club.events", "活动", "活动", "俱乐部活动", "club", "club", "/club/events", "/api/v1/events", "calendar", order=63),
    cap("club.resources", "会员供需", "供需", "会员供给和需求", "club", "club", "/club", "/api/v1/resources", "package", order=64),
    cap("club.matches", "会员撮合", "撮合", "会员撮合", "club", "club", "/club/matches", "/api/v1/resources", "shuffle", "manage_club", "membership", clients=("web", "admin"), order=65),
    cap("club.applications", "会员申请", "申请", "会员申请", "club", "club", "/club/admin/applications", "/api/v1/me/memberships", "clipboard-check", "manage_club", clients=("web", "admin"), order=66),
    cap("club.notifications", "通知", "通知", "俱乐部通知", "club", "club", "/club?tab=notifications", "/api/v1/me/club-context", "bell", order=67),
    cap("club.members", "会员管理", "会员管理", "会员管理", "club", "club", "/club/members", "/api/v1/me/memberships", "users-round", "manage_club", clients=("web", "admin"), order=68),
    cap("club.event_admin", "活动管理", "活动管理", "活动管理", "club", "club", "/club/events", "/api/v1/events", "calendar-cog", "manage_club", clients=("web", "admin"), order=69),
    cap("club.supply_admin", "供需管理", "供需管理", "供需管理", "club", "club", "/club", "/api/v1/resources", "package-check", "manage_club", clients=("web", "admin"), order=70),
    cap("club.import", "数据导入", "导入", "会员数据导入", "club", "club", "/club/import", "/api/v1/memberships", "upload", "manage_club", clients=("web", "admin"), order=71),
    cap("club.operations", "俱乐部运营", "运营", "俱乐部运营", "club", "club", "/club/members", "/api/v1/me/memberships", "landmark", "manage_club", clients=("web", "admin"), order=72),

    cap("account.identity", "我的产业身份", "身份", "账号关联的产业身份", "account", None, "/me/industry-profile", "/api/v1/me/person-link", "badge-check", "identity.view_self", clients=("web", "app", "miniprogram"), order=80),
    cap("account.membership", "我的会员", "会员", "我的会员身份", "account", None, "/member", "/api/v1/me/membership-context", "id-card", "membership.view_self", clients=("web", "app", "miniprogram"), order=81),
    cap("account.organization", "我的组织", "组织", "我的组织上下文", "account", None, "/network/organizations", "/api/v1/organizations", "briefcase", "organization.view_self", clients=("web", "app", "miniprogram"), order=82),
    cap("account.favorites", "我的收藏", "收藏", "收藏与关注", "account", None, "/workspace?tab=favorites", "/api/v1/collection", "bookmark", clients=("web", "app", "miniprogram"), order=83),
    cap("account.settings", "账号设置", "设置", "账号资料和密码", "account", None, "/account", "/api/v1/me", "settings", clients=("web",), order=84),

    cap("admin", "管理控制台", "管理", "平台管理控制台", "admin", None, "/admin/platform", "/api/v1/system", "shield", "manage_users", clients=("web", "admin"), order=90),
    cap("admin.people_orgs", "人物与机构", "人物机构", "人物和机构维护", "admin", "admin", "/admin/people", "/api/v1/subjects", "users-round", "edit_data", clients=("web", "admin"), order=91),
    cap("admin.club", "会员与俱乐部", "俱乐部", "会员、申请、活动和供需管理", "admin", "admin", "/club/members", "/api/v1/me/memberships", "landmark", "manage_club", clients=("web", "admin"), order=92),
    cap("admin.intelligence", "情报运营", "情报", "采集、加工、审核和发布", "admin", "admin", "/admin/intelligence", "/api/v1/intelligence", "database", "review_data", clients=("web", "admin"), order=93),
    cap("admin.resources", "资源与合作", "合作", "资源、机会和协作", "admin", "admin", "/opportunities", "/api/v1/opportunities", "handshake", "review_data", clients=("web", "admin"), order=94),
    cap("admin.data_integrity", "数据治理", "治理", "数据完整性和审核", "admin", "admin", "/admin/data-integrity", "/api/v1/system/data-integrity", "shield-alert", "review_data", clients=("web", "admin"), order=95),
    cap("admin.users", "用户与权限", "权限", "用户、角色和权限", "admin", "admin", "/admin/users", "/api/v1/auth", "user-cog", "manage_users", clients=("web", "admin"), order=96),
    cap("admin.ops", "系统运维", "运维", "健康、任务和备份", "admin", "admin", "/system/operations", "/api/v1/system", "server", "manage_users", clients=("web", "admin"), order=97),
)


def validate_registry() -> list[str]:
    errors: list[str] = []
    seen: set[str] = set()
    keys = {item.capability_key for item in CAPABILITIES}
    for item in CAPABILITIES:
        if item.capability_key in seen:
            errors.append(f"duplicate capability_key: {item.capability_key}")
        seen.add(item.capability_key)
        if item.category not in VALID_CATEGORIES:
            errors.append(f"invalid category {item.category}: {item.capability_key}")
        if item.status not in VALID_STATUS:
            errors.append(f"invalid status {item.status}: {item.capability_key}")
        bad_clients = set(item.client_support) - VALID_CLIENTS
        if bad_clients:
            errors.append(f"invalid clients {sorted(bad_clients)}: {item.capability_key}")
        if item.parent_key and item.parent_key not in keys:
            errors.append(f"missing parent {item.parent_key}: {item.capability_key}")
    return errors


def list_capabilities() -> list[dict[str, Any]]:
    return [capability.to_dict() for capability in sorted(CAPABILITIES, key=lambda item: item.order)]


def capability_by_key(key: str) -> dict[str, Any] | None:
    for capability in CAPABILITIES:
        if capability.capability_key == key:
            return capability.to_dict()
    return None


def filter_capabilities(permissions: set[str], *, client: str = "web", auth_disabled: bool = False) -> list[dict[str, Any]]:
    if auth_disabled:
        permissions = {
            "view_internal", "edit_data", "review_data", "manage_club", "manage_monitoring",
            "use_recommendations", "manage_users", "view_sensitive", "export_data",
            "identity.view_self", "identity.request_link", "membership.view_self", "organization.view_self",
        }
    client = client if client in VALID_CLIENTS else "web"
    result: list[dict[str, Any]] = []
    for capability in sorted(CAPABILITIES, key=lambda item: item.order):
        if capability.status == "disabled":
            continue
        if client not in capability.client_support and not (client == "web" and "admin" in capability.client_support):
            continue
        if capability.required_permission and capability.required_permission not in permissions:
            continue
        result.append(capability.to_dict())
    return result
