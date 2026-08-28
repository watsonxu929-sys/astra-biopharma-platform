from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.security import required_permission
from app.services.collection_service import (
    organization_monitoring_context,
    preview_website_import,
    save_website_import,
    set_admin_confirmed_official_domain,
)
from app.services.entity_governance_service import (
    EntityRegistryService,
    classify_identity,
    organization_duplicate_candidates,
)
from app.services.unified_search_service import UnifiedSearchService


def _organization(database: Path) -> dict:
    with sqlite3.connect(database) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT id,external_id,COALESCE(NULLIF(name,''),standard_name) AS name "
            "FROM organizations WHERE COALESCE(is_active,1)=1 ORDER BY id LIMIT 1"
        ).fetchone()
    assert row
    return dict(row)


def test_admin_confirmed_website_uses_existing_identifier_table(temp_database: Path) -> None:
    organization = _organization(temp_database)
    saved = set_admin_confirmed_official_domain(
        organization["external_id"], "https://r75-official.example.invalid/news",
        "r7.5-admin", db_path=temp_database,
    )
    assert saved["review_status"] == "approved"
    assert saved["identifier_type"] == "official_domain"
    context = organization_monitoring_context(organization["external_id"], temp_database)
    assert context["official_domain"]["normalized_value"] == "r75-official.example.invalid"


def test_alias_is_unique_and_searchable_without_second_index(temp_database: Path) -> None:
    organization = _organization(temp_database)
    registry = EntityRegistryService(temp_database)
    registry.add_alias(
        "organization", organization["external_id"], "R75 Unique Brand",
        alias_type="brand_name", source="管理员主数据", actor="r7.5-admin", permissions={"review_data"},
    )
    with sqlite3.connect(temp_database) as conn:
        other = conn.execute(
            "SELECT external_id FROM organizations WHERE external_id<>? ORDER BY id LIMIT 1",
            (organization["external_id"],),
        ).fetchone()
    assert other
    with pytest.raises(ValueError, match="alias_conflict"):
        registry.add_alias(
            "organization", other[0], "R75 Unique Brand",
            alias_type="brand_name", source="管理员主数据", actor="r7.5-admin", permissions={"review_data"},
        )
    engine = create_engine(f"sqlite:///{temp_database.as_posix()}")
    with Session(engine) as db:
        result = UnifiedSearchService(db).search("R75 Unique Brand")
    assert any(
        item["id"] == organization["id"]
        for group in result["groups"] if group["type"] == "organizations"
        for item in group["items"]
    )
    engine.dispose()


def test_identity_statuses_and_duplicate_hints_are_deterministic(temp_database: Path) -> None:
    assert classify_identity("organization", "某细胞治疗生物科技公司")["status"] == "INSUFFICIENT_DATA"
    assert classify_identity("person", "Admin")["status"] == "WRONG_ENTITY"
    assert classify_identity("organization", "杭州相关平台")["status"] == "IDENTITY_AMBIGUOUS"
    with sqlite3.connect(temp_database) as conn:
        base = _organization(temp_database)
        stamp = "2026-08-28T00:00:00"
        other = conn.execute(
            "SELECT external_id FROM organizations WHERE external_id<>? ORDER BY id LIMIT 1",
            (base["external_id"],),
        ).fetchone()
        assert other
        conn.execute(
            "UPDATE organizations SET standard_name=?,name=?,updated_at=? WHERE external_id=?",
            (base["name"] + "有限公司", base["name"] + "有限公司", stamp, other[0]),
        )
        conn.commit()
    candidates = organization_duplicate_candidates(base["external_id"], temp_database, threshold=.60)
    assert any(row["external_id"] == other[0] for row in candidates)


def test_website_csv_requires_preview_and_skips_unsafe_rows(temp_database: Path) -> None:
    organization = _organization(temp_database)
    text_value = (
        "organization_id,website\n"
        f"{organization['external_id']},https://csv-r75.example.invalid/news\n"
        "ORG-NOT-FOUND,https://missing.example.invalid/\n"
        f"{organization['external_id']},https://www.36kr.com/company/example\n"
    )
    preview = preview_website_import(text_value, temp_database)
    assert [row["status"] for row in preview] == ["READY", "NOT_FOUND", "INVALID_URL"]
    result = save_website_import(text_value, "r7.5-admin", temp_database)
    assert result == {"saved": 1, "exists": 0, "skipped": 2}
    assert preview_website_import(text_value, temp_database)[0]["status"] == "EXISTS"


def test_existing_evidence_only_produces_candidate_context(temp_database: Path) -> None:
    organization = _organization(temp_database)
    with sqlite3.connect(temp_database) as conn:
        conn.execute(
            "UPDATE organizations SET source_url=? WHERE external_id=?",
            ("https://evidence-r75.example.invalid/about", organization["external_id"]),
        )
        conn.commit()
    context = organization_monitoring_context(organization["external_id"], temp_database)
    assert context["official_domain"] is None
    assert context["website_evidence"] == [
        {"url": "https://evidence-r75.example.invalid/about", "basis": "Organization档案"}
    ]


def test_viewer_website_and_alias_writes_are_backend_forbidden() -> None:
    paths = [
        "/admin/organizations/1/update",
        "/admin/organizations/website-import/preview",
        "/admin/organizations/website-import/confirm",
    ]
    assert all(required_permission(path, "POST") == "edit_data" for path in paths)
