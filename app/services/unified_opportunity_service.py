from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import desc, or_, select, text
from sqlalchemy.orm import Session

from app.models_platform import CollabTask, ContactIntent, CooperationOpportunity, FollowUp, TimelineEntry


def _csv_ids(value: str | None) -> set[int]:
    ids: set[int] = set()
    for part in str(value or "").replace(";", ",").split(","):
        part = part.strip()
        if part.isdigit():
            ids.add(int(part))
    return ids


def _as_datetime(value: Any) -> datetime | None:
    if not value or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value).replace("Z", "+00:00"))


class UnifiedOpportunityService:
    canonical_model = "v06_opportunities"
    legacy_adapters = ("v04f_lead_records", "actions", "v04h_recommendations", "v06_contact_intents")

    def __init__(self, db: Session):
        self.db = db

    def _supported(self, table: str, values: dict[str, Any]) -> dict[str, Any]:
        columns = {str(row[1]) for row in self.db.execute(text(f"PRAGMA table_info({table})"))}
        return {key: value for key, value in values.items() if value is not None and key in columns}

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

    def list(self, *, user_id: int | None, is_admin: bool = False, status: str = "active", stage: str = "", q: str = "", outcome: str = "", owner_id: int | None = None, updated_period: str = "", follow_scope: str = "", closed_period: str = "", page: int = 1, page_size: int = 20) -> dict[str, Any]:
        page = max(1, int(page or 1)); page_size = max(1, min(int(page_size or 20), 100))
        stmt = select(CooperationOpportunity).order_by(desc(CooperationOpportunity.updated_at))
        if status and status != "all":
            stmt = stmt.where(CooperationOpportunity.status == status)
        if stage:
            stmt = stmt.where(CooperationOpportunity.stage == stage)
        if q:
            stmt = stmt.where(or_(CooperationOpportunity.title.contains(q), CooperationOpportunity.description.contains(q)))
        if outcome:
            stmt = stmt.where(CooperationOpportunity.outcome_status == outcome)
        if owner_id:
            stmt = stmt.where(CooperationOpportunity.owner_id == int(owner_id))
        today = datetime.now().date()
        if updated_period == "today":
            stmt = stmt.where(CooperationOpportunity.updated_at >= datetime.combine(today, datetime.min.time()))
        elif updated_period == "7days":
            stmt = stmt.where(CooperationOpportunity.updated_at >= datetime.now() - timedelta(days=7))
        elif updated_period == "30days":
            stmt = stmt.where(CooperationOpportunity.updated_at >= datetime.now() - timedelta(days=30))
        if follow_scope == "today":
            start = datetime.combine(today, datetime.min.time())
            stmt = stmt.where(CooperationOpportunity.next_follow_at >= start, CooperationOpportunity.next_follow_at < start + timedelta(days=1))
        elif follow_scope == "overdue":
            stmt = stmt.where(CooperationOpportunity.next_follow_at < datetime.combine(today, datetime.min.time()))
        elif follow_scope == "future":
            stmt = stmt.where(CooperationOpportunity.next_follow_at >= datetime.combine(today + timedelta(days=1), datetime.min.time()))
        if closed_period == "this_month":
            month_start = datetime(today.year, today.month, 1)
            next_month = datetime(today.year + (1 if today.month == 12 else 0), 1 if today.month == 12 else today.month + 1, 1)
            stmt = stmt.where(CooperationOpportunity.closed_at >= month_start, CooperationOpportunity.closed_at < next_month)
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
            next_follow_at=_as_datetime(fields.get("next_follow_at")),
            stage=fields.get("stage") or "lead",
            owner_id=fields.get("owner_id") or int(actor_user_id),
            participants=fields.get("participants"),
            status=fields.get("status") or "active",
            visibility=fields.get("visibility") or "organization",
            human_confirmed_by=int(actor_user_id),
            human_confirmed_at=datetime.now(),
            source_intelligence_id=fields.get("source_intelligence_id"),
            source_demand_resource_id=fields.get("source_demand_resource_id"),
            source_supply_resource_id=fields.get("source_supply_resource_id"),
            source_match_id=fields.get("source_match_id"),
        )
        self.db.add(opp)
        self.db.flush()
        extra = {
            "opportunity_no": fields.get("opportunity_no"), "currency": fields.get("currency"),
            "success_probability": fields.get("success_probability"), "target_complete_at": fields.get("target_complete_at"),
            "risk_summary": fields.get("risk_summary"), "last_stage_changed_at": fields.get("last_stage_changed_at"),
            "pilot_batch_id": fields.get("pilot_batch_id"),
        }
        values = self._supported("v06_opportunities", extra)
        if values:
            assignments = ",".join(f"{key}=:{key}" for key in values)
            self.db.execute(text(f"UPDATE v06_opportunities SET {assignments} WHERE id=:opp_id"), {**values, "opp_id": opp.id})
        self.db.add(TimelineEntry(opportunity_id=opp.id, event_type="created", description=f"Opportunity created: {opp.title}", actor_id=actor_user_id))
        if commit:
            self.db.commit()
            self.db.refresh(opp)
        else:
            self.db.flush()
        return opp

    def update_stage(self, opp_id: int, *, actor_user_id: int, stage: str, is_admin: bool = False, commit: bool = True) -> CooperationOpportunity:
        opp = self.detail(opp_id, user_id=actor_user_id, is_admin=is_admin)
        if not self.can_manage(opp, actor_user_id, is_admin=is_admin):
            raise HTTPException(status_code=403, detail={"code": "OPPORTUNITY_STAGE_FORBIDDEN", "message": "无权修改机会阶段", "details": {}})
        old = opp.stage
        opp.stage = stage or opp.stage
        opp.updated_at = datetime.now()
        self.db.add(TimelineEntry(opportunity_id=opp.id, event_type="stage_change", description=f"Stage changed from {old} to {opp.stage}", actor_id=actor_user_id))
        self.db.flush()
        if commit:
            self.db.commit(); self.db.refresh(opp)
        return opp

    def close_outcome(self, opp_id: int, *, actor_user_id: int, outcome: str, relationship_id: int | None,
                      reason: str = "", result_note: str = "", cooperation_scale: str = "", commit: bool = True) -> CooperationOpportunity:
        opp = self.detail(opp_id, user_id=actor_user_id, is_admin=True)
        if outcome not in {"won", "lost", "paused"}:
            raise HTTPException(status_code=400, detail="结果必须是达成、未成交或暂停")
        now = datetime.now()
        opp.stage = outcome
        opp.status = "closed" if outcome in {"won", "lost"} else "active"
        opp.outcome_status = outcome
        opp.final_result = {"won": "合作达成", "lost": "未成交", "paused": "暂停"}[outcome]
        opp.closed_reason = reason or None
        opp.final_result_note = result_note or None
        opp.final_cooperation_scale = cooperation_scale or None
        opp.closed_by_user_id = actor_user_id
        opp.closed_at = now if outcome in {"won", "lost"} else None
        opp.result_relationship_id = relationship_id if outcome == "won" else None
        opp.updated_at = now
        self.db.add(TimelineEntry(opportunity_id=opp.id, event_type="outcome", description=opp.final_result,
                                  actor_id=actor_user_id, metadata_json=json.dumps({"outcome": outcome, "reason": reason,
                                  "relationship_id": relationship_id}, ensure_ascii=False)))
        self.db.flush()
        if commit:
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

    def create_follow_up(self, *, opp_id: int, actor_user_id: int, fields: dict[str, Any], is_admin: bool = False, commit: bool = True) -> FollowUp:
        opp = self.detail(opp_id, user_id=actor_user_id, is_admin=is_admin)
        if not self.can_manage(opp, actor_user_id, is_admin=is_admin):
            raise HTTPException(status_code=403, detail={"code": "FOLLOW_UP_FORBIDDEN", "message": "无权新增跟进", "details": {}})
        follow = FollowUp(opportunity_id=opp.id, follow_type=fields.get("follow_type") or "note", content=str(fields.get("content") or ""), created_by=actor_user_id,
                          followed_at=_as_datetime(fields.get("followed_at")) or datetime.now(), next_follow_at=_as_datetime(fields.get("next_follow_at")),
                          visibility=fields.get("visibility") or "organization")
        self.db.add(follow); self.db.flush()
        extra = {"participants_json": json.dumps(fields.get("participants") or [], ensure_ascii=False) if "participants" in fields else None, "result": fields.get("result"),
                 "next_action": fields.get("next_action"), "shared_summary": fields.get("shared_summary"), "internal_note": fields.get("internal_note"),
                 "artifact_ids_json": json.dumps(fields.get("artifact_ids") or [], ensure_ascii=False) if "artifact_ids" in fields else None, "pilot_batch_id": fields.get("pilot_batch_id"),
                 "contact_result": fields.get("contact_result"), "stage_after": fields.get("stage_after")}
        values = self._supported("v06_follow_ups", extra)
        if values:
            assignments = ",".join(f"{key}=:{key}" for key in values)
            self.db.execute(text(f"UPDATE v06_follow_ups SET {assignments} WHERE id=:follow_id"), {**values, "follow_id": follow.id})
        if fields.get("next_action") is not None: opp.next_action = fields.get("next_action")
        if fields.get("next_follow_at") is not None: opp.next_follow_at = _as_datetime(fields.get("next_follow_at"))
        if fields.get("stage_after"): opp.stage = fields.get("stage_after")
        opp.updated_at = datetime.now()
        self.db.add(TimelineEntry(opportunity_id=opp.id, event_type="follow_up", description=follow.content[:120], actor_id=actor_user_id))
        self.db.flush()
        if commit:
            self.db.commit(); self.db.refresh(follow)
        return follow

    def create_task(self, *, opp_id: int | None, actor_user_id: int, owner_id: int, fields: dict[str, Any], is_admin: bool = False, commit: bool = True) -> CollabTask:
        opp = self.detail(opp_id, user_id=actor_user_id, is_admin=is_admin) if opp_id is not None else None
        if opp and not self.can_manage(opp, actor_user_id, is_admin=is_admin):
            raise HTTPException(status_code=403, detail={"code": "TASK_FORBIDDEN", "message": "无权创建任务", "details": {}})
        if opp and owner_id != actor_user_id and owner_id not in _csv_ids(opp.participants) and owner_id not in {opp.owner_id, opp.initiator_id} and not is_admin:
            raise HTTPException(status_code=403, detail={"code": "TASK_OWNER_FORBIDDEN", "message": "不能分配给无权访问机会的用户", "details": {}})
        if not opp and owner_id != actor_user_id and not is_admin:
            raise HTTPException(status_code=403, detail={"code": "TASK_OWNER_FORBIDDEN", "message": "独立任务只能分配给自己", "details": {}})
        participants = fields.get("participants")
        if isinstance(participants, (list, dict)): participants = json.dumps(participants, ensure_ascii=False)
        task = CollabTask(title=str(fields.get("title") or "").strip() or "未命名任务", opportunity_id=opp.id if opp else None, owner_id=owner_id,
                          due_date=_as_datetime(fields.get("due_date")), priority=fields.get("priority") or "P2", created_by=actor_user_id, participants=participants)
        self.db.add(task); self.db.flush()
        extra = {"task_type": fields.get("task_type"), "completion_criteria": fields.get("completion_criteria"),
                 "related_follow_up_id": fields.get("related_follow_up_id"), "related_meeting_id": fields.get("related_meeting_id"),
                 "visibility": fields.get("visibility"), "pilot_batch_id": fields.get("pilot_batch_id")}
        values = self._supported("v06_collab_tasks", extra)
        if values:
            assignments = ",".join(f"{key}=:{key}" for key in values)
            self.db.execute(text(f"UPDATE v06_collab_tasks SET {assignments} WHERE id=:task_id"), {**values, "task_id": task.id})
        if opp:
            self.db.add(TimelineEntry(opportunity_id=opp.id, event_type="task", description=f"Task created: {task.title}", actor_id=actor_user_id))
        self.db.flush()
        if commit:
            self.db.commit(); self.db.refresh(task)
        return task

    def update_task(self, task_id: int, *, actor_user_id: int, status: str, blocked_reason: str = "",
                    is_admin: bool = False, commit: bool = True) -> CollabTask:
        task = self.db.get(CollabTask, int(task_id))
        if not task:
            raise HTTPException(status_code=404, detail={"code": "TASK_NOT_FOUND", "message": "协作任务不存在", "details": {}})
        opp = self.detail(int(task.opportunity_id), user_id=actor_user_id, is_admin=is_admin)
        if actor_user_id != task.owner_id and not self.can_manage(opp, actor_user_id, is_admin=is_admin):
            raise HTTPException(status_code=403, detail={"code": "TASK_UPDATE_FORBIDDEN", "message": "无权更新任务", "details": {}})
        task.status = status
        task.updated_at = datetime.now()
        self.db.flush()
        self.db.execute(text("UPDATE v06_collab_tasks SET blocked_reason=:reason,completed_at=CASE WHEN :status='completed' THEN :at ELSE completed_at END WHERE id=:id"),
                        {"reason": blocked_reason or None, "status": status, "at": task.updated_at, "id": task.id})
        if commit:
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



