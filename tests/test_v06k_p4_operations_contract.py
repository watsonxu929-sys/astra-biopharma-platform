from __future__ import annotations

import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.capability_guard import CapabilityGuardMiddleware
from app.security import permissions_for, required_permission
from app.services.club_operations_service import (
    ClubEventService,
    ClubMembershipService,
    ClubOperationsDashboardService,
)
from app.services.schema_preflight import _CACHE, get_schema_preflight
from app.settings import Settings, sqlite_url_from_path
ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def p4_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    source_db = ROOT / "data" / "rehearsal" / "v06j_app_migrated.db"
    assert source_db.exists(), "v0.6J migrated rehearsal database is required"
    db_path = tmp_path / "v06k_p4.db"
    with sqlite3.connect(f"file:{source_db.as_posix()}?mode=ro", uri=True) as source:
        with sqlite3.connect(db_path) as destination:
            source.backup(destination)

    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("APP_DB_PATH", str(db_path))
    monkeypatch.setenv("DATABASE_URL", sqlite_url_from_path(db_path))
    monkeypatch.setenv("APP_AUTH_DISABLED", "true")
    monkeypatch.setenv("ENABLE_SCHEDULER_IN_WEB", "false")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    monkeypatch.setenv("WORKER_ENABLED", "false")
    monkeypatch.setenv("APP_OPEN_BROWSER", "false")
    monkeypatch.setenv("SECRET_KEY", "v06k-test-secret")
    monkeypatch.setenv("SESSION_SECRET", "v06k-test-session-secret")
    _CACHE.clear()
    baseline_metrics = ClubOperationsDashboardService(db_path).summary()["web_metrics"]

    stamp = datetime.now().replace(microsecond=0).isoformat()
    with sqlite3.connect(db_path) as conn:
        person_ids = []
        for number, name in ((1, "会员一"), (2, "会员二")):
            person_ids.append(
                int(
                    conn.execute(
                        """INSERT INTO people(external_id,name,visibility,verification_status,is_active,created_at)
                           VALUES (?,?,'internal','verified',1,?)""",
                        (f"P-V06K-{number}", name, stamp),
                    ).lastrowid
                )
            )
        organization_id = int(
            conn.execute(
                """INSERT INTO organizations(
                       external_id,standard_name,org_type,region,visibility,verification_status,is_active,created_at,updated_at
                   ) VALUES ('ORG-V06K-1','V06K测试机构','company','上海','internal','verified',1,?,?)""",
                (stamp, stamp),
            ).lastrowid
        )
        conn.commit()

    users = []
    with sqlite3.connect(db_path) as conn:
        for username, role in (
            ("v06k_admin", "admin"),
            ("v06k_viewer", "viewer"),
            ("v06k_viewer_two", "viewer"),
        ):
            user_id = int(
                conn.execute(
                    """INSERT INTO v05a_users(username,display_name,password_hash,role,status,created_at,updated_at)
                       VALUES (?,?,'',?,'active',?,?)""",
                    (username, username, role, stamp, stamp),
                ).lastrowid
            )
            users.append({"id": user_id, "username": username, "role": role})
        conn.commit()
    admin, viewer, viewer_two = users
    return {
        "db": db_path,
        "admin": admin,
        "viewer": viewer,
        "viewer_two": viewer_two,
        "person_ids": person_ids,
        "organization_id": organization_id,
        "baseline_metrics": baseline_metrics,
    }


def _membership(
    db_path: Path,
    *,
    person_id: int,
    user_id: int,
    organization_id: int,
    actor_user_id: int,
    suffix: str,
) -> tuple[dict, dict]:
    service = ClubMembershipService(db_path)
    application = service.submit_application(
        {
            "person_id": person_id,
            "user_id": user_id,
            "organization_id": organization_id,
            "mobile": f"1380000{suffix:0>4}",
            "email": f"member{suffix}@v06k.invalid",
            "member_type": "standard",
            "application_reason": "v0.6K闭环验收",
        },
        actor_user_id=user_id,
    )
    reviewed = service.review_application(
        int(application["id"]),
        decision="approved",
        actor="v06k_admin",
        actor_user_id=actor_user_id,
        person_id=person_id,
        organization_id=organization_id,
        user_id=user_id,
    )
    membership = reviewed["membership"]
    activated = service.transition_membership(
        int(membership["id"]),
        action="activate",
        actor="v06k_admin",
        actor_user_id=actor_user_id,
    )
    return application, activated["membership"]


