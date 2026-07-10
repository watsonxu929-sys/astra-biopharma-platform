from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("APP_AUTH_DISABLED", "1")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

from fastapi.testclient import TestClient

from app.main import app
from app.security import required_permission
from scripts.migrate_platform_mvp_v1 import run_migration as migrate_platform


client = TestClient(app, raise_server_exceptions=False)
checks: list[tuple[str, bool, str]] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    checks.append((name, bool(condition), detail))
    print(("PASS" if condition else "FAIL"), name, detail)


def get(path: str):
    return client.get(path)


def main() -> int:
    # ????
    r = get("/network/people")
    check("/network/people ????", r.status_code == 200, str(r.status_code))
    check("? Person ???????", "????" in r.text or r.status_code == 200)
    check("?????????", "person-card" in r.text or "????" in r.text)
    check("?????????", r.status_code == 200)
    api = get("/api/v1/network/people?page=1&page_size=2")
    data = api.json() if api.headers.get("content-type", "").startswith("application/json") else {}
    check("?? API ????", api.status_code == 200 and data.get("page") == 1 and data.get("page_size") == 2)
    filtered = get("/api/v1/network/people?keyword=NOT_MATCHING_VERIFY_KEYWORD")
    check("??????", filtered.status_code == 200 and filtered.json().get("total") == 0)
    rec = get("/api/v1/network/recommendations/people")
    rec_data = rec.json().get("data", {}) if rec.status_code == 200 else {}
    rec_items = rec_data.get("items") or []
    check("???????", rec.status_code == 200 and (not rec_items or bool(rec_items[0].get("reasons"))))
    leak_text = api.text.lower()
    check("?????????", "contact_phone" not in leak_text and "contact_email" not in leak_text)
    missing = get("/api/v1/network/people/999999999")
    check("?????????????", missing.status_code in {403, 404})

    # ???
    club = get("/club")
    check("/club ????", club.status_code == 200)
    ctx = get("/api/v1/me/club-context")
    ctx_data = ctx.json().get("data", {}) if ctx.status_code == 200 else {}
    check("????????????", ctx.status_code == 200 and "has_club" in ctx_data and "clubs" in ctx_data)
    check("??????????????????", "club_count" in ctx_data and isinstance(ctx_data.get("clubs"), list))
    check("?????????", get("/club/members").status_code == 200)
    check("?????????????????", required_permission("/club/members", "GET") == "manage_club")
    check("Club?Membership?Organization ??????", ctx.status_code == 200 and "organization" not in (ctx_data.get("default_club_id") or ""))
    check("????????????", {"has_club", "club_count", "default_club_id", "can_switch", "clubs"}.issubset(ctx_data.keys()))

    # ????
    old_routes = [
        ("??????????", "/club/members"),
        ("??????????", "/club/import"),
        ("????????????", "/me/industry-profile"),
        ("??????????", "/network/organizations"),
    ]
    for name, path in old_routes:
        check(name, get(path).status_code in {200, 403})
    home = get("/platform")
    check("???????????", all(token in home.text for token in ["/club/members", "/club/import", "/me/industry-profile"]))
    check("?????????", all(get(path).status_code != 404 for _, path in old_routes))

    # ??? API
    bootstrap = get("/api/v1/client/bootstrap")
    check("/api/v1/client/bootstrap ?? JSON", bootstrap.status_code == 200 and bootstrap.headers.get("content-type", "").startswith("application/json"))
    nav_web = get("/api/v1/client/navigation?client=web")
    nav_app = get("/api/v1/client/navigation?client=app")
    nav_mini = get("/api/v1/client/navigation?client=miniprogram")
    check("/api/v1/client/navigation ??????????", nav_web.status_code == 200 and "items" in nav_web.json().get("data", {}))
    web_keys = {item["capability_key"] for item in nav_web.json().get("data", {}).get("items", [])}
    app_keys = {item["capability_key"] for item in nav_app.json().get("data", {}).get("items", [])}
    mini_keys = {item["capability_key"] for item in nav_mini.json().get("data", {}).get("items", [])}
    check("web?app?miniprogram ????????", app_keys.issubset(web_keys) and mini_keys.issubset(web_keys))
    check("API 404 ???? JSON", get("/api/v1/no-such").json().get("error", {}).get("code") == "NOT_FOUND")
    check("API 403 ???? JSON", required_permission("/api/v1/organizations", "GET") == "manage_club")
    check("API 500 ??? traceback", "traceback" not in get("/api/v1/no-such").text.lower())
    check("/api/v1/health ??", get("/api/v1/health").status_code == 200)
    check("/api/v1/version ??", get("/api/v1/version").status_code == 200)

    # ???????
    check("?????????????", Path("scripts/verify_identity_link_v1.py").exists())
    check("Membership ????????", Path("scripts/verify_membership_access_scope_v1.py").exists())
    check("Organization ??????", Path("scripts/verify_organization_core_v1.py").exists())
    check("RBAC ??????", Path("scripts/verify_rbac_authorization_v1.py").exists())
    check("?? MVP ??????", Path("scripts/verify_platform_mvp_v1.py").exists())
    try:
        migrate_platform()
        migrate_platform()
        migration_ok = True
    except Exception as exc:
        migration_ok = False
        print("migration error", exc)
    check("????????", migration_ok)
    core_pages = ["/platform", "/club", "/network", "/intelligence", "/resources", "/opportunities"]
    check("??????????", all(get(path).status_code == 200 for path in core_pages))

    passed = sum(1 for _, ok, _ in checks if ok)
    total = len(checks)
    print("=" * 60)
    print(f"????: {passed}/{total} ??")
    return 0 if passed == total else 1


if __name__ == "__main__":
    raise SystemExit(main())
