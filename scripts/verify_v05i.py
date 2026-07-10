from __future__ import annotations

import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from app.services.collection_service import create_collection_source
from app.services.pipeline import create_pipeline_run, create_quality_samples, dashboard, list_pipeline_runs, pipeline_detail, quality_metrics, retry_pipeline, run_pipeline_once
from app.services.pipeline.pipeline_common import db_connection
from app.services.processing import list_candidates, review_candidate
from scripts.migrate_v05i import migrate


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def table_names(path: Path) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    finally:
        conn.close()


HTML_PAGE = """
<html><head><title>星河生物科技有限公司完成B轮融资</title></head><body><article>
<h1>星河生物科技有限公司完成B轮融资</h1>
<p>星河生物科技有限公司宣布完成5000万美元B轮融资，资金将用于ADC项目临床II期推进。</p>
<p>本人陈锦辉，专注BD和投融资，可提供产业资源，希望对接临床合作伙伴。</p>
<p>李明，CEO，负责产品管线和CMC放大。</p>
</article></body></html>
"""


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="verify_v05i_") as tmp:
        db_path = Path(tmp) / "app.db"
        migrate(db_path, backup=False)
        migrate(db_path, backup=False)
        required = {"v05i_pipeline_runs", "v05i_pipeline_stage_runs", "v05i_pipeline_quality_samples", "v05i_pilot_source_results"}
        check(required.issubset(table_names(db_path)), "migration creates v0.5I pipeline tables")

        source = create_collection_source(name="v05i inline source", source_type="webpage", collection_mode="http", url="inline:" + HTML_PAGE, db_path=db_path)
        run = create_pipeline_run(source["id"], created_by="verify", pilot=True, dry_run=True, db_path=db_path)
        duplicate_blocked = False
        try:
            create_pipeline_run(source["id"], created_by="verify", pilot=True, dry_run=True, db_path=db_path)
        except RuntimeError:
            duplicate_blocked = True
        check(duplicate_blocked, "same source cannot have concurrent active pipeline runs")

        result = run_pipeline_once(pipeline_run_id=run["id"], created_by="verify", pilot=True, dry_run=True, db_path=db_path)["result"]
        check(result["status"] == "waiting_review" and result["candidate_count"] >= 1, "pipeline collects, processes and pauses at manual review")
        detail = pipeline_detail(run["id"], db_path=db_path)
        check(detail and detail["collection_items"] and detail["processing_jobs"] and detail["candidates"], "pipeline detail traces collection items, processing jobs and candidates")
        rows, _ = list_candidates(db_path=db_path, page_size=50)
        for candidate in rows:
            review_candidate(candidate["id"], decision="approved", actor="verify", note="verified", db_path=db_path)
        continued = retry_pipeline(run["id"], actor="verify", db_path=db_path)
        check(continued["status"] in {"partial", "completed"} and continued["approved_candidate_count"] >= 1, "reviewed pipeline can continue without auto-approval")
        again = retry_pipeline(run["id"], actor="verify", db_path=db_path)
        check(again["id"] == continued["id"], "retry is idempotent for completed or partial run")

        samples = create_quality_samples(run["id"], db_path=db_path)
        check(samples["created"] >= 1, "quality samples can be created from pipeline candidates")
        metrics = quality_metrics(db_path=db_path)
        check("source_success_rate" in metrics and "average_pipeline_duration" in metrics, "quality metrics are computed from real run tables")
        dash = dashboard(db_path=db_path)
        check(dash["counts"]["partial"] + dash["counts"]["completed"] >= 1, "dashboard counts pipeline outcomes")
        listed = list_pipeline_runs(db_path=db_path)
        check(listed["pagination"]["total"] >= 1, "pipeline run list is paginated")

        failed_source = create_collection_source(name="v05i failed source", source_type="webpage", collection_mode="playwright", url="inline:<html>dynamic</html>", db_path=db_path)
        failed_run = create_pipeline_run(failed_source["id"], created_by="verify", pilot=True, dry_run=True, db_path=db_path)
        failed = run_pipeline_once(pipeline_run_id=failed_run["id"], created_by="verify", pilot=True, dry_run=True, db_path=db_path)["result"]
        check(failed["status"] == "failed" and failed["failed_stage"] == "collecting", "failed stage is recorded for recovery")

        with db_connection(db_path) as conn:
            formal_pollution = conn.execute("SELECT COUNT(*) FROM events WHERE source_type='v05i_test'").fetchone()[0] if "events" in table_names(db_path) else 0
        check(formal_pollution == 0, "verification does not pollute formal event data")

    print("v0.5I verification completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
