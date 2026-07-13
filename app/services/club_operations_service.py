from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.v04c_review import db_connection, default_db_path

MEMBERSHIP_APPLICATION_STATUSES = {
    "application", "pending_review", "approved", "need_more_info", "held", "rejected", "withdrawn"
}
MEMBERSHIP_STATUSES = {"pending", "active", "suspended", "expired", "withdrawn"}


class ClubOperationError(ValueError):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def _path(db_path: str | Path | None) -> Path:
    return Path(db_path) if db_path else default_db_path()


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _row(row: sqlite3.Row | None) -> dict[str, Any] | None:
    return dict(row) if row else None


def _number(prefix: str) -> str:
    return f"{prefix}-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:10].upper()}"


def record_audit(
    conn: sqlite3.Connection, *, action: str, target_type: str, target_id: str | int,
    actor: str, actor_user_id: int | None = None, before: Any = None, after: Any = None,
    reason: str = "", pilot_batch_id: str | None = None, result: str = "success",
) -> None:
    conn.execute(
        """
        INSERT INTO p4_operation_audit(
          audit_no,action,target_type,target_id,before_json,after_json,actor_user_id,actor,
          reason,result,pilot_batch_id,created_at
        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
        """,
        (_number("P4AUD"), action, target_type, str(target_id), _json(before) if before is not None else None,
         _json(after) if after is not None else None, actor_user_id, actor, reason or None, result,
         pilot_batch_id, now_iso()),
    )


def emit_domain_event(
    conn: sqlite3.Connection, *, event_type: str, aggregate_type: str, aggregate_id: str | int,
    payload: dict[str, Any], actor_user_id: int | None = None, pilot_batch_id: str | None = None,
) -> None:
    conn.execute(
        """
        INSERT INTO p4_domain_events(
          event_id,event_type,aggregate_type,aggregate_id,payload_json,actor_user_id,
          occurred_at,status,pilot_batch_id
        ) VALUES (?,?,?,?,?,?,?,'pending',?)
        """,
        (str(uuid.uuid4()), event_type, aggregate_type, str(aggregate_id), _json(payload),
         actor_user_id, now_iso(), pilot_batch_id),
    )


