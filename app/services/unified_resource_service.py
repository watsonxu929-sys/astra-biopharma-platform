from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from fastapi import HTTPException
from sqlalchemy import desc, func, or_, select, text
from sqlalchemy.orm import Session

from app.models import Organization, Person
from app.models_platform import MarketResource

RESOURCE_STATUSES = {"draft", "pending_review", "published", "paused", "matched", "closed", "expired", "rejected", "archived"}
_MATCH_STOPWORDS = {"资源", "合作", "服务", "提供", "需求", "供给", "寻找", "当前"}


def _match_keywords(value: Any) -> set[str]:
    terms: set[str] = set()
    for token in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]+", str(value or "").lower()):
        if len(token) >= 2:
            terms.add(token)
        if any("\u4e00" <= char <= "\u9fff" for char in token) and len(token) > 2:
            terms.update(token[index:index + 2] for index in range(len(token) - 1))
    return terms - _MATCH_STOPWORDS


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
        valid_until = fields.get("valid_until")
        if isinstance(valid_until, str):
            valid_until = datetime.fromisoformat(valid_until.strip()) if valid_until.strip() else None
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
            valid_until=valid_until,
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

    def update(self, resource_id: int, *, actor_user_id: int, fields: dict[str, Any],
               is_admin: bool = False, commit: bool = True) -> MarketResource:
        resource = self.detail(resource_id)
        if resource.publisher_id != actor_user_id and not is_admin:
            raise HTTPException(status_code=403, detail={"code": "RESOURCE_FORBIDDEN", "message": "无权修改该资源", "details": {}})
        direction = str(fields.get("direction") or resource.direction)
        if direction not in {"supply", "demand"}:
            raise HTTPException(status_code=400, detail={"code": "INVALID_RESOURCE_DIRECTION", "message": "资源方向无效", "details": {}})
        title = str(fields.get("title") or "").strip()
        if not title:
            raise HTTPException(status_code=400, detail={"code": "RESOURCE_TITLE_REQUIRED", "message": "资源标题不能为空", "details": {}})
        valid_until = fields.get("valid_until")
        if isinstance(valid_until, str):
            valid_until = datetime.fromisoformat(valid_until.strip()) if valid_until.strip() else None
        resource.title = title
        resource.direction = direction
        resource.resource_type = str(fields.get("resource_type") or fields.get("category") or "其他")
        resource.category = fields.get("category") or fields.get("resource_type")
        for key in ("summary", "description", "region", "industry_direction", "tags", "cooperation_mode", "budget_note", "contact_visibility"):
            if key in fields:
                setattr(resource, key, fields.get(key) or None)
        status = str(fields.get("status") or resource.status)
        if status not in RESOURCE_STATUSES:
            raise HTTPException(status_code=400, detail={"code": "INVALID_RESOURCE_STATUS", "message": "资源状态无效", "details": {}})
        resource.status = status
        for field, attr in (("owner_person_id", "owner_person_id"), ("organization_id", "organization_id")):
            if field in fields:
                value = fields.get(field)
                setattr(resource, attr, int(value) if value else None)
        resource.visibility = fields.get("visibility") or resource.visibility
        resource.valid_until = valid_until
        resource.updated_at = datetime.now()
        if commit:
            self.db.commit()
            self.db.refresh(resource)
        return resource

    def reference_counts(self, resource_id: int) -> dict[str, int]:
        params = {"resource_id": int(resource_id), "resource_text": str(resource_id)}
        matches = self.db.execute(text("""SELECT COUNT(*) FROM p4_resource_match_candidates
            WHERE demand_resource_id=:resource_id OR supply_resource_id=:resource_id"""), params).scalar() or 0
        opportunities = self.db.execute(text("""SELECT COUNT(*) FROM v06_opportunities
            WHERE related_resource_id=:resource_id OR source_demand_resource_id=:resource_id
               OR source_supply_resource_id=:resource_id"""), params).scalar() or 0
        relationships = self.db.execute(text("""SELECT COUNT(*) FROM p3_canonical_relationships WHERE
            (subject_type IN ('resource','market_resource') AND CAST(subject_id AS TEXT)=:resource_text) OR
            (object_type IN ('resource','market_resource') AND CAST(object_id AS TEXT)=:resource_text)"""), params).scalar() or 0
        return {"matches": int(matches), "opportunities": int(opportunities), "relationships": int(relationships)}

    def delete_safe(self, resource_id: int, *, actor_user_id: int, is_admin: bool = False,
                    commit: bool = True) -> dict[str, Any]:
        resource = self.detail(resource_id)
        if resource.publisher_id != actor_user_id and not is_admin:
            raise HTTPException(status_code=403, detail={"code": "RESOURCE_FORBIDDEN", "message": "无权删除该资源", "details": {}})
        references = self.reference_counts(resource_id)
        if any(references.values()):
            raise HTTPException(status_code=409, detail={"code": "RESOURCE_DELETE_PROTECTED", "message": "资源已进入匹配或商机链路，只能关闭归档", "details": references})
        self.db.delete(resource)
        if commit:
            self.db.commit()
        return {"deleted": True, "resource_id": int(resource_id), "references": references}

    def close(self, resource_id: int, *, actor_user_id: int, is_admin: bool = False) -> MarketResource:
        return self.update_status(resource_id, actor_user_id=actor_user_id, status="archived", is_admin=is_admin)

    def bulk_delete(self, resource_ids: list[int], *, actor_user_id: int, is_admin: bool = False) -> dict[str, Any]:
        result: dict[str, Any] = {"deleted": [], "protected": [], "missing": []}
        for resource_id in dict.fromkeys(int(value) for value in resource_ids):
            try:
                self.delete_safe(resource_id, actor_user_id=actor_user_id, is_admin=is_admin)
                result["deleted"].append(resource_id)
            except HTTPException as exc:
                if exc.status_code == 404:
                    result["missing"].append(resource_id)
                elif exc.status_code == 409:
                    result["protected"].append(resource_id)
                else:
                    raise
        return result

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
        candidates = list(self.db.scalars(
            self._base_stmt("published").where(
                MarketResource.direction == opposite, MarketResource.id != resource.id
            ).limit(100)
        ).all())
        rejected_pairs = {
            (int(row.demand_resource_id), int(row.supply_resource_id))
            for row in self.db.execute(text("""
                SELECT demand_resource_id,supply_resource_id
                FROM p4_resource_match_candidates
                WHERE status='rejected' OR intention_status='not_interested'
            """))
        }
        organization_ids = {int(row.organization_id) for row in candidates if row.organization_id}
        person_ids = {int(row.owner_person_id) for row in candidates if row.owner_person_id}
        organizations = {
            int(row.id): row.standard_name
            for row in self.db.scalars(select(Organization).where(Organization.id.in_(organization_ids))).all()
        } if organization_ids else {}
        people = {
            int(row.id): row.name
            for row in self.db.scalars(select(Person).where(Person.id.in_(person_ids))).all()
        } if person_ids else {}

        def owner_key(item: MarketResource) -> tuple[str, int] | None:
            if item.organization_id:
                return ("organization", int(item.organization_id))
            if item.owner_person_id:
                return ("person", int(item.owner_person_id))
            return None

        def keywords(item: MarketResource) -> set[str]:
            return _match_keywords(" ".join(str(part or "") for part in (
                item.title, item.resource_type, item.category, item.summary,
                item.description, item.industry_direction, item.region, item.tags,
            )))

        source_owner = owner_key(resource)
        source_keywords = keywords(resource)
        matches = []
        for candidate in candidates:
            candidate_owner = owner_key(candidate)
            if source_owner and candidate_owner and source_owner == candidate_owner:
                continue
            demand_id = resource.id if resource.direction == "demand" else candidate.id
            supply_id = resource.id if resource.direction == "supply" else candidate.id
            if (int(demand_id), int(supply_id)) in rejected_pairs:
                continue

            score = 0
            reasons: list[str] = []
            source_category = str(resource.category or resource.resource_type or "").strip().lower()
            candidate_category = str(candidate.category or candidate.resource_type or "").strip().lower()
            category_compatible = bool(source_category and source_category == candidate_category)
            if category_compatible:
                score += 45
                reasons.append(f"资源类别一致：{candidate.resource_type or candidate.category}")

            industry_overlap = _match_keywords(resource.industry_direction) & _match_keywords(candidate.industry_direction)
            if industry_overlap:
                score += 20
                reasons.append(f"产业方向重合：{'、'.join(sorted(industry_overlap)[:3])}")

            region_overlap = _match_keywords(resource.region) & _match_keywords(candidate.region)
            if region_overlap:
                score += 10
                reasons.append(f"区域条件相近：{'、'.join(sorted(region_overlap)[:2])}")

            keyword_overlap = source_keywords & keywords(candidate)
            if keyword_overlap:
                score += min(25, 5 * len(keyword_overlap))
                reasons.append(f"关键词重合：{'、'.join(sorted(keyword_overlap)[:4])}")

            if not category_compatible and not keyword_overlap:
                continue
            reasons.append("双方资源当前均为有效状态")
            owner_label = organizations.get(int(candidate.organization_id)) if candidate.organization_id else None
            owner_label = owner_label or (people.get(int(candidate.owner_person_id)) if candidate.owner_person_id else None)
            matches.append({
                "resource": candidate,
                "score": min(score, 100),
                "reasons": reasons,
                "owner_label": owner_label or "主体信息待补充",
                "match_category": candidate.resource_type or candidate.category or "其他",
                "demand_resource_id": int(demand_id),
                "supply_resource_id": int(supply_id),
            })
        matches.sort(key=lambda item: item["score"], reverse=True)
        return matches[:limit]

    def to_api(self, resource: MarketResource | dict[str, Any]) -> dict[str, Any]:
        if isinstance(resource, dict):
            return resource
        return {"id": resource.id, "canonical_id": f"resource:{resource.id}", "title": resource.title, "direction": resource.direction, "resource_type": resource.resource_type, "category": resource.category, "summary": resource.summary, "description": resource.description, "publisher_id": resource.publisher_id, "owner_person_id": resource.owner_person_id, "owner_organization_id": resource.organization_id, "visibility": resource.visibility, "region": resource.region, "industry_direction": resource.industry_direction, "tags": resource.tags, "cooperation_mode": resource.cooperation_mode, "budget_note": resource.budget_note, "valid_until": resource.valid_until, "status": resource.status, "legacy_source_type": resource.legacy_source_type, "legacy_source_id": resource.legacy_source_id}
