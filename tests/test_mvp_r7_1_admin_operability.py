from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.security import required_permission
from app.services.club_operations_service import ClubEventService, ClubOperationError
from app.services.collection_service import (
    create_collection_source,
    delete_or_retire_source,
    discover_source_candidates,
    list_sources,
    preview_source_import,
    save_source_import,
    set_source_enabled,
    source_detail,
    update_collection_source,
)
from app.services.unified_resource_service import UnifiedResourceService


ROOT = Path(__file__).resolve().parents[1]


def _session(database: Path) -> Session:
    return Session(create_engine(
        f"sqlite:///{database.as_posix()}", connect_args={"check_same_thread": False}
    ))


def test_source_crud_import_discovery_and_safe_retirement(
    temp_database: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    source = create_collection_source(
        name="R7.1 Source", source_type="webpage", url="https://example.invalid/r71",
        check_frequency="weekly", is_enabled=False, owner="r71-test", db_path=temp_database,
    )
    updated = update_collection_source(source["id"], {
        "name": "R7.1 Source Updated", "url": source["url"], "source_type": "webpage",
        "collection_mode": "http", "check_frequency": "daily",
    }, temp_database)
    assert updated["name"] == "R7.1 Source Updated"
    assert set_source_enabled(source["id"], True, temp_database)["is_enabled"] == 1

    monkeypatch.setattr(
        "app.services.collection_service.test_source_url",
        lambda url: {"ok": True, "status": "READY", "url": url},
    )
    preview = preview_source_import(
        "name,url\nExists,http://www.example.invalid/r71/\nNew,https://new.example.invalid/news",
        temp_database,
    )
    assert [row["status"] for row in preview] == ["EXISTS", "READY"]
    result = save_source_import(preview, "r71-test", temp_database)
    assert result == {"created": 1, "exists": 1, "invalid": 0, "failed": 0}
    candidates, _ = list_sources(temp_database, status="candidate", page_size=100)
    assert any(row["url"] == "https://new.example.invalid/news" for row in candidates)

    homepage = '<html><head><link rel="alternate" type="application/rss+xml" href="/feed"></head>' \
               '<body><a href="/newsroom">Newsroom</a></body></html>'
    monkeypatch.setattr(
        "app.services.collection_service._http_get",
        lambda url, **kwargs: (homepage if url.endswith(".invalid") else "<rss><channel><item><title>x</title></item></channel></rss>",
                               200, "text/html", {}),
    )
    discovered = discover_source_candidates(
        "https://discovery.example.invalid", organization_name="Discovery Org",
        owner="r71-test", db_path=temp_database,
    )
    assert discovered["homepage_ok"] is True
    assert discovered["created"] >= 1
    assert all(not row["is_enabled"] for row in discovered["candidates"])

    no_history = create_collection_source(
        name="Delete Me", source_type="webpage", url="https://delete.example.invalid",
        is_enabled=False, db_path=temp_database,
    )
    assert delete_or_retire_source(no_history["id"], temp_database)["action"] == "deleted"
    with pytest.raises(ValueError):
        source_detail(no_history["id"], temp_database)

    with sqlite3.connect(temp_database) as conn:
        historical_id = conn.execute(
            "SELECT monitoring_source_id FROM v05f_collection_items ORDER BY id LIMIT 1"
        ).fetchone()[0]
    retired = delete_or_retire_source(int(historical_id), temp_database)
    assert retired["action"] == "retired" and retired["history_preserved"] is True


def test_event_crud_registration_and_delete_protection(temp_database: Path) -> None:
    service = ClubEventService(temp_database)
    event = service.create_event({
        "name": "R7.1 Admin Event", "event_date": "2026-09-01", "event_type": "roadshow",
        "visibility": "public", "capacity": 20, "description": "真实运营验收活动",
    }, actor="r71-test", actor_user_id=1)
    updated = service.update_event(event["id"], {
        "name": "R7.1 Admin Event Updated", "event_date": "2026-09-02",
        "event_type": "roadshow", "visibility": "public", "capacity": 30,
        "description": "更新后的活动说明",
    }, actor="r71-test", actor_user_id=1)
    assert updated["capacity"] == 30
    service.transition_event(event["id"], action="publish", actor="r71-test", actor_user_id=1)
    service.transition_event(event["id"], action="open", actor="r71-test", actor_user_id=1)
    registration = service.register(event["id"], {
        "applicant_name": "R7.1 Viewer", "email": "r71-viewer@example.invalid",
    })
    assert registration["registration_no"]
    with pytest.raises(ClubOperationError) as protected:
        service.delete_safe_draft(event["id"], actor="r71-test", actor_user_id=1)
    assert protected.value.status_code == 409

    draft = service.create_event({"name": "R7.1 Safe Draft"}, actor="r71-test", actor_user_id=1)
    assert service.delete_safe_draft(draft["id"], actor="r71-test", actor_user_id=1)["deleted"] is True


def test_resource_edit_close_delete_and_reference_protection(temp_database: Path) -> None:
    with _session(temp_database) as db:
        service = UnifiedResourceService(db)
        removable = service.create(actor_user_id=1, fields={
            "title": "R7.1 Removable", "direction": "supply", "resource_type": "CRO服务",
            "summary": "before", "status": "published",
        })
        removable_id = int(removable.id)
        changed = service.update(removable_id, actor_user_id=1, fields={
            "title": "R7.1 Removable Updated", "direction": "supply", "resource_type": "CRO服务",
            "summary": "after", "valid_until": "2026-12-31",
        })
        assert changed.summary == "after"
        assert service.delete_safe(removable_id, actor_user_id=1)["deleted"] is True

        protected = service.create(actor_user_id=1, fields={
            "title": "R7.1 Protected", "direction": "demand", "resource_type": "CRO服务",
            "status": "published",
        })
        protected_id = int(protected.id)
        db.execute(text("""INSERT INTO v06_opportunities(
            title,opp_type,initiator_id,related_resource_id,stage,status,visibility,is_demo,created_at,updated_at
        ) VALUES ('R7.1 Opp','cooperation',1,:resource_id,'lead','active','organization',0,datetime('now'),datetime('now'))"""),
                   {"resource_id": protected_id})
        db.commit()
        with pytest.raises(HTTPException) as error:
            service.delete_safe(protected_id, actor_user_id=1)
        assert error.value.status_code == 409
        assert error.value.detail["details"]["opportunities"] == 1
        assert service.close(protected_id, actor_user_id=1).status == "archived"


        safe_ids = [int(service.create(actor_user_id=1, fields={
            "title": f"R7.1 Bulk {index}", "direction": "supply",
            "resource_type": "检测服务", "status": "published",
        }).id) for index in range(2)]
        bulk = service.bulk_delete([safe_ids[0], protected_id, safe_ids[1]], actor_user_id=1)
        assert bulk["deleted"] == safe_ids
        assert bulk["protected"] == [protected_id]
        assert db.get(type(protected), protected_id) is not None
def test_viewer_permissions_and_write_controls_are_explicit() -> None:
    assert required_permission("/club/events", "GET") == "view_internal"
    assert required_permission("/club/events/1", "GET") == "view_internal"
    assert required_permission("/club/events/1/edit", "POST") == "manage_club"
    assert required_permission("/resources", "GET") == "view_internal"
    assert required_permission("/resources/1/edit", "POST") == "edit_data"
    resources = (ROOT / "app/templates/platform/resources.html").read_text(encoding="utf-8")
    detail = (ROOT / "app/templates/platform/resource_detail.html").read_text(encoding="utf-8")
    event = (ROOT / "app/templates/v05c_club_events.html").read_text(encoding="utf-8")
    event_list = (ROOT / "app/templates/club_events.html").read_text(encoding="utf-8")
    collection = (ROOT / "app/templates/v05f_collection.html").read_text(encoding="utf-8")
    collection_routes = (ROOT / "app/v05f_collection.py").read_text(encoding="utf-8")
    event_routes = (ROOT / "app/v05c_club_events.py").read_text(encoding="utf-8")
    assert "{% if can_write %}" in resources and "{% if can_write %}" in detail
    assert "{% if can_manage %}" in event
    assert "sec.get('can_manage_club', False)" in event_list
    assert "can_manage_source" in collection
    assert '(s.discovery.get("test") or {}).get("status")' in collection
    assert "/collection/sources/{source_id:int}" in collection_routes
    assert "活动已有报名或已发布，不能删除" in event_routes
