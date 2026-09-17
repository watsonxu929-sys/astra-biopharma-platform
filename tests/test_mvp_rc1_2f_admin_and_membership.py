from __future__ import annotations

import sqlite3
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import Organization, Person
from app.services.canonical_relationship_service import CanonicalRelationshipService
from app.services.club_operations_service import ClubMembershipService, ClubOperationError
from app.services.collection_service import (
    create_collection_source,
    delete_or_retire_source,
    preview_source_import,
    test_source_url as probe_source_url,
)
from app.services.collectors.playwright_adapter import DynamicFetchResult, PlaywrightCollectionError
from app.services.data_quality import (
    check_organization_duplicates,
    check_person_duplicates,
    organization_reference_details,
    organization_reference_reasons,
    person_reference_details,
    person_reference_reasons,
)
from app.v05f_collection import _decode_source_import_file


def _session(database: Path) -> Session:
    return Session(create_engine(f"sqlite:///{database.as_posix()}", connect_args={"check_same_thread": False}))


def _override_app_database(database: Path):
    def override():
        with _session(database) as db:
            yield db
    return override


def test_source_bulk_formats_and_run_history_retire_safely(
    temp_database: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.collection_service.test_source_url",
        lambda url: {"ok": True, "status": "READY", "url": url},
    )
    preview = preview_source_import(
        "国家药品监督管理局    https://nmpa.rc12f.invalid/\nFDA,https://fda.rc12f.invalid/",
        temp_database,
    )
    assert [(row["line"], row["name"], row["status"]) for row in preview] == [
        (1, "国家药品监督管理局", "READY"), (2, "FDA", "READY"),
    ]

    source = create_collection_source(
        name="RC1.2F历史来源", source_type="webpage", url="https://history.rc12f.invalid/",
        is_enabled=False, db_path=temp_database,
    )
    with sqlite3.connect(temp_database) as conn:
        conn.execute(
            """INSERT INTO v04g_monitoring_runs(
                 run_no,monitoring_source_id,status,started_at,created_at
               ) VALUES ('RUN-RC12F',?,'failed',datetime('now'),datetime('now'))""",
            (source["id"],),
        )
        conn.commit()
    result = delete_or_retire_source(int(source["id"]), temp_database)
    assert result["action"] == "retired" and result["history_preserved"] is True


