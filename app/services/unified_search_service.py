from __future__ import annotations

from typing import Any

from sqlalchemy import select, or_, text
from sqlalchemy.orm import Session

from app.models import Organization, Person
from app.models_platform import CooperationOpportunity, IntelligenceItem, MarketResource


class UnifiedSearchService:
    def __init__(self, db: Session):
        self.db = db

    def search(self, q: str, *, user_id: int | None = None, is_admin: bool = False, limit: int = 10) -> dict[str, Any]:
        term = (q or "").strip()
        if not term:
            return {"q": q, "groups": [], "total": 0}
        groups: list[dict[str, Any]] = []
        people = list(self.db.scalars(select(Person).where(Person.is_active == True, Person.name.contains(term)).limit(limit)).all())
        if people:
            groups.append({"type": "people", "label": "产业人物", "items": [{"canonical_id": f"person:{p.id}", "id": p.id, "title": p.name, "summary": f"{p.public_role or ''} | {p.organization_network or ''}", "url": f"/network/people/{p.id}"} for p in people]})
        alias_ids = list(self.db.execute(
            text("""SELECT DISTINCT entity_id FROM p3_entity_aliases
                    WHERE entity_type='organization' AND review_status='approved'
                      AND normalized_alias LIKE :term"""),
            {"term": f"%{''.join(term.lower().split())}%"},
        ).scalars())
        orgs = list(self.db.scalars(
            select(Organization).where(
                Organization.is_active == True,
                or_(
                    Organization.standard_name.contains(term),
                    Organization.short_name.contains(term),
                    Organization.external_id.in_(alias_ids) if alias_ids else False,
                ),
            ).limit(limit)
        ).all())
        if orgs:
            groups.append({"type": "organizations", "label": "机构", "items": [{"canonical_id": f"organization:{o.id}", "id": o.id, "title": o.standard_name, "summary": f"{o.org_type or ''} | {o.region or ''}", "url": f"/organizations/{o.id}"} for o in orgs]})
        intel = list(self.db.scalars(select(IntelligenceItem).where(IntelligenceItem.status == "published", or_(IntelligenceItem.title.contains(term), IntelligenceItem.summary.contains(term))).limit(limit)).all())
        if intel:
            groups.append({"type": "intelligence", "label": "产业情报", "items": [{"canonical_id": f"intelligence:{i.id}", "id": i.id, "title": i.title, "summary": (i.summary or "")[:100], "url": f"/intelligence/{i.id}"} for i in intel]})
        resources = list(self.db.scalars(select(MarketResource).where(MarketResource.status == "published", or_(MarketResource.title.contains(term), MarketResource.summary.contains(term))).limit(limit)).all())
        if resources:
            groups.append({"type": "resources", "label": "产业资源", "items": [{"canonical_id": f"resource:{r.id}", "id": r.id, "title": r.title, "summary": f"{r.direction} | {r.resource_type}", "url": f"/resources/{r.id}"} for r in resources]})
        opps = list(self.db.scalars(select(CooperationOpportunity).where(CooperationOpportunity.status == "active", CooperationOpportunity.title.contains(term)).limit(limit)).all())
        visible = [o for o in opps if is_admin or o.visibility == "public" or user_id in {o.initiator_id, o.owner_id} or str(user_id or "") in (o.participants or "")]
        if visible:
            groups.append({"type": "opportunities", "label": "合作机会", "items": [{"canonical_id": f"opportunity:{o.id}", "id": o.id, "title": o.title, "summary": f"{o.opp_type} | {o.stage}", "url": f"/opportunities/{o.id}"} for o in visible]})
        return {"q": q, "groups": groups, "total": sum(len(group["items"]) for group in groups)}
