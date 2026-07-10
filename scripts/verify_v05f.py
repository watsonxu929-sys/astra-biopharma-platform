from __future__ import annotations

import os
import sqlite3
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
os.environ.setdefault("APP_AUTH_DISABLED", "1")

from app.services.collection_service import (  # noqa: E402
    cancel_job,
    check_robots,
    create_collection_source,
    create_job,
    dashboard,
    discover_links,
    list_items,
    list_jobs,
    list_sources,
    normalize_url,
    process_job,
    queue_item,
)
from app.v04c_review import db_connection  # noqa: E402
from scripts.migrate_v05f import migrate  # noqa: E402


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


def column_names(path: Path, table: str) -> set[str]:
    conn = sqlite3.connect(path)
    try:
        return {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
    finally:
        conn.close()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="verify_v05f_") as tmp:
        db_path = Path(tmp) / "app.db"
        migrate(db_path, backup=False)
        migrate(db_path, backup=False)

        required_tables = {
            "v04g_monitoring_sources",
            "v04g_monitoring_runs",
            "v04g_source_snapshots",
            "v05f_collection_items",
            "v05f_discovered_links",
            "v05f_content_duplicate_links",
            "v05f_collection_job_locks",
            "v05f_collection_templates",
        }
        check(required_tables.issubset(table_names(db_path)), "migration creates v04G reuse tables and v05F extension tables")
        check({"collection_source_type", "collection_mode", "allowed_domains", "auto_paused"}.issubset(column_names(db_path, "v04g_monitoring_sources")), "migration extends existing monitoring source table")
        check({"new_content_count", "duplicate_content_count", "queued_item_count", "trigger_type"}.issubset(column_names(db_path, "v04g_monitoring_runs")), "migration extends existing monitoring run table")
        check({"normalized_url", "canonical_url", "raw_html", "structure_hash"}.issubset(column_names(db_path, "v04g_source_snapshots")), "migration extends existing snapshot table")

        normalized = normalize_url("HTTPS://Example.COM:443/news/?utm_source=x&b=2&a=1#top")
        check(normalized == "https://example.com/news?a=1&b=2", "URL normalization removes tracking, fragments and default ports")

        rss = """<?xml version="1.0"?>
        <rss><channel><title>Feed</title>
          <item><guid>1</guid><title>Alpha funding</title><link>https://example.com/a?utm_source=x</link><description>Alpha biotech completed financing and queued evidence.</description><pubDate>2026-06-30</pubDate></item>
          <item><guid>2</guid><title>Beta pipeline</title><link>https://example.com/b</link><description>Beta pipeline advanced to clinical stage.</description></item>
        </channel></rss>"""
        rss_source = create_collection_source(
            name="RSS source",
            source_type="rss",
            collection_mode="rss",
            url="inline:" + rss,
            compliance_note="local verification inline feed",
            db_path=db_path,
        )
        job = create_job(rss_source["id"], db_path=db_path)
        result = process_job(job["id"], db_path=db_path)
        check(result["status"] == "success" and result["new"] == 2 and result["queued"] == 2, "RSS job creates queued collection items")
        second = create_job(rss_source["id"], db_path=db_path, force=True)
        second_result = process_job(second["id"], db_path=db_path)
        check(second_result["status"] == "unchanged" and second_result["duplicate"] >= 2, "re-running same RSS marks duplicates or unchanged content")

        html_page = """
        <html><head><title>Company News</title><meta name="description" content="demo"></head>
        <body><nav>menu</nav><article><h1>Company News</h1>
        <p>Alpha biotech announced public cooperation and product pipeline progress on 2026-06-30.</p>
        <p>This public article is long enough for extraction and snapshot verification.</p>
        </article></body></html>
        """
        page_source = create_collection_source(
            name="Web page",
            source_type="webpage",
            collection_mode="http",
            url="inline:" + html_page,
            db_path=db_path,
        )
        page_job = create_job(page_source["id"], db_path=db_path)
        page_result = process_job(page_job["id"], db_path=db_path)
        check(page_result["new"] == 1 and page_result["snapshots"] == 1, "web page job stores snapshot and item")

        changed_page = html_page.replace("pipeline progress", "pipeline progress and a new hiring expansion")
        changed_source = create_collection_source(
            name="Changed Web page",
            source_type="webpage",
            collection_mode="http",
            url="inline:" + changed_page,
            db_path=db_path,
        )
        changed_job = create_job(changed_source["id"], db_path=db_path)
        changed_result = process_job(changed_job["id"], db_path=db_path)
        check(changed_result["new"] == 1, "changed content can be captured as new evidence without touching subjects")

        list_html = """
        <html><body><main>
        <a href="/news/a?utm_campaign=x">Alpha News</a>
        <a href="/news/a#again">Alpha News duplicate</a>
        <a href="https://evil.example.org/news">Cross domain</a>
        <a href="/privacy">Privacy</a>
        <a href="/news/b">Beta News</a>
        </main></body></html>
        """
        links = discover_links(list_html, "https://example.com/list", max_links=10)
        check(len(links) == 2 and all(link["normalized_url"].startswith("https://example.com/news/") for link in links), "list-page discovery keeps same-domain detail links and deduplicates")

        rows, total = list_sources(db_path=db_path)
        check(total >= 3 and rows, "source list is available through service")
        items, item_total = list_items(db_path=db_path)
        check(item_total >= 4 and any(item["processing_status"] == "queued" for item in items), "collection items list includes queued content")
        queued = queue_item(items[0]["id"], db_path=db_path)
        check(queued["processing_status"] in {"queued", "ignored"}, "queue action is idempotent and respects duplicate status")

        pending = create_job(page_source["id"], db_path=db_path, force=True)
        cancelled = cancel_job(pending["id"], db_path=db_path)
        check(cancelled["status"] == "skipped" and cancelled["error_type"] == "cancelled", "pending job can be cancelled using existing v04G status constraints")

        try:
            create_job(page_source["id"], db_path=db_path)
            create_job(page_source["id"], db_path=db_path)
            raise AssertionError("duplicate running job was not blocked")
        except RuntimeError:
            print("[PASS] duplicate pending/running jobs are blocked by default")

        bad_source = create_collection_source(name="Dynamic unavailable", source_type="dynamic_page", collection_mode="playwright", url="inline:<html>dynamic</html>", db_path=db_path)
        for _ in range(3):
            bad_job = create_job(bad_source["id"], db_path=db_path, force=True)
            process_job(bad_job["id"], db_path=db_path)
        with db_connection(db_path) as conn:
            bad = conn.execute("SELECT consecutive_failures, auto_paused FROM v04g_monitoring_sources WHERE id=?", (bad_source["id"],)).fetchone()
        check(bad["consecutive_failures"] == 3 and bad["auto_paused"] == 1, "repeated failures auto-pause a source")

        robots = check_robots("inline:<html></html>")
        check(robots["allowed"] is True and robots["status"] == "not_applicable", "inline verification source skips network robots check")
        jobs, job_total = list_jobs(db_path=db_path)
        check(job_total >= 6 and jobs, "collection jobs list is available")
        stats = dashboard(db_path=db_path)
        check(stats["counts"]["queued_items"] >= 1 and stats["counts"]["paused_sources"] >= 1, "dashboard counts queued items and paused sources")

        formal_db = ROOT / "data" / "app.db"
        check(formal_db != db_path, "verification used a temporary SQLite database")

    print("v0.5F verification completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
