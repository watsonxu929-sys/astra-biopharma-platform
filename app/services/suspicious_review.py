from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import HistoricalEvent, Organization, Person, ProjectPool, Resource
from .manual_ingestion import GENERIC_PAGE_TITLES, NAVIGATION_NOISE


@dataclass
class SuspiciousRecord:
    entity_key: str
    entity_label: str
    item_id: int
    external_id: str
    title: str
    reason: str
    detail: str
    view_url: str
    edit_url: str

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


ENTITY_MODELS = {
    "people": ("人物", Person),
    "organizations": ("机构", Organization),
    "projects": ("项目", ProjectPool),
    "events": ("事件", HistoricalEvent),
    "resources": ("资源", Resource),
}


def _generic_title(value: str) -> bool:
    normalized = re.sub(r"^(?:标题|姓名|名称|项目名称|公司名称)[:：]\s*", "", value or "").split("|", 1)[0].strip()
    return normalized in GENERIC_PAGE_TITLES or normalized in NAVIGATION_NOISE


def _person_reasons(item: Person) -> list[str]:
    reasons: list[str] = []
    name = (item.name or "").strip()
    if _generic_title(name):
        reasons.append("姓名是栏目或页面名称")
    if len(name) > 40:
        reasons.append("姓名异常过长")
    if re.search(r"[；;、,/]|\s{2,}", name):
        reasons.append("姓名疑似包含多个人")
    if name and any(word in name for word in ("董事长", "总经理", "首席", "总裁", "总监", "团队")):
        reasons.append("姓名字段疑似混入职位")
    if len(item.public_role or "") > 260:
        reasons.append("公开角色异常过长")
    if len(item.organization_network or "") > 650:
        reasons.append("机构网络疑似混入大量经历")
    return reasons


def _organization_reasons(item: Organization) -> list[str]:
    reasons: list[str] = []
    name = (item.standard_name or "").strip()
    if _generic_title(name):
        reasons.append("机构名称是栏目或页面名称")
    if len(name) > 100:
        reasons.append("机构名称异常过长")
    if name.startswith("标题：") or name.startswith("标题:"):
        reasons.append("机构名称保留了网页标题前缀")
    return reasons


def _project_reasons(item: ProjectPool) -> list[str]:
    name = (item.name or "").strip()
    reasons: list[str] = []
    if _generic_title(name):
        reasons.append("项目名称是栏目或列表名称")
    if len(name) > 220:
        reasons.append("项目名称异常过长")
    return reasons


def _event_reasons(item: HistoricalEvent) -> list[str]:
    name = (item.name or "").strip()
    reasons: list[str] = []
    if _generic_title(name):
        reasons.append("事件名称是栏目或新闻列表名称")
    if len(name) > 260:
        reasons.append("事件名称异常过长")
    return reasons


def _resource_reasons(item: Resource) -> list[str]:
    reasons: list[str] = []
    owner = (item.owner_external_id or "").strip()
    category = (item.category or "").strip()
    if _generic_title(category):
        reasons.append("资源类别是栏目名称")
    if not owner:
        reasons.append("缺少提供主体")
    if len(category) > 100:
        reasons.append("资源类别异常过长")
    return reasons


REASON_FUNCTIONS = {
    "people": _person_reasons,
    "organizations": _organization_reasons,
    "projects": _project_reasons,
    "events": _event_reasons,
    "resources": _resource_reasons,
}


def suspicious_records(db: Session, entity_filter: str = "", limit: int = 300) -> list[SuspiciousRecord]:
    output: list[SuspiciousRecord] = []
    keys = [entity_filter] if entity_filter in ENTITY_MODELS else list(ENTITY_MODELS)
    for entity_key in keys:
        entity_label, model = ENTITY_MODELS[entity_key]
        rows = db.scalars(
            select(model).where(model.is_active.is_(True)).order_by(model.id.desc()).limit(limit)
        ).all()
        for item in rows:
            reasons = REASON_FUNCTIONS[entity_key](item)
            if not reasons:
                continue
            if entity_key == "people":
                title = item.name
                detail = item.public_role or item.organization_network or ""
                view_url = f"/people/{item.id}"
            elif entity_key == "organizations":
                title = item.standard_name
                detail = item.org_type or item.region or ""
                view_url = f"/organizations/{item.id}"
            elif entity_key == "projects":
                title = item.name
                detail = item.project_type or item.focus_tags or ""
                view_url = f"/projects/{item.id}"
            elif entity_key == "events":
                title = item.name
                detail = item.event_date or item.event_type or ""
                view_url = f"/events/{item.id}"
            else:
                title = item.category or item.external_id
                detail = item.description or ""
                view_url = f"/resources/{item.id}"
            output.append(SuspiciousRecord(
                entity_key=entity_key,
                entity_label=entity_label,
                item_id=item.id,
                external_id=item.external_id,
                title=title or "未命名",
                reason="；".join(reasons),
                detail=(detail or "")[:180],
                view_url=view_url,
                edit_url=f"/manage/{entity_key}/{item.id}/edit",
            ))
    output.sort(key=lambda item: (item.entity_label, item.item_id), reverse=True)
    return output[:limit]


def deactivate_suspicious_record(db: Session, entity_key: str, item_id: int, reason: str) -> Any | None:
    entry = ENTITY_MODELS.get(entity_key)
    if not entry:
        return None
    _, model = entry
    item = db.get(model, item_id)
    if not item:
        return None
    item.is_active = False
    if hasattr(item, "verification_status"):
        item.verification_status = "已失效"
    from datetime import datetime
    item.deactivated_at = datetime.now()
    item.deactivated_reason = reason or "疑似错误主体人工复核后停用"
    db.commit()
    return item
