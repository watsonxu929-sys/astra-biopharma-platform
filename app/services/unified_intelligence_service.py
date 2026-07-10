from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import desc, func, or_, select, text
from sqlalchemy.orm import Session

from app.models_platform import Favorite, IntelSubscription, IntelligenceItem


class UnifiedIntelligenceService:
    canonical_model = "v06_intelligence_items"
    read_model = "published_intelligence_feed"
    legacy_adapter = "raw_intelligence"

    def __init__(self, db: Session):
        self.db = db

    def list(self, *, user_id: int | None = None, intel_type: str = "", industry_direction: str = "", q: str = "", page: int = 1, page_size: int = 20) -> dict[str, Any]:
        page = max(1, int(page or 1))
        page_size = max(1, min(int(page_size or 20), 100))
        stmt = select(IntelligenceItem).where(
            IntelligenceItem.status == "published",
            IntelligenceItem.visibility.in_(["public", "organization"]),
        )
        if intel_type:
            stmt = stmt.where(IntelligenceItem.intel_type == intel_type)
        if industry_direction:
            stmt = stmt.where(IntelligenceItem.industry_directions.contains(industry_direction))
        if q:
            stmt = stmt.where(or_(IntelligenceItem.title.contains(q), IntelligenceItem.summary.contains(q), IntelligenceItem.content.contains(q)))
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(self.db.scalars(stmt.order_by(desc(IntelligenceItem.published_at), desc(IntelligenceItem.created_at)).offset((page - 1) * page_size).limit(page_size)).all())
        return {"items": rows, "total": int(total), "page": page, "page_size": page_size}

    def detail(self, item_id: int) -> IntelligenceItem:
        item = self.db.get(IntelligenceItem, int(item_id))
        if not item or item.status != "published":
            raise HTTPException(status_code=404, detail={"code": "INTELLIGENCE_NOT_FOUND", "message": "情报不存在", "details": {}})
        return item

    def publish_from_raw(self, raw_id: int, *, actor_user_id: int | None = None) -> IntelligenceItem:
        row = self.db.execute(text("SELECT * FROM raw_intelligence WHERE id=:id"), {"id": int(raw_id)}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail={"code": "RAW_INTELLIGENCE_NOT_FOUND", "message": "原始情报不存在", "details": {}})
        existing = self.db.scalar(select(IntelligenceItem).where(IntelligenceItem.source_name == "raw_intelligence", IntelligenceItem.source_url == (row.get("source_url") or None)))
        if existing:
            return existing
        item = IntelligenceItem(
            title=row.get("title") or f"Raw intelligence #{raw_id}",
            summary=(row.get("content") or "")[:300],
            content=row.get("content"),
            intel_type=row.get("source_type") or "raw",
            source_name="raw_intelligence",
            source_url=row.get("source_url"),
            published_at=datetime.now(),
            visibility=row.get("visibility") or "public",
            status="published",
            created_by=actor_user_id,
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def to_api(self, item: IntelligenceItem) -> dict[str, Any]:
        return {
            "id": item.id,
            "canonical_id": f"intelligence:{item.id}",
            "title": item.title,
            "summary": item.summary,
            "content": item.content,
            "intel_type": item.intel_type,
            "source_name": item.source_name,
            "source_url": item.source_url,
            "published_at": item.published_at,
            "importance": item.importance,
            "credibility": item.credibility,
            "status": item.status,
        }

    def subscriptions(self, user_id: int) -> list[IntelSubscription]:
        return list(self.db.scalars(select(IntelSubscription).where(IntelSubscription.user_id == int(user_id))).all())

    def favorite(self, user_id: int, item_id: int) -> dict[str, bool]:
        self.detail(item_id)
        existing = self.db.scalar(select(Favorite).where(Favorite.user_id == user_id, Favorite.target_type == "intelligence", Favorite.target_id == item_id))
        if existing:
            self.db.delete(existing)
            self.db.commit()
            return {"favorited": False}
        self.db.add(Favorite(user_id=user_id, target_type="intelligence", target_id=item_id))
        self.db.commit()
        return {"favorited": True}
