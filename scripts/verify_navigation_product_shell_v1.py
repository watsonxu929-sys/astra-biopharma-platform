from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.test_db_utils import run_migration_suite, temporary_database


def check(results: list[bool], name: str, condition: bool, detail: str = "") -> None:
    print(("PASS" if condition else "FAIL"), name, detail)
    results.append(bool(condition))


def main() -> int:
    results: list[bool] = []
    with temporary_database("nav_shell_") as db_path:
        run_migration_suite(db_path)
        os.environ["APP_AUTH_DISABLED"] = "1"
        from fastapi.testclient import TestClient
        from app.database import Base, engine
        from app.main import app
        from app.platform.capability_registry import validate_registry
        from app.services.navigation_service import get_client_navigation, validate_registered_routes
        Base.metadata.create_all(bind=engine)
        viewer = {"authenticated": True, "auth_disabled": False, "user": {"id": 1, "role": "viewer"}, "permissions": ["view_internal", "identity.view_self", "membership.view_self", "organization.view_self"]}
        admin = {"authenticated": True, "auth_disabled": False, "user": {"id": 2, "role": "admin"}, "permissions": ["view_internal", "identity.view_self", "membership.view_self", "organization.view_self", "review_data", "manage_club", "manage_users", "use_recommendations"]}
        primary = get_client_navigation(viewer, client="web", path="/platform")["primary"]
        check(results, "primary menu max five", len(primary) <= 5, str(len(primary)))
        check(results, "primary names and order", [x["name"] for x in primary] == ["工作台", "产业关系", "情报中心", "业务协同", "俱乐部"], str([x["name"] for x in primary]))
        check(results, "admin hidden for ordinary user", not get_client_navigation(viewer, client="web", path="/platform")["admin"])
        check(results, "admin visible for admin", bool(get_client_navigation(admin, client="web", path="/admin/platform")["admin"]))
        check(results, "registry validates", not validate_registry(), str(validate_registry()))
        check(results, "registered route validation", not validate_registered_routes(app), str(validate_registered_routes(app)))
        web_keys = {x["capability_key"] for x in get_client_navigation(viewer, client="web", path="/platform")["primary"]}
        app_keys = {x["capability_key"] for x in get_client_navigation(viewer, client="app", path="/platform")["primary"]}
        mini_keys = {x["capability_key"] for x in get_client_navigation(viewer, client="miniprogram", path="/platform")["primary"]}
        check(results, "three clients share primary capability keys", web_keys == app_keys == mini_keys, f"{web_keys}/{app_keys}/{mini_keys}")
        check(results, "client does not expand permissions", not get_client_navigation(viewer, client="app", path="/platform")["admin"])
        client = TestClient(app, raise_server_exceptions=False)
        for path in ["/api/v1/client/bootstrap", "/api/v1/client/navigation?client=web", "/api/v1/client/navigation?client=app", "/api/v1/client/navigation?client=miniprogram", "/api/v1/health", "/api/v1/version"]:
            r = client.get(path)
            check(results, f"api {path}", r.status_code == 200 and "traceback" not in r.text.lower(), str(r.status_code))
        boot = client.get("/api/v1/client/bootstrap").json()
        check(results, "bootstrap stable json", "schema_version" in boot and "available_capabilities" in boot)
        check(results, "sensitive fields not leaked", "database_path" not in str(boot).lower() and "session_secret" not in str(boot).lower())
        for path in ["/platform", "/network", "/intelligence", "/resources", "/club", "/admin/platform", "/intelligence/legacy", "/resources/legacy"]:
            r = client.get(path, follow_redirects=False)
            check(results, f"page {path}", r.status_code in {200, 303, 401, 403, 404} and r.status_code != 422 and "traceback" not in r.text.lower(), str(r.status_code))
        os.environ.pop("APP_AUTH_DISABLED", None)
        engine.dispose(close=True)
    print(f"verify_navigation_product_shell_v1 passed={sum(results)} failed={len(results)-sum(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

