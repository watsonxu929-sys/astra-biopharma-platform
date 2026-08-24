from __future__ import annotations

import inspect
from pathlib import Path

from app.services.collection_service import extract_html
from app.services.collectors.playwright_adapter import PlaywrightAdapter


ROOT = Path(__file__).resolve().parents[1]


def test_dynamic_fetch_has_bounded_dom_settlement() -> None:
    source = inspect.getsource(PlaywrightAdapter.fetch)
    assert "page.wait_for_timeout" in source
    assert "min(2000, max(500, timeout_ms // 10))" in source


def test_rendered_html_still_uses_trafilatura_as_the_extractor() -> None:
    page = extract_html(
        "<html><head><title>Dynamic source</title></head>"
        "<body><main><h1>Biopharma update</h1><p>" + "validated content " * 30 + "</p></main></body></html>",
        "https://example.test/dynamic",
    )
    assert page.extractor == "trafilatura"
    assert len(page.text) >= 200


def test_crawl4ai_poc_does_not_enter_production_dependencies() -> None:
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8").lower()
    assert "crawl4ai" not in requirements
    production = (ROOT / "app/services/collectors/playwright_adapter.py").read_text(encoding="utf-8").lower()
    assert "crawl4ai" not in production