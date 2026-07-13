from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models_platform import CooperationOpportunity
from app.services.unified_opportunity_service import UnifiedOpportunityService

P5_STAGES = (
    "draft", "validating", "matching", "introduced", "negotiating", "agreed",
    "executing", "on_hold", "won", "lost", "closed",
)
STAGE_TRANSITIONS = {
    "draft": {"validating", "lost", "closed"},
    "validating": {"matching", "on_hold", "lost", "closed"},
    "matching": {"introduced", "on_hold", "lost", "closed"},
    "introduced": {"negotiating", "on_hold", "lost", "closed"},
    "negotiating": {"agreed", "on_hold", "lost", "closed"},
    "agreed": {"executing", "on_hold", "lost", "closed"},
    "executing": {"on_hold", "won", "lost", "closed"},
    "on_hold": {"validating", "matching", "introduced", "negotiating", "agreed", "executing", "lost", "closed"},
    "won": {"closed"},
    "lost": {"closed"},
    "closed": set(),
}
LEGACY_STAGE_MAP = {
    "lead": "draft", "contacted": "validating", "qualified": "matching",
    "proposal": "negotiating", "due_diligence": "negotiating", "agreement": "agreed",
}
LEAD_STATES = {"new", "reviewing", "qualified", "disqualified", "converted"}
FOLLOW_TYPES = {
    "phone", "instant_message", "email", "meeting", "visit", "material_sent",
    "proposal", "technical_review", "negotiation", "internal_discussion", "other",
}
PARTICIPANT_TYPES = {"person", "organization", "user", "membership"}
PARTICIPANT_ROLES = {
    "demand_party", "supply_party", "owner", "collaborator", "decision_maker",
    "technical_evaluator", "business_contact", "advisor", "observer",
}
TASK_STATES = {"todo", "in_progress", "blocked", "completed", "cancelled"}


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def _as_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except ValueError as exc:
        raise HTTPException(400, detail={
            "code": "INVALID_DATETIME", "message": "日期时间格式无效", "details": {},
        }) from exc


def _number(prefix: str) -> str:
    return f"{prefix}-{datetime.now():%Y%m%d%H%M%S}-{uuid.uuid4().hex[:8].upper()}"


def _mapping(result) -> dict[str, Any] | None:
    row = result.mappings().first()
    return dict(row) if row else None


