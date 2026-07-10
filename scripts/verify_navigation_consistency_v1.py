from __future__ import annotations

import gc
import os
import sqlite3
import time
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup
from fastapi.testclient import TestClient

from scripts.test_db_utils import run_migration_suite, temporary_database


def u(value: str) -> str:
    return value.encode("ascii").decode("unicode_escape")


def check(results: list[bool], name: str, ok: bool, detail: str = "") -> None:
    print(("PASS" if ok else "FAIL"), name, detail)
    results.append(bool(ok))


EXPECTED_PRIMARY = [u(r"\u5de5\u4f5c\u53f0"), u(r"\u4ea7\u4e1a\u5173\u7cfb"), u(r"\u60c5\u62a5\u4e2d\u5fc3"), u(r"\u4e1a\u52a1\u534f\u540c"), u(r"\u4ff1\u4e50\u90e8")]
OLD_PRIMARY = [u(r"\u9996\u9875"), u(r"\u4ea7\u4e1a\u4eba\u8109"), u(r"\u4ea7\u4e1a\u60c5\u62a5"), u(r"\u4ea7\u4e1a\u8d44\u6e90"), u(r"\u5408\u4f5c\u4e0e\u4ea4\u6613"), u(r"\u5546\u52a1\u534f\u4f5c")]
CATEGORY_LABEL = {
    "workspace": u(r"\u5de5\u4f5c\u53f0"),
    "network": u(r"\u4ea7\u4e1a\u5173\u7cfb"),
    "intelligence": u(r"\u60c5\u62a5\u4e2d\u5fc3"),
    "resources": u(r"\u4e1a\u52a1\u534f\u540c"),
    "club": u(r"\u4ff1\u4e50\u90e8"),
}
EXPECTED = {
    "/platform": "workspace", "/workspace": "workspace",
    "/network": "network", "/network/people": "network", "/network/organizations": "network", "/admin/people": "network", "/admin/organizations": "network",
    "/intelligence": "intelligence", "/intelligence/operations": "intelligence", "/collection/sources": "intelligence", "/collection/jobs": "intelligence", "/collection/items": "intelligence", "/processing/jobs": "intelligence", "/processing/candidates": "intelligence", "/review": "intelligence", "/signals": "intelligence", "/reports": "intelligence", "/admin/intelligence": "intelligence",
    "/resources": "resources", "/opportunities": "resources",
    "/club": "club", "/club/members": "club", "/club/events": "club",
}


def nav_texts(body: str) -> tuple[list[str], list[str], list[str]]:
    soup = BeautifulSoup(body, "html.parser")
    primary = [a.get_text(strip=True) for a in soup.select("nav.main-nav a")]
    active_primary = [a.get_text(strip=True) for a in soup.select("nav.main-nav a.active")]
    secondary = [a.get_text(strip=True) for a in soup.select("nav.secondary-nav a")]
    return primary, active_primary, secondary


def main() -> int:
    results: list[bool] = []
    with temporary_database("v06i_nav_") as db_path:
        run_migration_suite(db_path)
        os.environ["APP_AUTH_DISABLED"] = "1"
        from app.database import Base, engine
        import app.models  # noqa: F401
        import app.models_platform  # noqa: F401
        Base.metadata.create_all(bind=engine)
        with sqlite3.connect(db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS identity_link_requests(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    person_id INTEGER,
                    status TEXT,
                    requested_at TEXT
                )
            """)
            conn.commit()
        from app.main import app
        from app.services.navigation_service import get_client_navigation
        client = TestClient(app)
        admin_ctx = {"permissions": {"view_internal", "edit_data", "review_data", "manage_monitoring", "manage_club", "manage_users", "use_recommendations"}}
        normal_ctx = {"permissions": {"view_internal", "identity.view_self", "membership.view_self", "organization.view_self"}}
        for path, category in EXPECTED.items():
            response = client.get(path)
            body = response.text
            primary, active_primary, secondary = nav_texts(body)
            nav = get_client_navigation(admin_ctx, path=path)
            check(results, f"page_{path}_200", response.status_code == 200, str(response.status_code))
            check(results, f"primary_consistent_{path}", primary == EXPECTED_PRIMARY, str(primary))
            check(results, f"old_primary_absent_{path}", not any(label in primary for label in OLD_PRIMARY), str(primary))
            check(results, f"active_primary_{path}", active_primary == [CATEGORY_LABEL[category]], str(active_primary))
            check(results, f"service_category_{path}", nav.get("active", {}).get("category") == category, str(nav.get("active")))
            secondary_categories = {item.get("category") for item in nav.get("secondary", [])}
            check(results, f"secondary_scoped_{path}", secondary_categories <= {category}, str(secondary_categories))
            check(results, f"secondary_visible_{path}", bool(secondary), str(secondary))
        normal_admin = get_client_navigation(normal_ctx, path="/platform").get("admin", [])
        admin_admin = get_client_navigation(admin_ctx, path="/platform").get("admin", [])
        check(results, "normal_user_no_admin_console", not normal_admin, str(normal_admin))
        check(results, "admin_user_has_admin_console", bool(admin_admin), str(admin_admin[:1]))
        for path in ["/collection/sources", "/processing/jobs", "/processing/candidates", "/review", "/signals", "/reports"]:
            nav = get_client_navigation(admin_ctx, path=path)
            check(results, f"intelligence_owner_{path}", nav.get("active", {}).get("category") == "intelligence", str(nav.get("active")))
        client.close()
        try:
            from sqlalchemy.orm import close_all_sessions
            close_all_sessions()
        except Exception:
            pass
        engine.dispose()
        for obj in list(gc.get_objects()):
            try:
                if isinstance(obj, sqlite3.Connection):
                    obj.close()
            except Exception:
                pass
        gc.collect()
        time.sleep(1.0)
    passed = sum(results)
    print(f"verify_navigation_consistency_v1 passed={passed} failed={len(results)-passed}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
