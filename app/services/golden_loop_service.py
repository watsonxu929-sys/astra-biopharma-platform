from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session


WRITE_ROLES = {"operator", "reviewer", "admin"}
OUTCOMES = {"won", "lost", "paused"}
SUBJECT_TABLES = {
    "person": ("people", "name"),
    "organization": ("organizations", "standard_name"),
    "project": ("projects", "name"),
}


def _now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)


class GoldenLoopService:
    """Single canonical write path for the MVP-RC1 commercial loop."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def require_writer(role: str) -> None:
        if role not in WRITE_ROLES:
            raise HTTPException(
                status_code=403,
                detail={"code": "GOLDEN_LOOP_FORBIDDEN", "message": "当前账号仅可查看，不能执行闭环写操作"},
            )

    def _one(self, sql: str, params: dict[str, Any]) -> dict[str, Any] | None:
        row = self.db.execute(text(sql), params).mappings().first()
        return dict(row) if row else None

    def _many(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        return [dict(row) for row in self.db.execute(text(sql), params).mappings().all()]

    def _workflow_event(
        self,
        intelligence_id: int,
        *,
        action: str,
        actor_user_id: int,
        note: str,
    ) -> None:
        item = self._one(
            """
            SELECT source_record_id FROM v06_intelligence_items
            WHERE id=:id AND source_record_type='v05f_collection_items'
              AND source_record_id IS NOT NULL
            """,
            {"id": int(intelligence_id)},
        )
        if not item:
            return
        collection = self._one(
            "SELECT id FROM v05f_collection_items WHERE id=:id",
            {"id": int(item["source_record_id"])},
        )
        if not collection:
            return
        self.db.execute(
            text(
                """
                INSERT INTO core_intelligence_workflow_events(
                    intelligence_item_id,collection_item_id,action,from_status,to_status,
                    actor_user_id,actor_username,note,created_at
                ) VALUES (
                    :item_id,:collection_id,:action,'published','published',
                    :actor,:actor_username,:note,:created_at
                )
                """
            ),
            {
                "item_id": int(intelligence_id),
                "collection_id": int(collection["id"]),
                "action": action,
                "actor": int(actor_user_id),
                "actor_username": str(actor_user_id),
                "note": note,
                "created_at": _now(),
            },
        )

    def _published_intelligence(self, item_id: int) -> dict[str, Any]:
        row = self._one(
            "SELECT * FROM v06_intelligence_items WHERE id=:id AND status='published'",
            {"id": int(item_id)},
        )
        if not row:
            raise HTTPException(status_code=404, detail="已发布情报不存在")
        return row

    def _resource(self, resource_id: int) -> dict[str, Any]:
        row = self._one(
            """
            SELECT r.*,i.title AS intelligence_title,o.standard_name AS organization_name,
                   p.name AS owner_person_name,pr.name AS project_name
            FROM v06_market_resources r
            LEFT JOIN v06_intelligence_items i ON i.id=r.source_intelligence_id
            LEFT JOIN organizations o ON o.id=r.organization_id
            LEFT JOIN people p ON p.id=r.owner_person_id
            LEFT JOIN projects pr ON pr.id=r.project_id
            WHERE r.id=:id
            """,
            {"id": int(resource_id)},
        )
        if not row:
            raise HTTPException(status_code=404, detail="资源不存在")
        return row

    def _match(self, match_id: int) -> dict[str, Any]:
        row = self._one(
            "SELECT * FROM p4_resource_match_candidates WHERE id=:id",
            {"id": int(match_id)},
        )
        if not row:
            raise HTTPException(status_code=404, detail="匹配记录不存在")
        return row

    def _opportunity(self, opportunity_id: int) -> dict[str, Any]:
        row = self._one(
            """
            SELECT o.*,i.title AS intelligence_title,d.title AS demand_title,
                   s.title AS supply_title,m.match_no,
                   od.standard_name AS demand_organization_name,
                   os.standard_name AS supply_organization_name
            FROM v06_opportunities o
            LEFT JOIN v06_intelligence_items i ON i.id=o.source_intelligence_id
            LEFT JOIN v06_market_resources d ON d.id=o.source_demand_resource_id
            LEFT JOIN v06_market_resources s ON s.id=o.source_supply_resource_id
            LEFT JOIN p4_resource_match_candidates m ON m.id=o.source_match_id
            LEFT JOIN organizations od ON od.id=o.demand_organization_id
            LEFT JOIN organizations os ON os.id=o.supply_organization_id
            WHERE o.id=:id
            """,
            {"id": int(opportunity_id)},
        )
        if not row:
            raise HTTPException(status_code=404, detail="合作机会不存在")
        return row

    def can_manage_opportunity(self, opportunity: dict[str, Any], user_id: int, role: str) -> bool:
        if role == "admin":
            return True
        participants = {
            int(part.strip())
            for part in str(opportunity.get("participants") or "").replace(";", ",").split(",")
            if part.strip().isdigit()
        }
        return int(user_id) in {
            int(opportunity.get("initiator_id") or -1),
            int(opportunity.get("owner_id") or -1),
            *participants,
        }

    def link_subject(
        self,
        intelligence_id: int,
        *,
        subject_type: str,
        subject_id: int,
        actor_user_id: int,
    ) -> dict[str, Any]:
        self._published_intelligence(intelligence_id)
        if subject_type not in SUBJECT_TABLES:
            raise HTTPException(status_code=400, detail="主体类型必须是人物、机构或项目")
        table, label_column = SUBJECT_TABLES[subject_type]
        subject = self._one(
            f'SELECT id,"{label_column}" AS label FROM "{table}" WHERE id=:id',
            {"id": int(subject_id)},
        )
        if not subject:
            raise HTTPException(status_code=404, detail="关联主体不存在")
        now = _now()
        try:
            self.db.execute(
                text(
                    """
                    INSERT INTO core_intelligence_subject_links(
                        intelligence_item_id,subject_type,subject_id,created_by_user_id,created_at
                    ) VALUES (:item_id,:subject_type,:subject_id,:actor,:created_at)
                    ON CONFLICT(intelligence_item_id,subject_type,subject_id) DO NOTHING
                    """
                ),
                {
                    "item_id": int(intelligence_id),
                    "subject_type": subject_type,
                    "subject_id": int(subject_id),
                    "actor": int(actor_user_id),
                    "created_at": now,
                },
            )
            self._workflow_event(
                intelligence_id,
                action="subject_linked",
                actor_user_id=actor_user_id,
                note=f"{subject_type}:{subject_id}",
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return {
            "intelligence_item_id": int(intelligence_id),
            "subject_type": subject_type,
            "subject_id": int(subject_id),
            "subject_label": subject["label"],
        }

    def subjects(self, intelligence_id: int) -> list[dict[str, Any]]:
        rows = self._many(
            """
            SELECT * FROM core_intelligence_subject_links
            WHERE intelligence_item_id=:item_id ORDER BY subject_type,id
            """,
            {"item_id": int(intelligence_id)},
        )
        for row in rows:
            table, label_column = SUBJECT_TABLES[row["subject_type"]]
            subject = self._one(
                f'SELECT id,external_id,"{label_column}" AS label FROM "{table}" WHERE id=:id',
                {"id": int(row["subject_id"])},
            )
            row["subject_label"] = subject["label"] if subject else "主体已归档"
            if subject:
                row["subject_url"] = (
                    f"/network/people/{subject['id']}"
                    if row["subject_type"] == "person"
                    else f"/network/entities/{row['subject_type']}/{subject['external_id']}"
                )
        return rows

    def create_resource_from_intelligence(
        self,
        intelligence_id: int,
        *,
        direction: str,
        actor_user_id: int,
        fields: dict[str, Any],
    ) -> dict[str, Any]:
        item = self._published_intelligence(intelligence_id)
        if direction not in {"demand", "supply"}:
            raise HTTPException(status_code=400, detail="资源方向必须是需求或供给")
        subjects = self.subjects(intelligence_id)
        if not subjects:
            raise HTTPException(status_code=409, detail="请先为情报关联正式人物、机构或项目")
        prefix = "需求" if direction == "demand" else "供给"
        title = str(fields.get("title") or f"{prefix}｜{item['title']}").strip()
        existing = self._one(
            """
            SELECT * FROM v06_market_resources
            WHERE source_intelligence_id=:item_id AND direction=:direction
              AND title=:title AND status<>'archived'
            ORDER BY id LIMIT 1
            """,
            {"item_id": int(intelligence_id), "direction": direction, "title": title},
        )
        if existing:
            return existing
        organization_id = int(fields["organization_id"]) if fields.get("organization_id") else None
        owner_person_id = int(fields["owner_person_id"]) if fields.get("owner_person_id") else None
        project_id = int(fields["project_id"]) if fields.get("project_id") else None
        linked_subjects = {
            (str(subject["subject_type"]), int(subject["subject_id"])) for subject in subjects
        }
        for subject_type, subject_id in (
            ("organization", organization_id),
            ("person", owner_person_id),
            ("project", project_id),
        ):
            if subject_id and (subject_type, subject_id) not in linked_subjects:
                raise HTTPException(status_code=400, detail="资源主体必须先关联到来源情报")
        for subject in subjects:
            if subject["subject_type"] == "organization" and not organization_id:
                organization_id = subject["subject_id"]
            elif subject["subject_type"] == "person" and not owner_person_id:
                owner_person_id = subject["subject_id"]
            elif subject["subject_type"] == "project" and not project_id:
                project_id = subject["subject_id"]
        content_hash = item.get("evidence_hash") or hashlib.sha256(
            str(item.get("content") or item.get("summary") or item["title"]).encode("utf-8")
        ).hexdigest()
        now = _now()
        try:
            result = self.db.execute(
                text(
                    """
                    INSERT INTO v06_market_resources(
                        title,direction,resource_type,category,summary,description,publisher_id,
                        owner_person_id,organization_id,visibility,region,industry_direction,tags,
                        cooperation_mode,budget_note,contact_visibility,status,created_at,updated_at,
                        source_intelligence_id,project_id,source_intelligence_title,
                        source_content_hash,opportunity_type,cooperation_terms,confidentiality_level
                    ) VALUES (
                        :title,:direction,:resource_type,:category,:summary,:description,:publisher_id,
                        :owner_person_id,:organization_id,'organization',:region,:industry_direction,:tags,
                        :cooperation_mode,:budget_note,'connected','published',:created_at,:updated_at,
                        :source_intelligence_id,:project_id,:source_intelligence_title,
                        :source_content_hash,:opportunity_type,:cooperation_terms,'internal'
                    )
                    """
                ),
                {
                    "title": title,
                    "direction": direction,
                    "resource_type": str(fields.get("resource_type") or "产业合作"),
                    "category": str(fields.get("category") or fields.get("resource_type") or "产业合作"),
                    "summary": fields.get("summary") or item.get("summary"),
                    "description": fields.get("description") or item.get("content"),
                    "publisher_id": int(actor_user_id),
                    "owner_person_id": owner_person_id,
                    "organization_id": organization_id,
                    "region": fields.get("region") or item.get("region"),
                    "industry_direction": fields.get("industry_direction") or item.get("industry_directions"),
                    "tags": fields.get("tags") or item.get("tags"),
                    "cooperation_mode": fields.get("cooperation_mode"),
                    "budget_note": fields.get("budget_note"),
                    "created_at": now,
                    "updated_at": now,
                    "source_intelligence_id": int(intelligence_id),
                    "project_id": project_id,
                    "source_intelligence_title": item["title"],
                    "source_content_hash": content_hash,
                    "opportunity_type": fields.get("opportunity_type"),
                    "cooperation_terms": fields.get("cooperation_terms"),
                },
            )
            resource_id = int(result.lastrowid)
            self._workflow_event(
                intelligence_id,
                action="resource_created",
                actor_user_id=actor_user_id,
                note=f"{direction}:{resource_id}",
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._resource(resource_id)

    def confirm_match(
        self,
        *,
        demand_resource_id: int,
        supply_resource_id: int,
        actor_user_id: int,
        note: str = "",
    ) -> dict[str, Any]:
        demand = self._resource(demand_resource_id)
        supply = self._resource(supply_resource_id)
        if demand["direction"] != "demand" or supply["direction"] != "supply":
            raise HTTPException(status_code=409, detail="匹配双方必须分别为需求和供给")
        if demand["status"] != "published" or supply["status"] != "published":
            raise HTTPException(status_code=409, detail="只有已发布资源可以确认匹配")
        reasons: list[str] = []
        score = 40
        if demand.get("resource_type") == supply.get("resource_type"):
            score += 30
            reasons.append("资源类型一致")
        if demand.get("industry_direction") and demand.get("industry_direction") == supply.get("industry_direction"):
            score += 20
            reasons.append("产业方向一致")
        if demand.get("region") and demand.get("region") == supply.get("region"):
            score += 10
            reasons.append("区域一致")
        if not reasons:
            reasons.append("运营人员人工确认")
        now = _now()
        evidence = {
            "demand_resource_id": int(demand_resource_id),
            "supply_resource_id": int(supply_resource_id),
            "demand_source_intelligence_id": demand.get("source_intelligence_id"),
            "supply_source_intelligence_id": supply.get("source_intelligence_id"),
            "confirmed_by_user_id": int(actor_user_id),
        }
        try:
            self.db.execute(
                text(
                    """
                    INSERT INTO p4_resource_match_candidates(
                        match_no,demand_resource_id,supply_resource_id,score,reasons_json,
                        evidence_json,generation_method,status,reviewed_by,reviewed_at,review_note,
                        created_at,updated_at,explanation,created_by_user_id,
                        intention_status,intention_note,intention_by_user_id,intention_at
                    ) VALUES (
                        :match_no,:demand_id,:supply_id,:score,:reasons,:evidence,
                        'manual','accepted',:reviewed_by,:reviewed_at,:review_note,
                        :created_at,:updated_at,:explanation,:actor,
                        'interested',:review_note,:actor,:reviewed_at
                    )
                    ON CONFLICT(demand_resource_id,supply_resource_id) DO UPDATE SET
                        score=excluded.score,reasons_json=excluded.reasons_json,
                        evidence_json=excluded.evidence_json,status='accepted',
                        reviewed_by=excluded.reviewed_by,reviewed_at=excluded.reviewed_at,
                        review_note=excluded.review_note,updated_at=excluded.updated_at,
                        explanation=excluded.explanation,created_by_user_id=excluded.created_by_user_id,
                        intention_status='interested',intention_note=excluded.intention_note,
                        intention_by_user_id=excluded.intention_by_user_id,
                        intention_at=excluded.intention_at
                    """
                ),
                {
                    "match_no": f"RC1-MATCH-{uuid.uuid4().hex[:12].upper()}",
                    "demand_id": int(demand_resource_id),
                    "supply_id": int(supply_resource_id),
                    "score": min(score, 100),
                    "reasons": _json(reasons),
                    "evidence": _json(evidence),
                    "reviewed_by": str(actor_user_id),
                    "reviewed_at": now,
                    "review_note": note,
                    "created_at": now,
                    "updated_at": now,
                    "explanation": "；".join(reasons),
                    "actor": int(actor_user_id),
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._one(
            """
            SELECT * FROM p4_resource_match_candidates
            WHERE demand_resource_id=:demand_id AND supply_resource_id=:supply_id
            """,
            {"demand_id": int(demand_resource_id), "supply_id": int(supply_resource_id)},
        )

    def set_match_intention(
        self,
        match_id: int,
        *,
        actor_user_id: int,
        intention: str,
        reason_code: str = "",
        note: str = "",
    ) -> dict[str, Any]:
        if intention not in {"interested", "not_interested", "later"}:
            raise HTTPException(status_code=400, detail="匹配意向无效")
        match = self._match(match_id)
        if match.get("opportunity_id") and intention != "interested":
            raise HTTPException(status_code=409, detail="已转为机会的匹配不能再拒绝或暂缓")
        status = {
            "interested": "accepted",
            "not_interested": "rejected",
            "later": "reviewed",
        }[intention]
        now = _now()
        self.db.execute(
            text(
                """
                UPDATE p4_resource_match_candidates
                SET status=:status,intention_status=:intention,
                    intention_reason_code=:reason_code,intention_note=:note,
                    intention_by_user_id=:actor,intention_at=:now,
                    reviewed_by=:reviewed_by,reviewed_at=:now,updated_at=:now
                WHERE id=:id
                """
            ),
            {
                "status": status,
                "intention": intention,
                "reason_code": reason_code or None,
                "note": note or None,
                "actor": int(actor_user_id),
                "reviewed_by": str(actor_user_id),
                "now": now,
                "id": int(match_id),
            },
        )
        self.db.commit()
        return self._match(match_id)
    def match_detail(self, match_id: int) -> dict[str, Any]:
        match = self._match(match_id)
        match["demand"] = self._resource(int(match["demand_resource_id"]))
        match["supply"] = self._resource(int(match["supply_resource_id"]))
        match["opportunity"] = (
            self._opportunity(int(match["opportunity_id"])) if match.get("opportunity_id") else None
        )
        for key in ("reasons_json", "evidence_json", "unmet_conditions_json", "conflicts_json"):
            try:
                match[key.removesuffix("_json")] = json.loads(match.get(key) or "[]" if key != "evidence_json" else match.get(key) or "{}")
            except (TypeError, json.JSONDecodeError):
                match[key.removesuffix("_json")] = [] if key != "evidence_json" else {}
        if match.get("opportunity"):
            guidance = {"current_state": "已进入业务协同", "next_action": "登记跟进并明确下一时间"}
        elif match.get("status") == "accepted":
            guidance = {"current_state": "匹配已确认", "next_action": "转为合作机会"}
        elif match.get("status") in {"pending", "reviewed"}:
            guidance = {"current_state": "有候选匹配", "next_action": "确认、拒绝或暂缓匹配"}
        else:
            guidance = {"current_state": "匹配已处理", "next_action": "查看处理原因并保留记录"}
        match["guidance"] = guidance
        source_ids = {
            int(value)
            for value in (
                match["demand"].get("source_intelligence_id"),
                match["supply"].get("source_intelligence_id"),
            )
            if value
        }
        match["source_intelligence"] = [
            self._published_intelligence(item_id) for item_id in sorted(source_ids)
        ]
        return match

    def resource_trace(self, resource_id: int) -> dict[str, Any]:
        resource = self._resource(resource_id)
        matches = self._many(
            """
            SELECT m.*,d.title AS demand_title,s.title AS supply_title
            FROM p4_resource_match_candidates m
            JOIN v06_market_resources d ON d.id=m.demand_resource_id
            JOIN v06_market_resources s ON s.id=m.supply_resource_id
            WHERE m.demand_resource_id=:id OR m.supply_resource_id=:id
            ORDER BY m.id DESC
            """,
            {"id": int(resource_id)},
        )
        opportunities = self._many(
            """
            SELECT * FROM v06_opportunities
            WHERE source_demand_resource_id=:id OR source_supply_resource_id=:id
            ORDER BY id DESC
            """,
            {"id": int(resource_id)},
        )
        if opportunities:
            guidance = {"current_state": "已进入业务协同", "next_action": "查看机会并登记跟进"}
        elif any(item["status"] == "accepted" for item in matches):
            guidance = {"current_state": "匹配已确认", "next_action": "将匹配转为合作机会"}
        elif matches:
            guidance = {"current_state": "已有候选匹配", "next_action": "人工判断匹配意向"}
        else:
            guidance = {"current_state": "等待匹配", "next_action": "查找可合作的需求或供给"}
        return {"resource": resource, "matches": matches, "opportunities": opportunities, "guidance": guidance}

    def opportunity_trace(self, opportunity_id: int) -> dict[str, Any]:
        opportunity = self._opportunity(opportunity_id)
        if opportunity.get("outcome_status") == "won" and opportunity.get("result_relationship_id"):
            guidance = {"current_state": "已达成并形成正式关系", "next_action": "查看合作关系与证据"}
        elif opportunity.get("outcome_status") == "won":
            guidance = {"current_state": "已达成，待补合作证据", "next_action": "补充证据并形成正式关系"}
        elif opportunity.get("outcome_status") == "lost":
            guidance = {"current_state": "未成交", "next_action": "查看原因并保留历史记录"}
        elif opportunity.get("outcome_status") == "paused":
            guidance = {"current_state": "已暂停", "next_action": "条件明确后恢复推进"}
        elif opportunity.get("next_follow_at") and str(opportunity["next_follow_at"])[:10] <= datetime.now().date().isoformat():
            guidance = {"current_state": "已到跟进时间", "next_action": "完成本次跟进并设置下一时间"}
        else:
            guidance = {"current_state": "跟进中", "next_action": "登记跟进并明确下一动作"}
        return {"opportunity": opportunity, "guidance": guidance}

    def convert_match_to_opportunity(self, match_id: int, *, actor_user_id: int) -> dict[str, Any]:
        match = self.match_detail(match_id)
        if match["status"] not in {"accepted", "introduced", "converted_to_lead"}:
            raise HTTPException(status_code=409, detail="只有已确认匹配可以转为合作机会")
        if match.get("opportunity"):
            return match["opportunity"]
        demand = match["demand"]
        supply = match["supply"]
        existing = self._one(
            "SELECT * FROM v06_opportunities WHERE source_match_id=:match_id LIMIT 1",
            {"match_id": int(match_id)},
        )
        if existing:
            self.db.execute(
                text("UPDATE p4_resource_match_candidates SET opportunity_id=:opp_id,status='converted_to_lead',updated_at=:now WHERE id=:id"),
                {"opp_id": existing["id"], "now": _now(), "id": int(match_id)},
            )
            self.db.commit()
            return existing
        now = _now()
        source_intelligence_id = demand.get("source_intelligence_id") or supply.get("source_intelligence_id")
        try:
            result = self.db.execute(
                text(
                    """
                    INSERT INTO v06_opportunities(
                        title,opp_type,source_type,source_id,initiator_id,organization_id,
                        demand_organization_id,supply_organization_id,related_resource_id,
                        description,expected_outcome,priority,next_action,stage,owner_id,status,
                        visibility,human_confirmed_by,human_confirmed_at,created_at,updated_at,
                        source_intelligence_id,source_demand_resource_id,
                        source_supply_resource_id,source_match_id
                    ) VALUES (
                        :title,'resource_match','resource_match',:source_id,:actor,:organization_id,
                        :demand_org,:supply_org,:related_resource_id,
                        :description,'推动供需双方形成可核验合作','P1','登记首次商务跟进',
                        'lead',:actor,'active','organization',:actor,:now,:now,:now,
                        :source_intelligence_id,:demand_id,:supply_id,:source_match_id
                    )
                    """
                ),
                {
                    "title": f"合作机会｜{demand['title']} × {supply['title']}",
                    "source_id": int(match_id),
                    "actor": int(actor_user_id),
                    "organization_id": demand.get("organization_id"),
                    "demand_org": demand.get("organization_id"),
                    "supply_org": supply.get("organization_id"),
                    "related_resource_id": int(demand["id"]),
                    "description": match.get("explanation") or "运营人员确认的供需匹配",
                    "now": now,
                    "source_intelligence_id": source_intelligence_id,
                    "demand_id": int(demand["id"]),
                    "supply_id": int(supply["id"]),
                    "source_match_id": int(match_id),
                },
            )
            opportunity_id = int(result.lastrowid)
            self.db.execute(
                text(
                    """
                    UPDATE p4_resource_match_candidates
                    SET opportunity_id=:opportunity_id,status='converted_to_lead',updated_at=:now
                    WHERE id=:match_id
                    """
                ),
                {"opportunity_id": opportunity_id, "now": now, "match_id": int(match_id)},
            )
            self.db.execute(
                text(
                    """
                    INSERT INTO v06_timeline_entries(
                        opportunity_id,event_type,description,actor_id,metadata_json,created_at
                    ) VALUES (:opportunity_id,'created','由已确认供需匹配转化',:actor,:metadata,:now)
                    """
                ),
                {
                    "opportunity_id": opportunity_id,
                    "actor": int(actor_user_id),
                    "metadata": _json({"source_match_id": int(match_id)}),
                    "now": now,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._opportunity(opportunity_id)

    def add_follow_up(
        self,
        opportunity_id: int,
        *,
        actor_user_id: int,
        content: str,
        next_action: str = "",
        contact_result: str = "",
        stage_after: str = "",
        next_follow_at: str = "",
    ) -> dict[str, Any]:
        opportunity = self._opportunity(opportunity_id)
        content = str(content).strip()
        if not content:
            raise HTTPException(status_code=400, detail="跟进内容不能为空")
        now = _now()
        try:
            result = self.db.execute(
                text(
                    """
                    INSERT INTO v06_follow_ups(
                        opportunity_id,follow_type,content,created_by,followed_at,next_follow_at,visibility,
                        created_at,next_action,contact_result,stage_after
                    ) VALUES (
                        :opportunity_id,'note',:content,:actor,:now,:next_follow_at,'organization',
                        :now,:next_action,:contact_result,:stage_after
                    )
                    """
                ),
                {
                    "opportunity_id": int(opportunity_id),
                    "content": content,
                    "actor": int(actor_user_id),
                    "now": now,
                    "next_action": next_action or None,
                    "contact_result": contact_result or None,
                    "stage_after": stage_after or None,
                    "next_follow_at": next_follow_at or None,
                },
            )
            follow_up_id = int(result.lastrowid)
            self.db.execute(
                text(
                    """
                    UPDATE v06_opportunities
                    SET next_action=COALESCE(:next_action,next_action),
                        next_follow_at=COALESCE(:next_follow_at,next_follow_at),
                        stage=COALESCE(:stage_after,stage),updated_at=:now
                    WHERE id=:opportunity_id
                    """
                ),
                {
                    "next_action": next_action or None,
                    "stage_after": stage_after or None,
                    "next_follow_at": next_follow_at or None,
                    "now": now,
                    "opportunity_id": int(opportunity_id),
                },
            )
            self.db.execute(
                text(
                    """
                    INSERT INTO v06_timeline_entries(
                        opportunity_id,event_type,description,actor_id,metadata_json,created_at
                    ) VALUES (:opportunity_id,'follow_up',:description,:actor,'{}',:now)
                    """
                ),
                {
                    "opportunity_id": int(opportunity_id),
                    "description": content[:200],
                    "actor": int(actor_user_id),
                    "now": now,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        return self._one(
            "SELECT * FROM v06_follow_ups WHERE id=:id",
            {"id": follow_up_id},
        )

    def create_task(
        self,
        opportunity_id: int,
        *,
        actor_user_id: int,
        title: str,
        due_date: str = "",
        priority: str = "P2",
    ) -> dict[str, Any]:
        self._opportunity(opportunity_id)
        title = title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="任务标题不能为空")
        now = _now()
        result = self.db.execute(
            text(
                """
                INSERT INTO v06_collab_tasks(
                    title,opportunity_id,owner_id,due_date,priority,status,
                    created_by,created_at,updated_at
                ) VALUES (
                    :title,:opportunity_id,:actor,:due_date,:priority,'todo',
                    :actor,:now,:now
                )
                """
            ),
            {
                "title": title,
                "opportunity_id": int(opportunity_id),
                "actor": int(actor_user_id),
                "due_date": due_date or None,
                "priority": priority if priority in {"P0", "P1", "P2", "P3"} else "P2",
                "now": now,
            },
        )
        task_id = int(result.lastrowid)
        self.db.execute(
            text(
                """
                INSERT INTO v06_timeline_entries(
                    opportunity_id,event_type,description,actor_id,metadata_json,created_at
                ) VALUES (:opportunity_id,'task',:description,:actor,:metadata,:now)
                """
            ),
            {
                "opportunity_id": int(opportunity_id),
                "description": f"Task created: {title}",
                "actor": int(actor_user_id),
                "metadata": _json({"task_id": task_id}),
                "now": now,
            },
        )
        self.db.commit()
        return self._one("SELECT * FROM v06_collab_tasks WHERE id=:id", {"id": task_id})

    def _cooperation_relationship(
        self,
        opportunity: dict[str, Any],
        *,
        actor_user_id: int,
        evidence_text: str,
    ) -> int | None:
        demand_org = opportunity.get("demand_organization_id")
        supply_org = opportunity.get("supply_organization_id")
        if not evidence_text.strip() or not demand_org or not supply_org or int(demand_org) == int(supply_org):
            return None
        demand = self._one(
            "SELECT external_id FROM organizations WHERE id=:id", {"id": int(demand_org)}
        )
        supply = self._one(
            "SELECT external_id FROM organizations WHERE id=:id", {"id": int(supply_org)}
        )
        if not demand or not supply:
            return None
        demand_ref = str(demand["external_id"])
        supply_ref = str(supply["external_id"])
        existing = self._one(
            """
            SELECT * FROM p3_canonical_relationships
            WHERE relationship_type='cooperates_with' AND review_status='approved'
              AND is_current=1
              AND ((subject_type='organization' AND subject_id IN (:demand_ref,:demand_legacy)
                    AND object_type='organization' AND object_id IN (:supply_ref,:supply_legacy))
                OR (subject_type='organization' AND subject_id IN (:supply_ref,:supply_legacy)
                    AND object_type='organization' AND object_id IN (:demand_ref,:demand_legacy)))
            ORDER BY CASE WHEN source_opportunity_id=:opportunity_id THEN 0 ELSE 1 END,id
            LIMIT 1
            """,
            {
                "demand_ref": demand_ref,
                "supply_ref": supply_ref,
                "demand_legacy": str(demand_org),
                "supply_legacy": str(supply_org),
                "opportunity_id": int(opportunity["id"]),
            },
        )
        now = _now()
        source_intelligence_id = opportunity.get("source_intelligence_id")
        source_match_id = opportunity.get("source_match_id")
        if existing:
            relationship_id = int(existing["id"])
            self.db.execute(
                text(
                    """
                    UPDATE p3_canonical_relationships
                    SET source_opportunity_id=COALESCE(source_opportunity_id,:opportunity_id),
                        source_match_id=COALESCE(source_match_id,:source_match_id),
                        source_intelligence_id=COALESCE(source_intelligence_id,:source_intelligence_id),
                        confidence=100,confidence_level='confirmed',
                        evidence_status='evidence_backed',updated_at=:now
                    WHERE id=:id
                    """
                ),
                {
                    "opportunity_id": int(opportunity["id"]),
                    "source_match_id": source_match_id,
                    "source_intelligence_id": source_intelligence_id,
                    "now": now,
                    "id": relationship_id,
                },
            )
        else:
            result = self.db.execute(
                text(
                    """
                    INSERT INTO p3_canonical_relationships(
                        relationship_no,subject_type,subject_id,relationship_type,
                        object_type,object_id,direction,is_current,confidence,review_status,
                        evidence_status,source_count,visibility,created_by,reviewed_by,
                        reviewed_at,review_note,created_at,updated_at,source_opportunity_id,
                        source_match_id,source_intelligence_id,confidence_level
                    ) VALUES (
                        :relationship_no,'organization',:demand_org,'cooperates_with',
                        'organization',:supply_org,'symmetric',1,100,'approved',
                        'evidence_backed',1,'internal',:actor,:actor,:now,
                        'MVP-RC1 商务结果人工确认',:now,:now,:opportunity_id,
                        :source_match_id,:source_intelligence_id,'confirmed'
                    )
                    """
                ),
                {
                    "relationship_no": f"RC1-REL-{uuid.uuid4().hex[:12].upper()}",
                    "demand_org": demand_ref,
                    "supply_org": supply_ref,
                    "actor": str(actor_user_id),
                    "now": now,
                    "opportunity_id": int(opportunity["id"]),
                    "source_match_id": source_match_id,
                    "source_intelligence_id": source_intelligence_id,
                },
            )
            relationship_id = int(result.lastrowid)
        evidence_hash = hashlib.sha256(
            f"rc1|{relationship_id}|{opportunity['id']}|{evidence_text.strip()}".encode("utf-8")
        ).hexdigest()
        source = (
            self._one(
                "SELECT source_url FROM v06_intelligence_items WHERE id=:id",
                {"id": int(source_intelligence_id)},
            )
            if source_intelligence_id
            else None
        )
        self.db.execute(
            text(
                """
                INSERT OR IGNORE INTO p3_relationship_evidence(
                    relationship_id,evidence_text,locator_json,source_url,
                    evidence_strength,evidence_hash,created_at
                ) VALUES (:relationship_id,:evidence_text,:locator_json,:source_url,
                          'authoritative',:evidence_hash,:created_at)
                """
            ),
            {
                "relationship_id": relationship_id,
                "evidence_text": evidence_text.strip(),
                "locator_json": _json(
                    {
                        "source_opportunity_id": int(opportunity["id"]),
                        "source_match_id": source_match_id,
                        "source_intelligence_id": source_intelligence_id,
                    }
                ),
                "source_url": source.get("source_url") if source else None,
                "evidence_hash": evidence_hash,
                "created_at": now,
            },
        )
        return relationship_id

    def close_outcome(
        self,
        opportunity_id: int,
        *,
        actor_user_id: int,
        outcome: str,
        reason: str = "",
        result_note: str = "",
        cooperation_scale: str = "",
        evidence_text: str = "",
    ) -> dict[str, Any]:
        if outcome not in OUTCOMES:
            raise HTTPException(status_code=400, detail="结果必须是达成、未成交或暂停")
        opportunity = self._opportunity(opportunity_id)
        if opportunity.get("outcome_status") == "won" and outcome != "won":
            raise HTTPException(status_code=409, detail="已形成正式合作关系的机会不能改为失败或暂停")
        now = _now()
        relationship_id = opportunity.get("result_relationship_id")
        try:
            if outcome == "won":
                relationship_id = self._cooperation_relationship(
                    opportunity,
                    actor_user_id=int(actor_user_id),
                    evidence_text=evidence_text,
                )
                stage, status, closed_at = "won", "closed", now
                final_result = "合作达成"
            elif outcome == "lost":
                relationship_id = None
                stage, status, closed_at = "lost", "closed", now
                final_result = "未成交"
            else:
                relationship_id = None
                stage, status, closed_at = "paused", "active", None
                final_result = "暂停"
            self.db.execute(
                text(
                    """
                    UPDATE v06_opportunities
                    SET stage=:stage,status=:status,outcome_status=:outcome,
                        final_result=:final_result,closed_reason=:reason,
                        final_result_note=:result_note,
                        final_cooperation_scale=:cooperation_scale,
                        closed_by_user_id=:actor,closed_at=:closed_at,
                        result_relationship_id=:relationship_id,updated_at=:now
                    WHERE id=:id
                    """
                ),
                {
                    "stage": stage,
                    "status": status,
                    "outcome": outcome,
                    "final_result": final_result,
                    "reason": reason or None,
                    "result_note": result_note or None,
                    "cooperation_scale": cooperation_scale or None,
                    "actor": int(actor_user_id),
                    "closed_at": closed_at,
                    "relationship_id": relationship_id,
                    "now": now,
                    "id": int(opportunity_id),
                },
            )
            self.db.execute(
                text(
                    """
                    INSERT INTO v06_timeline_entries(
                        opportunity_id,event_type,description,actor_id,metadata_json,created_at
                    ) VALUES (:opportunity_id,'outcome',:description,:actor,:metadata,:now)
                    """
                ),
                {
                    "opportunity_id": int(opportunity_id),
                    "description": final_result,
                    "actor": int(actor_user_id),
                    "metadata": _json(
                        {
                            "outcome": outcome,
                            "reason": reason,
                            "relationship_id": relationship_id,
                        }
                    ),
                    "now": now,
                },
            )
            self.db.commit()
        except Exception:
            self.db.rollback()
            raise
        result = self._opportunity(opportunity_id)
        result["relationship_created"] = bool(relationship_id)
        return result

    def trace(self, intelligence_id: int) -> dict[str, Any]:
        item = self._published_intelligence(intelligence_id)
        resources = self._many(
            """
            SELECT * FROM v06_market_resources
            WHERE source_intelligence_id=:item_id ORDER BY id
            """,
            {"item_id": int(intelligence_id)},
        )
        resources = [self._resource(int(row["id"])) for row in resources]
        resource_ids = [int(row["id"]) for row in resources]
        if resource_ids:
            marks = ",".join(str(value) for value in resource_ids)
            matches = self._many(
                f"""
                SELECT * FROM p4_resource_match_candidates
                WHERE demand_resource_id IN ({marks}) OR supply_resource_id IN ({marks})
                ORDER BY id
                """,
                {},
            )
        else:
            matches = []
        match_ids = [int(row["id"]) for row in matches]
        opportunities = self._many(
            """
            SELECT * FROM v06_opportunities
            WHERE source_intelligence_id=:item_id ORDER BY id
            """,
            {"item_id": int(intelligence_id)},
        )
        opportunities = [self._opportunity(int(row["id"])) for row in opportunities]
        opportunity_ids = [int(row["id"]) for row in opportunities]
        if opportunity_ids:
            marks = ",".join(str(value) for value in opportunity_ids)
            follow_ups = self._many(
                f"SELECT * FROM v06_follow_ups WHERE opportunity_id IN ({marks}) ORDER BY id",
                {},
            )
            relationships = self._many(
                f"""
                SELECT * FROM p3_canonical_relationships
                WHERE source_opportunity_id IN ({marks})
                   OR source_intelligence_id=:item_id
                ORDER BY id
                """,
                {"item_id": int(intelligence_id)},
            )
        else:
            follow_ups = []
            relationships = self._many(
                """
                SELECT * FROM p3_canonical_relationships
                WHERE source_intelligence_id=:item_id ORDER BY id
                """,
                {"item_id": int(intelligence_id)},
            )
        subjects = self.subjects(intelligence_id)
        if not subjects:
            guidance = {"current_state": "待关联主体", "next_action": "关联企业、人物或项目"}
        elif not resources:
            guidance = {"current_state": "待判断是否形成资源", "next_action": "判断并登记需求或供给"}
        elif not matches:
            guidance = {"current_state": "已形成资源", "next_action": "查找并确认供需匹配"}
        else:
            guidance = {"current_state": "闭环推进中", "next_action": "查看匹配或合作机会"}
        return {
            "intelligence": item,
            "subjects": subjects,
            "resources": resources,
            "matches": matches,
            "match_ids": match_ids,
            "opportunities": opportunities,
            "follow_ups": follow_ups,
            "relationships": relationships,
            "guidance": guidance,
        }

    def workbench(self) -> dict[str, Any]:
        def count(sql: str) -> int:
            return int(self.db.execute(text(sql)).scalar() or 0)

        return {
            "home_metrics": {
                "today_intelligence": count("SELECT COUNT(*) FROM v06_intelligence_items WHERE status='published' AND date(COALESCE(published_at,created_at))=date('now','localtime')"),
                "pending_subjects": count("SELECT COUNT(*) FROM v06_intelligence_items i WHERE i.status='published' AND NOT EXISTS (SELECT 1 FROM core_intelligence_subject_links l WHERE l.intelligence_item_id=i.id)"),
                "pending_judgement": count("SELECT COUNT(*) FROM v06_intelligence_items i WHERE i.status='published' AND EXISTS (SELECT 1 FROM core_intelligence_subject_links l WHERE l.intelligence_item_id=i.id) AND NOT EXISTS (SELECT 1 FROM v06_market_resources r WHERE r.source_intelligence_id=i.id AND r.status<>'archived')"),
                "active_resources": count("SELECT COUNT(*) FROM v06_market_resources WHERE status='published'"),
                "active_demands": count("SELECT COUNT(*) FROM v06_market_resources WHERE status='published' AND direction='demand' AND (valid_until IS NULL OR date(valid_until)>=date('now','localtime'))"),
                "active_supplies": count("SELECT COUNT(*) FROM v06_market_resources WHERE status='published' AND direction='supply' AND (valid_until IS NULL OR date(valid_until)>=date('now','localtime'))"),
                "pending_matches": count("SELECT COUNT(*) FROM p4_resource_match_candidates WHERE status IN ('pending','reviewed')"),
                "active_opportunities": count("SELECT COUNT(*) FROM v06_opportunities WHERE status='active'"),
                "today_followups": count("SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND next_follow_at IS NOT NULL AND date(next_follow_at)=date('now','localtime')"),
                "overdue_followups": count("SELECT COUNT(*) FROM v06_opportunities WHERE status='active' AND next_follow_at IS NOT NULL AND date(next_follow_at)<date('now','localtime')"),
                "won_this_month": count("SELECT COUNT(*) FROM v06_opportunities WHERE outcome_status='won' AND strftime('%Y-%m',closed_at)=strftime('%Y-%m','now')"),
                "recent_relationships": count("SELECT COUNT(*) FROM p3_canonical_relationships WHERE review_status='approved' AND date(created_at)>=date('now','-30 days')"),
            },
            "counts": {
                "published_intelligence": count("SELECT COUNT(*) FROM v06_intelligence_items WHERE status='published'"),
                "linked_intelligence": count("SELECT COUNT(DISTINCT intelligence_item_id) FROM core_intelligence_subject_links"),
                "open_resources": count("SELECT COUNT(*) FROM v06_market_resources WHERE status='published'"),
                "confirmed_matches": count("SELECT COUNT(*) FROM p4_resource_match_candidates WHERE status IN ('accepted','introduced','converted_to_lead')"),
                "active_opportunities": count("SELECT COUNT(*) FROM v06_opportunities WHERE status='active'"),
                "won": count("SELECT COUNT(*) FROM v06_opportunities WHERE outcome_status='won'"),
                "lost": count("SELECT COUNT(*) FROM v06_opportunities WHERE outcome_status='lost'"),
                "cooperation_relationships": count("SELECT COUNT(*) FROM p3_canonical_relationships WHERE relationship_type='cooperates_with' AND review_status='approved'"),
            },
            "intelligence": self._many(
                """
                SELECT i.id,i.title,i.published_at,
                       COUNT(DISTINCT l.id) AS subject_count,
                       COUNT(DISTINCT r.id) AS resource_count
                FROM v06_intelligence_items i
                LEFT JOIN core_intelligence_subject_links l ON l.intelligence_item_id=i.id
                LEFT JOIN v06_market_resources r ON r.source_intelligence_id=i.id
                WHERE i.status='published'
                GROUP BY i.id ORDER BY i.id DESC LIMIT 12
                """,
                {},
            ),
            "matches": self._many(
                """
                SELECT m.*,d.title AS demand_title,s.title AS supply_title
                FROM p4_resource_match_candidates m
                JOIN v06_market_resources d ON d.id=m.demand_resource_id
                JOIN v06_market_resources s ON s.id=m.supply_resource_id
                ORDER BY m.id DESC LIMIT 12
                """,
                {},
            ),
            "opportunities": self._many(
                """
                SELECT id,title,stage,status,outcome_status,result_relationship_id,updated_at
                FROM v06_opportunities ORDER BY id DESC LIMIT 12
                """,
                {},
            ),
        }
