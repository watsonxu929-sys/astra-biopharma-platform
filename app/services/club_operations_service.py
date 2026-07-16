from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import uuid
from datetime import datetime, timedelta
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


def _allow_v05c_legacy_fk_compatibility(conn: sqlite3.Connection) -> bool:
    """Disable only this connection's FK enforcement when legacy v05c points at a removed table."""
    targets = {str(row[2]) for row in conn.execute("PRAGMA foreign_key_list(v05c_club_event_registrations)")}
    broken = "v04f_club_memberships_old" in targets and not conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='v04f_club_memberships_old'"
    ).fetchone()
    if broken:
        conn.execute("PRAGMA foreign_keys=OFF")
    return broken


class ClubEventService:
    EVENT_TRANSITIONS = {
        "submit_review": ({"draft"}, "pending_review"),
        "approve": ({"pending_review"}, "published"),
        "publish": ({"draft", "pending_review"}, "published"),
        "open": ({"published", "registration_closed"}, "registration_open"),
        "close": ({"registration_open"}, "registration_closed"),
        "start": ({"published", "registration_open", "registration_closed"}, "ongoing"),
        "complete": ({"ongoing"}, "completed"),
        "cancel": ({"draft", "pending_review", "published", "registration_open", "registration_closed", "ongoing"}, "cancelled"),
        "archive": ({"completed", "cancelled"}, "archived"),
    }
    LEGACY_EVENT_STATUS = {
        "draft": "draft", "pending_review": "draft", "published": "published",
        "registration_open": "registration_open", "registration_closed": "registration_closed",
        "ongoing": "ongoing", "completed": "completed", "cancelled": "cancelled", "archived": "completed",
    }

    def __init__(self, db_path: str | Path | None = None):
        self.db_path = _path(db_path)

    def transition_event(
        self, club_event_id: int, *, action: str, actor: str, actor_user_id: int | None = None,
        note: str = "",
    ) -> dict[str, Any]:
        if action not in self.EVENT_TRANSITIONS:
            raise ClubOperationError(400, "INVALID_EVENT_ACTION", "无效活动操作")
        allowed, target = self.EVENT_TRANSITIONS[action]
        ts = now_iso()
        with db_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            event = _row(conn.execute("SELECT * FROM v05c_club_event_profiles WHERE id=?", (club_event_id,)).fetchone())
            if not event:
                raise ClubOperationError(404, "EVENT_NOT_FOUND", "活动不存在")
            current = event.get("lifecycle_status") or event["status"]
            if current == target:
                return {"event": event, "idempotent": True}
            if current not in allowed:
                raise ClubOperationError(409, "INVALID_EVENT_TRANSITION", "当前活动状态不允许该操作")
            registration_status = "open" if target == "registration_open" else "closed"
            conn.execute(
                """
                UPDATE v05c_club_event_profiles SET lifecycle_status=?,status=?,registration_status=?,
                  reviewed_by=CASE WHEN ? IN ('approve','publish') THEN ? ELSE reviewed_by END,
                  reviewed_at=CASE WHEN ? IN ('approve','publish') THEN ? ELSE reviewed_at END,
                  review_note=CASE WHEN ? IN ('approve','publish') THEN ? ELSE review_note END,updated_at=? WHERE id=?
                """,
                (target, self.LEGACY_EVENT_STATUS[target], registration_status, action, actor, action, ts,
                 action, note or None, ts, club_event_id),
            )
            after = dict(conn.execute("SELECT * FROM v05c_club_event_profiles WHERE id=?", (club_event_id,)).fetchone())
            record_audit(conn, action=f"event.{action}", target_type="club_event", target_id=club_event_id,
                         actor=actor, actor_user_id=actor_user_id, before={"status": current},
                         after={"status": target}, reason=note, pilot_batch_id=event.get("pilot_batch_id"))
            if target == "published":
                emit_domain_event(conn, event_type="event.published", aggregate_type="club_event",
                                  aggregate_id=club_event_id, payload={"status": target},
                                  actor_user_id=actor_user_id, pilot_batch_id=event.get("pilot_batch_id"))
            return {"event": after, "idempotent": False}

    def register(self, club_event_id: int, fields: dict[str, Any], *, actor_user_id: int | None = None) -> dict[str, Any]:
        ts = now_iso()
        pilot = fields.get("pilot_batch_id")
        with db_connection(self.db_path) as conn:
            _allow_v05c_legacy_fk_compatibility(conn)
            conn.execute("BEGIN IMMEDIATE")
            event = _row(conn.execute("SELECT * FROM v05c_club_event_profiles WHERE id=?", (club_event_id,)).fetchone())
            if not event:
                raise ClubOperationError(404, "EVENT_NOT_FOUND", "活动不存在")
            lifecycle = event.get("lifecycle_status") or event["status"]
            if lifecycle != "registration_open" or event["registration_status"] != "open":
                raise ClubOperationError(409, "REGISTRATION_NOT_OPEN", "活动报名未开放")
            if event.get("registration_start") and ts < str(event["registration_start"]):
                raise ClubOperationError(409, "REGISTRATION_NOT_STARTED", "尚未到报名开始时间")
            if event.get("registration_deadline") and ts[:10] > str(event["registration_deadline"])[:10]:
                raise ClubOperationError(409, "REGISTRATION_CLOSED", "活动报名已截止")
            user_id = int(fields.get("user_id") or actor_user_id or 0) or None
            person_id = int(fields.get("person_id") or 0) or None
            organization_id = int(fields.get("organization_id") or 0) or None
            mobile = str(fields.get("mobile") or "").strip()
            email = str(fields.get("email") or "").strip().lower()
            duplicate_clauses, params = [], [club_event_id]
            for column, value in (("user_id", user_id), ("person_id", person_id), ("mobile", mobile), ("email", email)):
                if value:
                    duplicate_clauses.append(f"{column}=?")
                    params.append(value)
            if duplicate_clauses:
                duplicate = conn.execute(
                    f"SELECT * FROM v05c_club_event_registrations WHERE club_event_id=? AND ({' OR '.join(duplicate_clauses)}) AND lifecycle_status<>'cancelled' LIMIT 1",
                    params,
                ).fetchone()
                if duplicate:
                    result = dict(duplicate)
                    result["idempotent"] = True
                    return result
            membership_id = int(fields.get("membership_id") or 0) or None
            if membership_id:
                membership = conn.execute(
                    "SELECT * FROM v04f_club_memberships WHERE id=? AND status='active' "
                    "AND (expired_at IS NULL OR date(expired_at)>=date('now'))",
                    (membership_id,),
                ).fetchone()
                if not membership:
                    raise ClubOperationError(400, "ACTIVE_MEMBERSHIP_REQUIRED", "会员身份无效")
                person_id = person_id or membership["person_id"]
                organization_id = organization_id or membership["organization_id"]
                user_id = user_id or membership["user_id"]
            legacy_membership_table = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='v04f_club_memberships_old'").fetchone()
            legacy_membership_id = membership_id if legacy_membership_table else None
            cur = conn.execute(
                """
                INSERT INTO v05c_club_event_registrations(
                  registration_no,club_event_id,membership_id,canonical_membership_id,applicant_name,organization_name,title,mobile,email,
                  registration_source,status,lifecycle_status,registered_at,user_id,person_id,organization_id,is_guest,
                  application_reason,interest_direction,desired_connections,offered_resources,current_needs,
                  pilot_batch_id,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,?,?,?,?,'submitted','pending_review',?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (_number("QBR"), club_event_id, legacy_membership_id, membership_id, str(fields.get("applicant_name") or "").strip(),
                 fields.get("organization_name"), fields.get("title"), mobile or None, email or None,
                 fields.get("registration_source") or ("member" if membership_id else "public"), ts,
                 user_id, person_id, organization_id, 0 if membership_id else 1, fields.get("application_reason"),
                 fields.get("interest_direction"), fields.get("desired_connections"), fields.get("offered_resources"),
                 fields.get("current_needs"), pilot or event.get("pilot_batch_id"), ts, ts),
            )
            registration = dict(conn.execute("SELECT * FROM v05c_club_event_registrations WHERE id=?", (cur.lastrowid,)).fetchone())
            record_audit(conn, action="registration.submitted", target_type="event_registration",
                         target_id=registration["id"], actor=str(user_id or "guest"), actor_user_id=user_id,
                         after={"status": "pending_review"}, pilot_batch_id=registration.get("pilot_batch_id"))
            registration["idempotent"] = False
            return registration

    def review_registration(
        self, club_event_id: int, registration_id: int, *, decision: str, actor: str,
        actor_user_id: int | None = None, note: str = "",
    ) -> dict[str, Any]:
        allowed = {"approved", "rejected", "waitlisted", "cancelled", "pending_review", "no_show"}
        if decision not in allowed:
            raise ClubOperationError(400, "INVALID_REGISTRATION_DECISION", "无效报名状态")
        legacy = {"pending_review": "submitted", "no_show": "approved"}.get(decision, decision)
        ts = now_iso()
        with db_connection(self.db_path) as conn:
            _allow_v05c_legacy_fk_compatibility(conn)
            conn.execute("BEGIN IMMEDIATE")
            registration = _row(conn.execute(
                "SELECT * FROM v05c_club_event_registrations WHERE id=? AND club_event_id=?",
                (registration_id, club_event_id),
            ).fetchone())
            event = _row(conn.execute("SELECT * FROM v05c_club_event_profiles WHERE id=?", (club_event_id,)).fetchone())
            if not registration or not event:
                raise ClubOperationError(404, "REGISTRATION_NOT_FOUND", "报名不存在")
            current = registration.get("lifecycle_status") or registration["status"]
            target = decision
            if target == "approved" and int(event.get("capacity") or 0) > 0:
                approved = int(conn.execute(
                    "SELECT COUNT(*) FROM v05c_club_event_registrations WHERE club_event_id=? AND lifecycle_status IN ('approved','checked_in') AND id<>?",
                    (club_event_id, registration_id),
                ).fetchone()[0])
                if approved >= int(event["capacity"]):
                    target, legacy = "waitlisted", "waitlisted"
            if target == "cancelled" and current == "checked_in":
                raise ClubOperationError(409, "CHECKED_IN_CANNOT_CANCEL", "已签到报名不能取消")
            if current == target:
                return {"registration": registration, "idempotent": True}
            conn.execute(
                """
                UPDATE v05c_club_event_registrations SET status=?,lifecycle_status=?,review_note=?,reviewed_at=?,
                  cancelled_at=CASE WHEN ?='cancelled' THEN ? ELSE cancelled_at END,updated_at=? WHERE id=?
                """,
                (legacy, target, note or None, ts, target, ts, ts, registration_id),
            )
            if target == "approved":
                conn.execute(
                    """
                    INSERT INTO v05c_club_event_participation(
                      club_event_id,registration_id,membership_id,canonical_membership_id,attendance_status,pilot_batch_id,created_at,updated_at
                    ) VALUES (?,?,NULL,?,'registered',?,?,?)
                    ON CONFLICT(club_event_id,registration_id) DO NOTHING
                    """,
                    (club_event_id, registration_id, registration.get("canonical_membership_id") or registration.get("membership_id"),
                     registration.get("pilot_batch_id"), ts, ts),
                )
            elif target == "cancelled" and current == "approved":
                conn.execute(
                    "DELETE FROM v05c_club_event_participation WHERE club_event_id=? AND registration_id=? AND attendance_status='registered'",
                    (club_event_id, registration_id),
                )
                waitlisted = conn.execute(
                    """
                    SELECT * FROM v05c_club_event_registrations
                    WHERE club_event_id=? AND lifecycle_status='waitlisted'
                    ORDER BY registered_at,id LIMIT 1
                    """,
                    (club_event_id,),
                ).fetchone()
                if waitlisted:
                    conn.execute(
                        "UPDATE v05c_club_event_registrations SET status='approved',lifecycle_status='approved',"
                        "review_note=COALESCE(review_note,'') || ' / promoted from waitlist',reviewed_at=?,updated_at=? WHERE id=?",
                        (ts, ts, waitlisted["id"]),
                    )
                    conn.execute(
                        """INSERT INTO v05c_club_event_participation(
                          club_event_id,registration_id,membership_id,canonical_membership_id,attendance_status,pilot_batch_id,created_at,updated_at
                        ) VALUES (?,?,NULL,?,'registered',?,?,?)
                        ON CONFLICT(club_event_id,registration_id) DO NOTHING""",
                        (club_event_id, waitlisted["id"], waitlisted["canonical_membership_id"] or waitlisted["membership_id"],
                         waitlisted["pilot_batch_id"], ts, ts),
                    )
                    record_audit(conn, action="registration.waitlist_promoted", target_type="event_registration",
                                 target_id=waitlisted["id"], actor=actor, actor_user_id=actor_user_id,
                                 before={"status": "waitlisted"}, after={"status": "approved"},
                                 reason="capacity released", pilot_batch_id=waitlisted["pilot_batch_id"])
                    emit_domain_event(conn, event_type="registration.approved", aggregate_type="event_registration",
                                      aggregate_id=waitlisted["id"], payload={"club_event_id": club_event_id, "source": "waitlist_promotion"},
                                      actor_user_id=actor_user_id, pilot_batch_id=waitlisted["pilot_batch_id"])
            updated = dict(conn.execute("SELECT * FROM v05c_club_event_registrations WHERE id=?", (registration_id,)).fetchone())
            record_audit(conn, action="registration.reviewed", target_type="event_registration",
                         target_id=registration_id, actor=actor, actor_user_id=actor_user_id,
                         before={"status": current}, after={"status": target}, reason=note,
                         pilot_batch_id=registration.get("pilot_batch_id"))
            if target == "approved":
                emit_domain_event(conn, event_type="registration.approved", aggregate_type="event_registration",
                                  aggregate_id=registration_id, payload={"club_event_id": club_event_id},
                                  actor_user_id=actor_user_id, pilot_batch_id=registration.get("pilot_batch_id"))
            return {"registration": updated, "idempotent": False}

    def issue_checkin_token(
        self, club_event_id: int, registration_id: int, *, actor_user_id: int | None = None,
        valid_minutes: int = 240,
    ) -> dict[str, Any]:
        raw = secrets.token_urlsafe(32)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        now = datetime.now().replace(microsecond=0)
        valid_until = now + timedelta(minutes=max(1, min(int(valid_minutes), 1440)))
        with db_connection(self.db_path) as conn:
            registration = conn.execute(
                "SELECT * FROM v05c_club_event_registrations WHERE id=? AND club_event_id=? AND lifecycle_status='approved'",
                (registration_id, club_event_id),
            ).fetchone()
            if not registration:
                raise ClubOperationError(409, "APPROVED_REGISTRATION_REQUIRED", "仅已通过报名可签发签到码")
            conn.execute("UPDATE p4_checkin_tokens SET status='revoked',updated_at=? WHERE club_event_id=? AND registration_id=? AND status='active'", (now.isoformat(), club_event_id, registration_id))
            cur = conn.execute(
                """
                INSERT INTO p4_checkin_tokens(
                  club_event_id,registration_id,token_hash,token_hint,valid_from,valid_until,status,
                  issued_by_user_id,pilot_batch_id,created_at,updated_at
                ) VALUES (?,?,?,?,?,?,'active',?,?,?,?)
                """,
                (club_event_id, registration_id, digest, raw[-6:], now.isoformat(), valid_until.isoformat(),
                 actor_user_id, registration["pilot_batch_id"], now.isoformat(), now.isoformat()),
            )
            return {"token_id": int(cur.lastrowid), "token": raw, "token_hint": raw[-6:],
                    "valid_from": now.isoformat(), "valid_until": valid_until.isoformat()}

    def check_in(
        self, club_event_id: int, *, registration_id: int | None = None, token: str = "",
        actor: str, actor_user_id: int | None = None, method: str = "manual", supplement: bool = False,
    ) -> dict[str, Any]:
        ts = now_iso()
        token_row = None
        with db_connection(self.db_path) as conn:
            _allow_v05c_legacy_fk_compatibility(conn)
            conn.execute("BEGIN IMMEDIATE")
            if token:
                digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
                token_row = conn.execute("SELECT * FROM p4_checkin_tokens WHERE token_hash=?", (digest,)).fetchone()
                if not token_row:
                    self._checkin_audit(conn, club_event_id, None, None, "invalid_attempt", "not_found", method, actor, actor_user_id, "签到码不存在")
                    raise ClubOperationError(404, "TOKEN_NOT_FOUND", "签到码无效")
                if int(token_row["club_event_id"]) != club_event_id:
                    self._checkin_audit(conn, club_event_id, token_row["registration_id"], token_row["id"], "invalid_attempt", "wrong_event", method, actor, actor_user_id, "签到码不属于本活动")
                    raise ClubOperationError(409, "TOKEN_WRONG_EVENT", "签到码不属于本活动")
                if token_row["status"] != "active" or ts < token_row["valid_from"] or ts > token_row["valid_until"]:
                    self._checkin_audit(conn, club_event_id, token_row["registration_id"], token_row["id"], "invalid_attempt", "expired", method, actor, actor_user_id, "签到码已失效")
                    raise ClubOperationError(409, "TOKEN_EXPIRED", "签到码已失效")
                registration_id = int(token_row["registration_id"])
            registration = _row(conn.execute(
                "SELECT * FROM v05c_club_event_registrations WHERE id=? AND club_event_id=?",
                (registration_id, club_event_id),
            ).fetchone())
            if not registration or registration.get("lifecycle_status") not in {"approved", "checked_in"}:
                self._checkin_audit(conn, club_event_id, registration_id, token_row["id"] if token_row else None, "invalid_attempt", "rejected", method, actor, actor_user_id, "报名未通过")
                raise ClubOperationError(409, "APPROVED_REGISTRATION_REQUIRED", "报名未通过，不能签到")
            if registration.get("lifecycle_status") == "checked_in":
                self._checkin_audit(conn, club_event_id, registration_id, token_row["id"] if token_row else None, "check_in", "duplicate", method, actor, actor_user_id, "重复签到")
                return {"registration": registration, "idempotent": True}
            conn.execute("UPDATE v05c_club_event_registrations SET status='approved',lifecycle_status='checked_in',checked_in_at=?,updated_at=? WHERE id=?", (ts, ts, registration_id))
            conn.execute(
                """
                INSERT INTO v05c_club_event_participation(
                  club_event_id,registration_id,membership_id,canonical_membership_id,attendance_status,check_in_method,check_in_time,pilot_batch_id,created_at,updated_at
                ) VALUES (?,?,NULL,?,'checked_in',?,?,?,?,?)
                ON CONFLICT(club_event_id,registration_id) DO UPDATE SET attendance_status='checked_in',
                  check_in_method=excluded.check_in_method,check_in_time=excluded.check_in_time,updated_at=excluded.updated_at
                """,
                (club_event_id, registration_id, registration.get("canonical_membership_id") or registration.get("membership_id"), method, ts,
                 registration.get("pilot_batch_id"), ts, ts),
            )
            if token_row:
                conn.execute("UPDATE p4_checkin_tokens SET status='used',updated_at=? WHERE id=?", (ts, token_row["id"]))
            action = "supplement" if supplement else "check_in"
            self._checkin_audit(conn, club_event_id, registration_id, token_row["id"] if token_row else None, action, "success", method, actor, actor_user_id, "")
            emit_domain_event(conn, event_type="registration.checked_in", aggregate_type="event_registration",
                              aggregate_id=registration_id, payload={"club_event_id": club_event_id, "method": method},
                              actor_user_id=actor_user_id, pilot_batch_id=registration.get("pilot_batch_id"))
            updated = dict(conn.execute("SELECT * FROM v05c_club_event_registrations WHERE id=?", (registration_id,)).fetchone())
            return {"registration": updated, "idempotent": False}

    def undo_checkin(self, club_event_id: int, registration_id: int, *, actor: str, actor_user_id: int | None = None, reason: str = "") -> dict[str, Any]:
        ts = now_iso()
        with db_connection(self.db_path) as conn:
            _allow_v05c_legacy_fk_compatibility(conn)
            conn.execute("BEGIN IMMEDIATE")
            registration = _row(conn.execute("SELECT * FROM v05c_club_event_registrations WHERE id=? AND club_event_id=?", (registration_id, club_event_id)).fetchone())
            if not registration:
                raise ClubOperationError(404, "REGISTRATION_NOT_FOUND", "报名不存在")
            if registration.get("lifecycle_status") != "checked_in":
                return {"registration": registration, "idempotent": True}
            conn.execute("UPDATE v05c_club_event_registrations SET lifecycle_status='approved',checked_in_at=NULL,updated_at=? WHERE id=?", (ts, registration_id))
            conn.execute("UPDATE v05c_club_event_participation SET attendance_status='registered',check_in_time=NULL,updated_at=? WHERE club_event_id=? AND registration_id=?", (ts, club_event_id, registration_id))
            self._checkin_audit(conn, club_event_id, registration_id, None, "undo", "success", "manual", actor, actor_user_id, reason)
            return {"registration": dict(conn.execute("SELECT * FROM v05c_club_event_registrations WHERE id=?", (registration_id,)).fetchone()), "idempotent": False}

    def submit_feedback(
        self, club_event_id: int, registration_id: int, fields: dict[str, Any], *, actor_user_id: int | None = None,
    ) -> dict[str, Any]:
        ts = now_iso()
        with db_connection(self.db_path) as conn:
            _allow_v05c_legacy_fk_compatibility(conn)
            conn.execute("BEGIN IMMEDIATE")
            event = _row(conn.execute("SELECT * FROM v05c_club_event_profiles WHERE id=?", (club_event_id,)).fetchone())
            registration = _row(conn.execute("SELECT * FROM v05c_club_event_registrations WHERE id=? AND club_event_id=?", (registration_id, club_event_id)).fetchone())
            if not event or not registration:
                raise ClubOperationError(404, "REGISTRATION_NOT_FOUND", "报名不存在")
            if (event.get("lifecycle_status") or event["status"]) not in {"completed", "archived"}:
                raise ClubOperationError(409, "EVENT_NOT_COMPLETED", "活动完成后才能提交反馈")
            if registration.get("lifecycle_status") not in {"checked_in", "no_show"}:
                raise ClubOperationError(409, "ATTENDANCE_REQUIRED", "仅活动参与者可提交反馈")
            scores = {key: int(fields.get(key) or 0) or None for key in ("content_score", "speaker_score", "organization_score", "satisfaction_score")}
            if any(score is not None and not 1 <= score <= 5 for score in scores.values()):
                raise ClubOperationError(400, "INVALID_FEEDBACK_SCORE", "评价分数必须在1到5之间")
            existing = conn.execute("SELECT id FROM p4_event_feedback WHERE club_event_id=? AND registration_id=?", (club_event_id, registration_id)).fetchone()
            if existing:
                conn.execute(
                    """
                    UPDATE p4_event_feedback SET content_score=?,speaker_score=?,organization_score=?,satisfaction_score=?,
                      content_feedback=?,interested_people=?,interested_organizations=?,cooperation_intent=?,new_demand=?,
                      new_supply=?,suggestions=?,submitted_by_user_id=?,updated_at=? WHERE id=?
                    """,
                    (scores["content_score"], scores["speaker_score"], scores["organization_score"], scores["satisfaction_score"],
                     fields.get("content_feedback"), fields.get("interested_people"), fields.get("interested_organizations"),
                     fields.get("cooperation_intent"), fields.get("new_demand"), fields.get("new_supply"), fields.get("suggestions"),
                     actor_user_id, ts, existing["id"]),
                )
                feedback_id = int(existing["id"])
            else:
                cur = conn.execute(
                    """
                    INSERT INTO p4_event_feedback(
                      feedback_no,club_event_id,registration_id,membership_id,content_score,speaker_score,
                      organization_score,satisfaction_score,content_feedback,interested_people,interested_organizations,
                      cooperation_intent,new_demand,new_supply,suggestions,status,submitted_by_user_id,pilot_batch_id,created_at,updated_at
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'submitted',?,?,?,?)
                    """,
                    (_number("QBF"), club_event_id, registration_id, registration.get("canonical_membership_id") or registration.get("membership_id"),
                     scores["content_score"], scores["speaker_score"], scores["organization_score"], scores["satisfaction_score"],
                     fields.get("content_feedback"), fields.get("interested_people"), fields.get("interested_organizations"),
                     fields.get("cooperation_intent"), fields.get("new_demand"), fields.get("new_supply"), fields.get("suggestions"),
                     actor_user_id, registration.get("pilot_batch_id"), ts, ts),
                )
                feedback_id = int(cur.lastrowid)
            conn.execute("UPDATE v05c_club_event_participation SET satisfaction_score=?,feedback=?,follow_up_note=?,updated_at=? WHERE club_event_id=? AND registration_id=?", (scores["satisfaction_score"], fields.get("content_feedback"), fields.get("cooperation_intent"), ts, club_event_id, registration_id))
            emit_domain_event(conn, event_type="feedback.submitted", aggregate_type="event_feedback",
                              aggregate_id=feedback_id, payload={"club_event_id": club_event_id, "registration_id": registration_id},
                              actor_user_id=actor_user_id, pilot_batch_id=registration.get("pilot_batch_id"))
            return dict(conn.execute("SELECT * FROM p4_event_feedback WHERE id=?", (feedback_id,)).fetchone())

    @staticmethod
    def _checkin_audit(
        conn: sqlite3.Connection, club_event_id: int, registration_id: int | None, token_id: int | None,
        action: str, result: str, method: str, actor: str, actor_user_id: int | None, detail: str,
    ) -> None:
        conn.execute(
            """
            INSERT INTO p4_checkin_audit(
              club_event_id,registration_id,token_id,action,result,method,detail,actor_user_id,actor,pilot_batch_id,created_at
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?)
            """,
            (club_event_id, registration_id, token_id, action, result, method, detail or None,
             actor_user_id, actor,
             (conn.execute("SELECT pilot_batch_id FROM v05c_club_event_registrations WHERE id=?", (registration_id,)).fetchone() or [None])[0] if registration_id else None,
             now_iso()),
        )

class ClubResourceMatchingService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = _path(db_path)

    def create_member_resource(
        self, membership_id: int, *, direction: str, fields: dict[str, Any], actor_user_id: int,
    ) -> dict[str, Any]:
        if direction not in {"demand", "supply"}:
            raise ClubOperationError(400, "INVALID_RESOURCE_DIRECTION", "资源方向无效")
        from sqlalchemy import create_engine, text
        from sqlalchemy.orm import Session
        from app.services.unified_resource_service import UnifiedResourceService

        with db_connection(self.db_path) as conn:
            member = _row(conn.execute(
                "SELECT * FROM v04f_club_memberships WHERE id=? AND status='active' "
                "AND (expired_at IS NULL OR date(expired_at)>=date('now'))",
                (membership_id,),
            ).fetchone())
            if not member:
                raise ClubOperationError(404, "MEMBERSHIP_NOT_FOUND", "会员不存在")
            if int(member.get("user_id") or actor_user_id) != actor_user_id:
                user = conn.execute("SELECT role FROM v05a_users WHERE id=?", (actor_user_id,)).fetchone()
                if not user or user["role"] != "admin":
                    raise ClubOperationError(403, "RESOURCE_FORBIDDEN", "无权代该会员发布资源")
        engine = create_engine(f"sqlite:///{self.db_path.as_posix()}", connect_args={"check_same_thread": False})
        try:
            with Session(engine) as session:
                unified = UnifiedResourceService(session)
                create_fields = {
                    **fields, "direction": direction, "owner_person_id": member.get("person_id"),
                    "owner_organization_id": member.get("organization_id"),
                    "legacy_source_type": "qbay_membership", "legacy_source_id": str(membership_id),
                    "status": fields.get("status") or "pending_review",
                }
                duplicates = [item for item in unified.find_duplicates(create_fields)
                              if item.legacy_source_type == "qbay_membership"
                              and item.legacy_source_id == str(membership_id)]
                created = not bool(duplicates)
                resource = duplicates[0] if duplicates else unified.create(actor_user_id=actor_user_id, fields=create_fields)
                if created:
                    session.execute(
                        text("UPDATE v06_market_resources SET source_event_id=:source_event_id,target_audience=:target_audience,pilot_batch_id=:pilot WHERE id=:id"),
                        {"source_event_id": fields.get("source_event_id"), "target_audience": fields.get("target_audience"),
                         "pilot": fields.get("pilot_batch_id"), "id": resource.id},
                    )
                    session.commit()
                result = unified.to_api(resource)
                result["pilot_batch_id"] = fields.get("pilot_batch_id")
                result["idempotent"] = not created
        finally:
            engine.dispose()
        if created:
            with db_connection(self.db_path) as conn:
                record_audit(conn, action="resource.submitted", target_type="market_resource", target_id=result["id"],
                             actor=str(actor_user_id), actor_user_id=actor_user_id, after={"direction": direction, "status": "pending_review"},
                             pilot_batch_id=fields.get("pilot_batch_id"))
        return result

    def review_resource(
        self, resource_id: int, *, decision: str, actor: str, actor_user_id: int | None = None, note: str = "",
    ) -> dict[str, Any]:
        status = {"approved": "published", "rejected": "rejected", "need_more_info": "pending_review"}.get(decision)
        if not status:
            raise ClubOperationError(400, "INVALID_RESOURCE_DECISION", "无效资源审核状态")
        ts = now_iso()
        with db_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            resource = _row(conn.execute("SELECT * FROM v06_market_resources WHERE id=?", (resource_id,)).fetchone())
            if not resource:
                raise ClubOperationError(404, "RESOURCE_NOT_FOUND", "资源不存在")
            if resource["status"] == status:
                return {"resource": resource, "idempotent": True}
            conn.execute("UPDATE v06_market_resources SET status=?,reviewed_by=?,reviewed_at=?,review_note=?,updated_at=? WHERE id=?", (status, actor, ts, note or None, ts, resource_id))
            updated = dict(conn.execute("SELECT * FROM v06_market_resources WHERE id=?", (resource_id,)).fetchone())
            record_audit(conn, action="resource.reviewed", target_type="market_resource", target_id=resource_id,
                         actor=actor, actor_user_id=actor_user_id, before={"status": resource["status"]},
                         after={"status": status}, reason=note, pilot_batch_id=resource.get("pilot_batch_id"))
            if decision == "approved":
                emit_domain_event(conn, event_type="resource.approved", aggregate_type="market_resource",
                                  aggregate_id=resource_id, payload={"direction": resource["direction"]},
                                  actor_user_id=actor_user_id, pilot_batch_id=resource.get("pilot_batch_id"))
            return {"resource": updated, "idempotent": False}

    def generate_matches(self, *, pilot_batch_id: str | None = None) -> list[dict[str, Any]]:
        ts = now_iso()
        created: list[dict[str, Any]] = []
        with db_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            resource_where = "status='published' AND (valid_until IS NULL OR date(valid_until)>=date(?))"
            resource_params: list[Any] = [ts[:10]]
            if pilot_batch_id:
                resource_where += " AND pilot_batch_id=?"
                resource_params.append(pilot_batch_id)
            resources = [dict(row) for row in conn.execute(
                f"SELECT * FROM v06_market_resources WHERE {resource_where} ORDER BY id", resource_params,
            ).fetchall()]
            demands = [row for row in resources if row["direction"] == "demand"]
            supplies = [row for row in resources if row["direction"] == "supply"]
            p3_available = conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='p3_canonical_relationships'").fetchone() is not None
            for demand in demands:
                for supply in supplies:
                    if demand["id"] == supply["id"] or (demand.get("organization_id") and demand.get("organization_id") == supply.get("organization_id")):
                        continue
                    score, reasons, risks, evidence, paths = 0, [], [], [], []
                    if demand["resource_type"] == supply["resource_type"]:
                        score += 40; reasons.append("资源类型一致")
                    demand_tags = set(filter(None, str(demand.get("tags") or demand.get("industry_direction") or "").replace("，", ",").split(",")))
                    supply_tags = set(filter(None, str(supply.get("tags") or supply.get("industry_direction") or "").replace("，", ",").split(",")))
                    common_tags = sorted(demand_tags & supply_tags)
                    if common_tags:
                        score += min(25, len(common_tags) * 10); reasons.append(f"共同产业标签：{'、'.join(common_tags)}")
                    if demand.get("region") and supply.get("region") and demand["region"] == supply["region"]:
                        score += 15; reasons.append("地区一致")
                    if p3_available and demand.get("organization_id") and supply.get("organization_id"):
                        d_ext = conn.execute("SELECT external_id FROM organizations WHERE id=?", (demand["organization_id"],)).fetchone()
                        s_ext = conn.execute("SELECT external_id FROM organizations WHERE id=?", (supply["organization_id"],)).fetchone()
                        if d_ext and s_ext:
                            relation = conn.execute(
                                """
                                SELECT relationship_no,relationship_type FROM p3_canonical_relationships
                                WHERE review_status='approved' AND ((subject_id=? AND object_id=?) OR (subject_id=? AND object_id=?)) LIMIT 1
                                """, (d_ext[0], s_ext[0], s_ext[0], d_ext[0]),
                            ).fetchone()
                            if relation:
                                score += 20; reasons.append("P3存在已确认主体关系")
                                paths.append({"relationship_no": relation["relationship_no"], "relationship_type": relation["relationship_type"]})
                                evidence.append({"source": "p3_canonical_relationship", "id": relation["relationship_no"]})
                    elif not p3_available:
                        risks.append("P3关系表未迁入当前数据库，未计算可信关系距离")
                    if score <= 0:
                        continue
                    existing = conn.execute("SELECT * FROM p4_resource_match_candidates WHERE demand_resource_id=? AND supply_resource_id=?", (demand["id"], supply["id"])).fetchone()
                    if existing:
                        continue
                    cur = conn.execute(
                        """
                        INSERT INTO p4_resource_match_candidates(
                          match_no,demand_resource_id,supply_resource_id,recommended_person_id,recommended_organization_id,
                          score,reasons_json,relationship_path_json,common_contacts_json,risks_json,evidence_json,
                          generation_method,status,pilot_batch_id,created_at,updated_at
                        ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,'pending',?,?,?)
                        """,
                        (_number("QBMAT"), demand["id"], supply["id"], supply.get("owner_person_id"), supply.get("organization_id"),
                         min(100, score), _json(reasons), _json(paths), _json([]), _json(risks), _json(evidence),
                         "controlled_rule_v1", pilot_batch_id or demand.get("pilot_batch_id") or supply.get("pilot_batch_id"), ts, ts),
                    )
                    created.append(dict(conn.execute("SELECT * FROM p4_resource_match_candidates WHERE id=?", (cur.lastrowid,)).fetchone()))
        return created

    def review_match(
        self, match_id: int, *, decision: str, actor: str, actor_user_id: int | None = None, note: str = "",
    ) -> dict[str, Any]:
        if decision not in {"reviewed", "accepted", "rejected", "introduced", "closed"}:
            raise ClubOperationError(400, "INVALID_MATCH_DECISION", "无效匹配状态")
        ts = now_iso()
        with db_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            match = _row(conn.execute("SELECT * FROM p4_resource_match_candidates WHERE id=?", (match_id,)).fetchone())
            if not match:
                raise ClubOperationError(404, "MATCH_NOT_FOUND", "匹配候选不存在")
            if match["status"] == decision:
                return {"match": match, "idempotent": True}
            conn.execute("UPDATE p4_resource_match_candidates SET status=?,reviewed_by=?,reviewed_at=?,review_note=?,updated_at=? WHERE id=?", (decision, actor, ts, note or None, ts, match_id))
            updated = dict(conn.execute("SELECT * FROM p4_resource_match_candidates WHERE id=?", (match_id,)).fetchone())
            record_audit(conn, action="match.reviewed", target_type="resource_match", target_id=match_id,
                         actor=actor, actor_user_id=actor_user_id, before={"status": match["status"]},
                         after={"status": decision}, reason=note, pilot_batch_id=match.get("pilot_batch_id"))
            if decision == "accepted":
                emit_domain_event(conn, event_type="match.accepted", aggregate_type="resource_match",
                                  aggregate_id=match_id, payload={"demand_resource_id": match["demand_resource_id"], "supply_resource_id": match["supply_resource_id"]},
                                  actor_user_id=actor_user_id, pilot_batch_id=match.get("pilot_batch_id"))
            return {"match": updated, "idempotent": False}

    def create_lead_from_match(
        self, match_id: int, *, actor: str, actor_user_id: int | None = None,
    ) -> dict[str, Any]:
        ts = now_iso()
        with db_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            match = _row(conn.execute("SELECT * FROM p4_resource_match_candidates WHERE id=?", (match_id,)).fetchone())
            if not match or match["status"] not in {"accepted", "introduced", "converted_to_lead"}:
                raise ClubOperationError(409, "ACCEPTED_MATCH_REQUIRED", "仅已接受匹配可生成线索候选")
            existing = conn.execute("SELECT * FROM p4_club_lead_candidates WHERE source_type='resource_match' AND source_id=?", (str(match_id),)).fetchone()
            if existing:
                return dict(existing)
            demand = dict(conn.execute("SELECT * FROM v06_market_resources WHERE id=?", (match["demand_resource_id"],)).fetchone())
            supply = dict(conn.execute("SELECT * FROM v06_market_resources WHERE id=?", (match["supply_resource_id"],)).fetchone())
            cur = conn.execute(
                """
                INSERT INTO p4_club_lead_candidates(
                  lead_no,title,source_type,source_id,demand_organization_id,supply_organization_id,
                  person_ids_json,organization_ids_json,reason,evidence_json,owner_user_id,priority,next_action,
                  status,pilot_batch_id,created_at,updated_at
                ) VALUES (?,?, 'resource_match',?,?,?,?,?,?,?,?,'P2',?,'pending',?,?,?)
                """,
                (_number("QBL"), f"{demand['title']} × {supply['title']}", str(match_id), demand.get("organization_id"),
                 supply.get("organization_id"), _json([value for value in [demand.get("owner_person_id"), supply.get("owner_person_id")] if value]),
                 _json([value for value in [demand.get("organization_id"), supply.get("organization_id")] if value]),
                 "人工接受的资源匹配候选", match["evidence_json"], actor_user_id, "由运营确认双方联系意愿",
                 match.get("pilot_batch_id"), ts, ts),
            )
            lead = dict(conn.execute("SELECT * FROM p4_club_lead_candidates WHERE id=?", (cur.lastrowid,)).fetchone())
            conn.execute("UPDATE p4_resource_match_candidates SET status='converted_to_lead',updated_at=? WHERE id=?", (ts, match_id))
            record_audit(conn, action="lead.created", target_type="club_lead_candidate", target_id=lead["id"],
                         actor=actor, actor_user_id=actor_user_id, after={"status": "pending"},
                         pilot_batch_id=match.get("pilot_batch_id"))
            emit_domain_event(conn, event_type="lead.created", aggregate_type="club_lead_candidate",
                              aggregate_id=lead["id"], payload={"source_type": "resource_match", "source_id": match_id},
                              actor_user_id=actor_user_id, pilot_batch_id=match.get("pilot_batch_id"))
            return lead

    def generate_event_relationship_candidates(self, club_event_id: int) -> list[dict[str, Any]]:
        ts = now_iso()
        created: list[dict[str, Any]] = []
        with db_connection(self.db_path) as conn:
            event = _row(conn.execute("SELECT * FROM v05c_club_event_profiles WHERE id=?", (club_event_id,)).fetchone())
            if not event:
                raise ClubOperationError(404, "EVENT_NOT_FOUND", "活动不存在")
            participants = [dict(row) for row in conn.execute(
                """
                SELECT r.id AS registration_id,r.person_id,r.organization_id,r.applicant_name
                FROM v05c_club_event_registrations r
                WHERE r.club_event_id=? AND r.lifecycle_status='checked_in' AND r.person_id IS NOT NULL
                ORDER BY r.id
                """, (club_event_id,),
            ).fetchall()]
            conn.execute("BEGIN IMMEDIATE")
            for index, left in enumerate(participants):
                for right in participants[index + 1:]:
                    if left["person_id"] == right["person_id"]:
                        continue
                    evidence = [{"club_event_id": club_event_id, "event_no": event["event_no"],
                                 "registration_ids": [left["registration_id"], right["registration_id"]],
                                 "statement": "仅证明同场签到，不代表认识或合作"}]
                    try:
                        cur = conn.execute(
                            """
                            INSERT INTO p4_event_relationship_candidates(
                              candidate_no,club_event_id,relationship_type,subject_type,subject_id,object_type,object_id,
                              evidence_json,confidence,status,pilot_batch_id,created_at,updated_at
                            ) VALUES (?,?,'attended_same_event','person',?,'person',?,?,25,'pending',?,?,?)
                            """,
                            (_number("QBREL"), club_event_id, str(left["person_id"]), str(right["person_id"]),
                             _json(evidence), event.get("pilot_batch_id"), ts, ts),
                        )
                    except sqlite3.IntegrityError:
                        continue
                    created.append(dict(conn.execute("SELECT * FROM p4_event_relationship_candidates WHERE id=?", (cur.lastrowid,)).fetchone()))
        return created
    def review_event_relationship(
        self, candidate_id: int, *, decision: str, actor: str, note: str = "",
    ) -> dict[str, Any]:
        if decision not in {"reviewed", "accepted", "rejected", "closed"}:
            raise ClubOperationError(400, "INVALID_RELATIONSHIP_DECISION", "无效关系候选状态")
        ts = now_iso()
        with db_connection(self.db_path) as conn:
            conn.execute("BEGIN IMMEDIATE")
            candidate = _row(conn.execute("SELECT * FROM p4_event_relationship_candidates WHERE id=?", (candidate_id,)).fetchone())
            if not candidate:
                raise ClubOperationError(404, "RELATIONSHIP_CANDIDATE_NOT_FOUND", "关系候选不存在")
            if candidate["status"] == decision:
                return {"candidate": candidate, "idempotent": True}
            conn.execute("UPDATE p4_event_relationship_candidates SET status=?,reviewed_by=?,reviewed_at=?,review_note=?,updated_at=? WHERE id=?", (decision, actor, ts, note or None, ts, candidate_id))
            return {"candidate": dict(conn.execute("SELECT * FROM p4_event_relationship_candidates WHERE id=?", (candidate_id,)).fetchone()), "idempotent": False}

    def deposit_feedback(self, feedback_id: int, *, actor_user_id: int) -> dict[str, Any]:
        with db_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT f.*,r.canonical_membership_id,r.membership_id,r.person_id,r.organization_id
                FROM p4_event_feedback f JOIN v05c_club_event_registrations r ON r.id=f.registration_id
                WHERE f.id=?
                """, (feedback_id,),
            ).fetchone()
            if not row:
                raise ClubOperationError(404, "FEEDBACK_NOT_FOUND", "反馈不存在")
            feedback = dict(row)
        membership_id = feedback.get("canonical_membership_id") or feedback.get("membership_id")
        resources = []
        if membership_id and feedback.get("new_demand"):
            resources.append(self.create_member_resource(
                int(membership_id), direction="demand", actor_user_id=actor_user_id,
                fields={"title": str(feedback["new_demand"])[:120], "description": feedback["new_demand"],
                        "resource_type": "活动反馈资源", "source_event_id": feedback["club_event_id"],
                        "pilot_batch_id": feedback.get("pilot_batch_id"), "status": "draft"},
            ))
        if membership_id and feedback.get("new_supply"):
            resources.append(self.create_member_resource(
                int(membership_id), direction="supply", actor_user_id=actor_user_id,
                fields={"title": str(feedback["new_supply"])[:120], "description": feedback["new_supply"],
                        "resource_type": "活动反馈资源", "source_event_id": feedback["club_event_id"],
                        "pilot_batch_id": feedback.get("pilot_batch_id"), "status": "draft"},
            ))
        lead = None
        if feedback.get("cooperation_intent"):
            ts = now_iso()
            with db_connection(self.db_path) as conn:
                existing = conn.execute("SELECT * FROM p4_club_lead_candidates WHERE source_type='event_feedback' AND source_id=?", (str(feedback_id),)).fetchone()
                if existing:
                    lead = dict(existing)
                else:
                    cur = conn.execute(
                        """
                        INSERT INTO p4_club_lead_candidates(
                          lead_no,title,source_type,source_id,demand_organization_id,person_ids_json,organization_ids_json,
                          reason,evidence_json,owner_user_id,priority,next_action,status,pilot_batch_id,created_at,updated_at
                        ) VALUES (?,?,'event_feedback',?,?,?,?,?,?,?,'P2',?,'pending',?,?,?)
                        """,
                        (_number("QBL"), f"活动反馈合作意向：{str(feedback['cooperation_intent'])[:80]}", str(feedback_id),
                         feedback.get("organization_id"), _json([feedback["person_id"]] if feedback.get("person_id") else []),
                         _json([feedback["organization_id"]] if feedback.get("organization_id") else []),
                         feedback["cooperation_intent"], _json([{"feedback_id": feedback_id, "club_event_id": feedback["club_event_id"]}]),
                         actor_user_id, "运营核实合作意向并征得双方同意", feedback.get("pilot_batch_id"), ts, ts),
                    )
                    lead = dict(conn.execute("SELECT * FROM p4_club_lead_candidates WHERE id=?", (cur.lastrowid,)).fetchone())
                    emit_domain_event(conn, event_type="lead.created", aggregate_type="club_lead_candidate",
                                      aggregate_id=lead["id"], payload={"source_type": "event_feedback", "source_id": feedback_id},
                                      actor_user_id=actor_user_id, pilot_batch_id=feedback.get("pilot_batch_id"))
        relationships = self.generate_event_relationship_candidates(int(feedback["club_event_id"]))
        return {"resources": resources, "lead": lead, "relationship_candidates": relationships}

