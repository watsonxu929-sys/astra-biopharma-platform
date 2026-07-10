from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
BASE = os.environ.get("VERIFY_BASE_URL", "http://127.0.0.1:8050")
DB_PATH = ROOT / "data" / "app.db"
SCREENSHOTS = [
    "artifacts/screenshots/v06h_workspace_1440.png",
    "artifacts/screenshots/v06h_people_admin_1440.png",
    "artifacts/screenshots/v06h_person_edit_1440.png",
    "artifacts/screenshots/v06h_intelligence_1440.png",
    "artifacts/screenshots/v06h_resources_1440.png",
    "artifacts/screenshots/v06h_opportunities_1440.png",
    "artifacts/screenshots/v06h_intelligence_operations_1440.png",
    "artifacts/screenshots/v06h_admin_platform_1440.png",
    "artifacts/screenshots/v06h_mobile_navigation.png",
]


def http_get(path: str) -> tuple[int, str]:
    try:
        with urlopen(Request(BASE + path), timeout=12) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return int(exc.code), body
    except (URLError, OSError) as exc:
        return 0, str(exc)


def http_post(path: str, data: dict[str, str]) -> tuple[int, str]:
    payload = urlencode(data).encode("utf-8")
    req = Request(BASE + path, data=payload, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        opener = urlopen(req, timeout=12)
        return int(opener.status), opener.read().decode("utf-8", errors="replace")
    except HTTPError as exc:
        if exc.code in {302, 303, 307, 308}:
            return int(exc.code), ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return int(exc.code), body


def check(results: list[bool], name: str, ok: bool, detail: str = "") -> None:
    print(("PASS" if ok else "FAIL"), name, detail)
    results.append(bool(ok))


def card_count(body: str, marker: str) -> int:
    return body.count(marker)


def db_value(sql: str) -> str:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(sql).fetchone()
    return str(row[0] or "") if row else ""


def page_count(path: str, marker: str) -> int:
    code, body = http_get(path)
    if code != 200:
        return -1
    return card_count(body, marker)


def verify_person_edit(results: list[bool]) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM people WHERE name LIKE 'V06E%' ORDER BY id LIMIT 1").fetchone()
        if row is None:
            row = conn.execute("SELECT * FROM people ORDER BY id DESC LIMIT 1").fetchone()
    if row is None:
        check(results, "person_edit_save", False, "no person row")
        return
    original_tags = row["ability_tags"] or ""
    new_tags = (original_tags + ";v06h-usability-check").strip(";")
    base = {
        "name": row["name"] or "",
        "public_role": row["public_role"] or "",
        "organization_network": row["organization_network"] or "",
        "value_provided": row["value_provided"] or "",
        "visibility": row["visibility"] or "",
        "verification_status": row["verification_status"] or "",
    }
    edit_path = f"/admin/people/{row['id']}"
    code, body = http_get(edit_path)
    saved_code, _ = http_post(f"/admin/people/{row['id']}/update", {**base, "ability_tags": new_tags, "is_active": "1"})
    verify_code, verify_body = http_get(edit_path)
    saved = verify_code == 200 and "v06h-usability-check" in verify_body
    restore_data = {**base, "ability_tags": original_tags}
    if row["is_active"]:
        restore_data["is_active"] = "1"
    restore_code, _ = http_post(f"/admin/people/{row['id']}/update", restore_data)
    restored_code, restored_body = http_get(edit_path)
    restored = restored_code == 200 and "v06h-usability-check" not in restored_body
    check(results, "person_edit_entry", code == 200 and "/update" in body, f"person_id={row['id']}")
    check(results, "person_edit_save", saved_code in {302, 303, 307, 308, 200} and saved, f"save={saved_code}")
    check(results, "person_edit_restore", restore_code in {302, 303, 307, 308, 200} and restored, f"restore={restore_code}")


def verify_filters(results: list[bool]) -> None:
    intel_type = db_value("SELECT intel_type FROM v06_intelligence_items WHERE status='published' AND intel_type<>'' LIMIT 1")
    intel_q = db_value("SELECT substr(title,1,8) FROM v06_intelligence_items WHERE status='published' LIMIT 1")
    res_type = db_value("SELECT resource_type FROM v06_market_resources WHERE status='published' AND resource_type<>'' LIMIT 1")
    res_q = db_value("SELECT substr(title,1,8) FROM v06_market_resources WHERE status='published' LIMIT 1")
    opp_stage = db_value("SELECT stage FROM v06_opportunities WHERE status='active' AND stage<>'' LIMIT 1")
    opp_q = db_value("SELECT substr(title,1,8) FROM v06_opportunities LIMIT 1")

    i0 = page_count("/intelligence", 'class="intel-card"')
    check(results, "intelligence_q_filter_changes", page_count("/intelligence?" + urlencode({"q": intel_q}), 'class="intel-card"') != i0, intel_q)
    check(results, "intelligence_type_filter_changes", page_count("/intelligence?" + urlencode({"intel_type": intel_type}), 'class="intel-card"') != i0, intel_type)
    code, ibody = http_get("/intelligence?status=published&importance=high")
    check(results, "intelligence_invalid_filters_hidden", code == 200 and 'name="status"' not in ibody and 'name="importance"' not in ibody)

    r0 = page_count("/resources", 'class="resource-card"')
    check(results, "resources_q_filter_changes", page_count("/resources?" + urlencode({"q": res_q}), 'class="resource-card"') != r0, res_q)
    check(results, "resources_direction_filter_changes", page_count("/resources?direction=supply", 'class="resource-card"') != r0)
    check(results, "resources_type_filter_changes", page_count("/resources?" + urlencode({"resource_type": res_type}), 'class="resource-card"') != r0, res_type)
    code, rbody = http_get("/resources?status=published")
    check(results, "resources_invalid_status_hidden", code == 200 and 'name="status"' not in rbody)

    o0 = page_count("/opportunities", 'class="opportunity-card"')
    check(results, "opportunities_q_filter_changes", page_count("/opportunities?" + urlencode({"q": opp_q}), 'class="opportunity-card"') != o0, opp_q)
    check(results, "opportunities_stage_filter_changes", page_count("/opportunities?" + urlencode({"stage": opp_stage}), 'class="opportunity-card"') != o0, opp_stage)
    code, obody = http_get("/opportunities?status=active")
    check(results, "opportunities_status_filter_kept", code == 200 and 'name="status"' in obody)


def verify_navigation(results: list[bool]) -> None:
    from app.services.navigation_service import get_client_navigation
    admin = {"permissions": {"view_internal", "edit_data", "review_data", "manage_monitoring", "manage_club", "manage_users", "use_recommendations"}}
    expected = {
        "/platform": "workspace",
        "/network": "network",
        "/network/people": "network",
        "/admin/people": "network",
        "/intelligence": "intelligence",
        "/intelligence/operations": "intelligence",
        "/resources": "resources",
        "/opportunities": "resources",
        "/club": "club",
        "/admin/platform": "admin",
    }
    for path, category in expected.items():
        code, _ = http_get(path)
        nav = get_client_navigation(admin, path=path)
        secondary = [x["category"] for x in nav.get("secondary", [])]
        check(results, f"nav_{path}", code == 200 and nav.get("active", {}).get("category") == category and all(x == category for x in secondary), str(nav.get("active", {})))


def verify_screenshots(results: list[bool]) -> None:
    for rel in SCREENSHOTS:
        path = ROOT / rel
        check(results, f"screenshot_{Path(rel).name}", path.exists() and path.stat().st_size > 1000, str(path.stat().st_size if path.exists() else 0))


def main() -> int:
    os.environ["APP_AUTH_DISABLED"] = "1"
    os.environ.setdefault("DATABASE_URL", "sqlite:///data/app.db")
    proc = None
    if not os.environ.get("VERIFY_BASE_URL"):
        proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8050"], cwd=ROOT, env=os.environ.copy(), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(5)
    results: list[bool] = []
    try:
        for path in ["/admin/people", "/opportunities", "/intelligence", "/resources"]:
            code, body = http_get(path)
            check(results, f"page_{path}", code == 200 and "Traceback" not in body and "Internal Server Error" not in body, f"status={code}")
        code, people_body = http_get("/admin/people")
        check(results, "people_edit_links", code == 200 and "/admin/people/" in people_body and "编辑" in people_body)
        verify_person_edit(results)
        verify_filters(results)
        verify_navigation(results)
        verify_screenshots(results)
    finally:
        if proc and proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
    passed = sum(1 for item in results if item)
    print(f"verify_product_usability_v1 passed={passed} failed={len(results)-passed}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())



