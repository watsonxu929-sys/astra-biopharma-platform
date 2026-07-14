from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import desc, or_, select
from sqlalchemy.orm import Session

from app.models_platform import CollabTask, ContactIntent, CooperationOpportunity, FollowUp, TimelineEntry


def _csv_ids(value: str | None) -> set[int]:
    ids: set[int] = set()
    for part in str(value or "").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


class UnifiedOpportunityService:
    canonical_model = "v06_opportunities"
    legacy_adapters = ("v04f_lead_records", "actions", "v04h_recommendations", "v06_contact_intents")

    def __init__(self, db: Session):
        self.db = db

    def can_access(self, opp: CooperationOpportunity, user_id: int | None, *, is_admin: bool = False) -> bool:
        if is_admin:
            return True
        if user_id is None:
            return opp.visibility == "public"
        uid = int(user_id)
        if uid in {opp.initiator_id, opp.owner_id}:
            return True
        if uid in _csv_ids(opp.participants):
            return True
        return opp.visibility == "public"

    def can_manage(self, opp: CooperationOpportunity, user_id: int | None, *, is_admin: bool = False) -> bool:
        if is_admin:
            return True
        if user_id is None:
            return False
        uid = int(user_id)
        return uid in {opp.initiator_id, opp.owner_id} or uid in _csv_ids(opp.participants)

    def list(self, *, user_id: int | None, is_admin: bool = False, status: str = "active", stage: str = "", q: str = "", page: int = 1, page_size: int = 20) -> dict[str, Any]:
        page = max(1, int(page or 1)); page_size = max(1, min(int(page_size or 20), 100))
        stmt = select(CooperationOpportunity).order_by(desc(CooperationOpportunity.updated_at))
        if status:
            stmt = stmt.where(CooperationOpportunity.status == status)
        if stage:
            stmt = stmt.where(CooperationOpportunity.stage == stage)
        if q:
            stmt = stmt.where(or_(CooperationOpportunity.title.contains(q), CooperationOpportunity.description.contains(q)))
        rows = list(self.db.scalars(stmt.limit(500)).all())
        visible = [row for row in rows if self.can_access(row, user_id, is_admin=is_admin)]
        start = (page - 1) * page_size
        return {"items": visible[start:start + page_size], "total": len(visible), "page": page, "page_size": page_size}

    def detail(self, opp_id: int, *, user_id: int | None, is_admin: bool = False) -> CooperationOpportunity:
        opp = self.db.get(CooperationOpportunity, int(opp_id))
        if not opp:
            raise HTTPException(status_code=404, detail={"code": "OPPORTUNITY_NOT_FOUND", "message": "机会不存在", "details": {}})
        if not self.can_access(opp, user_id, is_admin=is_admin):
            raise HTTPException(status_code=403, detail={"code": "OPPORTUNITY_FORBIDDEN", "message": "无权访问该机会", "details": {}})
        return opp

    def create(self, *, actor_user_id: int, fields: dict[str, Any], commit: bool = True) -> CooperationOpportunity:
        if fields.get("human_confirmed") is not True:
            raise HTTPException(status_code=409, detail={"code": "OPPORTUNITY_HUMAN_CONFIRMATION_REQUIRED", "message": "正式商机必须由人工确认", "details": {}})
        source_type = fields.get("source_type")
        source_id = fields.get("source_id")
        if source_type and source_id:
            existing = self.db.scalar(select(CooperationOpportunity).where(CooperationOpportunity.source_type == source_type, CooperationOpportunity.source_id == int(source_id)))
            if existing:
                return existing
        opp = CooperationOpportunity(
            title=str(fields.get("title") or "").strip() or "未命名合作机会",
            opp_type=str(fields.get("opp_type") or "other"),
            source_type=source_type,
            source_id=int(source_id) if source_id else None,
            initiator_id=int(actor_user_id),
            organization_id=fields.get("organization_id"),
            target_person_id=fields.get("target_person_id"),
            target_organization_id=fields.get("target_organization_id"),
            related_resource_id=fields.get("related_resource_id"),
            demand_organization_id=fields.get("demand_organization_id"),
            supply_organization_id=fields.get("supply_organization_id"),
            description=fields.get("description"),
            expected_outcome=fields.get("expected_outcome"),
            priority=fields.get("priority") or "P2",
            estimated_amount=fields.get("estimated_amount"),
            next_action=fields.get("next_action"),
            next_follow_at=fields.get("next_follow_at"),
            owner_id=fields.get("owner_id") or int(actor_user_id),
            participants=fields.get("participants"),
            status=fields.get("status") or "active",
            visibility=fields.get("visibility") or "organization",
            human_confirmed_by=int(actor_user_id),
            human_confirmed_at=datetime.now(),
        )
        self.db.add(opp)
        self.db.flush()
        self.db.add(TimelineEntry(opportunity_id=opp.id, event_type="created", description=f"Opportunity created: {opp.title}", actor_id=actor_user_id))
        if commit:
            self.db.commit()
            self.db.refresh(opp)
        else:
            self.db.flush()
        return opp

    def update_stage(self, opp_id: int, *, actor_user_id: int, stage: str, is_admin: bool = False) -> CooperationOpportunity:
        opp = self.detail(opp_id, user_id=actor_user_id, is_admin=is_admin)
        if not self.can_manage(opp, actor_user_id, is_admin=is_admin):
            raise HTTPException(status_code=403, detail={"code": "OPPORTUNITY_STAGE_FORBIDDEN", "message": "无权修改机会阶段", "details": {}})
        old = opp.stage
        opp.stage = stage or opp.stage
        opp.updated_at = datetime.now()
        self.db.add(TimelineEntry(opportunity_id=opp.id, event_type="stage_change", description=f"Stage changed from {old} to {opp.stage}", actor_id=actor_user_id))
        self.db.commit(); self.db.refresh(opp)
        return opp

    def follow_ups(self, opp_id: int, *, user_id: int | None, is_admin: bool = False) -> list[FollowUp]:
        self.detail(opp_id, user_id=user_id, is_admin=is_admin)
        return list(self.db.scalars(select(FollowUp).where(FollowUp.opportunity_id == int(opp_id)).order_by(desc(FollowUp.followed_at))).all())

    def tasks(self, opp_id: int, *, user_id: int | None, is_admin: bool = False) -> list[CollabTask]:
        self.detail(opp_id, user_id=user_id, is_admin=is_admin)
        return list(self.db.scalars(select(CollabTask).where(CollabTask.opportunity_id == int(opp_id)).order_by(desc(CollabTask.created_at))).all())

    def timeline(self, opp_id: int, *, user_id: int | None, is_admin: bool = False) -> list[TimelineEntry]:
        self.detail(opp_id, user_id=user_id, is_admin=is_admin)
        return list(self.db.scalars(select(TimelineEntry).where(TimelineEntry.opportunity_id == int(opp_id)).order_by(desc(TimelineEntry.created_at))).all())

    def create_follow_up(self, *, opp_id: int, actor_user_id: int, fields: dict[str, Any], is_admin: bool = False) -> FollowUp:
        opp = self.detail(opp_id, user_id=actor_user_id, is_admin=is_admin)
        if not self.can_manage(opp, actor_user_id, is_admin=is_admin):
            raise HTTPException(status_code=403, detail={"code": "FOLLOW_UP_FORBIDDEN", "message": "无权新增跟进", "details": {}})
        follow = FollowUp(opportunity_id=opp.id, follow_type=fields.get("follow_type") or "note", content=str(fields.get("content") or ""), created_by=actor_user_id, visibility=fields.get("visibility") or "organization")
        self.db.add(follow); self.db.flush()
        self.db.add(TimelineEntry(opportunity_id=opp.id, event_type="follow_up", description=follow.content[:120], actor_id=actor_user_id))
        self.db.commit(); self.db.refresh(follow)
        return follow

    def create_task(self, *, opp_id: int, actor_user_id: int, owner_id: int, fields: dict[str, Any], is_admin: bool = False) -> CollabTask:
        opp = self.detail(opp_id, user_id=actor_user_id, is_admin=is_admin)
        if not self.can_manage(opp, actor_user_id, is_admin=is_admin):
            raise HTTPException(status_code=403, detail={"code": "TASK_FORBIDDEN", "message": "无权创建任务", "details": {}})
        if owner_id != actor_user_id and owner_id not in _csv_ids(opp.participants) and owner_id not in {opp.owner_id, opp.initiator_id} and not is_admin:
            raise HTTPException(status_code=403, detail={"code": "TASK_OWNER_FORBIDDEN", "message": "不能分配给无权访问机会的用户", "details": {}})
        task = CollabTask(title=str(fields.get("title") or "").strip() or "未命名任务", opportunity_id=opp.id, owner_id=owner_id, priority=fields.get("priority") or "P2", created_by=actor_user_id, participants=fields.get("participants"))
        self.db.add(task); self.db.flush()
        self.db.add(TimelineEntry(opportunity_id=opp.id, event_type="task", description=f"Task created: {task.title}", actor_id=actor_user_id))
        self.db.commit(); self.db.refresh(task)
        return task

    def convert_contact_intent(self, *, intent_id: int, actor_user_id: int, is_admin: bool = False) -> CooperationOpportunity:
        intent = self.db.get(ContactIntent, int(intent_id))
        if not intent:
            raise HTTPException(status_code=404, detail={"code": "CONTACT_INTENT_NOT_FOUND", "message": "联系意向不存在", "details": {}})
        if intent.status != "accepted":
            raise HTTPException(status_code=409, detail={"code": "CONTACT_INTENT_NOT_ACCEPTED", "message": "只有已接受的联系意向可以转化", "details": {}})
        if intent.from_user_id != actor_user_id and intent.responded_by != actor_user_id and not is_admin:
            raise HTTPException(status_code=403, detail={"code": "CONVERT_FORBIDDEN", "message": "无权转化该联系意向", "details": {}})
        return self.create(actor_user_id=actor_user_id, fields={"title": f"联系意向转化: {intent.intent_type}", "opp_type": "contact", "source_type": "contact_intent", "source_id": intent.id, "description": intent.message, "status": "active", "visibility": "organization", "target_person_id": intent.target_id if intent.target_type == "person" else None, "target_organization_id": intent.target_id if intent.target_type == "organization" else None, "human_confirmed": True})

    def to_api(self, opp: CooperationOpportunity) -> dict[str, Any]:
        return {"id": opp.id, "canonical_id": f"opportunity:{opp.id}", "title": opp.title, "opp_type": opp.opp_type, "source_type": opp.source_type, "source_id": opp.source_id, "initiator_id": opp.initiator_id, "organization_id": opp.organization_id, "target_person_id": opp.target_person_id, "target_organization_id": opp.target_organization_id, "related_resource_id": opp.related_resource_id, "demand_organization_id": opp.demand_organization_id, "supply_organization_id": opp.supply_organization_id, "stage": opp.stage, "priority": opp.priority, "estimated_amount": opp.estimated_amount, "next_action": opp.next_action, "next_follow_at": opp.next_follow_at, "status": opp.status, "visibility": opp.visibility, "owner_id": opp.owner_id, "participants": opp.participants, "human_confirmed_by": opp.human_confirmed_by, "human_confirmed_at": opp.human_confirmed_at}



