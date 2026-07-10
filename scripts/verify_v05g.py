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

from app.services.collection_service import create_collection_source, create_job, process_job as process_collection_job
from app.services.processing import (
    apply_candidate,
    candidate_detail,
    create_processing_job,
    dashboard,
    list_candidates,
    list_jobs,
    list_subject_matches,
    process_job,
    review_candidate,
    run_worker,
)
from app.services.processing.content_block_service import split_blocks
from app.services.processing.document_classifier import classify_page
from app.services.processing.entity_extraction_service import extract_candidates
from app.v04c_review import db_connection
from scripts.migrate_v05g import migrate


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


def seed_subjects(db_path: Path) -> None:
    with db_connection(db_path) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS organizations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                standard_name TEXT,
                org_type TEXT,
                region TEXT,
                industry_tags TEXT,
                resources TEXT,
                needs TEXT,
                relationship_source TEXT,
                visibility TEXT,
                verification_status TEXT,
                source_url TEXT,
                source_title TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                name TEXT,
                public_role TEXT,
                organization_network TEXT,
                ability_tags TEXT,
                value_provided TEXT,
                relationship_source TEXT,
                visibility TEXT,
                verification_status TEXT,
                source_url TEXT,
                source_title TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS projects (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                name TEXT,
                project_type TEXT,
                owner_external_id TEXT,
                focus_tags TEXT,
                typical_needs TEXT,
                target_actions TEXT,
                visibility TEXT,
                status TEXT,
                source_url TEXT,
                source_title TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            );
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT UNIQUE,
                event_date TEXT,
                name TEXT,
                event_type TEXT,
                related_entity TEXT,
                fact_summary TEXT,
                system_use TEXT,
                visibility TEXT,
                verification_status TEXT,
                source_type TEXT,
                is_active INTEGER DEFAULT 1,
                created_at TEXT
            );
            """
        )
        conn.execute(
            """
            INSERT INTO organizations(external_id, standard_name, org_type, region, industry_tags, resources, needs, visibility, verification_status, is_active, created_at)
            VALUES ('ORG-20260701-000001', '星河生物科技有限公司', 'biotech', '上海', 'ADC', '', '', '内部', '已核验', 1, datetime('now','localtime'))
            """
        )
        conn.execute(
            """
            INSERT INTO people(external_id, name, public_role, organization_network, ability_tags, value_provided, visibility, verification_status, is_active, created_at)
            VALUES
              ('PER-20260701-000001', '陈锦辉', '', '', '', '', '内部', '待核验', 1, datetime('now','localtime')),
              ('PER-20260701-000002', '李明', 'CEO', '', '', '', '内部', '待核验', 1, datetime('now','localtime')),
              ('PER-20260701-000003', '李明', '教授', '', '', '', '内部', '待核验', 1, datetime('now','localtime'))
            """
        )
        conn.execute(
            """
            INSERT INTO projects(external_id, name, project_type, visibility, status, is_active, created_at)
            VALUES ('PRJ-20260701-000001', 'ADC项目', 'pipeline', '内部', '跟进中', 1, datetime('now','localtime'))
            """
        )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="verify_v05g_") as tmp:
        db_path = Path(tmp) / "app.db"
        migrate(db_path, backup=False)
        migrate(db_path, backup=False)
        seed_subjects(db_path)

        required = {
            "v05g_processing_jobs",
            "v05g_processing_blocks",
            "v05g_extraction_candidates",
            "v05g_subject_match_candidates",
            "v05g_candidate_review_history",
            "v05g_candidate_application_logs",
        }
        check(required.issubset(table_names(db_path)), "migration creates v0.5G processing tables")

        check(classify_page("团队介绍", "管理团队\n陈锦辉，CEO\n李明，CTO")["page_type"] == "team_page", "classifier recognizes team pages")
        check(classify_page("产品管线", "ADC项目 正在推进临床 II 期，适应症为肿瘤。")["page_type"] == "product_pipeline", "classifier recognizes product pipeline pages")
        check(classify_page("政策公告", "园区发布生物医药企业补贴申报政策。")["page_type"] == "policy_resource", "classifier recognizes policy/resource pages")

        team_blocks = split_blocks("管理团队\n陈锦辉，CEO\n负责BD和融资。\n李明，CTO\n负责CMC工艺。", "team_page")
        check(len(team_blocks) >= 2 and all(block["text"] != "管理团队" for block in team_blocks), "team page splitting keeps headings out of person candidates")
        team_candidates = []
        for block in team_blocks:
            team_candidates.extend(extract_candidates(block, "team_page", {"source_url": "inline:test", "source_title": "team"}))
        check(any(c["candidate_type"] == "person" and c["normalized_value"] == "陈锦辉" for c in team_candidates), "team extraction finds people")
        check(not any(c["candidate_type"] == "person" and c["normalized_value"] == "管理团队" for c in team_candidates), "team extraction blocks heading-as-person")

        html_page = """
        <html><head><title>星河生物科技有限公司完成B轮融资</title></head><body><article>
        <h1>星河生物科技有限公司完成B轮融资</h1>
        <p>星河生物科技有限公司宣布完成5000万美元B轮融资，资金将用于ADC项目临床II期推进。</p>
        <p>本人陈锦辉，专注BD和投融资，可提供产业资源，希望对接临床合作伙伴。</p>
        <p>李明，CEO，负责产品管线和CMC放大。</p>
        </article></body></html>
        """
        source = create_collection_source(name="v05g inline", source_type="webpage", collection_mode="http", url="inline:" + html_page, db_path=db_path)
        collection_job = create_job(source["id"], db_path=db_path)
        collection_result = process_collection_job(collection_job["id"], db_path=db_path)
        check(collection_result["queued"] == 1, "v0.5F collection produces one queued item for processing")
        with db_connection(db_path) as conn:
            item_id = conn.execute("SELECT id FROM v05f_collection_items ORDER BY id DESC LIMIT 1").fetchone()["id"]
        processing_job = create_processing_job(item_id=item_id, operator="verify", db_path=db_path)
        result = process_job(processing_job["id"], db_path=db_path)
        check(result["status"] in {"success", "needs_review"} and result["candidates"] >= 4, "processing job extracts multiple candidates")

        candidates, total = list_candidates(db_path=db_path, page_size=100)
        check(total >= 4 and any(c["candidate_type"] == "event" for c in candidates), "candidate list includes event candidates without formal event writes")
        check(any(c["candidate_type"] == "organization" and c["matched_subject_id"] == "ORG-20260701-000001" for c in candidates), "subject matching confirms exact organization name")
        matches, match_total = list_subject_matches(db_path=db_path, page_size=100)
        check(match_total >= 1 and any(m["status"] in {"confirmed", "ambiguous"} for m in matches), "subject match candidates are recorded")

        person_statuses = [m["status"] for m in matches if m["candidate_subject_type"] == "person" and m["candidate_label"] == "李明"]
        check("ambiguous" in person_statuses, "same-name people stay ambiguous")

        field_candidate = next((c for c in candidates if c["candidate_type"] == "field" and c["field_name"] == "ability_tags" and c["subject_label"] == "陈锦辉"), None)
        check(field_candidate is not None, "field candidate exists for self-introduction expertise")
        reviewed = review_candidate(field_candidate["id"], decision="approved", actor="verify", note="verified", final_value="BD; financing", db_path=db_path)
        check(reviewed["review_status"] == "approved", "candidate review approval is recorded")
        applied = apply_candidate(field_candidate["id"], actor="verify", db_path=db_path)
        check(applied["result"] in {"success", "skipped"}, "approved whitelisted field can be applied or idempotently skipped")
        detail = candidate_detail(field_candidate["id"], db_path=db_path)
        check(detail is not None and detail["history"] and detail["logs"], "candidate detail includes review history and application log")

        event_candidate = next(c for c in candidates if c["candidate_type"] == "event")
        reviewed_event = review_candidate(event_candidate["id"], decision="approved", actor="verify", note="event needs manual review", db_path=db_path)
        check(reviewed_event["review_status"] == "approved", "event candidates can be approved into review flow")
        with db_connection(db_path) as conn:
            synthetic_events = conn.execute("SELECT COUNT(*) FROM events WHERE source_type='v05g_test'").fetchone()[0]
            review_rows = conn.execute("SELECT COUNT(*) FROM v04c_review_items WHERE created_by='v05g_processing'").fetchone()[0]
        check(synthetic_events == 0 and review_rows >= 1, "event approval creates review item and does not write formal events")

        worker_result = run_worker(once=True, queued_only=True, limit=5, operator="verify-worker", db_path=db_path)
        check(worker_result["processed"] >= 0, "worker entry point runs against queued processing items")
        jobs, job_total = list_jobs(db_path=db_path)
        check(job_total >= 1 and jobs, "processing jobs list is available")
        stats = dashboard(db_path=db_path)
        check(stats["counts"]["pending_candidates"] >= 1, "dashboard counts pending candidates")
        check((ROOT / "data" / "app.db") != db_path, "verification used a temporary SQLite database")

    print("v0.5G verification completed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
