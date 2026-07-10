from __future__ import annotations

import importlib.util
from importlib import import_module
import os
import sqlite3
from pathlib import Path

import pytest

from app.platform.capability_registry import list_capabilities
from app.services.ai import MockProvider, OpenAIProvider, ProviderRegistry, ProviderUnavailable, RuleProvider
from app.services.ai_analysis_service import AIAnalysisService
from app.services.collection_service import create_job, retry_job
from app.services.collectors import PlaywrightAdapter, PlaywrightUnavailable
from app.services.evidence_service import EvidenceService
from app.services.fact_candidate_service import FactCandidateService
from app.services.intelligence_product_service import IntelligenceProductService
from app.services.intelligence_review_service import IntelligenceReviewService
from app.services.navigation_service import resolve_active_capability
from app.services.parsers import DocumentParser, HtmlParser, ParserUnavailable, UnsupportedContentType
from app.services.parsing_service import ParsingService
from app.services.processing.processing_job_service import create_processing_job
apply_schema = import_module("scripts.migrations.003_intelligence_evidence_pipeline").apply_schema


@pytest.fixture
def p2_db(temp_database: Path) -> Path:
    with sqlite3.connect(temp_database) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        apply_schema(conn)
        conn.commit()
    return temp_database


def source_and_run(db_path: Path) -> tuple[int, int, int]:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT r.monitoring_source_id,r.id,s.id FROM v04g_monitoring_runs r JOIN v04g_source_snapshots s ON s.monitoring_run_id=r.id ORDER BY s.id LIMIT 1"
        ).fetchone()
    assert row
    return int(row[0]), int(row[1]), int(row[2])


def test_snapshot_dedup_change_and_immutability(p2_db: Path):
    source_id, run_id, _ = source_and_run(p2_db)
    service = EvidenceService(p2_db)
    args = {"source_id": source_id, "job_id": run_id, "url": "https://example.invalid/p2/snapshot", "raw_content": "alpha", "raw_html": "<article>alpha</article>", "page_title": "P2 snapshot"}
    first, created = service.get_or_create_snapshot(**args)
    duplicate, duplicate_created = service.get_or_create_snapshot(**args)
    changed, changed_created = service.get_or_create_snapshot(**{**args, "raw_content": "beta", "raw_html": "<article>beta</article>"})
    assert created is True
    assert duplicate_created is False and duplicate["id"] == first["id"]
    assert changed_created is True and changed["id"] != first["id"]
    assert changed["previous_snapshot_id"] == first["id"]
    with sqlite3.connect(p2_db) as conn, pytest.raises(sqlite3.IntegrityError, match="evidence_snapshot_is_immutable"):
        conn.execute("UPDATE v04g_source_snapshots SET raw_content='overwritten' WHERE id=?", (first["id"],))


def test_raw_normalization_dedup_does_not_overwrite_snapshot(p2_db: Path):
    _, _, snapshot_id = source_and_run(p2_db)
    with sqlite3.connect(p2_db) as conn:
        before = conn.execute("SELECT raw_content,content_hash FROM v04g_source_snapshots WHERE id=?", (snapshot_id,)).fetchone()
    first, created = EvidenceService(p2_db).normalize(snapshot_id, text="normalized content", title="normalized")
    second, duplicate_created = EvidenceService(p2_db).normalize(snapshot_id, text="normalized content", title="normalized")
    with sqlite3.connect(p2_db) as conn:
        after = conn.execute("SELECT raw_content,content_hash FROM v04g_source_snapshots WHERE id=?", (snapshot_id,)).fetchone()
    assert created is True and duplicate_created is False and first["id"] == second["id"]
    assert before == after


def test_collection_job_pending_and_retry_lineage(p2_db: Path):
    source_id, original_id, _ = source_and_run(p2_db)
    created = create_job(source_id, trigger_type="test", operator="pytest", db_path=p2_db, force=True)
    assert created["status"] == "pending"
    retried = retry_job(original_id, operator="pytest", db_path=p2_db)
    assert retried["status"] == "pending"
    assert retried["parent_job_id"] == original_id


def test_parsers_and_optional_dependencies_are_explicit(monkeypatch):
    result = HtmlParser().parse({"content_type": "text/html", "raw_html": "<html><body><nav>skip</nav><article><h1>标题</h1><p>正文</p></article></body></html>"})
    assert "正文" in result.text and result.citations
    with pytest.raises(UnsupportedContentType, match="unsupported_content_type"):
        ParsingService().parse({"content_type": "application/x-unknown", "raw_content": "x"})
    monkeypatch.setattr(importlib.util, "find_spec", lambda name: None)
    with pytest.raises(ParserUnavailable, match="docling_parser_unavailable"):
        DocumentParser().parse({"content_type": "application/pdf", "attachment_path": "missing.pdf"})
    with pytest.raises(PlaywrightUnavailable, match="playwright_unavailable"):
        PlaywrightAdapter().fetch("https://example.invalid", dynamic=True)
    assert HtmlParser().parse({"content_type": "text/html", "raw_html": "<article>still works</article>"}).text == "still works"


