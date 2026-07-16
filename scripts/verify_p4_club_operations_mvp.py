from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.club_operations_service import (
    ClubEventService,
    ClubMembershipService,
    ClubResourceMatchingService,
)
from app.settings import resolved_db_path

PILOT_BATCH_ID = "P4-CLUB-OPERATIONS-MVP"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _formal_counts(path: Path) -> dict[str, int]:
    with closing(sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)) as conn:
        return {
            table: int(conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0])
            for table in (
                "people", "organizations", "v04f_club_memberships", "v05c_club_event_profiles",
                "v05c_club_event_registrations", "v05c_club_event_participation",
                "v06_market_resources", "v06_opportunities",
            )
        }


def _migrate_copy(path: Path) -> None:
    for script in (
        ROOT / "scripts" / "migrations" / "006_entity_relationship_network.py",
        ROOT / "scripts" / "migrations" / "007_club_operations_mvp.py",
    ):
        completed = subprocess.run(
            [sys.executable, str(script), "--apply", "--db", str(path)],
            cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        if completed.returncode:
            raise RuntimeError(f"migration_failed:{script.name}:{completed.stderr or completed.stdout}")


def _create_users(conn: sqlite3.Connection, person_ids: list[int]) -> list[int]:
    ts = datetime.now().replace(microsecond=0).isoformat()
    user_ids = []
    for index, person_id in enumerate(person_ids, 1):
        username = f"p4_pilot_member_{index}"
        row = conn.execute("SELECT id FROM v05a_users WHERE username=?", (username,)).fetchone()
        if row:
            user_ids.append(int(row[0]))
            continue
        cur = conn.execute(
            """
            INSERT INTO v05a_users(
              username,password_hash,display_name,role,status,created_by,created_at,updated_at,person_id
            ) VALUES (?,?,?,?,?,'p4_pilot',?,?,?)
            """,
            (username, "pilot-account-disabled", f"P4试点会员{index}", "viewer", "active", ts, ts, person_id),
        )
        user_ids.append(int(cur.lastrowid))
    return user_ids


def _create_event(conn: sqlite3.Connection, index: int, organization_id: int, capacity: int) -> int:
    ts = datetime.now().replace(microsecond=0).isoformat()
    external_id = f"P4-PILOT-EVENT-{index}"
    event = conn.execute("SELECT id FROM events WHERE external_id=?", (external_id,)).fetchone()
    if event:
        event_id = int(event[0])
    else:
        # Some legacy copies contain club profiles whose event_id is not yet
        # present in events. Never let a pilot insert reuse such a dangling ID.
        next_event_id = int(conn.execute(
            """
            SELECT MAX(value) + 1 FROM (
              SELECT COALESCE(MAX(id), 0) AS value FROM events
              UNION ALL
              SELECT COALESCE(MAX(event_id), 0) AS value FROM v05c_club_event_profiles
            )
            """
        ).fetchone()[0])
        cur = conn.execute(
            """
            INSERT INTO events(
              id,external_id,event_date,name,event_type,fact_summary,visibility,verification_status,
              created_at,source_type,manually_confirmed,is_active,subject_manually_confirmed
            ) VALUES (?,?,?,?,?,?,'internal','已确认',?,'P4受控试点',1,1,1)
            """,
            (next_event_id, external_id, datetime.now().date().isoformat(), f"P4试点活动{index}", "qbay_club",
             "仅存在于数据库副本的P4受控试点活动", ts),
        )
        event_id = int(cur.lastrowid)
    profile = conn.execute("SELECT id FROM v05c_club_event_profiles WHERE event_id=?", (event_id,)).fetchone()
    if profile:
        return int(profile[0])
    cur = conn.execute(
        """
        INSERT INTO v05c_club_event_profiles(
          event_id,event_no,event_type,registration_status,capacity,organizer,owner,visibility,
          member_only,status,lifecycle_status,topic,channel,audience,review_mode,industry_tags,
          pilot_batch_id,created_at,updated_at
        ) VALUES (?,?,?,'closed',?,?,?,'controlled',0,'draft','draft',?,'offline','会员与受邀嘉宾',
                  'manual','生物医药',?,?,?)
        """,
        (event_id, f"P4-EVT-{index}", "qbay_club", capacity, f"机构{organization_id}",
         "p4_pilot_operator", f"P4试点主题{index}", PILOT_BATCH_ID, ts, ts),
    )
    return int(cur.lastrowid)


def _pilot_counts(conn: sqlite3.Connection) -> dict[str, int]:
    scalar = lambda sql, params=(): int(conn.execute(sql, params).fetchone()[0] or 0)
    return {
        "members": scalar("SELECT COUNT(*) FROM v04f_club_memberships WHERE pilot_batch_id=?", (PILOT_BATCH_ID,)),
        "organizations": scalar(
            "SELECT COUNT(DISTINCT organization_id) FROM v04f_club_memberships WHERE pilot_batch_id=?", (PILOT_BATCH_ID,)
        ),
        "events": scalar("SELECT COUNT(*) FROM v05c_club_event_profiles WHERE pilot_batch_id=?", (PILOT_BATCH_ID,)),
        "registrations": scalar("SELECT COUNT(*) FROM v05c_club_event_registrations WHERE pilot_batch_id=?", (PILOT_BATCH_ID,)),
        "waitlisted": scalar("SELECT COUNT(*) FROM v05c_club_event_registrations WHERE pilot_batch_id=? AND lifecycle_status='waitlisted'", (PILOT_BATCH_ID,)),
        "cancelled": scalar("SELECT COUNT(*) FROM v05c_club_event_registrations WHERE pilot_batch_id=? AND lifecycle_status='cancelled'", (PILOT_BATCH_ID,)),
        "waitlist_promotions": scalar("SELECT COUNT(*) FROM p4_operation_audit WHERE pilot_batch_id=? AND action='registration.waitlist_promoted'", (PILOT_BATCH_ID,)),
        "rejected_matches": scalar("SELECT COUNT(*) FROM p4_resource_match_candidates WHERE pilot_batch_id=? AND status='rejected'", (PILOT_BATCH_ID,)),
        "cancelled_participations": scalar(
            "SELECT COUNT(*) FROM v05c_club_event_participation p JOIN v05c_club_event_registrations r ON r.id=p.registration_id WHERE r.pilot_batch_id=? AND r.lifecycle_status='cancelled'",
            (PILOT_BATCH_ID,),
        ),
        "checkins": scalar("SELECT COUNT(*) FROM v05c_club_event_registrations WHERE pilot_batch_id=? AND lifecycle_status='checked_in'", (PILOT_BATCH_ID,)),
        "feedback": scalar("SELECT COUNT(*) FROM p4_event_feedback WHERE pilot_batch_id=?", (PILOT_BATCH_ID,)),
        "demands": scalar("SELECT COUNT(*) FROM v06_market_resources WHERE pilot_batch_id=? AND direction='demand'", (PILOT_BATCH_ID,)),
        "supplies": scalar("SELECT COUNT(*) FROM v06_market_resources WHERE pilot_batch_id=? AND direction='supply'", (PILOT_BATCH_ID,)),
        "matches": scalar("SELECT COUNT(*) FROM p4_resource_match_candidates WHERE pilot_batch_id=?", (PILOT_BATCH_ID,)),
        "relationship_candidates": scalar("SELECT COUNT(*) FROM p4_event_relationship_candidates WHERE pilot_batch_id=?", (PILOT_BATCH_ID,)),
        "lead_candidates": scalar("SELECT COUNT(*) FROM p4_club_lead_candidates WHERE pilot_batch_id=?", (PILOT_BATCH_ID,)),
        "opportunities": scalar("SELECT COUNT(*) FROM v06_opportunities"),
    }


def run_pilot(source_db: Path) -> dict[str, Any]:
    source_db = source_db.resolve()
    source_sha_before = _sha256(source_db)
    source_counts_before = _formal_counts(source_db)
    with tempfile.TemporaryDirectory(prefix="p4_club_pilot_") as temp_dir:
        copy_path = Path(temp_dir) / "p4_pilot.db"
        shutil.copy2(source_db, copy_path)
        _migrate_copy(copy_path)
        membership_service = ClubMembershipService(copy_path)
        event_service = ClubEventService(copy_path)
        resource_service = ClubResourceMatchingService(copy_path)

        with closing(sqlite3.connect(copy_path)) as conn:
            conn.row_factory = sqlite3.Row
            people = [int(row[0]) for row in conn.execute(
                """
                SELECT p.id FROM people p
                WHERE p.id NOT IN (SELECT person_id FROM v04f_club_memberships WHERE person_id IS NOT NULL)
                  AND p.id NOT IN (SELECT person_id FROM v05a_users WHERE person_id IS NOT NULL)
                ORDER BY p.id LIMIT 5
                """
            ).fetchall()]
            organizations = [int(row[0]) for row in conn.execute("SELECT id FROM organizations ORDER BY id LIMIT 2").fetchall()]
            if len(people) < 5 or len(organizations) < 2:
                raise RuntimeError("pilot_requires_five_people_and_two_organizations")
            users = _create_users(conn, people)
            conn.commit()

        memberships: list[dict[str, Any]] = []
        for index, (person_id, user_id) in enumerate(zip(people, users)):
            organization_id = organizations[index % 2]
            application = membership_service.submit_application(
                {
                    "person_id": person_id, "user_id": user_id, "organization_id": organization_id,
                    "member_type": "standard", "professional_direction": "生物医药",
                    "offered_resources": f"P4试点供给{index + 1}", "cooperation_needs": f"P4试点需求{index + 1}",
                    "application_reason": "P4受控试点", "pilot_batch_id": PILOT_BATCH_ID,
                }, actor_user_id=user_id,
            )
            reviewed = membership_service.review_application(
                application["id"], decision="approved", actor="p4_pilot_operator",
                actor_user_id=user_id, note="P4受控试点审核",
            )
            activated = membership_service.transition_membership(
                reviewed["membership"]["id"], action="activate", actor="p4_pilot_operator",
                actor_user_id=user_id, reason="P4受控试点激活",
            )
            memberships.append(activated["membership"])

        with closing(sqlite3.connect(copy_path)) as conn:
            event_ids = [
                _create_event(conn, 1, organizations[0], 4),
                _create_event(conn, 2, organizations[1], 10),
            ]
            conn.commit()

        duplicate_registration_idempotent = False
        registrations_by_event: dict[int, list[dict[str, Any]]] = {}
        for event_index, club_event_id in enumerate(event_ids, 1):
            event_service.transition_event(club_event_id, action="publish", actor="p4_pilot_operator")
            event_service.transition_event(club_event_id, action="open", actor="p4_pilot_operator")
            registrations = []
            for member_index, member in enumerate(memberships, 1):
                registration = event_service.register(
                    club_event_id,
                    {
                        "membership_id": member["id"], "user_id": member["user_id"],
                        "person_id": member["person_id"], "organization_id": member["organization_id"],
                        "applicant_name": f"P4试点会员{member_index}", "organization_name": f"试点机构{member_index % 2 + 1}",
                        "application_reason": "参加P4受控试点活动", "interest_direction": "生物医药合作",
                        "desired_connections": "寻找合作伙伴", "pilot_batch_id": PILOT_BATCH_ID,
                    }, actor_user_id=int(member["user_id"]),
                )
                reviewed = event_service.review_registration(
                    club_event_id, registration["id"], decision="approved", actor="p4_pilot_operator",
                    actor_user_id=int(member["user_id"]), note="P4试点报名审核",
                )
                registrations.append(reviewed["registration"])
            registrations_by_event[club_event_id] = registrations
            if event_index == 1:
                member = memberships[0]
                duplicate = event_service.register(
                    club_event_id,
                    {
                        "membership_id": member["id"], "user_id": member["user_id"],
                        "person_id": member["person_id"], "organization_id": member["organization_id"],
                        "applicant_name": "P4试点会员1", "pilot_batch_id": PILOT_BATCH_ID,
                    }, actor_user_id=int(member["user_id"]),
                )
                duplicate_registration_idempotent = bool(
                    duplicate.get("idempotent") and duplicate["id"] == registrations[0]["id"]
                )

        first_event_registration = registrations_by_event[event_ids[0]][0]
        event_service.review_registration(
            event_ids[0], first_event_registration["id"], decision="cancelled",
            actor="p4_pilot_operator", note="P4试点释放名额",
        )
        with closing(sqlite3.connect(copy_path)) as conn:
            conn.row_factory = sqlite3.Row
            for club_event_id in event_ids:
                registrations_by_event[club_event_id] = [dict(row) for row in conn.execute(
                    "SELECT * FROM v05c_club_event_registrations WHERE club_event_id=? ORDER BY id",
                    (club_event_id,),
                ).fetchall()]


        checked_in: list[tuple[int, dict[str, Any]]] = []
        for event_index, club_event_id in enumerate(event_ids):
            approved = [row for row in registrations_by_event[club_event_id] if row["lifecycle_status"] == "approved"][:3]
            for index, registration in enumerate(approved):
                if event_index == 0 and index == 0:
                    token = event_service.issue_checkin_token(club_event_id, registration["id"], actor_user_id=registration["user_id"])
                    result = event_service.check_in(
                        club_event_id, token=token["token"], actor="p4_pilot_operator",
                        actor_user_id=registration["user_id"], method="token",
                    )
                else:
                    result = event_service.check_in(
                        club_event_id, registration_id=registration["id"], actor="p4_pilot_operator",
                        actor_user_id=registration["user_id"], method="manual",
                    )
                checked_in.append((club_event_id, result["registration"]))
            event_service.transition_event(club_event_id, action="start", actor="p4_pilot_operator")
            event_service.transition_event(club_event_id, action="complete", actor="p4_pilot_operator")

        first_event_checked = [item for item in checked_in if item[0] == event_ids[0]][:3]
        for index, (club_event_id, registration) in enumerate(first_event_checked, 1):
            feedback = event_service.submit_feedback(
                club_event_id, registration["id"],
                {
                    "satisfaction_score": 5, "content_score": 4, "speaker_score": 4,
                    "organization_score": 5, "content_feedback": f"P4试点反馈{index}",
                    "cooperation_intent": f"P4试点合作意向{index}",
                    "new_demand": f"P4试点需求资源{index}", "new_supply": f"P4试点供给资源{index}",
                    "suggestions": "继续组织专题交流",
                }, actor_user_id=registration["user_id"],
            )
            resource_service.deposit_feedback(feedback["id"], actor_user_id=registration["user_id"])

        with closing(sqlite3.connect(copy_path)) as conn:
            resource_ids = [int(row[0]) for row in conn.execute(
                "SELECT id FROM v06_market_resources WHERE pilot_batch_id=? ORDER BY id", (PILOT_BATCH_ID,)
            ).fetchall()]
        for resource_id in resource_ids:
            resource_service.review_resource(
                resource_id, decision="approved", actor="p4_pilot_operator", note="P4试点资源审核",
            )
        matches = resource_service.generate_matches(pilot_batch_id=PILOT_BATCH_ID)
        if matches:
            resource_service.review_match(matches[0]["id"], decision="accepted", actor="p4_pilot_operator")
            resource_service.create_lead_from_match(matches[0]["id"], actor="p4_pilot_operator")
        resource_service.generate_event_relationship_candidates(event_ids[0])

        if len(matches) > 1:
            resource_service.review_match(matches[1]["id"], decision="rejected", actor="p4_pilot_operator", note="P4试点拒绝")
        duplicate_matches_prevented = not resource_service.generate_matches(pilot_batch_id=PILOT_BATCH_ID)
        with closing(sqlite3.connect(copy_path)) as conn:
            counts = _pilot_counts(conn)
            total_opportunities = int(conn.execute("SELECT COUNT(*) FROM v06_opportunities").fetchone()[0])
            pilot_missing = {
                "v04f_club_applications": int(conn.execute(
                    """SELECT COUNT(*) FROM v04f_club_applications a JOIN v05a_users u ON u.id=a.user_id
                       WHERE u.username LIKE 'p4_pilot_member_%' AND a.pilot_batch_id<>?""", (PILOT_BATCH_ID,)
                ).fetchone()[0]),
                "v04f_club_memberships": int(conn.execute(
                    """SELECT COUNT(*) FROM v04f_club_memberships m JOIN v05a_users u ON u.id=m.user_id
                       WHERE u.username LIKE 'p4_pilot_member_%' AND m.pilot_batch_id<>?""", (PILOT_BATCH_ID,)
                ).fetchone()[0]),
                "v05c_club_event_profiles": int(conn.execute(
                    """SELECT COUNT(*) FROM v05c_club_event_profiles p JOIN events e ON e.id=p.event_id
                       WHERE e.external_id LIKE 'P4-PILOT-EVENT-%' AND p.pilot_batch_id<>?""", (PILOT_BATCH_ID,)
                ).fetchone()[0]),
                "v05c_club_event_registrations": int(conn.execute(
                    """SELECT COUNT(*) FROM v05c_club_event_registrations r JOIN v05c_club_event_profiles p ON p.id=r.club_event_id
                       WHERE p.pilot_batch_id=? AND r.pilot_batch_id<>?""", (PILOT_BATCH_ID, PILOT_BATCH_ID)
                ).fetchone()[0]),
                "v05c_club_event_participation": int(conn.execute(
                    """SELECT COUNT(*) FROM v05c_club_event_participation p JOIN v05c_club_event_registrations r ON r.id=p.registration_id
                       WHERE r.pilot_batch_id=? AND p.pilot_batch_id<>?""", (PILOT_BATCH_ID, PILOT_BATCH_ID)
                ).fetchone()[0]),
                "v06_market_resources": int(conn.execute(
                    "SELECT COUNT(*) FROM v06_market_resources WHERE title LIKE 'P4试点%' AND pilot_batch_id<>?", (PILOT_BATCH_ID,)
                ).fetchone()[0]),
            }
            for table in (
                "p4_event_feedback", "p4_checkin_tokens", "p4_checkin_audit",
                "p4_event_relationship_candidates", "p4_resource_match_candidates",
                "p4_club_lead_candidates", "p4_domain_events", "p4_operation_audit",
            ):
                pilot_missing[table] = int(conn.execute(
                    f'SELECT COUNT(*) FROM "{table}" WHERE pilot_batch_id IS NULL OR pilot_batch_id<>?',
                    (PILOT_BATCH_ID,),
                ).fetchone()[0])

        validations = {
            "five_members": counts["members"] == 5,
            "two_organizations": counts["organizations"] == 2,
            "two_events": counts["events"] == 2,
            "registrations_8_to_12": 8 <= counts["registrations"] <= 12,
            "waitlist_consumed_after_cancellation": counts["waitlisted"] == 0,
            "cancelled_slot_recorded": counts["cancelled"] == 1,
            "waitlist_promoted": counts["waitlist_promotions"] == 1,
            "duplicate_registration_prevented": duplicate_registration_idempotent,
            "cancelled_has_no_participation": counts["cancelled_participations"] == 0,
            "at_least_five_checkins": counts["checkins"] >= 5,
            "at_least_three_feedback": counts["feedback"] >= 3,
            "three_demands": counts["demands"] == 3,
            "three_supplies": counts["supplies"] == 3,
            "at_least_three_matches": counts["matches"] >= 3,
            "rejected_match_not_pending": counts["rejected_matches"] >= 1,
            "duplicate_matches_prevented": duplicate_matches_prevented,
            "at_least_two_relationship_candidates": counts["relationship_candidates"] >= 2,
            "at_least_two_lead_candidates": counts["lead_candidates"] >= 2,
            "no_opportunity_created": total_opportunities == source_counts_before["v06_opportunities"],
            "all_pilot_rows_marked": all(value == 0 for value in pilot_missing.values()),
        }
        report = {
            "pilot_batch_id": PILOT_BATCH_ID, "copy_database_name": copy_path.name,
            "counts": counts, "validations": validations, "pilot_marker_missing": pilot_missing,
            "formal_counts_before": source_counts_before,
        }
        if not all(validations.values()):
            raise AssertionError(json.dumps(report, ensure_ascii=False, indent=2))

    source_counts_after = _formal_counts(source_db)
    source_sha_after = _sha256(source_db)
    report.update({
        "formal_counts_after": source_counts_after,
        "formal_sha256_unchanged": source_sha_before == source_sha_after,
        "formal_counts_unchanged": source_counts_before == source_counts_after,
        "status": "passed",
    })
    if not report["formal_sha256_unchanged"] or not report["formal_counts_unchanged"]:
        raise AssertionError("formal_database_changed")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify P4 Q-BAY club operations MVP on a database copy")
    parser.add_argument("--db", type=Path, default=resolved_db_path())
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report = run_pilot(args.db)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
