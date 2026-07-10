from __future__ import annotations

import gc
import os
import sqlite3
import time
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient

from scripts.test_db_utils import run_migration_suite, temporary_database


def u(value: str) -> str:
    return value.encode("ascii").decode("unicode_escape")


def check(results: list[bool], name: str, ok: bool, detail: str = "") -> None:
    print(("PASS" if ok else "FAIL"), name, detail)
    results.append(bool(ok))


def seed_failed_jobs(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        source_id = conn.execute("SELECT id FROM v04g_monitoring_sources ORDER BY id LIMIT 1").fetchone()["id"]
        now = "2026-07-06T16:30:00"
        conn.execute("""
            INSERT INTO v04g_monitoring_runs(run_no, monitoring_source_id, status, started_at, finished_at, created_at, job_type, trigger_type, error_type, error_message)
            VALUES ('JOB-V06I-ROBOTS', ?, 'failed', ?, ?, ?, 'collection', 'manual', 'robots_denied', 'robots blocked')
        """, (source_id, now, now, now))
        conn.execute("""
            INSERT INTO v04g_monitoring_runs(run_no, monitoring_source_id, status, started_at, finished_at, created_at, job_type, trigger_type, error_type, error_message)
            VALUES ('JOB-V06I-DISABLED', ?, 'skipped', ?, ?, ?, 'collection', 'manual', 'source_disabled', 'source disabled')
        """, (source_id, now, now, now))
        conn.commit()


def main() -> int:
    results: list[bool] = []
    with temporary_database("v06i_crawl_") as db_path:
        run_migration_suite(db_path)
        os.environ["APP_AUTH_DISABLED"] = "1"
        from app.database import Base, engine
        import app.models  # noqa: F401
        import app.models_platform  # noqa: F401
        Base.metadata.create_all(bind=engine)
        from app.main import app
        from app.services.collection_service import create_collection_source, create_job, process_job, list_items
        from app.services.intelligence_flow_service import create_processing_jobs_for_collection_run
        from app.services.product_recovery_service import publish_collection_item
        from app.v04c_review import create_review_item, resolve_review_item
        from app.services.processing import review_candidate
        from app.database import SessionLocal

        html = "<html><head><title>v06i crawl visibility</title></head><body><article><h1>v06i crawl visibility test</h1><p>BioNova Harbor BioPark oncology CMC biomarkers v06i_test</p></article></body></html>"
        source = create_collection_source(name="v06i_crawl_source", source_type="webpage", url="inline:" + html, collection_mode="http", owner="v06i", db_path=db_path)
        job = create_job(int(source["id"]), operator="v06i", db_path=db_path)
        result = process_job(int(job["id"]), db_path=db_path)
        create_processing_jobs_for_collection_run(int(job["id"]), db_path=db_path, operator="v06i")
        items, _ = list_items(db_path=db_path, page_size=10)
        item_id = int(items[0]["id"])
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            cand = conn.execute("SELECT id FROM v05g_extraction_candidates WHERE collection_item_id=? ORDER BY id LIMIT 1", (item_id,)).fetchone()
        if cand:
            review_candidate(int(cand["id"]), decision="approved", actor="v06i", note="visibility", db_path=db_path)
        review = create_review_item(item_type="intelligence_publish", subject_type="collection_item", subject_id=str(item_id), subject_label="v06i crawl publish", field_name="publication", proposed_value="publish", batch_tag="v06i_crawl", created_by="v06i", db_path=db_path)
        resolve_review_item(int(review["id"]), decision="approved", actor="v06i", note="approved", db_path=db_path)
        db = SessionLocal()
        try:
            published = publish_collection_item(db, item_id, actor_user_id=1, status="published")
            published_id = int(published.id)
        finally:
            db.close()
        seed_failed_jobs(db_path)

        client = TestClient(app)
        paths = ["/intelligence/operations", "/collection/sources", "/collection/jobs", "/collection/items", "/processing/jobs", "/processing/candidates", "/review"]
        bodies: dict[str, str] = {}
        for path in paths:
            resp = client.get(path)
            bodies[path] = resp.text
            check(results, f"page_{path}_200", resp.status_code == 200 and "Traceback" not in resp.text, str(resp.status_code))

        sources = bodies["/collection/sources"]
        jobs = bodies["/collection/jobs"]
        items_body = bodies["/collection/items"]
        operations = bodies["/intelligence/operations"]
        review_body = bodies["/review"]
        front = client.get(f"/intelligence/{published_id}")

        check(results, "source_status_chinese", u(r"\u5df2\u542f\u7528") in sources or u(r"\u5df2\u6682\u505c") in sources)
        check(results, "job_failure_reason_visible", "robots_denied" in jobs and "source_disabled" in jobs)
        check(results, "robots_denied_explained", u(r"\u76ee\u6807\u7f51\u7ad9\u9650\u5236\u81ea\u52a8\u6293\u53d6") in jobs or u(r"\u76ee\u6807\u7f51\u7ad9\u9650\u5236\u81ea\u52a8\u6293\u53d6") in sources)
        check(results, "source_disabled_explained", u(r"\u8be5\u6570\u636e\u6e90\u5df2\u6682\u505c") in jobs or u(r"\u8be5\u6570\u636e\u6e90\u5df2\u6682\u505c") in sources)
        check(results, "created_job_number_visible", str(job["run_no"]) in jobs or "JOB-V06I" in jobs)
        check(results, "job_links_source", f"/collection/sources/{source['id']}" in jobs)
        check(results, "job_links_items_or_reason", "/collection/items/" in jobs or u(r"\u7b49\u5f85\u91c7\u96c6\u7ed3\u679c") in jobs)
        check(results, "raw_item_processing_path", "/processing/jobs" in items_body and (u(r"\u8fdb\u5165\u5904\u7406") in items_body or u(r"\u5df2\u8fdb\u5165\u5904\u7406\u4efb\u52a1") in items_body))
        check(results, "review_to_front_visible", front.status_code == 200 and "v06i" in front.text)
        check(results, "operations_flow_visible", all(label in operations for label in [u(r"\u6570\u636e\u6e90"), u(r"\u91c7\u96c6\u4efb\u52a1"), u(r"\u539f\u59cb\u60c5\u62a5"), u(r"\u6570\u636e\u5904\u7406"), u(r"\u5019\u9009"), u(r"\u60c5\u62a5\u5ba1\u6838")]))
        check(results, "review_page_available", u(r"\u5ba1\u6838") in review_body or review_body)
        from app.services.navigation_service import get_client_navigation
        normal = {"permissions": {"view_internal"}}
        normal_nav = get_client_navigation(normal, path="/intelligence")
        admin_visible = bool(normal_nav.get("admin"))
        ops_visible = any(item.get("route") == "/intelligence/operations" for item in normal_nav.get("secondary", []))
        check(results, "normal_user_no_internal_ops", not admin_visible and not ops_visible, str(normal_nav))
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
    print(f"verify_intelligence_crawl_visibility_v1 passed={passed} failed={len(results)-passed}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
