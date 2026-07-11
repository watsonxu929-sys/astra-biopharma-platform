from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.main import app
from app.services.navigation_service import get_secondary_navigation, resolve_active_capability


RAW_ITEM = {
    "id": 101,
    "item_no": "RAW-P2-101",
    "title": "P2.1 可发现性验收情报",
    "normalized_url": "https://example.invalid/p2",
    "source_name": "P2.1 试点来源",
    "source_no": "SRC-P2",
    "captured_at": "2026-07-11T09:00:00",
    "page_structure": "article",
    "dedup_status": "new",
    "change_status": "changed",
    "processing_status": "processed",
    "processing_status_label": "已加工",
    "candidate_count": 1,
    "first_candidate_id": 201,
    "snapshot_id": 301,
    "published_intelligence_id": 401,
    "flow_hint": "已有候选，等待审核或发布",
    "is_pilot": True,
    "pilot_batch_id": "P2P-UI-ACCEPTANCE",
}

CANDIDATE = {
    "id": 201,
    "candidate_no": "CND-P2-201",
    "collection_item_id": 101,
    "candidate_type": "event",
    "field_name": "事件",
    "subject_label": "试点企业",
    "subject_id": None,
    "matched_subject_id": None,
    "normalized_value": "试点企业发布产业进展",
    "raw_value": "试点企业发布产业进展",
    "confidence_score": 88,
    "confidence_level": "high",
    "validation_status": "valid",
    "review_status": "pending",
    "pipeline_review_status": "pending",
    "evidence_excerpt": "试点企业发布产业进展。",
    "source_url": "https://example.invalid/p2",
    "source_title": "P2.1 试点来源",
    "warning_list": [],
    "is_pilot": True,
    "pilot_batch_id": "P2P-UI-ACCEPTANCE",
}

SNAPSHOT = {
    "id": 301,
    "snapshot_no": "SNP-P2-301",
    "page_title": "P2.1 试点来源",
    "source_name": "P2.1 试点来源",
    "captured_at": "2026-07-11T09:00:00",
    "normalized_url": "https://example.invalid/p2",
    "url": "https://example.invalid/p2",
    "cleaned_text": "试点企业发布产业进展。",
    "content_hash": "a" * 64,
    "is_pilot": True,
    "pilot_batch_id": "P2P-UI-ACCEPTANCE",
}

EVIDENCE = [{"snapshot_id": 301, "page_title": "P2.1 试点来源", "url": "https://example.invalid/p2", "captured_at": "2026-07-11T09:00:00", "evidence_excerpt": "试点企业发布产业进展。", "char_start": 0, "char_end": 14, "page_number": None, "snapshot_hash": "a" * 64}]
DETAIL = {"candidate": CANDIDATE, "matches": [], "history": [], "logs": [], "evidence": EVIDENCE}


def test_intelligence_secondary_navigation_has_only_six_work_entries():
    context = {"permissions": ["view_internal", "review_data", "manage_monitoring"], "auth_disabled": True}
    items = get_secondary_navigation(context, "intelligence", "/processing/candidates/201")
    assert [item["label"] for item in items] == ["原始情报", "数据处理", "候选匹配", "情报审核", "产业信号", "报告中心"]
    assert resolve_active_capability("/processing/candidates/201/evidence")["capability_key"] == "intelligence.candidates"
    assert resolve_active_capability("/collection/snapshots/301")["capability_key"] == "intelligence.raw_items"


def test_lists_expose_clickable_p2_detail_links(monkeypatch):
    monkeypatch.setenv("APP_AUTH_DISABLED", "1")
    monkeypatch.setattr("app.v05f_collection.list_items", lambda **kwargs: ([RAW_ITEM], 1))
    monkeypatch.setattr("app.v05g_processing.list_candidates", lambda **kwargs: ([CANDIDATE], 1))
    monkeypatch.setattr("app.v05g_processing.list_review_queue", lambda **kwargs: ([CANDIDATE], 1))
    monkeypatch.setattr("app.v05h_reports.list_reports", lambda **kwargs: {"data": [], "pagination": {"total": 0}})
    monkeypatch.setattr("app.v05h_reports.list_report_jobs", lambda **kwargs: {"data": [], "pagination": {"total": 0}})
    monkeypatch.setattr("app.v05h_reports.UnifiedIntelligenceService.list", lambda self, **kwargs: {"items": [{"id": 401, "title": "P2.1 正式产品", "source_name": "fact_candidate", "is_pilot": True, "pilot_batch_id": "P2P-UI-ACCEPTANCE"}]})
    with TestClient(app) as client:
        raw_html = client.get("/collection/items").text
        assert 'href="/collection/items/101"' in raw_html
        assert 'href="/collection/snapshots/301"' in raw_html
        assert 'href="/processing/jobs?item_id=101"' in raw_html
        candidate_html = client.get("/processing/candidates").text
        assert 'href="/processing/candidates/201"' in candidate_html
        assert 'href="/processing/candidates/201/matches"' in candidate_html
        assert 'href="/processing/candidates/201/evidence"' in candidate_html
        review_html = client.get("/processing/review-queue").text
        assert 'href="/processing/candidates/201"' in review_html
        assert 'action="/processing/candidates/201/review"' in review_html
        reports_html = client.get("/reports").text
        assert 'href="/reports/products/401"' in reports_html


def test_p2_detail_pages_render_http_200(monkeypatch):
    monkeypatch.setenv("APP_AUTH_DISABLED", "1")
    monkeypatch.setattr("app.v05f_collection.list_items", lambda **kwargs: ([RAW_ITEM], 1))
    monkeypatch.setattr("app.v05f_collection.snapshot_detail", lambda snapshot_id: SNAPSHOT)
    monkeypatch.setattr("app.v05g_processing.candidate_detail", lambda candidate_id: DETAIL)
    product = SimpleNamespace(id=401, title="P2.1 正式产品", intel_type="event", credibility=4, importance=3, source_name="fact_candidate", published_at=None, summary="正式产品摘要", content="正式产品正文", companies=None, industry_directions=None, is_pilot=True, pilot_batch_id="P2P-UI-ACCEPTANCE")
    monkeypatch.setattr("app.v05h_reports.UnifiedIntelligenceService.detail", lambda self, product_id: product)
    monkeypatch.setattr("app.v05h_reports.IntelligenceProductService.trace", lambda self, product_id: {"candidates": [CANDIDATE], "evidence": EVIDENCE})
    with TestClient(app) as client:
        for url in ["/collection/items/101", "/collection/snapshots/301", "/processing/candidates/201", "/processing/candidates/201/matches", "/processing/candidates/201/evidence", "/reports/products/401"]:
            response = client.get(url)
            assert response.status_code == 200, (url, response.text[:500])