def test_txt_upload_bom_and_more_than_one_hundred_urls_are_supported(
    temp_database: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    text_value = "\n".join(f"https://source-{index}.rc12f.invalid/" for index in range(263))
    decoded = _decode_source_import_file(
        "生物医药情报采集网址_仅URL.txt", "application/octet-stream",
        b"\xef\xbb\xbf" + text_value.encode("utf-8"),
    )
    monkeypatch.setattr(
        "app.services.collection_service.test_source_url",
        lambda url: {
            "ok": True, "status": "READY", "url": url,
            "recommended_mode": "http", "recommendation": "HTTP列表页",
        },
    )
    preview = preview_source_import(decoded, temp_database)
    assert len(preview) == 263
    assert all(row["status"] == "READY" for row in preview)
    with pytest.raises(ValueError, match="source_import_invalid_encoding"):
        _decode_source_import_file("bad.txt", "text/plain", b"\xff\xfe")
    with pytest.raises(ValueError, match="source_import_invalid_file_type"):
        _decode_source_import_file("bad.xlsx", "application/octet-stream", b"https://example.test")


def test_source_probe_falls_back_to_existing_playwright_and_keeps_real_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_http(url: str, **kwargs):
        response = httpx.Response(412, request=httpx.Request("GET", url))
        cause = httpx.HTTPStatusError("precondition failed", request=response.request, response=response)
        raise RuntimeError("FETCH_FAILED") from cause

    class BrowserReady:
        def fetch(self, url: str, **kwargs) -> DynamicFetchResult:
            html = "<html><head><title>NMPA</title></head><body><main>" + ("公开信息 " * 60) + "</main></body></html>"
            return DynamicFetchResult(url, html, None, "NMPA", "success", 10)

    monkeypatch.setattr("app.services.collection_service._http_get", reject_http)
    monkeypatch.setattr("app.services.collection_service.PlaywrightAdapter", BrowserReady)
    ready = probe_source_url("https://www.nmpa.gov.cn/")
    assert ready["status"] == "BROWSER_READY"
    assert ready["http_status"] == 412 and ready["browser_accessible"] is True
    assert ready["recommended_mode"] == "playwright"

    class BrowserRejected:
        def fetch(self, url: str, **kwargs) -> DynamicFetchResult:
            raise PlaywrightCollectionError("playwright_http_412")

    monkeypatch.setattr("app.services.collection_service.PlaywrightAdapter", BrowserRejected)
    rejected = probe_source_url("https://www.nmpa.gov.cn/")
    assert rejected["ok"] is False and rejected["http_status"] == 412
    assert rejected["recommendation"] == "暂不可采集"
    assert "HTTP 412" in rejected["failure_reason"]


def test_master_data_duplicate_and_reference_protection(temp_database: Path) -> None:
    with _session(temp_database) as db:
        org = Organization(
            external_id="ORG-RC12F-NEW", standard_name="RC1.2F安全机构",
            manually_confirmed=True, is_active=True,
        )
        person = Person(
            external_id="PER-RC12F-NEW", name="RC1.2F安全人物",
            organization_network="RC1.2F安全机构", public_role="BD负责人",
            manually_confirmed=True, is_active=True,
        )
        db.add_all([org, person])
        db.commit()

        org_duplicate = check_organization_duplicates(db, "RC1.2F安全机构")
        person_duplicate = check_person_duplicates(db, "RC1.2F安全人物", "RC1.2F安全机构", "BD负责人")
        assert org_duplicate.blocks_save is True
        assert person_duplicate.blocks_save is True
        assert organization_reference_reasons(db, org) == []  # Exact current employer can detach.
        assert person_reference_reasons(db, person) == []


def test_protected_person_can_inspect_archive_return_and_then_delete(
    temp_database: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _session(temp_database) as db:
        org = Organization(
            external_id="ORG-RC12F-REFERENCE", standard_name="RC1.2F引用机构",
            manually_confirmed=True, is_active=True,
        )
        person = Person(
            external_id="PER-RC12F-REFERENCE", name="RC1.2F受保护人物",
            manually_confirmed=True, is_active=True,
        )
        db.add_all([org, person])
        db.commit()
        person_id, person_external_id, org_external_id = person.id, person.external_id, org.external_id

    relationship_service = CanonicalRelationshipService(temp_database)
    candidate = relationship_service.create_candidate(
        subject_type="person", subject_id=person_external_id, relationship_type="employed_by",
        object_type="organization", object_id=org_external_id, actor="rc12f-test",
    )
    relationship = relationship_service.review_candidate(
        candidate["id"], "approved", actor="rc12f-reviewer", permissions={"review_data"},
    )["relationship"]

    with _session(temp_database) as db:
        person = db.get(Person, person_id)
        details = person_reference_details(db, person)
        relationship_detail = next(item for item in details if item["key"] == "relationships")
        assert relationship_detail["count"] == 1
        assert relationship_detail["items"][0]["url"] == f"/network/relationships/{relationship['id']}"
        assert next(item for item in details if item["key"] == "follow_ups")["count"] == 0
        assert next(item for item in details if item["key"] == "resources")["count"] == 0
        assert next(item for item in details if item["key"] == "memberships")["count"] == 0

    monkeypatch.setenv("APP_AUTH_DISABLED", "1")
    app.dependency_overrides[get_db] = _override_app_database(temp_database)
    try:
        with TestClient(app) as client:
            detail_page = client.get(f"/admin/people/{person_id}")
            assert detail_page.status_code == 200
            assert "无法直接删除该人物" in detail_page.text
            assert "正式关系" in detail_page.text and "跟进事项" in detail_page.text
            assert f'/network/relationships/{relationship["id"]}?return_to=' in detail_page.text

            relationship_page = client.get(
                f"/network/relationships/{relationship['id']}?return_to=/admin/people/{person_id}"
            )
            assert relationship_page.status_code == 200
            assert "归档错误或测试关系" in relationship_page.text
            assert f'value="/admin/people/{person_id}"' in relationship_page.text

            deactivated = client.post(f"/admin/people/{person_id}/deactivate", follow_redirects=False)
            assert deactivated.status_code == 303

            archived = client.post(
                f"/network/relationships/{relationship['id']}/archive",
                data={"reason": "隔离测试关系", "return_to": f"/admin/people/{person_id}"},
                follow_redirects=False,
            )
            assert archived.status_code == 303
            assert archived.headers["location"].startswith(f"/admin/people/{person_id}?")

            deleted = client.post(
                f"/admin/people/{person_id}/delete", data={"confirm": "1"},
                follow_redirects=False,
            )
            assert deleted.status_code == 303 and deleted.headers["location"].startswith("/admin/people")
    finally:
        app.dependency_overrides.pop(get_db, None)

    with _session(temp_database) as db:
        assert db.get(Person, person_id) is None
    assert relationship_service.detail(relationship["id"])["review_status"] == "archived"


def test_organization_reference_panel_and_bulk_delete_partial_success(
    temp_database: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    with _session(temp_database) as db:
        org = Organization(
            external_id="ORG-RC12F-BULK-PROTECTED", standard_name="RC1.2F批量受保护机构",
            manually_confirmed=True, is_active=True,
        )
        safe = Organization(
            external_id="ORG-RC12F-BULK-SAFE", standard_name="RC1.2F批量可删除机构",
            manually_confirmed=True, is_active=True,
        )
        db.add_all([org, safe])
        db.flush()
        person = Person(
            external_id="PER-RC12F-BULK-LINK", name="RC1.2F机构关联人物",
            organization_network=org.standard_name + " / 未核实历史机构", manually_confirmed=True, is_active=True,
        )
        db.add(person)
        db.commit()
        org_id, safe_id = org.id, safe.id
        details = organization_reference_details(db, org)
        people_detail = next(item for item in details if item["key"] == "people")
        assert people_detail["count"] == 1
        assert people_detail["items"][0]["url"] == f"/admin/people/{person.id}"

    monkeypatch.setenv("APP_AUTH_DISABLED", "1")
    app.dependency_overrides[get_db] = _override_app_database(temp_database)
    try:
        with TestClient(app) as client:
            result = client.post(
                "/admin/organizations/bulk-delete",
                data={"organization_ids": [str(safe_id), str(org_id)]},
                follow_redirects=False,
            )
            assert result.status_code == 303 and "protected_ids=" in result.headers["location"]
            page = client.get(result.headers["location"])
            assert page.status_code == 200
            assert "Partial Success" in page.text
            assert "RC1.2F批量受保护机构" in page.text
            assert "关联人物 1 条" in page.text
            assert f'href="/admin/organizations/{org_id}"' in page.text

            deactivated = client.post(f"/admin/organizations/{org_id}/deactivate", follow_redirects=False)
            assert deactivated.status_code == 303
    finally:
        app.dependency_overrides.pop(get_db, None)

    with _session(temp_database) as db:
        assert db.get(Organization, safe_id) is None
        protected = db.get(Organization, org_id)
        assert protected is not None and protected.is_active is False


def test_membership_application_canonical_review_and_activation(temp_database: Path) -> None:
    with sqlite3.connect(temp_database) as conn:
        user_id = int(conn.execute("SELECT id FROM v05a_users ORDER BY id LIMIT 1").fetchone()[0])
        person_id = int(conn.execute("SELECT id FROM people ORDER BY id LIMIT 1").fetchone()[0])
        organization_id = int(conn.execute("SELECT id FROM organizations ORDER BY id LIMIT 1").fetchone()[0])

    service = ClubMembershipService(temp_database)
    application = service.submit_application({
        "user_id": user_id, "applicant_name": "待匹配申请人", "organization_name": "待匹配机构",
        "mobile": "13800001234", "member_type": "organization", "application_reason": "产业合作",
    }, actor_user_id=user_id)
    assert application["status"] == "under_review"
    assert application["matched_person_id"] is None and application["matched_organization_id"] is None

    service.review_application(
        int(application["id"]), decision="need_more_info", actor="rc12f-admin", note="请补充主体信息",
    )
    resubmitted = service.submit_application({
        "user_id": user_id, "applicant_name": "待匹配申请人", "organization_name": "待匹配机构",
        "mobile": "13800001234", "member_type": "organization", "application_reason": "补充后的产业合作说明",
    }, actor_user_id=user_id)
    assert resubmitted["id"] == application["id"] and resubmitted["status"] == "under_review"

    with pytest.raises(ClubOperationError) as missing_links:
        service.review_application(int(application["id"]), decision="approved", actor="rc12f-admin")
    assert missing_links.value.code == "IDENTITY_LINKS_REQUIRED"

    reviewed = service.review_application(
        int(application["id"]), decision="approved", actor="rc12f-admin", actor_user_id=user_id,
        person_id=person_id, organization_id=organization_id, user_id=user_id,
    )
    activated = service.transition_membership(
        int(reviewed["membership"]["id"]), action="activate", actor="rc12f-admin", actor_user_id=user_id,
    )
    assert activated["membership"]["status"] == "active"


def test_master_data_management_is_reachable_from_formal_admin_ui(
    temp_database: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_DISABLED", "1")
    with TestClient(app) as client:
        admin = client.get("/admin/platform")
        organizations = client.get("/admin/organizations")
        people = client.get("/admin/people")
        new_person = client.get("/admin/people/new")

    assert admin.status_code == 200
    assert 'href="/admin/organizations"' in admin.text and "企业/机构管理" in admin.text
    assert 'href="/admin/people"' in admin.text and "人物管理" in admin.text
    assert organizations.status_code == 200
    assert "新增企业/机构" in organizations.text
    assert 'data-bulk-delete' in organizations.text and 'formaction="/admin/organizations/' in organizations.text
    assert people.status_code == 200
    assert "新增人物" in people.text and "批量新增" in people.text
    assert 'data-bulk-delete' in people.text and 'formaction="/admin/people/' in people.text
    assert new_person.status_code == 200
    assert 'list="organization-options"' in new_person.text
    assert "不使用内部编号" in new_person.text


def test_club_apply_redirects_anonymous_user_and_renders_without_existing_application(
    temp_database: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_AUTH_DISABLED", "0")
    with TestClient(app) as client:
        anonymous = client.get("/club/apply", follow_redirects=False)
    assert anonymous.status_code == 303
    assert anonymous.headers["location"] == "/account/login?next=/club/apply"

    monkeypatch.setenv("APP_AUTH_DISABLED", "1")
    with sqlite3.connect(temp_database) as conn:
        conn.execute("DELETE FROM v04f_club_applications")
        conn.commit()
    with TestClient(app) as client:
        application = client.get("/club/apply")
    assert application.status_code == 200
    assert "申请加入Q-BAY俱乐部" in application.text
    assert 'name="application_reason"' in application.text
    assert 'name="cooperation_needs"' in application.text
    assert 'name="offered_resources"' in application.text
    assert "系统暂时无法完成本次请求" not in application.text

    with TestClient(app) as client:
        submitted = client.post(
            "/club/apply",
            data={
                "member_type": "individual",
                "applicant_name": "RC1.2F申请页回归用户",
                "mobile": "13800000000",
                "application_reason": "验证现有会员申请链路",
                "industry_tags": "生物医药",
                "cooperation_needs": "产业交流",
                "offered_resources": "行业经验",
                "consent_to_store": "1",
                "consent_to_contact": "1",
            },
            follow_redirects=False,
        )
        assert submitted.status_code == 303
        assert submitted.headers["location"].startswith("/club/application?submitted=")
        status_page = client.get(submitted.headers["location"])
    assert status_page.status_code == 200
    assert "会员申请已提交" in status_page.text
    assert "RC1.2F申请页回归用户" in status_page.text
