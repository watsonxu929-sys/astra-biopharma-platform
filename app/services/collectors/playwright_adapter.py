from __future__ import annotations

import importlib.util
from dataclasses import dataclass


class PlaywrightUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class DynamicFetchResult:
    url: str
    html: str
    screenshot_path: str | None
    status: str


class PlaywrightAdapter:
    @property
    def available(self) -> bool:
        return importlib.util.find_spec("playwright") is not None

    def fetch(self, url: str, *, dynamic: bool, timeout_ms: int = 15000, screenshot_path: str | None = None) -> DynamicFetchResult:
        if not dynamic:
            raise ValueError("playwright_requires_dynamic_source")
        if not self.available:
            raise PlaywrightUnavailable("playwright_unavailable")
        from playwright.sync_api import sync_playwright
        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.goto(url, wait_until="domcontentloaded", timeout=max(1000, min(timeout_ms, 60000)))
                if screenshot_path:
                    page.screenshot(path=screenshot_path, full_page=True)
                return DynamicFetchResult(url=page.url, html=page.content(), screenshot_path=screenshot_path, status="success")
            finally:
                browser.close()