def test_p4_field_contract_uses_joined_events_date(p4_runtime: dict[str, object]) -> None:
    db_path = Path(p4_runtime["db"])
    with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
        event_columns = {row[1] for row in conn.execute("PRAGMA table_info(events)")}
        profile_columns = {row[1] for row in conn.execute("PRAGMA table_info(v05c_club_event_profiles)")}
        registration_columns = {row[1] for row in conn.execute("PRAGMA table_info(v05c_club_event_registrations)")}
        participation_columns = {row[1] for row in conn.execute("PRAGMA table_info(v05c_club_event_participation)")}
        feedback_columns = {row[1] for row in conn.execute("PRAGMA table_info(p4_event_feedback)")}
        profile_fks = conn.execute("PRAGMA foreign_key_list(v05c_club_event_profiles)").fetchall()

    assert "event_date" in event_columns
    assert "event_date" not in profile_columns
    assert {"event_id", "registration_deadline", "status", "lifecycle_status"} <= profile_columns
    assert {"status", "lifecycle_status", "registered_at", "checked_in_at"} <= registration_columns
    assert {"attendance_status", "check_in_time"} <= participation_columns
    assert {"status", "created_at", "updated_at"} <= feedback_columns
    assert any(row[2] == "events" and row[3] == "event_id" and row[4] == "id" for row in profile_fks)

    source = (Path(__file__).resolve().parents[1] / "app" / "v04f_operations.py").read_text(encoding="utf-8")
    assert "FROM v05c_club_event_profiles WHERE status='ongoing' OR (event_date=" not in source
    assert not re.search(r"FROM v05c_club_event_profiles\s+WHERE\s+event_date", source)
    assert "JOIN events e ON e.id=p.event_id" in source

    preflight = get_schema_preflight(refresh=True)
    assert preflight.capability("club_operations").enabled


