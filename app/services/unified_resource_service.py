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
    def __init__(self, db: Session):
        self.db = db

    def _base_stmt(self, status: str = "published"):
        stmt = select(MarketResource)
        if status != "all":
            stmt = stmt.where(MarketResource.status == (status or "published"))
        if (status or "published") == "published":
            stmt = stmt.where(or_(MarketResource.valid_until.is_(None), MarketResource.valid_until >= datetime.now()))
        return stmt

    def list(self, *, direction: str = "", resource_type: str = "", q: str = "", industry_direction: str = "", region: str = "", status: str = "published", page: int = 1, page_size: int = 20, include_legacy: bool = False) -> dict[str, Any]:
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 100))
        status = status if status in RESOURCE_STATUSES or status == "all" else "published"
        stmt = self._base_stmt(status)
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
        return {"items": rows, "legacy_items": [], "total": int(total), "page": page, "page_size": page_size}

    def detail(self, resource_id: int) -> MarketResource:
        resource = self.db.get(MarketResource, int(resource_id))
        if not resource:
            raise HTTPException(status_code=404, detail={"code": "RESOURCE_NOT_FOUND", "message": "资源不存在", "details": {}})
        return resource

    def create(self, *, actor_user_id: int, fields: dict[str, Any], commit: bool = True) -> MarketResource:
        direction = str(fields.get("direction") or "supply")
        if direction not in {"supply", "demand"}:
            raise HTTPException(status_code=400, detail={"code": "INVALID_RESOURCE_DIRECTION", "message": "资源方向无效", "details": {}})
        status = str(fields.get("status") or "published")
        if status not in RESOURCE_STATUSES:
            status = "published"
        source_intelligence_id = fields.get("source_intelligence_id")
        title = str(fields.get("title") or "").strip() or "未命名资源"
        duplicate = None
        if source_intelligence_id:
            duplicate = self.db.scalar(select(MarketResource).where(
                MarketResource.source_intelligence_id == int(source_intelligence_id),
                MarketResource.direction == direction,
                MarketResource.title == title,
                MarketResource.status != "archived",
            ))
        elif fields.get("legacy_source_type") and fields.get("legacy_source_id") is not None:
            duplicate = self.db.scalar(select(MarketResource).where(
                MarketResource.legacy_source_type == str(fields["legacy_source_type"]),
                MarketResource.legacy_source_id == str(fields["legacy_source_id"]),
                MarketResource.direction == direction,
            ))
        if duplicate:
            return duplicate
        resource = MarketResource(
            title=title,
            direction=direction,
            resource_type=str(fields.get("resource_type") or fields.get("category") or "其他"),
            category=fields.get("category") or fields.get("resource_type"),
            summary=fields.get("summary"),
            description=fields.get("description"),
            publisher_id=int(actor_user_id),
            owner_person_id=fields.get("owner_person_id"),
            organization_id=fields.get("owner_organization_id") or fields.get("organization_id"),
            visibility=fields.get("visibility") or "organization",
            legacy_source_type=fields.get("legacy_source_type"),
            legacy_source_id=str(fields.get("legacy_source_id")) if fields.get("legacy_source_id") is not None else None,
            region=fields.get("region"),
            industry_direction=fields.get("industry_direction"),
            tags=fields.get("tags"),
            cooperation_mode=fields.get("cooperation_mode"),
            budget_note=fields.get("budget_note"),
            valid_until=fields.get("valid_until"),
            contact_visibility=fields.get("contact_visibility") or "connected",
            status=status,
            source_intelligence_id=int(source_intelligence_id) if source_intelligence_id else None,
            project_id=int(fields["project_id"]) if fields.get("project_id") else None,
            source_intelligence_title=fields.get("source_intelligence_title"),
            cooperation_terms=fields.get("cooperation_terms"),
        )
        self.db.add(resource)
        self.db.flush()
        extra_columns = {
            "source_content_hash": fields.get("source_content_hash"),
            "opportunity_type": fields.get("opportunity_type"),
            "confidentiality_level": fields.get("confidentiality_level"),
            "source_event_id": fields.get("source_event_id"),
            "target_audience": fields.get("target_audience"),
            "pilot_batch_id": fields.get("pilot_batch_id"),
        }
        values = {key: value for key, value in extra_columns.items() if value is not None}
        if values:
            assignments = ",".join(f"{key}=:{key}" for key in values)
            self.db.execute(text(f"UPDATE v06_market_resources SET {assignments} WHERE id=:resource_id"), {**values, "resource_id": resource.id})
        if commit:
            self.db.commit()
            self.db.refresh(resource)
        return resource

    def update_status(
        self, resource_id: int, *, actor_user_id: int, status: str, is_admin: bool = False,
        reviewed_by: str | None = None, reviewed_at: str | None = None,
        review_note: str | None = None, commit: bool = True,
    ) -> MarketResource:
        resource = self.detail(resource_id)
        if resource.publisher_id != actor_user_id and not is_admin:
            raise HTTPException(status_code=403, detail={"code": "RESOURCE_FORBIDDEN", "message": "无权修改该资源", "details": {}})
        if status not in RESOURCE_STATUSES:
            raise HTTPException(status_code=400, detail={"code": "INVALID_RESOURCE_STATUS", "message": "资源状态无效", "details": {}})
        resource.status = status
        resource.updated_at = datetime.now()
        self.db.flush()
        if reviewed_by is not None or reviewed_at is not None or review_note is not None:
            self.db.execute(text("""
                UPDATE v06_market_resources SET reviewed_by=:reviewed_by,reviewed_at=:reviewed_at,
                  review_note=:review_note,updated_at=:updated_at WHERE id=:resource_id
            """), {"reviewed_by": reviewed_by, "reviewed_at": reviewed_at, "review_note": review_note,
                    "updated_at": resource.updated_at, "resource_id": resource.id})
        if commit:
            self.db.commit()
            self.db.refresh(resource)
        return resource

    def find_duplicates(self, fields: dict[str, Any], limit: int = 20) -> list[MarketResource]:
        title = str(fields.get("title") or "").strip()
        direction = str(fields.get("direction") or "supply")
        if not title:
            return []
        stmt = select(MarketResource).where(MarketResource.direction == direction, MarketResource.title == title)
        owner_org = fields.get("owner_organization_id") or fields.get("organization_id")
        if owner_org is not None:
            stmt = stmt.where(MarketResource.organization_id == int(owner_org))
        return list(self.db.scalars(stmt.limit(limit)).all())

    def match(self, resource_id: int, limit: int = 10) -> list[dict[str, Any]]:
        resource = self.detail(resource_id)
        opposite = "demand" if resource.direction == "supply" else "supply"
        candidates = list(self.db.scalars(self._base_stmt("published").where(MarketResource.direction == opposite, MarketResource.id != resource.id).limit(100)).all())
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

    def to_api(self, resource: MarketResource | dict[str, Any]) -> dict[str, Any]:
        if isinstance(resource, dict):
            return resource
        return {"id": resource.id, "canonical_id": f"resource:{resource.id}", "title": resource.title, "direction": resource.direction, "resource_type": resource.resource_type, "category": resource.category, "summary": resource.summary, "description": resource.description, "publisher_id": resource.publisher_id, "owner_person_id": resource.owner_person_id, "owner_organization_id": resource.organization_id, "visibility": resource.visibility, "region": resource.region, "industry_direction": resource.industry_direction, "tags": resource.tags, "cooperation_mode": resource.cooperation_mode, "budget_note": resource.budget_note, "valid_until": resource.valid_until, "status": resource.status, "legacy_source_type": resource.legacy_source_type, "legacy_source_id": resource.legacy_source_id}
