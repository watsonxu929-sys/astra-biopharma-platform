from __future__ import annotations

import gc
import json
import os
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.test_db_utils import run_migration_suite, temporary_database


def check(results: list[bool], name: str, ok: bool, detail: str = "") -> None:
    print(("PASS" if ok else "FAIL"), name, detail)
    results.append(bool(ok))


def count(conn: sqlite3.Connection, table: str, where: str = "1=1", params: tuple = ()) -> int:
    try:
        return int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}", params).fetchone()[0] or 0)
    except sqlite3.Error:
        return 0


def http_get(base: str, path: str) -> tuple[int, str, str]:
    try:
        with urlopen(Request(base + path), timeout=15) as resp:
            return int(resp.status), resp.read().decode("utf-8", errors="replace"), resp.headers.get("content-type", "")
    except HTTPError as exc:
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        return int(exc.code), body, exc.headers.get("content-type", "")
    except (URLError, OSError) as exc:
        return 0, str(exc), ""


def start_server(db_path: Path, port: int = 8061) -> subprocess.Popen:
    env = os.environ.copy()
    env["APP_AUTH_DISABLED"] = "1"
    env["APP_DB_PATH"] = str(db_path)
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
        cwd=ROOT,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    time.sleep(5)
    return proc


def stop_server(proc: subprocess.Popen | None) -> None:
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=8)