class ClubMembershipService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = _path(db_path)

    def submit_application(self, fields: dict[str, Any], *, actor_user_id: int | None = None) -> dict[str, Any]:
        person_id = int(fields.get("person_id") or 0)
        user_id = int(fields.get("user_id") or actor_user_id or 0)
        organization_id = int(fields.get("organization_id") or 0)
        if not person_id or not user_id or not organization_id:
            raise ClubOperationError(400, "IDENTITY_LINKS_REQUIRED", "申请必须关联现有人物、登录账号和机构")
        ts = now_iso()
        pilot = fields.get("pilot_batch_id")
        with db_connection(self.db_path) as conn:
            for table, object_id, label in (
                ("people", person_id, "人物"), ("v05a_users", user_id, "账号"),
                ("organizations", organization_id, "机构"),
            ):
                if not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (object_id,)).fetchone():
                    raise ClubOperationError(404, "LINKED_OBJECT_NOT_FOUND", f"{label}不存在")
            existing = conn.execute(
                """
                SELECT * FROM v04f_club_applications
                WHERE user_id=? AND status IN ('submitted','under_review','need_more_info','approved')
                ORDER BY id DESC LIMIT 1
                """, (user_id,),
            ).fetchone()
            if existing:
                return dict(existing)
            person = conn.execute("SELECT name FROM people WHERE id=?", (person_id,)).fetchone()
            org = conn.execute("SELECT standard_name FROM organizations WHERE id=?", (organization_id,)).fetchone()
            application_no = _number("QBA")
            cur = conn.execute(
                """
                INSERT INTO v04f_club_applications(
                  application_no,applicant_name,mobile,email,wechat,organization_name,title,city,
                  industry_tags,expertise_tags,offered_resources,cooperation_needs,self_introduction,
                  referral_source,referrer_name,preferred_contact_method,consent_to_store,consent_to_contact,
                  status,submitted_at,matched_person_id,matched_organization_id,user_id,member_type,
                  professional_direction,application_reason,source_event_id,pilot_batch_id,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,1,1,'under_review',?,?,?,?,?,?,?,?,?,?,?)
                """,
                (application_no, person["name"], fields.get("mobile"), fields.get("email"), fields.get("wechat"),
                 org["standard_name"], fields.get("title"), fields.get("city"), fields.get("industry_tags"),
                 fields.get("professional_direction") or fields.get("expertise_tags"), fields.get("offered_resources"),
                 fields.get("cooperation_needs"), fields.get("self_introduction"), fields.get("referral_source"),
                 fields.get("referrer_name"), fields.get("preferred_contact_method"), ts, person_id,
                 organization_id, user_id, fields.get("member_type") or "standard",
                 fields.get("professional_direction"), fields.get("application_reason"), fields.get("source_event_id"),
                 pilot, ts, ts),
            )
            application_id = int(cur.lastrowid)
            record_audit(conn, action="membership.application_submitted", target_type="membership_application",
                         target_id=application_id, actor=str(user_id), actor_user_id=user_id,
                         after={"status": "pending_review"}, pilot_batch_id=pilot)
            return dict(conn.execute("SELECT * FROM v04f_club_applications WHERE id=?", (application_id,)).fetchone())

    def review_application(
        self, application_id: int, *, decision: str, actor: str, actor_user_id: int | None = None,
        note: str = "", owner: str = "", person_id: int | None = None,
        organization_id: int | None = None, user_id: int | None = None,
    ) -> dict[str, Any]:
        mapping = {
            "under_review": "under_review", "pending_review": "under_review",
            "need_more_info": "need_more_info", "approved": "approved", "rejected": "rejected",
            "held": "under_review", "withdrawn": "withdrawn",
        }
        if decision not in mapping:
            raise ClubOperationError(400, "INVALID_APPLICATION_DECISION", "无效会员审核状态")
        target = mapping[decision]
        ts = now_iso()
        with db_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            application = _row(conn.execute("SELECT * FROM v04f_club_applications WHERE id=?", (application_id,)).fetchone())
            if not application:
                raise ClubOperationError(404, "APPLICATION_NOT_FOUND", "会员申请不存在")
            if application["status"] == target and ((decision == "held" and application.get("held_reason")) or (decision != "held" and not application.get("held_reason"))):
                membership = _row(conn.execute("SELECT * FROM v04f_club_memberships WHERE source=?", (application["application_no"],)).fetchone())
                return {"application": application, "membership": membership, "idempotent": True}
            resolved_person_id = int(person_id or application.get("matched_person_id") or 0)
            resolved_org_id = int(organization_id or application.get("matched_organization_id") or 0)
            resolved_user_id = int(user_id or application.get("user_id") or 0)
            membership = None
            if target == "approved":
                if not resolved_person_id or not resolved_org_id or not resolved_user_id:
                    raise ClubOperationError(400, "IDENTITY_LINKS_REQUIRED", "批准前必须确认人物、账号和机构")
                for table, object_id in (("people", resolved_person_id), ("organizations", resolved_org_id), ("v05a_users", resolved_user_id)):
                    if not conn.execute(f"SELECT 1 FROM {table} WHERE id=?", (object_id,)).fetchone():
                        raise ClubOperationError(404, "LINKED_OBJECT_NOT_FOUND", "关联主体不存在")
                existing = conn.execute(
                    "SELECT * FROM v04f_club_memberships WHERE person_id=? AND status IN ('pending','active','suspended')",
                    (resolved_person_id,),
                ).fetchone()
                if existing:
                    if str(existing["source"] or "") != application["application_no"]:
                        raise ClubOperationError(409, "ACTIVE_MEMBERSHIP_EXISTS", "该人物已有有效会员身份")
                    membership = dict(existing)
                else:
                    cur = conn.execute(
                        """
                        INSERT INTO v04f_club_memberships(
                          member_no,person_id,organization_id,user_id,member_role,member_level,status,joined_at,
                          source,owner,industry_tags,expertise_tags,cooperation_preferences,pilot_batch_id,created_at,updated_at
                        ) VALUES (?,?,?,?,?,?,'pending',?,?,?,?,?,?,?,?,?)
                        """,
                        (_number("QBM"), resolved_person_id, resolved_org_id, resolved_user_id,
                         application.get("title"), application.get("member_type") or "standard", ts,
                         application["application_no"], owner or actor, application.get("industry_tags"),
                         application.get("professional_direction") or application.get("expertise_tags"),
                         application.get("cooperation_needs"), application.get("pilot_batch_id"), ts, ts),
                    )
                    membership = dict(conn.execute("SELECT * FROM v04f_club_memberships WHERE id=?", (cur.lastrowid,)).fetchone())
            before = {"status": application["status"]}
            conn.execute(
                """
                UPDATE v04f_club_applications SET status=?,review_note=?,reviewed_at=?,reviewed_by=?,
                  matched_person_id=?,matched_organization_id=?,user_id=?,owner=?,held_reason=?,updated_at=? WHERE id=?
                """,
                (target, note or None, ts, actor, resolved_person_id or None, resolved_org_id or None,
                 resolved_user_id or None, owner or None, note if decision == "held" else None, ts, application_id),
            )
            conn.execute(
                """
                INSERT INTO p4_membership_history(
                  membership_id,application_id,change_type,old_status,new_status,before_json,after_json,
                  reason,actor_user_id,actor,pilot_batch_id,created_at
                ) VALUES (?,?, 'application_reviewed',?,?,?,?,?,?,?,?,?)
                """,
                (membership["id"] if membership else None, application_id, application["status"], "held" if decision == "held" else target,
                 _json(before), _json({"status": "held" if decision == "held" else target}), note or None, actor_user_id, actor,
                 application.get("pilot_batch_id"), ts),
            )
            record_audit(conn, action="membership.application_reviewed", target_type="membership_application",
                         target_id=application_id, actor=actor, actor_user_id=actor_user_id,
                         before=before, after={"status": "held" if decision == "held" else target}, reason=note,
                         pilot_batch_id=application.get("pilot_batch_id"))
            if target == "approved":
                emit_domain_event(conn, event_type="membership.approved", aggregate_type="membership",
                                  aggregate_id=membership["id"], payload={"application_id": application_id},
                                  actor_user_id=actor_user_id, pilot_batch_id=application.get("pilot_batch_id"))
            updated = dict(conn.execute("SELECT * FROM v04f_club_applications WHERE id=?", (application_id,)).fetchone())
            return {"application": updated, "membership": membership, "idempotent": False}

    def transition_membership(
        self, membership_id: int, *, action: str, actor: str, actor_user_id: int | None = None,
        reason: str = "", changes: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        transitions = {
            "activate": ({"pending"}, "active", "membership_activated"),
            "suspend": ({"active"}, "suspended", "suspended"),
            "resume": ({"suspended"}, "active", "resumed"),
            "expire": ({"active", "suspended"}, "inactive", "expired"),
            "withdraw": ({"pending", "active", "suspended"}, "exited", "withdrawn"),
        }
        if action not in transitions and action != "change":
            raise ClubOperationError(400, "INVALID_MEMBERSHIP_ACTION", "无效会员操作")
        ts = now_iso()
        with db_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            member = _row(conn.execute("SELECT * FROM v04f_club_memberships WHERE id=?", (membership_id,)).fetchone())
            if not member:
                raise ClubOperationError(404, "MEMBERSHIP_NOT_FOUND", "会员不存在")
            before = dict(member)
            change_type = "member_type_changed"
            target_status = member["status"]
            updates: dict[str, Any] = {}
            if action == "change":
                allowed = {"member_level", "organization_id", "member_role", "expired_at"}
                updates = {key: value for key, value in (changes or {}).items() if key in allowed and value != member.get(key)}
                if not updates:
                    return {"membership": member, "idempotent": True}
                if "organization_id" in updates:
                    change_type = "organization_changed"
                elif "member_role" in updates:
                    change_type = "role_changed"
                elif "expired_at" in updates:
                    change_type = "validity_changed"
            else:
                allowed_statuses, target_status, change_type = transitions[action]
                if member["status"] == target_status:
                    return {"membership": member, "idempotent": True}
                if member["status"] not in allowed_statuses:
                    raise ClubOperationError(409, "INVALID_MEMBERSHIP_TRANSITION", "当前会员状态不允许该操作")
                updates["status"] = target_status
                if target_status in {"inactive", "exited"}:
                    updates["deactivated_at"] = ts
            updates["updated_at"] = ts
            assignments = ",".join(f'"{key}"=?' for key in updates)
            conn.execute(f"UPDATE v04f_club_memberships SET {assignments} WHERE id=?", [*updates.values(), membership_id])
            after = dict(conn.execute("SELECT * FROM v04f_club_memberships WHERE id=?", (membership_id,)).fetchone())
            conn.execute(
                """
                INSERT INTO p4_membership_history(
                  membership_id,change_type,old_status,new_status,before_json,after_json,reason,
                  actor_user_id,actor,pilot_batch_id,created_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
                """,
                (membership_id, change_type, before["status"], after["status"], _json(before), _json(after),
                 reason or None, actor_user_id, actor, member.get("pilot_batch_id"), ts),
            )
            record_audit(conn, action=f"membership.{action}", target_type="membership", target_id=membership_id,
                         actor=actor, actor_user_id=actor_user_id, before=before, after=after, reason=reason,
                         pilot_batch_id=member.get("pilot_batch_id"))
            if action == "activate":
                emit_domain_event(conn, event_type="membership.activated", aggregate_type="membership",
                                  aggregate_id=membership_id, payload={"status": "active"},
                                  actor_user_id=actor_user_id, pilot_batch_id=member.get("pilot_batch_id"))
            return {"membership": after, "idempotent": False}

    def history(self, membership_id: int) -> list[dict[str, Any]]:
        with db_connection(self.db_path) as conn:
            return [dict(row) for row in conn.execute(
                "SELECT * FROM p4_membership_history WHERE membership_id=? ORDER BY id DESC", (membership_id,),
            ).fetchall()]
