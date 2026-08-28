from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from app.security import required_permission
from app.services.collection_service import (
    discover_source_candidates,
    organization_monitoring_context,
    propose_official_domain_candidate,
    review_official_domain_candidate,
    set_source_enabled,
    validate_official_domain_candidate,
)


def _organization(database: Path) -> dict:
    with sqlite3.connect(database) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT external_id,COALESCE(NULLIF(name,''),standard_name) AS name FROM organizations ORDER BY id LIMIT 1"
        ).fetchone()
    assert row
    return dict(row)


def _official_site_get(organization_name: str):
    homepage = f'''<html><head><title>{organization_name} 官方网站</title>
    <meta property="og:site_name" content="{organization_name}">
    <script type="application/ld+json">{{"@type":"Organization","name":"{organization_name}"}}</script>
    <link rel="alternate" type="application/rss+xml" href="/feed.xml"></head>
    <body><h1>{organization_name}</h1><a href="/press-releases">Press Releases</a></body></html>'''
    rss = """<rss><channel><item><title>真实研发进展</title><pubDate>Thu, 27 Aug 2026 08:00:00 GMT</pubDate></item></channel></rss>"""

    def fake(url: str, **kwargs):
        if url.endswith("/robots.txt"):
            return "", 200, "text/plain", {}
        if url.endswith("/sitemap.xml"):
            return "<urlset></urlset>", 200, "application/xml", {}
        if url.endswith("/feed.xml"):
            return rss, 200, "application/rss+xml", {}
        if url.endswith("/press-releases"):
            return "<html><body><h2>真实新闻样本</h2></body></html>", 200, "text/html", {}
        if url == "https://official.example.invalid/":
            return homepage, 200, "text/html", {}
        raise RuntimeError("FETCH_FAILED")

    return fake


def test_official_domain_candidate_is_reviewed_before_discovery(
    temp_database: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization = _organization(temp_database)
    monkeypatch.setattr(
        "app.services.collection_service._http_get", _official_site_get(organization["name"]),
    )
    proposal = propose_official_domain_candidate(
        organization["external_id"], organization["name"],
        "https://official.example.invalid/about", "测试档案明确链接", "r7.3-test", temp_database,
    )
    assert proposal["created"] is True
    assert proposal["candidate"]["review_status"] == "pending"
    assert not organization_monitoring_context(
        organization["external_id"], temp_database,
    )["official_domain"]

    approved = review_official_domain_candidate(
        proposal["candidate"]["id"], organization["external_id"],
        "approved", "r7.3-admin", temp_database,
    )
    assert approved["review_status"] == "approved"
    discovered = discover_source_candidates(
        approved["identifier_value"], organization["external_id"], organization["name"],
        owner="r7.3-admin", db_path=temp_database,
    )
    assert discovered["created"] >= 1
    assert all(row["subject_id"] == organization["external_id"] for row in discovered["candidates"])
    assert all(not row["is_enabled"] for row in discovered["candidates"])
    assert any(row["test"].get("recent_items") for row in discovered["candidates"])

    context = organization_monitoring_context(organization["external_id"], temp_database)
    assert context["monitoring_status"] == "COVERED_CANDIDATE"
    assert context["candidate_sources"][0]["discovery"]["test"]["recent_items"]
    set_source_enabled(context["candidate_sources"][0]["id"], True, temp_database)
    refreshed = organization_monitoring_context(organization["external_id"], temp_database)
    assert refreshed["monitoring_status"] == "COVERED_ACTIVE"


def test_domain_rejection_and_subject_binding_are_persistent(
    temp_database: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    organization = _organization(temp_database)
    assert validate_official_domain_candidate(
        "https://www.36kr.com/company/example", organization["name"],
    )["status"] == "THIRD_PARTY_DOMAIN"
    monkeypatch.setattr(
        "app.services.collection_service._http_get", _official_site_get(organization["name"]),
    )
    proposal = propose_official_domain_candidate(
        organization["external_id"], organization["name"],
        "https://official.example.invalid/", "管理员提交", "r7.3-test", temp_database,
    )
    with pytest.raises(ValueError):
        review_official_domain_candidate(
            proposal["candidate"]["id"], "ORG-NOT-THE-SAME", "approved", "r7.3-admin", temp_database,
        )
    rejected = review_official_domain_candidate(
        proposal["candidate"]["id"], organization["external_id"],
        "rejected", "r7.3-admin", temp_database,
    )
    assert rejected["review_status"] == "rejected"
    assert organization_monitoring_context(
        organization["external_id"], temp_database,
    )["domain_candidate"] is None


def test_monitoring_routes_require_backend_write_permission() -> None:
    paths = [
        "/network/entities/organization/ORG-1/monitoring/discover",
        "/network/entities/organization/ORG-1/monitoring/domain-candidates",
        "/network/entities/organization/ORG-1/monitoring/domain-candidates/1/review",
    ]
    assert all(required_permission(path, "POST") == "edit_data" for path in paths)