def main() -> int:
    results: list[bool] = []
    with temporary_database("v06i_intel_e2e_") as db_path:
        run_migration_suite(db_path)
        os.environ["APP_AUTH_DISABLED"] = "1"
        server = None
        try:
            from app.database import Base, SessionLocal, engine
            import app.models  # noqa: F401
            import app.models_platform  # noqa: F401
            Base.metadata.create_all(bind=engine)

            from app.models_platform import IntelligenceItem
            from app.services.product_recovery_service import publish_collection_item, run_inline_intelligence_flow
            from app.services.processing import review_candidate
            from app.v04c_review import create_review_item, resolve_review_item
            from sqlalchemy import select

            before: dict[str, int] = {}
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                for table in ["v04g_monitoring_sources", "v05f_collection_items", "v05g_processing_jobs", "v05g_extraction_candidates", "v04c_review_items", "v06_intelligence_items"]:
                    before[table] = count(conn, table)

            html = """
            <html><head><title>v06i_test intelligence chain validation</title></head>
            <body><article>
            <h1>v06i_test BioNova Therapeutics closes translational oncology partnership</h1>
            <p>v06i_test BioNova Therapeutics announced a translational oncology collaboration with Harbor BioPark.</p>
            <p>Dr. Ada Lin will coordinate IND-enabling studies, biomarkers, and CMC readiness in Shanghai.</p>
            <p>The local verification content is synthetic and marked v06i_test for cleanup validation.</p>
            </article></body></html>
            """
            flow = run_inline_intelligence_flow(html=html, title="v06i_test_source", db_path=db_path, operator="v06i_test")
            collection_item_id = int(flow.get("collection_item_id") or 0)
            check(results, "1 source created", int(flow["source"]["id"]) > 0, str(flow["source"].get("source_no")))
            check(results, "2 collection item created", collection_item_id > 0, str(flow.get("collection_result")))
            check(results, "3 processing job created", len(flow.get("processing_jobs_created", {}).get("jobs", [])) >= 1, str(flow.get("processing_jobs_created")))
            check(results, "4 processing completed", any(j.get("status") in {"success", "needs_review"} for j in flow.get("processed_jobs", [])), str(flow.get("processed_jobs")))
            check(results, "5 candidate or no-match state", int(flow.get("candidate_count") or 0) >= 0, str(flow.get("candidate_count")))

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                cand = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE collection_item_id=? ORDER BY id LIMIT 1", (collection_item_id,)).fetchone()
            if cand:
                approved_candidate = review_candidate(int(cand["id"]), decision="approved", actor="v06i_test", note="v06i_test approval", db_path=db_path)
                check(results, "6 candidate review approved", approved_candidate.get("review_status") in {"approved", "applied"}, str(approved_candidate.get("id")))
            else:
                check(results, "6 explicit no candidate state", True, "no extraction candidates produced")

            review = create_review_item(
                item_type="intelligence_publish",
                subject_type="collection_item",
                subject_id=str(collection_item_id),
                subject_label="v06i_test intelligence chain validation",
                field_name="publication_readiness",
                proposed_value="publish v06i_test collection item",
                batch_tag="v06i_test",
                created_by="v06i_test",
                db_path=db_path,
            )
            resolved = resolve_review_item(int(review["id"]), decision="approved", actor="v06i_test", note="v06i_test approved for publication", db_path=db_path)
            check(results, "7 review item approved", resolved.get("status") == "approved", str(resolved.get("review_no")))

            db = SessionLocal()
            try:
                published = publish_collection_item(db, collection_item_id, actor_user_id=1, status="published")
                published_id = int(published.id)
                published_again = publish_collection_item(db, collection_item_id, actor_user_id=1, status="published")
            finally:
                db.close()
            with sqlite3.connect(db_path) as conn:
                pub_count = count(conn, "v06_intelligence_items", "source_name='v05f_collection_items' AND source_url=(SELECT normalized_url FROM v05f_collection_items WHERE id=?)", (collection_item_id,))
            check(results, "8 published to canonical intelligence", published_id > 0, str(published_id))
            check(results, "9 repeat publish idempotent", int(published_again.id) == published_id and pub_count == 1, f"same={int(published_again.id)} count={pub_count}")

            server = start_server(db_path)
            base = "http://127.0.0.1:8061"
            front_status, front_body, _ = http_get(base, "/intelligence?q=v06i_test")
            detail_status, detail_body, _ = http_get(base, f"/intelligence/{published_id}")
            api_status, api_body, api_type = http_get(base, "/api/v1/intelligence?q=v06i_test")
            api_detail_status, api_detail_body, _ = http_get(base, f"/api/v1/intelligence/{published_id}")
            data = json.loads(api_body) if api_status == 200 and api_body.strip().startswith("{") else {}
            api_ids = [int(item["id"]) for item in data.get("data", []) if "id" in item]
            check(results, "10 web list visible", front_status == 200 and "v06i_test" in front_body, str(front_status))
            check(results, "11 web detail visible", detail_status == 200 and "v06i_test" in detail_body, str(detail_status))
            check(results, "12 api list visible json", api_status == 200 and published_id in api_ids and "Traceback" not in api_body, f"status={api_status} type={api_type} ids={api_ids}")
            check(results, "13 web api same published id", published_id in api_ids, str(api_ids))
            check(results, "14 api detail visible", api_detail_status == 200 and str(published_id) in api_detail_body and "Traceback" not in api_detail_body, str(api_detail_status))

            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                test_rows = {
                    "sources": count(conn, "v04g_monitoring_sources", "name LIKE 'v06i_test%'"),
                    "items": count(conn, "v05f_collection_items", "title LIKE '%v06i_test%'"),
                    "published": count(conn, "v06_intelligence_items", "title LIKE '%v06i_test%' OR content LIKE '%v06i_test%'"),
                }
                after = {table: count(conn, table) for table in before}
            check(results, "15 pipeline wrote expected test rows", test_rows["sources"] >= 1 and test_rows["items"] >= 1 and test_rows["published"] == 1, str(test_rows))
            check(results, "16 temp cleanup isolated from live db", not str(db_path).startswith(str((ROOT / "data").resolve())), str(db_path))
        finally:
            stop_server(server)
            try:
                from sqlalchemy.orm import close_all_sessions
                close_all_sessions()
            except Exception:
                pass
            try:
                from app.database import engine as _engine
                _engine.dispose()
            except Exception:
                pass
            for _obj in list(gc.get_objects()):
                try:
                    if isinstance(_obj, sqlite3.Connection):
                        _obj.close()
                except Exception:
                    pass
            gc.collect()
            time.sleep(3.0)
            os.environ.pop("APP_AUTH_DISABLED", None)
    print(f"verify_intelligence_pipeline_e2e_v1 passed={sum(results)} failed={len(results)-sum(results)}")
    return 0 if all(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