def test_ai_providers_and_no_key_behavior(monkeypatch):
    assert RuleProvider().analyze("某公司宣布融资").event_classification == "financing"
    assert MockProvider().analyze("x").generated_by == "mock"
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    provider = OpenAIProvider()
    assert provider.available is False
    with pytest.raises(ProviderUnavailable, match="openai_api_key_unavailable"):
        provider.analyze("must not call network")
    assert ProviderRegistry().get("openai").name == "rule"


def test_invalid_ai_result_is_failed_and_creates_no_candidate(p2_db: Path):
    _, _, snapshot_id = source_and_run(p2_db)
    job = create_processing_job(snapshot_id=snapshot_id, queued_only=False, db_path=p2_db)
    invalid = MockProvider({"importance": 9, "candidates": [{"candidate_type": "event", "value": "x"}]})
    registry = ProviderRegistry({"rule": RuleProvider(), "mock": invalid})
    result = AIAnalysisService(p2_db, registry).analyze(processing_job_id=job["id"], snapshot_id=snapshot_id, text="x", provider_name="mock")
    assert result["status"] == "failed" and result["candidate_ids"] == []
    with sqlite3.connect(p2_db) as conn:
        assert conn.execute("SELECT status FROM p2_ai_analysis_runs WHERE id=?", (result["run_id"],)).fetchone()[0] == "failed"
        assert conn.execute("SELECT COUNT(*) FROM v05g_extraction_candidates WHERE processing_job_id=?", (job["id"],)).fetchone()[0] == 0


def test_review_evidence_publish_trace_and_delete(p2_db: Path):
    _, _, snapshot_id = source_and_run(p2_db)
    job = create_processing_job(snapshot_id=snapshot_id, queued_only=False, db_path=p2_db)
    analysis = AIAnalysisService(p2_db).analyze(processing_job_id=job["id"], snapshot_id=snapshot_id, text="某生物医药公司入选产业榜单", provider_name="rule")
    candidate_id = analysis["candidate_ids"][0]
    products = IntelligenceProductService(p2_db)
    with pytest.raises(ValueError, match="candidate_not_approved"):
        products.publish_candidate(candidate_id, actor="reviewer", permissions={"review_data"})
    with pytest.raises(PermissionError, match="review_data_required"):
        IntelligenceReviewService(p2_db).review_candidate(candidate_id, decision="approved", actor="outsider", permissions=set())
    approved = IntelligenceReviewService(p2_db).review_candidate(candidate_id, decision="approved", actor="reviewer", permissions={"review_data"}, final_value="recognition-reviewed")
    assert approved["reviewed_by"] == "reviewer" and approved["reviewed_at"]
    assert approved["normalized_value"] == "recognition-reviewed"
    evidence = EvidenceService(p2_db).candidate_trace(candidate_id)
    assert evidence and evidence[0]["snapshot_id"] == snapshot_id
    EvidenceService(p2_db).link_candidate(candidate_id, snapshot_id, excerpt=evidence[0]["evidence_excerpt"], char_start=evidence[0]["char_start"], char_end=evidence[0]["char_end"], locator={"duplicate": True})
    with sqlite3.connect(p2_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM p2_fact_candidate_evidence WHERE candidate_id=?", (candidate_id,)).fetchone()[0] == 1
    product = products.publish_candidate(candidate_id, actor="reviewer", permissions={"review_data"})
    trace = products.trace(product["id"])
    assert trace["candidates"][0]["id"] == candidate_id
    assert trace["evidence"][0]["snapshot_id"] == snapshot_id
    products.delete(product["id"], actor="reviewer", permissions={"review_data"})
    with sqlite3.connect(p2_db) as conn:
        assert conn.execute("SELECT 1 FROM v04g_source_snapshots WHERE id=?", (snapshot_id,)).fetchone()


def test_rejection_reason_and_merge_are_audited(p2_db: Path):
    _, _, snapshot_id = source_and_run(p2_db)
    job = create_processing_job(snapshot_id=snapshot_id, queued_only=False, db_path=p2_db)
    service = FactCandidateService(p2_db)
    common = {"processing_job_id": job["id"], "snapshot_id": snapshot_id, "candidate_type": "risk", "evidence_excerpt": "风险证据", "confidence_score": 55, "generated_by": "rule", "provider": "rule", "model": "test", "prompt_version": "v1"}
    rejected = service.create(value="风险一", **common)
    merged = service.create(value="风险二", **common)
    target = service.create(value="风险三", **common)
    row = service.review(rejected["id"], decision="rejected", actor="reviewer", permissions={"review_data"}, reason="证据不足")
    assert row["rejection_reason"] == "证据不足"
    row = service.review(merged["id"], decision="merged", actor="reviewer", permissions={"review_data"}, reason="重复候选", merged_into_candidate_id=target["id"])
    assert row["pipeline_review_status"] == "merged" and row["merged_into_candidate_id"] == target["id"]


def test_intelligence_navigation_has_unique_formal_routes_and_legacy_resolution():
    children = [item for item in list_capabilities() if item.get("parent_key") == "intelligence"]
    keys = [item["capability_key"] for item in children]
    routes = [item["web_route"] for item in children]
    assert len(keys) == len(set(keys))
    assert len(routes) == len(set(routes))
    assert resolve_active_capability("/signals")["capability_key"] == "intelligence.signals"
    assert resolve_active_capability("/signals/watchlists")["capability_key"] == "intelligence.company_updates"
