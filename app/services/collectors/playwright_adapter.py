from __future__ import annotations

import importlib.util
import time
from dataclasses import dataclass
from pathlib import Path


class PlaywrightUnavailable(RuntimeError):
    pass


class PlaywrightCollectionError(RuntimeError):
    def __init__(self, code: str, *, network_errors: list[str] | None = None):
        super().__init__(code)
        self.code = code
        self.network_errors = list(network_errors or [])[:20]



@dataclass(frozen=True)
class DynamicFetchResult:
    url: str
    html: str
    screenshot_path: str | None
    title: str
    status: str
    duration_ms: int
    network_errors: tuple[str, ...] = ()


class PlaywrightAdapter:
    @property
    def available(self) -> bool:
        return importlib.util.find_spec("playwright") is not None

    def fetch(
        self,
        url: str,
        *,
        dynamic: bool,
        timeout_ms: int = 15000,
        wait_selector: str = "",
        screenshot_path: str | None = None,
    ) -> DynamicFetchResult:
        if not dynamic:
            raise ValueError("playwright_requires_dynamic_source")
        if not self.available:
            raise PlaywrightUnavailable("playwright_unavailable")

        from playwright.sync_api import sync_playwright

        started = time.perf_counter()
        network_errors: list[str] = []
        if screenshot_path:
            Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)

        with sync_playwright() as runtime:
            browser = runtime.chromium.launch(headless=True)
            try:
                context = browser.new_context(
                    user_agent="BiopharmaIntelligencePilot/2.2 (+controlled-public-source-pilot)"
                )
                page = context.new_page()
                page.on(
                    "requestfailed",
                    lambda request: network_errors.append(
                        f"{request.method} {request.url[:300]}: {request.failure or 'request_failed'}"
                    ),
                )
                response = page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=max(1000, min(timeout_ms, 60000)),
                )
                if response and response.status >= 400:
                    raise PlaywrightCollectionError(
                        f"playwright_http_{response.status}", network_errors=network_errors
                    )
                if wait_selector:
                    page.wait_for_selector(
                        wait_selector,
                        state="attached",
                        timeout=max(1000, min(timeout_ms, 60000)),
                    )
                page.wait_for_timeout(min(2000, max(500, timeout_ms // 10)))
                if screenshot_path:
                    page.screenshot(path=screenshot_path, full_page=True)
                return DynamicFetchResult(
                    url=page.url,
                    html=page.content(),
                    title=page.title(),
                    screenshot_path=screenshot_path,
                    status="success",
                    duration_ms=round((time.perf_counter() - started) * 1000),
                    network_errors=tuple(network_errors[:20]),
                )
            except PlaywrightCollectionError:
                raise
            except Exception as exc:
                code = (
                    "playwright_timeout"
                    if exc.__class__.__name__ == "TimeoutError"
                    else "playwright_fetch_failed"
                )
                raise PlaywrightCollectionError(code, network_errors=network_errors) from exc
            finally:
                browser.close()
