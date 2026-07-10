from __future__ import annotations

import os
import shutil
import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SRC_DB = ROOT / "data" / "app.db"
passed = 0
failed = 0


def check(condition: bool, message: str) -> None:
    global passed, failed
    if condition:
        passed += 1
        print(f"[PASS] {message}")
    else:
        failed += 1
        print(f"[FAIL] {message}")


def seed(conn: sqlite3.Connection) -> dict[str, str]:
    ts = datetime.now().replace(microsecond=0).isoformat()
    suffix = datetime.now().strftime("%H%M%S%f")
    org_ext = f"ORG-V05E-{suffix}"
    person_ext = f"PER-V05E-{suffix}"
    project_ext = f"PRJ-V05E-{suffix}"
    conn.execute(
        "INSERT INTO organizations(external_id,standard_name,org_type,region,industry_tags,visibility,verification_status,created_at,manually_confirmed,is_active) VALUES (?,?,?,?,?,'内部','已确认',?,1,1)",
        (org_ext, "v05E验证生物", "biotech", "上海", "创新药;融资", ts),
    )
    conn.execute(
        "INSERT INTO people(external_id,name,public_role,organization_network,ability_tags,visibility,verification_status,created_at,manually_confirmed,is_active) VALUES (?,?,?,?,?,'内部','已确认',?,1,1)",
        (person_ext, "v05E张验证", "CEO", "v05E验证生物", "融资;BD", ts),
    )
    conn.execute(
        "INSERT INTO projects(external_id,name,project_type,owner_external_id,focus_tags,visibility,status,created_at,manually_confirmed,is_active) VALUES (?,?,?,?,?,'内部','已确认',?,1,1)",
        (project_ext, "v05E融资项目", "BD", org_ext, "融资;合作", ts),
    )
    conn.execute(
        "INSERT INTO relations(external_id,source_external_id,relation_type,target_external_id,period,evidence_source,visibility,verification_status,created_at,manually_confirmed,is_active) VALUES (?,?,?,?,?,'验证证据','内部','已确认',?,1,1)",
        (f"REL-V05E-{suffix}", person_ext, "任职", org_ext, "2026", ts),
    )
    conn.execute(
        "INSERT INTO events(external_id,event_date,name,event_type,related_entity,fact_summary,visibility,verification_status,created_at,manually_confirmed,is_active) VALUES (?,?,?,?,?,?,'内部','已确认',?,1,1)",
        (f"EVT-V05E-{suffix}", "2026-06-30", "v05E验证生物完成战略融资", "融资", org_ext, "公司完成战略融资，用于临床推进和产能建设。", ts),
    )
    conn.execute(
        "INSERT INTO raw_intelligence(title,source_url,source_type,content,visibility,review_status,created_at) VALUES (?,?,?,?,?,?,?)",
        ("v05E验证情报", "https://example.invalid/v05e", "manual", "v05E验证生物完成战略融资。", "内部", "已审核", ts),
    )
    conn.execute(
        "INSERT INTO v04g_monitoring_sources(source_no,name,source_type,url,subject_type,subject_id,check_frequency,is_enabled,fetch_mode,created_at,updated_at) VALUES (?,?,?,?,?,'{}','manual',1,'manual',?,?)".format(org_ext),
        (f"SRC-V05E-{suffix}", "v05E官网", "official", "https://example.invalid/source", "organization", ts, ts),
    )
    source_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO v04g_monitoring_runs(run_no,monitoring_source_id,status,started_at,finished_at,changed,created_proposal_count,created_at) VALUES (?,?, 'success',?,?,1,1,?)",
        (f"RUN-V05E-{suffix}", source_id, ts, ts, ts),
    )
    run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO v04g_update_proposals(proposal_no,monitoring_source_id,monitoring_run_id,subject_type,subject_id,proposal_type,field_name,old_value,proposed_value,evidence_excerpt,confidence_level,status,conflict_level,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (f"PROP-V05E-{suffix}", source_id, run_id, "organization", org_ext, "field_update", "needs", "", "融资需求", "官网新增融资需求", "high", "pending", "none", ts, ts),
    )
    conn.commit()
    return {"org": org_ext, "person": person_ext, "project": project_ext}


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="verify_v05e_") as tmp:
        tmp_db = Path(tmp) / "app.db"
        if SRC_DB.exists():
            shutil.copy2(SRC_DB, tmp_db)
        else:
            tmp_db.touch()
        os.environ["APP_DB_PATH"] = str(tmp_db)
        from scripts.migrate_v05e import migrate

        migrate(tmp_db, backup=False)
        migrate(tmp_db, backup=False)
        conn = sqlite3.connect(tmp_db)
        conn.row_factory = sqlite3.Row
        ids = seed(conn)
        before_actions = conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        conn.close()

        from fastapi.testclient import TestClient
        from app.main import app

        os.environ["APP_AUTH_DISABLED"] = ""
        public_client = TestClient(app, follow_redirects=False)
        unauth = public_client.get("/api/v1/subjects")
        check(unauth.status_code == 401 and unauth.headers.get("content-type", "").startswith("application/json") and "error" in unauth.json(), "unauthenticated internal API returns 401 JSON")

        os.environ["APP_AUTH_DISABLED"] = "1"
        client = TestClient(app, follow_redirects=False)
        for path in ["/api/v1/health", "/api/v1/meta", "/api/v1/me", "/api/v1/subjects", f"/api/v1/subjects/organization/{ids['org']}", "/api/v1/events", "/api/v1/relationships", "/api/v1/intelligence", "/api/v1/monitoring/sources", "/api/v1/monitoring/runs", "/api/v1/monitoring/proposals", "/api/v1/signals", "/api/v1/watchlists", "/api/v1/dashboard"]:
            r = client.get(path)
            check(r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"), f"{path} returns JSON 200")

        search = client.get("/api/v1/search?q=%25")
        check(search.status_code == 200 and "data" in search.json() and search.json()["data"]["q"] == "%", "search handles special character safely")
        empty_search = client.get("/api/v1/search?q=")
        check(empty_search.status_code == 200 and empty_search.json()["data"]["total"] == 0, "empty search does not run full database search")
        subject = client.get(f"/api/v1/subjects/organization/{ids['org']}").json()["data"]
        check("source_text" not in subject and "mobile" not in subject and subject["api_url"].startswith("/api/v1/subjects/"), "subject API hides raw text and sensitive contacts")
        missing = client.get("/api/v1/subjects/organization/NOT-FOUND-V05E")
        check(missing.status_code == 404 and "error" in missing.json(), "missing subject returns 404 JSON")
        invalid = client.get("/api/v1/subjects?subject_type=unknown")
        check(invalid.status_code == 422, "invalid subject type returns 422")

        generated = client.post("/api/v1/signals/generate-from-events?limit=20")
        check(generated.status_code == 200 and generated.json()["data"]["created"] >= 1, "confirmed event can generate industry signal")
        duplicate = client.post("/api/v1/signals/generate-from-events?limit=20")
        check(duplicate.status_code == 200 and duplicate.json()["data"]["created"] == 0, "same source does not duplicate signal")
        signals = client.get("/api/v1/signals?signal_level=high").json()["data"]
        signal_id = signals[0]["id"]
        status = client.post(f"/api/v1/signals/{signal_id}/status?status=important")
        check(status.status_code == 200 and status.json()["data"]["status"] == "important", "signal status can be updated")
        converted = client.post(f"/api/v1/signals/{signal_id}/convert-action")
        converted_again = client.post(f"/api/v1/signals/{signal_id}/convert-action")
        check(converted.status_code == 200 and converted.json()["data"].get("created") is True, "signal converts to action only after manual POST")
        check(converted_again.json()["data"].get("idempotent") is True, "signal to action conversion is idempotent")

        wl = client.post("/api/v1/watchlists?name=v05E清单&category=key_organization&visibility=team")
        watchlist_id = wl.json()["data"]["id"]
        add = client.post(f"/api/v1/watchlists/{watchlist_id}/items?subject_type=organization&subject_id={ids['org']}&priority=high&reason=验证关注")
        add_again = client.post(f"/api/v1/watchlists/{watchlist_id}/items?subject_type=organization&subject_id={ids['org']}&priority=high")
        items = client.get(f"/api/v1/watchlists/{watchlist_id}/items")
        check(wl.status_code == 200 and add.json()["data"]["created"] is True, "watchlist can be created and linked to existing subject")
        check(add_again.json()["data"].get("idempotent") is True and items.json()["pagination"]["total"] == 1, "watchlist blocks duplicate active subject")
        remove = client.post(f"/api/v1/watchlists/items/{items.json()['data'][0]['id']}/remove")
        check(remove.status_code == 200 and remove.json()["data"]["removed"] is True, "watchlist item supports soft removal")

        dashboard = client.get("/api/v1/dashboard?days=30&industry=创新药&region=上海")
        check(dashboard.status_code == 200 and dashboard.json()["data"]["counts"]["recent_events"] >= 1, "dashboard metrics come from seeded real data")
        for path in ["/intelligence/dashboard", "/signals", "/watchlists"]:
            r = client.get(path)
            check(r.status_code == 200 and "text/html" in r.headers.get("content-type", ""), f"{path} page returns 200")

        conn = sqlite3.connect(tmp_db)
        after_actions = conn.execute("SELECT COUNT(*) FROM actions").fetchone()[0]
        signal_tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'v05e_%'")}
        conn.close()
        check({"v05e_industry_signals", "v05e_watchlists", "v05e_watchlist_items"}.issubset(signal_tables), "v05E migration tables exist")
        check(after_actions == before_actions + 1, "only explicit signal conversion creates one action")

    print(f"verify_v05e completed passed={passed} failed={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