def test_p4_permissions_and_missing_schema_are_controlled(
    p4_runtime: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    assert required_permission("/club/operations", "GET") == "manage_club"
    assert required_permission("/club/applications", "GET") == "manage_club"
    assert required_permission("/club/events/1/registrations", "GET") == "manage_club"
    assert "manage_club" not in permissions_for({"role": "viewer"})

    monkeypatch.setenv("APP_AUTH_DISABLED", "false")
    from app.main import app

    with TestClient(app) as client:
        assert client.get("/club/operations", follow_redirects=False).status_code in {302, 303, 307, 401, 403}
        assert client.get("/club/applications", follow_redirects=False).status_code in {302, 303, 307, 401, 403}
        assert client.post(
            "/club/events/create",
            data={"name": "越权活动"},
            follow_redirects=False,
        ).status_code in {302, 303, 307, 401, 403}
        assert client.get("/api/v1/club/operations").status_code in {401, 403}

    missing = tmp_path / "missing_p4.db"
    with sqlite3.connect(missing):
        pass
    monkeypatch.setenv("DATABASE_URL", sqlite_url_from_path(missing))
    monkeypatch.setenv("APP_DB_PATH", str(missing))
    _CACHE.clear()
    guarded = FastAPI()
    guarded.add_middleware(CapabilityGuardMiddleware)

    @guarded.get("/club/operations")
    def unexpected() -> dict[str, bool]:
        return {"unexpected": True}

    with TestClient(guarded) as client:
        response = client.get("/club/operations")
    assert response.status_code == 503
    assert "unexpected" not in response.text


def test_p4_closed_loop_persists_after_refresh_and_client_restart(
    p4_runtime: dict[str, object],
) -> None:
    db_path = Path(p4_runtime["db"])
    admin = p4_runtime["admin"]
    viewer = p4_runtime["viewer"]
    viewer_two = p4_runtime["viewer_two"]
    person_one, person_two = p4_runtime["person_ids"]
    organization_id = int(p4_runtime["organization_id"])
    membership_service = ClubMembershipService(db_path)

    application_one = membership_service.submit_application(
        {
            "person_id": person_one,
            "user_id": int(viewer["id"]),
            "organization_id": organization_id,
            "mobile": "13800006001",
            "email": "member1@v06k.invalid",
            "member_type": "standard",
            "application_reason": "v0.6K会员申请",
        },
        actor_user_id=int(viewer["id"]),
    )

    from app.main import app

    with TestClient(app) as client:
        assert client.get("/club").status_code == 200
        assert client.get("/club/events").status_code == 200
        assert client.get("/club/operations").status_code == 200

        applications = client.get("/club/applications")
        assert applications.status_code == 200
        assert str(application_one["application_no"]) in applications.text

        review = client.post(
            f"/club/admin/applications/{application_one['id']}/review",
            data={
                "decision": "approved",
                "person_id": person_one,
                "organization_id": organization_id,
                "user_id": viewer["id"],
                "note": "v0.6K审核通过",
            },
            follow_redirects=False,
        )
        assert review.status_code == 303

        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            membership_one = dict(
                conn.execute(
                    "SELECT * FROM v04f_club_memberships WHERE source=?",
                    (application_one["application_no"],),
                ).fetchone()
            )
        activate = client.post(
            f"/club/members/{membership_one['id']}/lifecycle",
            data={"action": "activate", "reason": "v0.6K验收"},
            follow_redirects=False,
        )
        assert activate.status_code == 303
        members = client.get("/club/members")
        assert members.status_code == 200
        assert "会员一" in members.text

        create = client.post(
            "/club/events/create",
            data={
                "name": "V06K字段契约活动",
                "event_type": "club",
                "event_date": date.today().isoformat(),
                "venue": "上海测试会场",
                "capacity": 10,
                "registration_deadline": date.today().isoformat(),
                "organizer": "Q-BAY",
                "owner": "v06k_admin",
                "visibility": "public",
                "description": "创建时说明",
            },
            follow_redirects=False,
        )
        assert create.status_code == 303
        event_id = int(create.headers["location"].split("?")[0].rstrip("/").split("/")[-1])

        update = client.post(
            f"/club/events/{event_id}/update",
            data={
                "name": "V06K字段契约活动（已更新）",
                "event_date": date.today().isoformat(),
                "venue": "上海更新会场",
                "capacity": 8,
                "registration_deadline": date.today().isoformat(),
                "organizer": "Q-BAY",
                "owner": "v06k_admin",
                "visibility": "public",
                "description": "更新后说明",
            },
            follow_redirects=False,
        )
        assert update.status_code == 303
        detail = client.get(f"/club/events/{event_id}")
        assert detail.status_code == 200
        assert "V06K字段契约活动（已更新）" in detail.text
        assert "上海更新会场" in detail.text

        for action in ("publish", "open"):
            response = client.post(
                f"/club/events/{event_id}/status",
                data={"action": action, "note": "v0.6K状态推进"},
                follow_redirects=False,
            )
            assert response.status_code == 303

        registration_payload = {
            "membership_id": membership_one["id"],
            "person_id": person_one,
            "organization_id": organization_id,
            "applicant_name": "会员一",
            "organization_name": "V06K测试机构",
            "mobile": "13800006001",
            "email": "member1@v06k.invalid",
        }
        first_registration = client.post(
            f"/api/v1/club/events/{event_id}/registrations",
            json=registration_payload,
        )
        duplicate_registration = client.post(
            f"/api/v1/club/events/{event_id}/registrations",
            json=registration_payload,
        )
        assert first_registration.status_code == 200
        assert duplicate_registration.status_code == 200
        registration_id = int(first_registration.json()["data"]["id"])
        assert int(duplicate_registration.json()["data"]["id"]) == registration_id

        ClubEventService(db_path).review_registration(
            event_id,
            registration_id,
            decision="approved",
            actor="v06k_admin",
            actor_user_id=int(admin["id"]),
        )

        application_two, membership_two = _membership(
            db_path,
            person_id=person_two,
            user_id=int(viewer_two["id"]),
            organization_id=organization_id,
            actor_user_id=int(admin["id"]),
            suffix="6002",
        )
        membership_service.transition_membership(
            int(membership_two["id"]),
            action="change",
            actor="v06k_admin",
            actor_user_id=int(admin["id"]),
            changes={"expired_at": (date.today() - timedelta(days=1)).isoformat()},
        )

        event_service = ClubEventService(db_path)
        waitlisted = event_service.register(
            event_id,
            {
                "user_id": int(viewer_two["id"]),
                "person_id": person_two,
                "organization_id": organization_id,
                "applicant_name": "会员二",
                "email": "waitlist@v06k.invalid",
            },
            actor_user_id=int(viewer_two["id"]),
        )
        event_service.review_registration(
            event_id,
            int(waitlisted["id"]),
            decision="waitlisted",
            actor="v06k_admin",
            actor_user_id=int(admin["id"]),
        )
        cancelled = event_service.register(
            event_id,
            {
                "user_id": int(admin["id"]),
                "applicant_name": "取消报名",
                "email": "cancelled@v06k.invalid",
            },
            actor_user_id=int(admin["id"]),
        )
        event_service.review_registration(
            event_id,
            int(cancelled["id"]),
            decision="cancelled",
            actor="v06k_admin",
            actor_user_id=int(admin["id"]),
        )

        for expected_idempotent in (False, True):
            checkin = client.post(
                f"/api/v1/club/events/{event_id}/checkin",
                json={"registration_id": registration_id, "token": "", "supplement": False},
            )
            assert checkin.status_code == 200
            assert checkin.json()["data"]["idempotent"] is expected_idempotent

        for action in ("start", "complete"):
            response = client.post(
                f"/club/events/{event_id}/status",
                data={"action": action, "note": "v0.6K完成活动"},
                follow_redirects=False,
            )
            assert response.status_code == 303

        for content in ("首次反馈", "刷新后的反馈"):
            feedback = client.post(
                f"/api/v1/club/events/{event_id}/registrations/{registration_id}/feedback",
                json={"satisfaction_score": 5, "content_feedback": content},
            )
            assert feedback.status_code == 200

        operations = client.get("/club/operations")
        assert operations.status_code == 200
        assert "运营管理" in operations.text
        assert client.get("/club/operations?tab=checkin").status_code == 200
        assert client.get("/club/events/999999", follow_redirects=False).status_code == 404

    metrics = ClubOperationsDashboardService(db_path).summary()["web_metrics"]
    baseline = p4_runtime["baseline_metrics"]
    assert metrics["total_members"] == baseline["total_members"] + 2
    assert metrics["active_members"] == baseline["active_members"] + 1
    assert metrics["total_events"] == baseline["total_events"] + 1
    assert metrics["registrations"] == baseline["registrations"] + 2
    assert metrics["pending_registrations"] == baseline["pending_registrations"]
    assert metrics["checked_in"] == baseline["checked_in"] + 1
    assert metrics["feedback"] == baseline["feedback"] + 1
    assert metrics["waitlisted"] == baseline["waitlisted"] + 1
    assert metrics["today_events"] == baseline["today_events"] + 1

    with sqlite3.connect(f"file:{db_path.as_posix()}?mode=ro", uri=True) as conn:
        profile = conn.execute(
            """SELECT p.event_id,p.venue,p.capacity,p.registration_deadline,e.name,e.event_date,e.fact_summary
               FROM v05c_club_event_profiles p JOIN events e ON e.id=p.event_id WHERE p.id=?""",
            (event_id,),
        ).fetchone()
        assert profile[1:] == (
            "上海更新会场",
            8,
            date.today().isoformat(),
            "V06K字段契约活动（已更新）",
            date.today().isoformat(),
            "更新后说明",
        )
        assert conn.execute(
            "SELECT COUNT(*) FROM v05c_club_event_registrations WHERE club_event_id=?",
            (event_id,),
        ).fetchone()[0] == 3
        assert conn.execute(
            "SELECT COUNT(*) FROM v05c_club_event_participation WHERE club_event_id=? AND registration_id=?",
            (event_id, registration_id),
        ).fetchone()[0] == 1
        assert conn.execute(
            "SELECT content_feedback FROM p4_event_feedback WHERE club_event_id=? AND registration_id=?",
            (event_id, registration_id),
        ).fetchone()[0] == "刷新后的反馈"

    with TestClient(app) as restarted:
        assert restarted.get("/club/operations").status_code == 200
        persisted_detail = restarted.get(f"/club/events/{event_id}")
        assert persisted_detail.status_code == 200
        assert "V06K字段契约活动（已更新）" in persisted_detail.text
        assert "刷新后的反馈" in sqlite3.connect(db_path).execute(
            "SELECT content_feedback FROM p4_event_feedback WHERE club_event_id=?",
            (event_id,),
        ).fetchone()[0]