class BusinessCollaborationService:
    def __init__(self, db: Session):
        self.db = db
        self.opportunities = UnifiedOpportunityService(db)

    def schema_ready(self) -> bool:
        return self.db.execute(text(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='p5_opportunity_participants'"
        )).first() is not None

    def require_schema(self) -> None:
        if not self.schema_ready():
            raise HTTPException(409, detail={
                "code": "P5_MIGRATION_REQUIRED",
                "message": "当前数据库尚未应用 P5 增量迁移，请在受控副本执行 008 后验收",
                "details": {},
            })

    def _event(self, event_type: str, aggregate_type: str, aggregate_id: int | str,
               payload: dict[str, Any], actor_user_id: int | None, pilot_batch_id: str | None) -> None:
        self.db.execute(text("""
            INSERT INTO p5_domain_events(
              event_id,event_type,aggregate_type,aggregate_id,payload_json,actor_user_id,
              occurred_at,status,pilot_batch_id
            ) VALUES (:event_id,:event_type,:aggregate_type,:aggregate_id,:payload,:actor,:at,'pending',:pilot)
        """), {
            "event_id": str(uuid.uuid4()), "event_type": event_type,
            "aggregate_type": aggregate_type, "aggregate_id": str(aggregate_id),
            "payload": _dump(payload), "actor": actor_user_id, "at": now_iso(),
            "pilot": pilot_batch_id,
        })

    def _audit(self, action: str, target_type: str, target_id: int | str, actor_user_id: int,
               *, before: Any = None, after: Any = None, reason: str = "",
               pilot_batch_id: str | None = None) -> None:
        self.db.execute(text("""
            INSERT INTO p5_operation_audit(
              audit_no,action,target_type,target_id,before_json,after_json,actor_user_id,
              reason,result,pilot_batch_id,created_at
            ) VALUES (:no,:action,:type,:id,:before,:after,:actor,:reason,'success',:pilot,:at)
        """), {
            "no": _number("P5AUD"), "action": action, "type": target_type,
            "id": str(target_id), "before": _dump(before) if before is not None else None,
            "after": _dump(after) if after is not None else None, "actor": actor_user_id,
            "reason": reason or None, "pilot": pilot_batch_id, "at": now_iso(),
        })

    def _timeline(self, opportunity_id: int, event_type: str, description: str,
                  actor_user_id: int | None, pilot_batch_id: str | None) -> None:
        self.db.execute(text("""
            INSERT INTO v06_timeline_entries(
              opportunity_id,event_type,description,actor_id,metadata_json,created_at,pilot_batch_id
            ) VALUES (:opp,:type,:description,:actor,NULL,:at,:pilot)
        """), {
            "opp": opportunity_id, "type": event_type, "description": description[:500],
            "actor": actor_user_id, "at": now_iso(), "pilot": pilot_batch_id,
        })
    def _opportunity_row(self, opportunity_id: int) -> dict[str, Any]:
        row = _mapping(self.db.execute(text("SELECT * FROM v06_opportunities WHERE id=:id"), {"id": opportunity_id}))
        if not row:
            raise HTTPException(404, detail={"code": "OPPORTUNITY_NOT_FOUND", "message": "合作机会不存在", "details": {}})
        return row

    def _can_access(self, opportunity_id: int, actor_user_id: int, *, is_admin: bool = False) -> bool:
        if is_admin:
            return True
        opp = self.db.get(CooperationOpportunity, int(opportunity_id))
        if opp and self.opportunities.can_access(opp, actor_user_id, is_admin=False):
            return True
        if not self.schema_ready():
            return False
        return self.db.execute(text("""
            SELECT 1 FROM p5_opportunity_participants p
            LEFT JOIN v04f_club_memberships m
              ON p.participant_type='membership' AND CAST(m.id AS TEXT)=p.participant_id
            LEFT JOIN v05a_users u
              ON p.participant_type='person' AND CAST(u.person_id AS TEXT)=p.participant_id
            WHERE p.opportunity_id=:opp AND p.ended_at IS NULL
              AND ((p.participant_type='user' AND p.participant_id=:uid)
                   OR m.user_id=:user_id OR u.id=:user_id)
            LIMIT 1
        """), {"opp": opportunity_id, "uid": str(actor_user_id), "user_id": actor_user_id}).first() is not None

    def _can_manage(self, opportunity_id: int, actor_user_id: int, *, is_admin: bool = False) -> bool:
        if is_admin:
            return True
        opp = self.db.get(CooperationOpportunity, int(opportunity_id))
        if opp and int(actor_user_id) in {opp.initiator_id, opp.owner_id}:
            return True
        if not self.schema_ready():
            return False
        return self.db.execute(text("""
            SELECT 1 FROM p5_opportunity_participants
            WHERE opportunity_id=:opp AND participant_type='user' AND participant_id=:uid
              AND role IN ('owner','collaborator') AND ended_at IS NULL
        """), {"opp": opportunity_id, "uid": str(actor_user_id)}).first() is not None

    def create_lead(self, fields: dict[str, Any], *, actor_user_id: int) -> dict[str, Any]:
        self.require_schema()
        source_type = str(fields.get("source_type") or "manual")
        source_record_id = str(fields.get("source_record_id") or "").strip() or None
        if source_record_id:
            existing = _mapping(self.db.execute(text("""
                SELECT * FROM v04f_lead_records WHERE source_type=:type AND source_record_id=:source LIMIT 1
            """), {"type": source_type, "source": source_record_id}))
            if existing:
                existing["idempotent"] = True
                return existing
        ts = now_iso()
        subject_type = str(fields.get("subject_type") or "organization")
        if subject_type not in {"organization", "project"}:
            raise HTTPException(400, detail={"code": "INVALID_LEAD_SUBJECT", "message": "线索主体类型无效", "details": {}})
        subject_id = str(fields.get("subject_id") or fields.get("demand_organization_id") or fields.get("supply_organization_id") or "").strip()
        if not subject_id:
            raise HTTPException(400, detail={"code": "LEAD_SUBJECT_REQUIRED", "message": "线索必须关联机构或项目", "details": {}})
        result = self.db.execute(text("""
            INSERT INTO v04f_lead_records(
              lead_no,subject_type,subject_id,funnel_stage,system_score,system_grade,owner,next_action,
              status,created_at,updated_at,title,source_type,source_record_id,demand_organization_id,
              supply_organization_id,person_ids_json,organization_ids_json,recommendation_reason,
              relationship_path_json,evidence_json,owner_user_id,priority,suggested_next_action,
              lifecycle_status,pilot_batch_id
            ) VALUES (
              :no,:subject_type,:subject_id,'待识别',0,'C',:owner,:next_action,'active',:at,:at,
              :title,:source_type,:source_record_id,:demand_org,:supply_org,:people,:organizations,
              :reason,:path,:evidence,:owner_user,:priority,:next_action,'new',:pilot
            )
        """), {
            "no": _number("P5L"), "subject_type": subject_type, "subject_id": subject_id,
            "owner": str(fields.get("owner") or actor_user_id), "next_action": fields.get("next_action"),
            "at": ts, "title": str(fields.get("title") or "未命名商务线索").strip(),
            "source_type": source_type, "source_record_id": source_record_id,
            "demand_org": fields.get("demand_organization_id"), "supply_org": fields.get("supply_organization_id"),
            "people": _dump(fields.get("person_ids") or []), "organizations": _dump(fields.get("organization_ids") or []),
            "reason": fields.get("recommendation_reason"), "path": _dump(fields.get("relationship_path") or []),
            "evidence": _dump(fields.get("evidence") or []), "owner_user": fields.get("owner_user_id") or actor_user_id,
            "priority": fields.get("priority") or "P2", "pilot": fields.get("pilot_batch_id"),
        })
        lead_id = int(result.lastrowid)
        lead = self.lead_detail(lead_id)
        self._audit("lead.created", "lead", lead_id, actor_user_id, after={"status": "new"}, pilot_batch_id=lead.get("pilot_batch_id"))
        self.db.commit()
        lead["idempotent"] = False
        return lead

    def list_leads(self, *, lifecycle_status: str = "", limit: int = 200) -> list[dict[str, Any]]:
        self.require_schema()
        sql = "SELECT * FROM v04f_lead_records WHERE source_type IS NOT NULL"
        params: dict[str, Any] = {"limit": max(1, min(int(limit), 500))}
        if lifecycle_status:
            sql += " AND lifecycle_status=:status"
            params["status"] = lifecycle_status
        sql += " ORDER BY updated_at DESC,id DESC LIMIT :limit"
        return [dict(row) for row in self.db.execute(text(sql), params).mappings()]

    def lead_detail(self, lead_id: int) -> dict[str, Any]:
        self.require_schema()
        row = _mapping(self.db.execute(text("SELECT * FROM v04f_lead_records WHERE id=:id"), {"id": lead_id}))
        if not row:
            raise HTTPException(404, detail={"code": "LEAD_NOT_FOUND", "message": "线索不存在", "details": {}})
        for key in ("person_ids_json", "organization_ids_json", "relationship_path_json", "evidence_json"):
            row[key.removesuffix("_json")] = _loads(row.get(key), [])
        return row

    def review_lead(self, lead_id: int, *, decision: str, actor_user_id: int, reason: str = "") -> dict[str, Any]:
        self.require_schema()
        if decision not in {"reviewing", "qualified", "disqualified"}:
            raise HTTPException(400, detail={"code": "INVALID_LEAD_DECISION", "message": "无效线索审核状态", "details": {}})
        if decision == "disqualified" and not reason.strip():
            raise HTTPException(400, detail={"code": "LEAD_REASON_REQUIRED", "message": "否决线索必须填写原因", "details": {}})
        lead = self.lead_detail(lead_id)
        if lead["lifecycle_status"] == decision:
            return {"lead": lead, "idempotent": True}
        if lead["lifecycle_status"] == "converted":
            raise HTTPException(409, detail={"code": "LEAD_ALREADY_CONVERTED", "message": "已转化线索不能重新审核", "details": {}})
        self.db.execute(text("""
            UPDATE v04f_lead_records SET lifecycle_status=:status,
              funnel_stage=:stage,decision_reason=:reason,updated_at=:at WHERE id=:id
        """), {
            "status": decision, "stage": {"reviewing": "审核中", "qualified": "已确认", "disqualified": "已否决"}[decision],
            "reason": reason or None, "at": now_iso(), "id": lead_id,
        })
        self._audit("lead.reviewed", "lead", lead_id, actor_user_id,
                    before={"status": lead["lifecycle_status"]}, after={"status": decision},
                    reason=reason, pilot_batch_id=lead.get("pilot_batch_id"))
        if decision == "qualified":
            self._event("lead.qualified", "lead", lead_id, {"source_type": lead.get("source_type")}, actor_user_id, lead.get("pilot_batch_id"))
        self.db.commit()
        return {"lead": self.lead_detail(lead_id), "idempotent": False}

    def _insert_participant(self, opportunity_id: int, *, participant_type: str, participant_id: int | str,
                            role: str, actor_user_id: int, visibility: str = "organization",
                            is_internal: bool = False, pilot_batch_id: str | None = None) -> None:
        if participant_type not in PARTICIPANT_TYPES or role not in PARTICIPANT_ROLES:
            raise HTTPException(400, detail={"code": "INVALID_PARTICIPANT", "message": "参与者类型或角色无效", "details": {}})
        ts = now_iso()
        self.db.execute(text("""
            INSERT INTO p5_opportunity_participants(
              opportunity_id,participant_type,participant_id,role,is_internal,visibility,
              started_at,added_by_user_id,pilot_batch_id,created_at,updated_at
            ) VALUES (:opp,:type,:pid,:role,:internal,:visibility,:at,:actor,:pilot,:at,:at)
            ON CONFLICT(opportunity_id,participant_type,participant_id,role)
            DO UPDATE SET ended_at=NULL,visibility=excluded.visibility,updated_at=excluded.updated_at
        """), {
            "opp": opportunity_id, "type": participant_type, "pid": str(participant_id), "role": role,
            "internal": int(is_internal), "visibility": visibility, "at": ts,
            "actor": actor_user_id, "pilot": pilot_batch_id,
        })

    def convert_lead(self, lead_id: int, *, actor_user_id: int,
                     fields: dict[str, Any], is_admin: bool = False) -> dict[str, Any]:
        self.require_schema()
        lead = self.lead_detail(lead_id)
        if lead.get("converted_opportunity_id"):
            return {"opportunity": self._opportunity_row(int(lead["converted_opportunity_id"])), "lead": lead, "idempotent": True}
        if lead["lifecycle_status"] != "qualified":
            raise HTTPException(409, detail={"code": "QUALIFIED_LEAD_REQUIRED", "message": "只有人工确认的线索可以转化", "details": {}})
        source_type = str(lead.get("source_type") or "lead")
        source_record_id = str(lead.get("source_record_id") or lead_id)
        duplicate = _mapping(self.db.execute(text("""
            SELECT opportunity_id FROM p5_opportunity_sources
            WHERE source_type=:type AND source_record_id=:source LIMIT 1
        """), {"type": source_type, "source": source_record_id}))
        if duplicate:
            raise HTTPException(409, detail={
                "code": "DUPLICATE_OPPORTUNITY_SOURCE", "message": "该来源已存在正式合作机会",
                "details": {"opportunity_id": duplicate["opportunity_id"]},
            })
        ts = now_iso()
        opportunity = self.opportunities.create(actor_user_id=actor_user_id, fields={
            "title": fields.get("title") or lead.get("title") or "未命名合作机会",
            "opp_type": fields.get("opp_type") or "collaboration",
            "source_type": "lead", "source_id": lead_id,
            "demand_organization_id": lead.get("demand_organization_id"),
            "supply_organization_id": lead.get("supply_organization_id"),
            "description": fields.get("description") or lead.get("recommendation_reason"),
            "expected_outcome": fields.get("expected_outcome"),
            "priority": fields.get("priority") or lead.get("priority") or "P2",
            "estimated_amount": fields.get("estimated_amount"),
            "next_action": fields.get("next_action") or lead.get("suggested_next_action"),
            "next_follow_at": _as_datetime(fields.get("next_follow_at")),
            "owner_id": fields.get("owner_id") or lead.get("owner_user_id") or actor_user_id,
            "visibility": fields.get("visibility") or "organization",
            "human_confirmed": True,
        }, commit=False)
        opportunity.stage = "draft"
        self.db.flush()
        opportunity_no = _number("P5O")
        self.db.execute(text("""
            UPDATE v06_opportunities SET opportunity_no=:no,currency=:currency,
              success_probability=:probability,target_complete_at=:target,risk_summary=:risk,
              last_stage_changed_at=:at,pilot_batch_id=:pilot,updated_at=:at WHERE id=:id
        """), {
            "no": opportunity_no, "currency": fields.get("currency"),
            "probability": fields.get("success_probability"), "target": fields.get("target_complete_at"),
            "risk": fields.get("risk_summary"), "at": ts, "pilot": lead.get("pilot_batch_id"),
            "id": opportunity.id,
        })
        self.db.execute(text("""
            INSERT INTO p5_opportunity_stage_history(
              opportunity_id,old_stage,new_stage,reason,actor_user_id,pilot_batch_id,created_at
            ) VALUES (:opp,NULL,'draft','线索人工确认转化',:actor,:pilot,:at)
        """), {"opp": opportunity.id, "actor": actor_user_id, "pilot": lead.get("pilot_batch_id"), "at": ts})
        self.db.execute(text("""
            INSERT INTO p5_opportunity_sources(
              opportunity_id,source_type,source_record_id,source_label,evidence_json,
              relationship_path_json,added_by_user_id,pilot_batch_id,created_at
            ) VALUES (:opp,:type,:source,:label,:evidence,:path,:actor,:pilot,:at)
        """), {
            "opp": opportunity.id, "type": source_type, "source": source_record_id,
            "label": lead.get("title"), "evidence": lead.get("evidence_json"),
            "path": lead.get("relationship_path_json"), "actor": actor_user_id,
            "pilot": lead.get("pilot_batch_id"), "at": ts,
        })
        owner_id = int(fields.get("owner_id") or lead.get("owner_user_id") or actor_user_id)
        self._insert_participant(opportunity.id, participant_type="user", participant_id=owner_id,
                                 role="owner", actor_user_id=actor_user_id, is_internal=True,
                                 pilot_batch_id=lead.get("pilot_batch_id"))
        for org_id, role in ((lead.get("demand_organization_id"), "demand_party"), (lead.get("supply_organization_id"), "supply_party")):
            if org_id:
                self._insert_participant(opportunity.id, participant_type="organization", participant_id=org_id,
                                         role=role, actor_user_id=actor_user_id, pilot_batch_id=lead.get("pilot_batch_id"))
        for person_id in _loads(lead.get("person_ids_json"), []):
            self._insert_participant(opportunity.id, participant_type="person", participant_id=person_id,
                                     role="business_contact", actor_user_id=actor_user_id,
                                     pilot_batch_id=lead.get("pilot_batch_id"))
        self.db.execute(text("""
            UPDATE v04f_lead_records SET lifecycle_status='converted',funnel_stage='已转化',
              converted_opportunity_id=:opp,updated_at=:at WHERE id=:id
        """), {"opp": opportunity.id, "at": ts, "id": lead_id})
        self._event("lead.converted", "lead", lead_id, {"opportunity_id": opportunity.id}, actor_user_id, lead.get("pilot_batch_id"))
        self._event("opportunity.created", "opportunity", opportunity.id, {"lead_id": lead_id, "stage": "draft"}, actor_user_id, lead.get("pilot_batch_id"))
        self._audit("lead.converted", "lead", lead_id, actor_user_id,
                    before={"status": "qualified"}, after={"status": "converted", "opportunity_id": opportunity.id},
                    pilot_batch_id=lead.get("pilot_batch_id"))
        self.db.commit()
        return {"opportunity": self._opportunity_row(opportunity.id), "lead": self.lead_detail(lead_id), "idempotent": False}

    def update_stage(self, opportunity_id: int, *, stage: str, actor_user_id: int,
                     reason: str = "", is_admin: bool = False) -> dict[str, Any]:
        self.require_schema()
        if stage not in P5_STAGES:
            raise HTTPException(400, detail={"code": "INVALID_OPPORTUNITY_STAGE", "message": "无效合作机会阶段", "details": {}})
        if not self._can_manage(opportunity_id, actor_user_id, is_admin=is_admin):
            raise HTTPException(403, detail={"code": "OPPORTUNITY_STAGE_FORBIDDEN", "message": "无权推进该合作机会", "details": {}})
        opp = self._opportunity_row(opportunity_id)
        current = LEGACY_STAGE_MAP.get(str(opp["stage"]), str(opp["stage"]))
        if current == stage:
            return {"opportunity": opp, "idempotent": True, "warnings": []}
        if stage not in STAGE_TRANSITIONS.get(current, set()):
            raise HTTPException(409, detail={"code": "INVALID_STAGE_TRANSITION", "message": f"不能从 {current} 直接进入 {stage}", "details": {}})
        if stage in {"lost", "closed"} and not reason.strip():
            raise HTTPException(400, detail={"code": "STAGE_REASON_REQUIRED", "message": "失败或关闭必须填写原因", "details": {}})
        open_tasks = int(self.db.execute(text("""
            SELECT COUNT(*) FROM v06_collab_tasks
            WHERE opportunity_id=:opp AND status NOT IN ('completed','cancelled')
        """), {"opp": opportunity_id}).scalar() or 0)
        warnings = [f"仍有 {open_tasks} 个未完成任务"] if stage in {"won", "lost", "closed"} and open_tasks else []
        ts = now_iso()
        self.db.execute(text("""
            UPDATE v06_opportunities SET stage=:stage,
              status=CASE WHEN :stage='closed' THEN 'closed' ELSE status END,
              last_stage_changed_at=:at,updated_at=:at WHERE id=:id
        """), {"stage": stage, "at": ts, "id": opportunity_id})
        self.db.execute(text("""
            INSERT INTO p5_opportunity_stage_history(
              opportunity_id,old_stage,new_stage,reason,actor_user_id,
              unresolved_task_count,pilot_batch_id,created_at
            ) VALUES (:opp,:old,:new,:reason,:actor,:tasks,:pilot,:at)
        """), {
            "opp": opportunity_id, "old": current, "new": stage, "reason": reason or None,
            "actor": actor_user_id, "tasks": open_tasks, "pilot": opp.get("pilot_batch_id"), "at": ts,
        })
        self._timeline(opportunity_id, "stage_change", f"Stage changed from {current} to {stage}: {reason}", actor_user_id, opp.get("pilot_batch_id"))
        self._event("opportunity.stage_changed", "opportunity", opportunity_id,
                    {"old_stage": current, "new_stage": stage, "reason": reason}, actor_user_id, opp.get("pilot_batch_id"))
        if stage in {"won", "lost"}:
            self._event(f"opportunity.{stage}", "opportunity", opportunity_id,
                        {"reason": reason}, actor_user_id, opp.get("pilot_batch_id"))
        self._audit("opportunity.stage_changed", "opportunity", opportunity_id, actor_user_id,
                    before={"stage": current}, after={"stage": stage}, reason=reason,
                    pilot_batch_id=opp.get("pilot_batch_id"))
        self.db.commit()
        return {"opportunity": self._opportunity_row(opportunity_id), "idempotent": False, "warnings": warnings}

    def add_participant(self, opportunity_id: int, fields: dict[str, Any], *, actor_user_id: int,
                        is_admin: bool = False) -> dict[str, Any]:
        self.require_schema()
        if not self._can_manage(opportunity_id, actor_user_id, is_admin=is_admin):
            raise HTTPException(403, detail={"code": "PARTICIPANT_FORBIDDEN", "message": "无权管理参与者", "details": {}})
        opp = self._opportunity_row(opportunity_id)
        self._insert_participant(opportunity_id, participant_type=str(fields.get("participant_type")),
                                 participant_id=str(fields.get("participant_id")), role=str(fields.get("role")),
                                 actor_user_id=actor_user_id, visibility=str(fields.get("visibility") or "organization"),
                                 is_internal=bool(fields.get("is_internal")), pilot_batch_id=opp.get("pilot_batch_id"))
        self._audit("participant.added", "opportunity", opportunity_id, actor_user_id,
                    after={k: fields.get(k) for k in ("participant_type", "participant_id", "role")},
                    pilot_batch_id=opp.get("pilot_batch_id"))
        self.db.commit()
        return {"participants": self.participants(opportunity_id, actor_user_id=actor_user_id, is_admin=is_admin)}

    def participants(self, opportunity_id: int, *, actor_user_id: int, is_admin: bool = False) -> list[dict[str, Any]]:
        if not self._can_access(opportunity_id, actor_user_id, is_admin=is_admin):
            raise HTTPException(403, detail={"code": "OPPORTUNITY_FORBIDDEN", "message": "无权查看该合作机会", "details": {}})
        return [dict(row) for row in self.db.execute(text("""
            SELECT id,opportunity_id,participant_type,participant_id,role,is_internal,
                   visibility,started_at,ended_at
            FROM p5_opportunity_participants WHERE opportunity_id=:opp ORDER BY id
        """), {"opp": opportunity_id}).mappings()]

    def add_follow_up(self, opportunity_id: int, fields: dict[str, Any], *, actor_user_id: int,
                      is_admin: bool = False) -> dict[str, Any]:
        self.require_schema()
        if not self._can_manage(opportunity_id, actor_user_id, is_admin=is_admin):
            raise HTTPException(403, detail={"code": "FOLLOW_UP_FORBIDDEN", "message": "无权新增跟进", "details": {}})
        follow_type = str(fields.get("follow_type") or "other")
        if follow_type not in FOLLOW_TYPES:
            raise HTTPException(400, detail={"code": "INVALID_FOLLOW_UP_TYPE", "message": "无效跟进类型", "details": {}})
        opp = self._opportunity_row(opportunity_id)
        ts = str(fields.get("followed_at") or now_iso())
        result = self.db.execute(text("""
            INSERT INTO v06_follow_ups(
              opportunity_id,follow_type,content,created_by,followed_at,next_follow_at,visibility,
              created_at,participants_json,result,next_action,shared_summary,internal_note,
              artifact_ids_json,pilot_batch_id
            ) VALUES (:opp,:type,:content,:actor,:followed,:next_follow,:visibility,:at,:participants,
                      :result,:next_action,:shared,:internal,:artifacts,:pilot)
        """), {
            "opp": opportunity_id, "type": follow_type, "content": str(fields.get("content") or ""),
            "actor": actor_user_id, "followed": ts, "next_follow": fields.get("next_follow_at"),
            "visibility": fields.get("visibility") or "organization", "at": now_iso(),
            "participants": _dump(fields.get("participants") or []), "result": fields.get("result"),
            "next_action": fields.get("next_action"), "shared": fields.get("shared_summary"),
            "internal": fields.get("internal_note"), "artifacts": _dump(fields.get("artifact_ids") or []),
            "pilot": opp.get("pilot_batch_id"),
        })
        follow_id = int(result.lastrowid)
        if fields.get("next_action") is not None or fields.get("next_follow_at") is not None:
            self.db.execute(text("""
                UPDATE v06_opportunities SET next_action=COALESCE(:action,next_action),
                  next_follow_at=COALESCE(:follow,next_follow_at),updated_at=:at WHERE id=:id
            """), {"action": fields.get("next_action"), "follow": fields.get("next_follow_at"), "at": now_iso(), "id": opportunity_id})
        self._timeline(opportunity_id, "follow_up", str(fields.get("shared_summary") or fields.get("content") or ""), actor_user_id, opp.get("pilot_batch_id"))
        self._event("opportunity.followup_added", "opportunity", opportunity_id,
                    {"follow_up_id": follow_id, "follow_type": follow_type}, actor_user_id, opp.get("pilot_batch_id"))
        self._audit("follow_up.added", "follow_up", follow_id, actor_user_id,
                    after={"opportunity_id": opportunity_id, "follow_type": follow_type}, pilot_batch_id=opp.get("pilot_batch_id"))
        self.db.commit()
        return self.follow_up_detail(follow_id, can_view_internal=True)

    def follow_up_detail(self, follow_id: int, *, can_view_internal: bool) -> dict[str, Any]:
        row = _mapping(self.db.execute(text("SELECT * FROM v06_follow_ups WHERE id=:id"), {"id": follow_id}))
        if not row:
            raise HTTPException(404, detail={"code": "FOLLOW_UP_NOT_FOUND", "message": "跟进记录不存在", "details": {}})
        if not can_view_internal:
            row.pop("internal_note", None)
        return row

    def create_task(self, opportunity_id: int, fields: dict[str, Any], *, actor_user_id: int,
                    is_admin: bool = False) -> dict[str, Any]:
        self.require_schema()
        if not self._can_manage(opportunity_id, actor_user_id, is_admin=is_admin):
            raise HTTPException(403, detail={"code": "TASK_FORBIDDEN", "message": "无权创建协作任务", "details": {}})
        owner_id = int(fields.get("owner_id") or actor_user_id)
        if not self._can_access(opportunity_id, owner_id, is_admin=is_admin):
            raise HTTPException(403, detail={"code": "TASK_OWNER_FORBIDDEN", "message": "任务负责人无权访问该合作机会", "details": {}})
        opp = self._opportunity_row(opportunity_id)
        result = self.db.execute(text("""
            INSERT INTO v06_collab_tasks(
              title,opportunity_id,owner_id,participants,due_date,priority,status,created_by,
              is_demo,created_at,updated_at,task_type,completion_criteria,related_follow_up_id,
              related_meeting_id,visibility,pilot_batch_id
            ) VALUES (:title,:opp,:owner,:participants,:due,:priority,'todo',:actor,0,:at,:at,
                      :type,:criteria,:follow,:meeting,:visibility,:pilot)
        """), {
            "title": str(fields.get("title") or "未命名协作任务"), "opp": opportunity_id,
            "owner": owner_id, "participants": _dump(fields.get("participants") or []),
            "due": fields.get("due_date"), "priority": fields.get("priority") or "P2",
            "actor": actor_user_id, "at": now_iso(), "type": fields.get("task_type") or "other",
            "criteria": fields.get("completion_criteria"), "follow": fields.get("related_follow_up_id"),
            "meeting": fields.get("related_meeting_id"), "visibility": fields.get("visibility") or "organization",
            "pilot": opp.get("pilot_batch_id"),
        })
        task_id = int(result.lastrowid)
        self._timeline(opportunity_id, "task", f"Task created: {fields.get('title')}", actor_user_id, opp.get("pilot_batch_id"))
        self._event("task.assigned", "collaboration_task", task_id,
                    {"opportunity_id": opportunity_id, "owner_id": owner_id}, actor_user_id, opp.get("pilot_batch_id"))
        self.db.commit()
        return self.task_detail(task_id)

    def task_detail(self, task_id: int) -> dict[str, Any]:
        row = _mapping(self.db.execute(text("SELECT * FROM v06_collab_tasks WHERE id=:id"), {"id": task_id}))
        if not row:
            raise HTTPException(404, detail={"code": "TASK_NOT_FOUND", "message": "协作任务不存在", "details": {}})
        row["overdue"] = bool(row.get("due_date") and str(row["due_date"]) < now_iso() and row.get("status") not in {"completed", "cancelled"})
        return row

    def update_task(self, task_id: int, *, status: str, actor_user_id: int,
                    blocked_reason: str = "", is_admin: bool = False) -> dict[str, Any]:
        if status not in TASK_STATES:
            raise HTTPException(400, detail={"code": "INVALID_TASK_STATUS", "message": "无效任务状态", "details": {}})
        task = self.task_detail(task_id)
        opp = self._opportunity_row(int(task["opportunity_id"]))
        allowed = actor_user_id == int(task["owner_id"]) or self._can_manage(int(task["opportunity_id"]), actor_user_id, is_admin=is_admin)
        if not allowed:
            raise HTTPException(403, detail={"code": "TASK_UPDATE_FORBIDDEN", "message": "只有负责人或授权人员可更新任务", "details": {}})
        if status == "blocked" and not blocked_reason.strip():
            raise HTTPException(400, detail={"code": "BLOCKED_REASON_REQUIRED", "message": "阻塞任务必须填写原因", "details": {}})
        self.db.execute(text("""
            UPDATE v06_collab_tasks SET status=:status,blocked_reason=:reason,
              completed_at=CASE WHEN :status='completed' THEN :at ELSE completed_at END,
              updated_at=:at WHERE id=:id
        """), {"status": status, "reason": blocked_reason or None, "at": now_iso(), "id": task_id})
        if status == "completed":
            self._event("task.completed", "collaboration_task", task_id,
                        {"opportunity_id": task["opportunity_id"]}, actor_user_id, opp.get("pilot_batch_id"))
        self._audit("task.updated", "collaboration_task", task_id, actor_user_id,
                    before={"status": task["status"]}, after={"status": status}, reason=blocked_reason,
                    pilot_batch_id=opp.get("pilot_batch_id"))
        self.db.commit()
        return self.task_detail(task_id)

    def schedule_meeting(self, opportunity_id: int, fields: dict[str, Any], *, actor_user_id: int,
                         is_admin: bool = False) -> dict[str, Any]:
        self.require_schema()
        if not self._can_manage(opportunity_id, actor_user_id, is_admin=is_admin):
            raise HTTPException(403, detail={"code": "MEETING_FORBIDDEN", "message": "无权安排会议", "details": {}})
        opp = self._opportunity_row(opportunity_id)
        ts = now_iso()
        result = self.db.execute(text("""
            INSERT INTO p5_opportunity_meetings(
              meeting_no,opportunity_id,subject,starts_at,ends_at,location,online_url,
              organizer_user_id,participants_json,agenda,status,external_calendar_id,
              calendar_sync_status,visibility,pilot_batch_id,created_at,updated_at
            ) VALUES (:no,:opp,:subject,:starts,:ends,:location,:url,:organizer,:participants,
                      :agenda,'scheduled',:external_id,'not_started',:visibility,:pilot,:at,:at)
        """), {
            "no": _number("P5M"), "opp": opportunity_id, "subject": str(fields.get("subject") or "合作推进会议"),
            "starts": fields.get("starts_at") or ts, "ends": fields.get("ends_at"),
            "location": fields.get("location"), "url": fields.get("online_url"), "organizer": actor_user_id,
            "participants": _dump(fields.get("participants") or []), "agenda": fields.get("agenda"),
            "external_id": fields.get("external_calendar_id"), "visibility": fields.get("visibility") or "organization",
            "pilot": opp.get("pilot_batch_id"), "at": ts,
        })
        meeting_id = int(result.lastrowid)
        self._event("meeting.scheduled", "opportunity_meeting", meeting_id,
                    {"opportunity_id": opportunity_id}, actor_user_id, opp.get("pilot_batch_id"))
        self.db.commit()
        return self.meeting_detail(meeting_id)

    def meeting_detail(self, meeting_id: int) -> dict[str, Any]:
        row = _mapping(self.db.execute(text("SELECT * FROM p5_opportunity_meetings WHERE id=:id"), {"id": meeting_id}))
        if not row:
            raise HTTPException(404, detail={"code": "MEETING_NOT_FOUND", "message": "会议不存在", "details": {}})
        return row

    def complete_meeting(self, meeting_id: int, fields: dict[str, Any], *, actor_user_id: int,
                         is_admin: bool = False) -> dict[str, Any]:
        meeting = self.meeting_detail(meeting_id)
        opportunity_id = int(meeting["opportunity_id"])
        if not self._can_manage(opportunity_id, actor_user_id, is_admin=is_admin):
            raise HTTPException(403, detail={"code": "MEETING_FORBIDDEN", "message": "无权完成会议", "details": {}})
        if meeting["status"] == "completed":
            return {"meeting": meeting, "tasks": [], "idempotent": True}
        ts = now_iso()
        self.db.execute(text("""
            UPDATE p5_opportunity_meetings SET status='completed',minutes=:minutes,
              decisions=:decisions,completed_at=:at,updated_at=:at WHERE id=:id
        """), {"minutes": fields.get("minutes"), "decisions": fields.get("decisions"), "at": ts, "id": meeting_id})
        tasks = []
        for draft in fields.get("task_drafts") or []:
            draft = {**draft, "related_meeting_id": meeting_id}
            tasks.append(self.create_task(opportunity_id, draft, actor_user_id=actor_user_id, is_admin=is_admin))
        opp = self._opportunity_row(opportunity_id)
        self._event("meeting.completed", "opportunity_meeting", meeting_id,
                    {"opportunity_id": opportunity_id, "task_ids": [task["id"] for task in tasks]},
                    actor_user_id, opp.get("pilot_batch_id"))
        self.db.commit()
        return {"meeting": self.meeting_detail(meeting_id), "tasks": tasks, "idempotent": False}

    def add_artifact(self, opportunity_id: int, fields: dict[str, Any], *, actor_user_id: int,
                     is_admin: bool = False) -> dict[str, Any]:
        self.require_schema()
        if not self._can_manage(opportunity_id, actor_user_id, is_admin=is_admin):
            raise HTTPException(403, detail={"code": "ARTIFACT_FORBIDDEN", "message": "无权添加材料引用", "details": {}})
        if not fields.get("local_path") and not fields.get("external_url"):
            raise HTTPException(400, detail={"code": "ARTIFACT_REFERENCE_REQUIRED", "message": "必须填写本地路径或外部链接", "details": {}})
        opp = self._opportunity_row(opportunity_id)
        result = self.db.execute(text("""
            INSERT INTO p5_opportunity_artifacts(
              artifact_no,opportunity_id,follow_up_id,meeting_id,file_name,artifact_type,
              local_path,external_url,file_hash,uploaded_by_user_id,visibility,version,
              pilot_batch_id,created_at
            ) VALUES (:no,:opp,:follow,:meeting,:name,:type,:path,:url,:hash,:actor,
                      :visibility,:version,:pilot,:at)
        """), {
            "no": _number("P5A"), "opp": opportunity_id, "follow": fields.get("follow_up_id"),
            "meeting": fields.get("meeting_id"), "name": str(fields.get("file_name") or "未命名材料"),
            "type": fields.get("artifact_type") or "other", "path": fields.get("local_path"),
            "url": fields.get("external_url"), "hash": fields.get("file_hash"), "actor": actor_user_id,
            "visibility": fields.get("visibility") or "organization", "version": int(fields.get("version") or 1),
            "pilot": opp.get("pilot_batch_id"), "at": now_iso(),
        })
        artifact_id = int(result.lastrowid)
        self._audit("artifact.added", "opportunity_artifact", artifact_id, actor_user_id,
                    after={"opportunity_id": opportunity_id, "file_name": fields.get("file_name")},
                    pilot_batch_id=opp.get("pilot_batch_id"))
        self.db.commit()
        return _mapping(self.db.execute(text("SELECT * FROM p5_opportunity_artifacts WHERE id=:id"), {"id": artifact_id})) or {}

    def calculate_risks(self, *, pilot_batch_id: str | None = None) -> list[dict[str, Any]]:
        self.require_schema()
        params: dict[str, Any] = {}
        sql = "SELECT * FROM v06_opportunities WHERE status='active' AND stage NOT IN ('won','lost','closed')"
        if pilot_batch_id:
            sql += " AND pilot_batch_id=:pilot"
            params["pilot"] = pilot_batch_id
        opportunities = [dict(row) for row in self.db.execute(text(sql), params).mappings()]
        detected: list[dict[str, Any]] = []
        now = datetime.now().replace(microsecond=0)
        for opp in opportunities:
            risks: list[tuple[str, str, str, str]] = []
            if not opp.get("owner_id"):
                risks.append(("missing_owner", "high", "合作机会没有负责人", "分配机会负责人"))
            if not str(opp.get("next_action") or "").strip():
                risks.append(("missing_next_action", "medium", "下一步行动为空", "补充明确的下一步行动"))
            if opp.get("next_follow_at") and str(opp["next_follow_at"]) < now.isoformat():
                risks.append(("follow_up_overdue", "high", "下次跟进时间已过", "立即补充跟进记录并重设日期"))
            overdue_tasks = int(self.db.execute(text("""
                SELECT COUNT(*) FROM v06_collab_tasks WHERE opportunity_id=:opp
                  AND due_date IS NOT NULL AND due_date<:now AND status NOT IN ('completed','cancelled')
            """), {"opp": opp["id"], "now": now.isoformat()}).scalar() or 0)
            if overdue_tasks:
                risks.append(("task_overdue", "high", f"有 {overdue_tasks} 个任务逾期", "重新安排或完成逾期任务"))
            participants = int(self.db.execute(text("SELECT COUNT(*) FROM p5_opportunity_participants WHERE opportunity_id=:opp AND ended_at IS NULL"), {"opp": opp["id"]}).scalar() or 0)
            if participants < 2:
                risks.append(("missing_key_participant", "medium", "关键参与者不足", "补充需求方、资源方或决策人"))
            sources = int(self.db.execute(text("SELECT COUNT(*) FROM p5_opportunity_sources WHERE opportunity_id=:opp"), {"opp": opp["id"]}).scalar() or 0)
            if not sources:
                risks.append(("insufficient_evidence", "medium", "缺少可追溯来源或证据", "关联情报、研究、匹配或人工证据"))
            changed = opp.get("last_stage_changed_at") or opp.get("updated_at")
            if changed:
                try:
                    if datetime.fromisoformat(str(changed)) < now - timedelta(days=30):
                        risks.append(("stage_stagnant", "medium", "阶段停留超过 30 天", "核实推进障碍并更新阶段"))
                except ValueError:
                    pass
            for risk_type, level, reason, action in risks:
                self.db.execute(text("""
                    INSERT INTO p5_opportunity_risks(
                      opportunity_id,risk_type,risk_level,reason,suggested_action,status,
                      detected_at,pilot_batch_id
                    ) VALUES (:opp,:type,:level,:reason,:action,'open',:at,:pilot)
                    ON CONFLICT(opportunity_id,risk_type,status)
                    DO UPDATE SET risk_level=excluded.risk_level,reason=excluded.reason,
                                  suggested_action=excluded.suggested_action,detected_at=excluded.detected_at
                """), {"opp": opp["id"], "type": risk_type, "level": level, "reason": reason,
                         "action": action, "at": now.isoformat(), "pilot": opp.get("pilot_batch_id")})
                detected.append({"opportunity_id": opp["id"], "risk_type": risk_type, "risk_level": level,
                                 "reason": reason, "suggested_action": action})
            if any(item[1] == "high" for item in risks):
                self._event("opportunity.overdue", "opportunity", opp["id"],
                            {"risks": [item[0] for item in risks if item[1] == "high"]}, None, opp.get("pilot_batch_id"))
        self.db.commit()
        return detected

    def dashboard(self, *, actor_user_id: int, is_admin: bool = False) -> dict[str, Any]:
        if not self.schema_ready():
            return {"schema_ready": False, "metrics": {}, "queues": {}, "generated_at": now_iso()}
        today = datetime.now().date().isoformat()
        week = (datetime.now() + timedelta(days=7)).date().isoformat()
        month = datetime.now().strftime("%Y-%m")
        scalar = lambda sql, params=None: int(self.db.execute(text(sql), params or {}).scalar() or 0)
        metrics = {
            "新线索": scalar("SELECT COUNT(*) FROM v04f_lead_records WHERE lifecycle_status='new'"),
            "待确认线索": scalar("SELECT COUNT(*) FROM v04f_lead_records WHERE lifecycle_status IN ('reviewing','qualified')"),
            "推进中机会": scalar("SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND stage NOT IN ('won','lost','closed')"),
            "本周待跟进": scalar("SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND date(next_follow_at) BETWEEN date(:today) AND date(:week)", {"today": today, "week": week}),
            "已逾期跟进": scalar("SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND next_follow_at IS NOT NULL AND date(next_follow_at)<date(:today)", {"today": today}),
            "待完成任务": scalar("SELECT COUNT(*) FROM v06_collab_tasks WHERE status NOT IN ('completed','cancelled')"),
            "逾期任务": scalar("SELECT COUNT(*) FROM v06_collab_tasks WHERE due_date IS NOT NULL AND date(due_date)<date(:today) AND status NOT IN ('completed','cancelled')", {"today": today}),
            "待召开会议": scalar("SELECT COUNT(*) FROM p5_opportunity_meetings WHERE status='scheduled' AND starts_at>=:today", {"today": today}),
            "谈判中机会": scalar("SELECT COUNT(*) FROM v06_opportunities WHERE stage='negotiating' AND status='active'"),
            "执行中机会": scalar("SELECT COUNT(*) FROM v06_opportunities WHERE stage='executing' AND status='active'"),
            "暂停机会": scalar("SELECT COUNT(*) FROM v06_opportunities WHERE stage='on_hold' AND status='active'"),
            "本月成交": scalar("SELECT COUNT(*) FROM p5_opportunity_stage_history WHERE new_stage='won' AND substr(created_at,1,7)=:month", {"month": month}),
            "本月关闭": scalar("SELECT COUNT(*) FROM p5_opportunity_stage_history WHERE new_stage='closed' AND substr(created_at,1,7)=:month", {"month": month}),
            "高风险机会": scalar("SELECT COUNT(DISTINCT opportunity_id) FROM p5_opportunity_risks WHERE status='open' AND risk_level='high'"),
            "无负责人机会": scalar("SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND owner_id IS NULL"),
            "无下一步行动机会": scalar("SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND (next_action IS NULL OR trim(next_action)='')"),
        }
        return {
            "schema_ready": True, "metrics": metrics,
            "queues": {
                "线索审核": "/collaboration/leads", "合作机会": "/opportunities",
                "任务": "/collaboration/tasks", "会议": "/collaboration/meetings",
                "风险提醒": "/collaboration/risks",
            },
            "generated_at": now_iso(),
        }

    def work_queue(self, kind: str, *, actor_user_id: int, is_admin: bool = False,
                   can_view_internal: bool = False, limit: int = 200) -> list[dict[str, Any]]:
        self.require_schema()
        queries = {
            "tasks": "SELECT * FROM v06_collab_tasks ORDER BY due_date,id DESC LIMIT :limit",
            "meetings": "SELECT * FROM p5_opportunity_meetings ORDER BY starts_at DESC,id DESC LIMIT :limit",
            "artifacts": "SELECT * FROM p5_opportunity_artifacts ORDER BY id DESC LIMIT :limit",
            "risks": "SELECT * FROM p5_opportunity_risks WHERE status='open' ORDER BY risk_level DESC,id DESC LIMIT :limit",
        }
        if kind not in queries:
            raise HTTPException(400, detail={"code": "INVALID_WORK_QUEUE", "message": "无效协作队列", "details": {}})
        rows = [dict(row) for row in self.db.execute(
            text(queries[kind]), {"limit": max(1, min(int(limit), 500))}
        ).mappings()]
        visible = [row for row in rows if self._can_access(
            int(row["opportunity_id"]), actor_user_id, is_admin=is_admin
        )]
        if kind == "artifacts" and not can_view_internal:
            visible = [row for row in visible if row.get("visibility") != "private"]
            for row in visible:
                row.pop("local_path", None)
        return visible
    def detail_bundle(self, opportunity_id: int, *, actor_user_id: int, is_admin: bool = False,
                      can_view_internal: bool = False) -> dict[str, Any]:
        self.require_schema()
        if not self._can_access(opportunity_id, actor_user_id, is_admin=is_admin):
            raise HTTPException(403, detail={"code": "OPPORTUNITY_FORBIDDEN", "message": "无权查看该合作机会", "details": {}})
        followups = [dict(row) for row in self.db.execute(text("SELECT * FROM v06_follow_ups WHERE opportunity_id=:opp ORDER BY followed_at DESC,id DESC"), {"opp": opportunity_id}).mappings()]
        if not can_view_internal:
            for row in followups:
                row.pop("internal_note", None)
        artifact_rows = [dict(row) for row in self.db.execute(text(
            "SELECT * FROM p5_opportunity_artifacts WHERE opportunity_id=:opp ORDER BY id DESC"
        ), {"opp": opportunity_id}).mappings()]
        if not can_view_internal:
            artifact_rows = [row for row in artifact_rows if row.get("visibility") != "private"]
            for row in artifact_rows:
                row.pop("local_path", None)
        return {
            "opportunity": self._opportunity_row(opportunity_id),
            "participants": self.participants(opportunity_id, actor_user_id=actor_user_id, is_admin=is_admin),
            "stage_history": [dict(row) for row in self.db.execute(text("SELECT * FROM p5_opportunity_stage_history WHERE opportunity_id=:opp ORDER BY id DESC"), {"opp": opportunity_id}).mappings()],
            "follow_ups": followups,
            "tasks": [self.task_detail(int(row[0])) for row in self.db.execute(text("SELECT id FROM v06_collab_tasks WHERE opportunity_id=:opp ORDER BY created_at DESC"), {"opp": opportunity_id})],
            "meetings": [dict(row) for row in self.db.execute(text("SELECT * FROM p5_opportunity_meetings WHERE opportunity_id=:opp ORDER BY starts_at DESC"), {"opp": opportunity_id}).mappings()],
            "artifacts": artifact_rows,
            "sources": [dict(row) for row in self.db.execute(text("SELECT * FROM p5_opportunity_sources WHERE opportunity_id=:opp ORDER BY id"), {"opp": opportunity_id}).mappings()],
            "risks": [dict(row) for row in self.db.execute(text("SELECT * FROM p5_opportunity_risks WHERE opportunity_id=:opp AND status='open' ORDER BY risk_level DESC,id"), {"opp": opportunity_id}).mappings()],
        }

    def domain_events(self, *, status: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
        self.require_schema()
        return [dict(row) for row in self.db.execute(text("""
            SELECT * FROM p5_domain_events WHERE status=:status ORDER BY id LIMIT :limit
        """), {"status": status, "limit": max(1, min(int(limit), 500))}).mappings()]