class ClubOperationsDashboardService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = _path(db_path)

    @staticmethod
    def _exists(conn: sqlite3.Connection, table: str) -> bool:
        return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

    def summary(self) -> dict[str, Any]:
        today = datetime.now().date().isoformat()
        soon = (datetime.now() + timedelta(days=30)).date().isoformat()
        with db_connection(self.db_path) as conn:
            scalar = lambda sql, params=(): int(conn.execute(sql, params).fetchone()[0] or 0)
            metrics: dict[str, int] = {
                "会员总数": scalar("SELECT COUNT(*) FROM v04f_club_memberships"),
                "正常会员": scalar("SELECT COUNT(*) FROM v04f_club_memberships WHERE status='active'"),
                "待审核申请": scalar("SELECT COUNT(*) FROM v04f_club_applications WHERE status IN ('submitted','under_review','need_more_info')"),
                "即将到期会员": scalar("SELECT COUNT(*) FROM v04f_club_memberships WHERE status='active' AND expired_at IS NOT NULL AND date(expired_at) BETWEEN date(?) AND date(?)", (today, soon)),
                "待审核活动": 0,
                "开放报名活动": scalar("SELECT COUNT(*) FROM v05c_club_event_profiles WHERE status='registration_open'"),
                "待审核报名": scalar("SELECT COUNT(*) FROM v05c_club_event_registrations WHERE status='submitted'"),
                "今日活动": scalar("SELECT COUNT(*) FROM v05c_club_event_profiles p JOIN events e ON e.id=p.event_id WHERE date(e.event_date)=date(?)", (today,)),
                "待签到": scalar("SELECT COUNT(*) FROM v05c_club_event_registrations WHERE status='approved' AND checked_in_at IS NULL"),
                "活动后待跟进": 0,
                "有效需求": scalar("SELECT COUNT(*) FROM v06_market_resources WHERE direction='demand' AND status='published' AND (valid_until IS NULL OR date(valid_until)>=date(?))", (today,)),
                "有效供给": scalar("SELECT COUNT(*) FROM v06_market_resources WHERE direction='supply' AND status='published' AND (valid_until IS NULL OR date(valid_until)>=date(?))", (today,)),
                "待审核匹配": 0,
                "推进中匹配": 0,
                "潜在线索": 0,
                "待处理任务": scalar("SELECT COUNT(*) FROM actions WHERE status NOT IN ('已完成','completed','closed','cancelled')"),
            }
            if self._exists(conn, "p4_resource_match_candidates"):
                metrics["待审核活动"] = scalar("SELECT COUNT(*) FROM v05c_club_event_profiles WHERE lifecycle_status='pending_review'")
                metrics["开放报名活动"] = scalar("SELECT COUNT(*) FROM v05c_club_event_profiles WHERE lifecycle_status='registration_open'")
                metrics["待审核报名"] = scalar("SELECT COUNT(*) FROM v05c_club_event_registrations WHERE lifecycle_status='pending_review'")
                metrics["待签到"] = scalar("SELECT COUNT(*) FROM v05c_club_event_registrations WHERE lifecycle_status='approved'")
                metrics["活动后待跟进"] = scalar(
                    """SELECT COUNT(*) FROM v05c_club_event_registrations r
                       JOIN v05c_club_event_profiles e ON e.id=r.club_event_id
                       LEFT JOIN p4_event_feedback f ON f.registration_id=r.id
                       WHERE e.lifecycle_status IN ('completed','archived') AND r.lifecycle_status='checked_in' AND f.id IS NULL"""
                )
                metrics["待审核匹配"] = scalar("SELECT COUNT(*) FROM p4_resource_match_candidates WHERE status IN ('pending','reviewed')")
                metrics["推进中匹配"] = scalar("SELECT COUNT(*) FROM p4_resource_match_candidates WHERE status IN ('accepted','introduced','converted_to_lead')")
                metrics["潜在线索"] = scalar("SELECT COUNT(*) FROM p4_club_lead_candidates WHERE status IN ('pending','reviewed','accepted')")
            queues = {
                "会员审核": "/club/admin/applications", "活动管理": "/club/events",
                "供需审核": "/club/resources", "匹配管理": "/club/matches",
                "会后关系候选": "/club/relationship-candidates", "潜在线索": "/club/leads",
            }
            return {"metrics": metrics, "queues": queues, "generated_at": now_iso()}

    def domain_events(self, *, status: str = "pending", limit: int = 100) -> list[dict[str, Any]]:
        with db_connection(self.db_path) as conn:
            if not self._exists(conn, "p4_domain_events"):
                return []
            return [dict(row) for row in conn.execute(
                "SELECT * FROM p4_domain_events WHERE status=? ORDER BY id LIMIT ?", (status, max(1, min(limit, 500))),
            ).fetchall()]
