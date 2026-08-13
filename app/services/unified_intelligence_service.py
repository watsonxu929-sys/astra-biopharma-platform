from __future__ import annotations

from datetime import datetime
import hashlib
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

    def list(self, *, user_id: int | None = None, intel_type: str = "", industry_direction: str = "", q: str = "", source: str = "", time_range: str = "", workflow: str = "", page: int = 1, page_size: int = 20) -> dict[str, Any]:
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
        if source:
            stmt = stmt.where(IntelligenceItem.source_name.contains(source))
        if time_range == "today":
            stmt = stmt.where(func.date(func.coalesce(IntelligenceItem.published_at, IntelligenceItem.created_at)) == func.date("now"))
        elif time_range == "7days":
            stmt = stmt.where(func.date(func.coalesce(IntelligenceItem.published_at, IntelligenceItem.created_at)) >= func.date("now", "-7 days"))
        elif time_range == "30days":
            stmt = stmt.where(func.date(func.coalesce(IntelligenceItem.published_at, IntelligenceItem.created_at)) >= func.date("now", "-30 days"))
        if workflow == "pending_subject":
            stmt = stmt.where(text("NOT EXISTS (SELECT 1 FROM core_intelligence_subject_links l WHERE l.intelligence_item_id=v06_intelligence_items.id)"))
        elif workflow == "pending_resource":
            stmt = stmt.where(text("EXISTS (SELECT 1 FROM core_intelligence_subject_links l WHERE l.intelligence_item_id=v06_intelligence_items.id) AND NOT EXISTS (SELECT 1 FROM v06_market_resources r WHERE r.source_intelligence_id=v06_intelligence_items.id AND r.status<>'archived')"))
        elif workflow == "with_resource":
            stmt = stmt.where(text("EXISTS (SELECT 1 FROM v06_market_resources r WHERE r.source_intelligence_id=v06_intelligence_items.id AND r.status<>'archived')"))
        total = self.db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        rows = list(self.db.scalars(stmt.order_by(desc(IntelligenceItem.published_at), desc(IntelligenceItem.created_at)).offset((page - 1) * page_size).limit(page_size)).all())
        return {"items": rows, "total": int(total), "page": page, "page_size": page_size}

    def detail(self, item_id: int) -> IntelligenceItem:
        item = self.db.get(IntelligenceItem, int(item_id))
        if not item or item.status != "published":
            raise HTTPException(status_code=404, detail={"code": "INTELLIGENCE_NOT_FOUND", "message": "情报不存在", "details": {}})
        return item

    def publish_from_raw(self, raw_id: int, *, actor_user_id: int | None = None) -> IntelligenceItem:
        """Compatibility guard: P2.1 publication must start from an approved FactCandidate."""
        raise HTTPException(
            status_code=409,
            detail={
                "code": "FACT_CANDIDATE_REVIEW_REQUIRED",
                "message": "原始情报必须先形成有证据的候选并通过人工审核",
                "details": {"raw_id": int(raw_id)},
            },
        )

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
            "source_record_type": item.source_record_type,
            "source_record_id": item.source_record_id,
            "evidence_hash": item.evidence_hash,
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
