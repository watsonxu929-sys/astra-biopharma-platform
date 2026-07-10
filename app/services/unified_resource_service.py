from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import desc, func, or_, select, text
from sqlalchemy.orm import Session

from app.models_platform import MarketResource

RESOURCE_STATUSES = {"draft", "pending_review", "published", "paused", "matched", "closed", "expired", "rejected", "archived"}


class UnifiedResourceService:
    canonical_model = "v06_market_resources"
    legacy_adapters = ("resources", "v04f_club_needs", "v04f_club_offerings")

    def __init__(self, db: Session):
        self.db = db

    def _base_stmt(self):
        return select(MarketResource).where(MarketResource.status == "published").where(or_(MarketResource.valid_until.is_(None), MarketResource.valid_until >= datetime.now()))

    def list(self, *, direction: str = "", resource_type: str = "", q: str = "", industry_direction: str = "", region: str = "", page: int = 1, page_size: int = 20, include_legacy: bool = True) -> dict[str, Any]:
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 100))
        stmt = self._base_stmt()
        if direction:
            stmt = stmt.where(MarketResource.direction == direction)
        if resource_type:
            stmt = stmt.where(MarketResource.resource_type == resource_type)
        if q:
            stmt = stmt.where(or_(MarketResource.title.contains(q), MarketResource.summary.contains(q), MarketResource.description.contains(q)))
        if industry_direction:
            stmt = stmt.where(MarketResource.industry_direction.contains(industry_direction))
        if region:
            stmt = stmt.where(MarketResource.region.contains(region))
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(self.db.scalars(stmt.order_by(desc(MarketResource.created_at)).offset((page - 1) * page_size).limit(page_size)).all())
        items: list[Any] = rows
        legacy = self.legacy_resources(direction=direction, q=q, limit=max(0, page_size - len(rows))) if include_legacy and page == 1 else []
        return {"items": items, "legacy_items": legacy, "total": int(total) + len(legacy), "page": page, "page_size": page_size}

    def detail(self, resource_id: int) -> MarketResource:
        resource = self.db.get(MarketResource, int(resource_id))
        if not resource:
            raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "资源不存在", "details": {}})
        return resource

    def create(self, *, actor_user_id: int, fields: dict[str, Any]) -> MarketResource:
        direction = str(fields.get("direction") or "supply")
        if direction not in {"supply", "demand"}:
            raise HTTPException(status_code=400, detail={"code": "INVALID_RESOURCE_DIRECTION", "message": "资源方向无效", "details": {}})
        status = str(fields.get("status") or "published")
        if status not in RESOURCE_STATUSES:
            status = "published"
        resource = MarketResource(
            title=str(fields.get("title") or "").strip() or "未命名资源",
            direction=direction,
            resource_type=str(fields.get("resource_type") or "其他"),
            summary=fields.get("summary"),
            description=fields.get("description"),
            publisher_id=int(actor_user_id),
            organization_id=fields.get("organization_id"),
            region=fields.get("region"),
            industry_direction=fields.get("industry_direction"),
            tags=fields.get("tags"),
            cooperation_mode=fields.get("cooperation_mode"),
            budget_note=fields.get("budget_note"),
            valid_until=fields.get("valid_until"),
            contact_visibility=fields.get("contact_visibility") or "connected",
            status=status,
        )
        self.db.add(resource)
        self.db.commit()
        self.db.refresh(resource)
        return resource

    def update_status(self, resource_id: int, *, actor_user_id: int, status: str, is_admin: bool = False) -> MarketResource:
        resource = self.detail(resource_id)
        if resource.publisher_id != actor_user_id and not is_admin:
            raise HTTPException(status_code=403, detail={"code": "RESOURCE_FORBIDDEN", "message": "无权修改该资源", "details": {}})
        if status not in RESOURCE_STATUSES:
            raise HTTPException(status_code=400, detail={"code": "INVALID_RESOURCE_STATUS", "message": "资源状态无效", "details": {}})
        resource.status = status
        resource.updated_at = datetime.now()
        self.db.commit()
        return resource

    def match(self, resource_id: int, limit: int = 10) -> list[dict[str, Any]]:
        resource = self.detail(resource_id)
        opposite = "demand" if resource.direction == "supply" else "supply"
        candidates = list(self.db.scalars(self._base_stmt().where(MarketResource.direction == opposite, MarketResource.id != resource.id).limit(100)).all())
        matches = []
        for candidate in candidates:
            score = 0
            reasons = []
            if candidate.resource_type == resource.resource_type:
                score += 40; reasons.append("resource_type")
            if resource.industry_direction and candidate.industry_direction and resource.industry_direction in candidate.industry_direction:
                score += 30; reasons.append("industry_direction")
            if resource.region and candidate.region and resource.region in candidate.region:
                score += 20; reasons.append("region")
            if score > 0:
                matches.append({"resource": candidate, "score": score, "reasons": reasons})
        matches.sort(key=lambda item: item["score"], reverse=True)
        return matches[:limit]

    def legacy_resources(self, *, direction: str = "", q: str = "", limit: int = 20) -> list[dict[str, Any]]:
        if limit <= 0:
            return []
        rows: list[dict[str, Any]] = []
        try:
            if direction in {"", "demand"}:
                for row in self.db.execute(text("SELECT n.*,m.user_id,m.organization_id FROM v04f_club_needs n LEFT JOIN v04f_club_memberships m ON m.id=n.membership_id WHERE n.status='active' ORDER BY n.id DESC LIMIT :limit"), {"limit": limit}).mappings():
                    if q and q not in (row.get("title") or "") and q not in (row.get("description") or ""):
                        continue
                    rows.append({"canonical_id": f"legacy:club_need:{row['id']}", "legacy": True, "source_system": "qbay", "direction": "demand", "id": row["id"], "title": row["title"], "summary": row.get("description"), "resource_type": row.get("need_type"), "region": row.get("region")})
            if len(rows) < limit and direction in {"", "supply"}:
                for row in self.db.execute(text("SELECT o.*,m.user_id,m.organization_id FROM v04f_club_offerings o LEFT JOIN v04f_club_memberships m ON m.id=o.membership_id WHERE o.status='active' ORDER BY o.id DESC LIMIT :limit"), {"limit": limit - len(rows)}).mappings():
                    if q and q not in (row.get("title") or "") and q not in (row.get("description") or ""):
                        continue
                    rows.append({"canonical_id": f"legacy:club_offering:{row['id']}", "legacy": True, "source_system": "qbay", "direction": "supply", "id": row["id"], "title": row["title"], "summary": row.get("description"), "resource_type": row.get("offering_type"), "region": row.get("region")})
        except Exception:
            return rows
        return rows[:limit]

    def to_api(self, resource: MarketResource | dict[str, Any]) -> dict[str, Any]:
        if isinstance(resource, dict):
            return resource
        return {"id": resource.id, "canonical_id": f"resource:{resource.id}", "title": resource.title, "direction": resource.direction, "resource_type": resource.resource_type, "summary": resource.summary, "description": resource.description, "publisher_id": resource.publisher_id, "organization_id": resource.organization_id, "region": resource.region, "industry_direction": resource.industry_direction, "tags": resource.tags, "cooperation_mode": resource.cooperation_mode, "budget_note": resource.budget_note, "valid_until": resource.valid_until, "status": resource.status}
