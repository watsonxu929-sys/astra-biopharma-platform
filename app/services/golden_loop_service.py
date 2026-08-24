from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.canonical_relationship_service import CanonicalRelationshipService
from app.services.intelligence_product_service import EVENT_PROFILES
from app.services.unified_opportunity_service import UnifiedOpportunityService
from app.services.unified_resource_service import UnifiedResourceService


WRITE_ROLES = {"operator", "reviewer", "admin"}
OUTCOMES = {"won", "lost", "paused"}
SUBJECT_TABLES = {
    "person": ("people", "name"),
    "organization": ("organizations", "standard_name"),
    "project": ("projects", "name"),
}
EVENT_ACTIONS = {
    "approval": ["查看获批主体", "核对产品与适应症", "判断是否形成资源需求"],
    "clinical": ["查看研发主体", "核对临床阶段", "持续关注后续节点"],
    "financing": ["查看融资企业", "核对投资机构", "建立持续关注"],
    "merger": ["查看交易双方", "核对关系与资产变化", "判断合作窗口"],
    "cooperation": ["查看合作双方", "核对合作证据", "判断是否创建合作机会"],
    "product_launch": ["查看产品主体", "判断渠道或服务需求", "必要时创建资源"],
    "tech_progress": ["查看研发主体", "核对技术证据", "持续关注产业化进度"],
    "policy": ["查看适用主体", "核对政策范围", "判断区域或合规影响"],
    "corporate": ["查看企业档案", "判断是否需要持续关注"],
    "conference": ["查看涉及主体", "判断是否形成活动或合作线索"],
    "recruitment": ["查看相关人物", "关联任职企业", "核对是否形成正式关系证据"],
    "expansion": ["查看扩张主体", "检查空间与产业服务需求", "必要时创建资源"],
    "other": ["查看公开来源", "人工判断涉及主体与业务价值"],
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
            SELECT source_record_type,source_record_id FROM v06_intelligence_items
            WHERE id=:id
            """,
            {"id": int(intelligence_id)},
        )
        if not item:
            return
        collection_id = None
        if item.get("source_record_type") == "v05f_collection_items" and item.get("source_record_id"):
            collection_id = int(item["source_record_id"])
        elif item.get("source_record_type") == "fact_candidate" and item.get("source_record_id"):
            row = self._one(
                "SELECT collection_item_id FROM v05g_extraction_candidates WHERE id=:id",
                {"id": int(item["source_record_id"])},
            )
            collection_id = int(row["collection_item_id"]) if row and row.get("collection_item_id") else None
        if not collection_id:
            row = self._one(
                """
                SELECT c.collection_item_id FROM p2_intelligence_product_candidates pc
                JOIN v05g_extraction_candidates c ON c.id=pc.candidate_id
                WHERE pc.product_id=:id AND c.collection_item_id IS NOT NULL
                ORDER BY c.id LIMIT 1
                """,
                {"id": int(intelligence_id)},
            )
            collection_id = int(row["collection_item_id"]) if row else None
        if not collection_id:
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
                "collection_id": collection_id,
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

    def event_insight(self, intelligence_id: int) -> dict[str, Any]:
        item = self._published_intelligence(intelligence_id)
        event_type = str(item.get("event_type") or "").strip().lower()
        if event_type not in EVENT_PROFILES:
            label_to_code = {profile[0]: code for code, profile in EVENT_PROFILES.items()}
            event_type = label_to_code.get(str(item.get("intel_type") or "").strip(), "other")
        label, default_importance, reason = EVENT_PROFILES.get(
            event_type,
            ("其他", 1, "规则未识别出明确事件类型，需要人工结合公开证据判断。"),
        )
        importance = max(1, min(5, int(item.get("importance") or default_importance)))
        return {
            "event_type": event_type,
            "event_label": label,
            "importance": importance,
            "importance_reason": reason,
            "actions": EVENT_ACTIONS.get(event_type, EVENT_ACTIONS["other"]),
        }

    def subject_candidates(self, intelligence_id: int) -> list[dict[str, Any]]:
        self._published_intelligence(intelligence_id)
        matched = self._many(
            """
            SELECT sm.candidate_subject_type AS subject_type,
                   sm.matched_subject_id AS external_id,
                   sm.matched_subject_label AS extracted_label,
                   sm.match_method,sm.match_score
            FROM p2_intelligence_product_candidates pc
            JOIN v05g_extraction_candidates origin ON origin.id=pc.candidate_id
            JOIN v05g_extraction_candidates c
              ON c.collection_item_id=origin.collection_item_id
             AND c.candidate_type IN ('organization','person')
            JOIN v05g_subject_match_candidates sm ON sm.extraction_candidate_id=c.id
            WHERE pc.product_id=:item_id
              AND sm.matched_subject_id IS NOT NULL
              AND sm.status IN ('confirmed','candidate','ambiguous')
            ORDER BY sm.match_score DESC,sm.id
            """,
            {"item_id": int(intelligence_id)},
        )
        matched.extend(
            self._many(
                """
                SELECT ci.subject_type_candidate AS subject_type,
                       ci.subject_id_candidate AS external_id,
                       s.name AS extracted_label,
                       'source_registry' AS match_method,100 AS match_score
                FROM p2_intelligence_product_candidates pc
                JOIN v05g_extraction_candidates origin ON origin.id=pc.candidate_id
                JOIN v05f_collection_items ci ON ci.id=origin.collection_item_id
                LEFT JOIN v04g_monitoring_sources s ON s.id=ci.monitoring_source_id
                WHERE pc.product_id=:item_id
                  AND ci.subject_type_candidate IN ('organization','person')
                  AND ci.subject_id_candidate IS NOT NULL
                """,
                {"item_id": int(intelligence_id)},
            )
        )
        linked = {
            (str(row["subject_type"]), int(row["subject_id"]))
            for row in self._many(
                "SELECT subject_type,subject_id FROM core_intelligence_subject_links WHERE intelligence_item_id=:id",
                {"id": int(intelligence_id)},
            )
        }
        ignored = {
            str(row["note"] or "")
            for row in self._many(
                "SELECT note FROM core_intelligence_workflow_events WHERE intelligence_item_id=:id AND action='subject_candidate_ignored'",
                {"id": int(intelligence_id)},
            )
        }
        candidates: list[dict[str, Any]] = []
        seen: set[tuple[str, int]] = set()
        for row in matched:
            subject_type = str(row.get("subject_type") or "")
            config = SUBJECT_TABLES.get(subject_type)
            if not config:
                continue
            table, label_column = config
            subject = self._one(
                f'SELECT id,"{label_column}" AS label FROM "{table}" WHERE external_id=:external_id AND COALESCE(is_active,1)=1',
                {"external_id": row.get("external_id")},
            )
            if not subject:
                continue
            key = (subject_type, int(subject["id"]))
            marker = f"{subject_type}:{subject['id']}"
            if key in seen or key in linked or marker in ignored:
                continue
            seen.add(key)
            score = max(0, min(100, int(row.get("match_score") or 0)))
            candidates.append(
                {
                    "subject_type": subject_type,
                    "subject_id": int(subject["id"]),
                    "subject_label": subject["label"],
                    "confidence": "高" if score >= 85 else "中",
                    "score": score,
                    "reason": "名称与现有正式主体精确一致" if score >= 85 else "名称包含关系或存在同名，需要人工确认",
                }
            )
        return candidates[:8]

    def ignore_subject_candidate(
        self, intelligence_id: int, *, subject_type: str, subject_id: int, actor_user_id: int
    ) -> None:
        self._published_intelligence(intelligence_id)
        if subject_type not in SUBJECT_TABLES:
            raise HTTPException(status_code=400, detail="主体类型无效")
        self._workflow_event(
            intelligence_id,
            action="subject_candidate_ignored",
            actor_user_id=actor_user_id,
            note=f"{subject_type}:{int(subject_id)}",
        )
        self.db.commit()

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
        try:
            resource = UnifiedResourceService(self.db).create(actor_user_id=actor_user_id, commit=False, fields={
                **fields, "title": title, "direction": direction, "resource_type": str(fields.get("resource_type") or "产业合作"),
                "category": str(fields.get("category") or fields.get("resource_type") or "产业合作"),
                "summary": fields.get("summary") or item.get("summary"), "description": fields.get("description") or item.get("content"),
                "owner_person_id": owner_person_id, "organization_id": organization_id,
                "region": fields.get("region") or item.get("region"),
                "industry_direction": fields.get("industry_direction") or item.get("industry_directions"),
                "tags": fields.get("tags") or item.get("tags"), "status": "published", "visibility": "organization",
                "source_intelligence_id": int(intelligence_id), "project_id": project_id,
                "source_intelligence_title": item["title"], "source_content_hash": content_hash,
                "confidentiality_level": "internal",
            })
            resource_id = int(resource.id)
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

    def persist_match_candidate(self, fields: dict[str, Any], *, commit: bool = True) -> dict[str, Any]:
        now = _now()
        existing = self._one("SELECT * FROM p4_resource_match_candidates WHERE demand_resource_id=:demand AND supply_resource_id=:supply",
                             {"demand": int(fields["demand_resource_id"]), "supply": int(fields["supply_resource_id"])})
        if existing:
            return existing
        result = self.db.execute(text("""INSERT INTO p4_resource_match_candidates(
            match_no,demand_resource_id,supply_resource_id,recommended_person_id,recommended_organization_id,score,
            reasons_json,relationship_path_json,common_contacts_json,risks_json,evidence_json,generation_method,status,
            pilot_batch_id,created_at,updated_at) VALUES (:match_no,:demand,:supply,:person,:organization,:score,:reasons,
            :paths,:contacts,:risks,:evidence,:method,:status,:pilot,:now,:now)"""), {
            "match_no": fields.get("match_no") or f"MATCH-{uuid.uuid4().hex[:12].upper()}",
            "demand": int(fields["demand_resource_id"]), "supply": int(fields["supply_resource_id"]),
            "person": fields.get("recommended_person_id"), "organization": fields.get("recommended_organization_id"),
            "score": int(fields.get("score") or 0), "reasons": _json(fields.get("reasons") or []),
            "paths": _json(fields.get("relationship_paths") or []), "contacts": _json(fields.get("common_contacts") or []),
            "risks": _json(fields.get("risks") or []), "evidence": _json(fields.get("evidence") or []),
            "method": fields.get("generation_method") or "manual", "status": fields.get("status") or "pending",
            "pilot": fields.get("pilot_batch_id"), "now": now,
        })
        if commit:
            self.db.commit()
        return self._match(int(result.lastrowid))

    def review_match(self, match_id: int, *, decision: str, actor: str, note: str = "", commit: bool = True) -> dict[str, Any]:
        self._match(match_id)
        self.db.execute(text("""UPDATE p4_resource_match_candidates SET status=:status,reviewed_by=:actor,
            reviewed_at=:now,review_note=:note,updated_at=:now WHERE id=:id"""),
            {"status": decision, "actor": actor, "now": _now(), "note": note or None, "id": int(match_id)})
        if commit:
            self.db.commit()
        return self._match(match_id)

    def link_match_opportunity(self, match_id: int, opportunity_id: int, *, commit: bool = True) -> dict[str, Any]:
        self.db.execute(text("""UPDATE p4_resource_match_candidates SET opportunity_id=:opportunity_id,
            status='converted_to_lead',updated_at=:now WHERE id=:match_id"""),
            {"opportunity_id": int(opportunity_id), "now": _now(), "match_id": int(match_id)})
        if commit:
            self.db.commit()
        return self._match(match_id)

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
            self.link_match_opportunity(match_id, int(existing["id"]))
            return existing
        source_intelligence_id = demand.get("source_intelligence_id") or supply.get("source_intelligence_id")
        try:
            opportunity = UnifiedOpportunityService(self.db).create(actor_user_id=actor_user_id, commit=False, fields={
                "title": f"合作机会｜{demand['title']} × {supply['title']}", "opp_type": "resource_match",
                "source_type": "resource_match", "source_id": int(match_id), "organization_id": demand.get("organization_id"),
                "demand_organization_id": demand.get("organization_id"), "supply_organization_id": supply.get("organization_id"),
                "related_resource_id": int(demand["id"]), "description": match.get("explanation") or "运营人员确认的供需匹配",
                "expected_outcome": "推动供需双方形成可核验合作", "priority": "P1", "next_action": "登记首次商务跟进",
                "source_intelligence_id": source_intelligence_id, "source_demand_resource_id": int(demand["id"]),
                "source_supply_resource_id": int(supply["id"]), "source_match_id": int(match_id), "human_confirmed": True,
            })
            opportunity_id = int(opportunity.id)
            self.link_match_opportunity(match_id, opportunity_id, commit=False)
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
        content = str(content).strip()
        if not content:
            raise HTTPException(status_code=400, detail="跟进内容不能为空")
        try:
            follow = UnifiedOpportunityService(self.db).create_follow_up(opp_id=opportunity_id, actor_user_id=actor_user_id,
                is_admin=True, fields={"content": content, "next_action": next_action or None,
                "contact_result": contact_result or None, "stage_after": stage_after or None,
                "next_follow_at": next_follow_at or None})
            follow_up_id = int(follow.id)
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
        title = title.strip()
        if not title:
            raise HTTPException(status_code=400, detail="任务标题不能为空")
        task = UnifiedOpportunityService(self.db).create_task(opp_id=opportunity_id, actor_user_id=actor_user_id,
            owner_id=actor_user_id, is_admin=True, fields={"title": title, "due_date": due_date or None,
            "priority": priority if priority in {"P0", "P1", "P2", "P3"} else "P2"})
        task_id = int(task.id)
        return self._one("SELECT * FROM v06_collab_tasks WHERE id=:id", {"id": task_id})

    def _cooperation_relationship(
        self,
        opportunity: dict[str, Any],
        *,
        actor_user_id: int,
        evidence_text: str,
    ) -> int | None:
        return CanonicalRelationshipService().upsert_cooperation_outcome(
            self.db, opportunity, actor_user_id=actor_user_id, evidence_text=evidence_text)

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
            UnifiedOpportunityService(self.db).close_outcome(opportunity_id, actor_user_id=actor_user_id,
                outcome=outcome, relationship_id=relationship_id, reason=reason, result_note=result_note,
                cooperation_scale=cooperation_scale, commit=False)
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
