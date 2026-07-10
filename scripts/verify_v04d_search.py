from __future__ import annotations

import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
os.environ.setdefault("APP_AUTH_DISABLED", "1")


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    print(f"[PASS] {label}")


def main() -> int:
    from app.database import SessionLocal
    from app.main import app
    from app.models import Organization
    from fastapi.testclient import TestClient
    from sqlalchemy import select

    client = TestClient(app)
    smoke_paths = [
        "/",
        "/health",
        "/review/health",
        "/review/intake/health",
        "/search",
        "/organizations",
        "/people",
        "/projects",
        "/review",
        "/review/structure",
    ]
    html_paths = {"/", "/search", "/organizations", "/people", "/projects", "/review", "/review/structure"}
    for path in smoke_paths:
        response = client.get(path)
        check(response.status_code == 200, f"{path} returns 200")
        if path in html_paths:
            check('class="nav-search"' in response.text, f"{path} has nav search form")
            check('name="q"' in response.text, f"{path} nav search keeps q input")
            check('href="/intelligence/new"' in response.text, f"{path} keeps new intelligence action")

    cases = [
        "",
        "不存在的关键词-v04d",
        "澄明生物",
        "SRC-20260629-0005",
        "%",
        "_",
        "'",
    ]
    with SessionLocal() as db:
        org = db.scalars(select(Organization).limit(1)).first()
        if org:
            cases.extend([org.standard_name[:4], org.external_id])

    for keyword in cases:
        response = client.get("/search", params={"q": keyword})
        check(response.status_code == 200, f"search handles {keyword!r}")
        if keyword and keyword not in {"不存在的关键词-v04d", "澄明生物", "SRC-20260629-0005", "%", "_", "'"}:
            check("href=\"/organizations/" in response.text, f"search result has real organization link for {keyword!r}")

    empty_response = client.get("/search", params={"q": ""})
    check("请输入关键词" in empty_response.text, "empty keyword shows no-query hint")

    print("ALL V0.4D SEARCH CHECKS PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
