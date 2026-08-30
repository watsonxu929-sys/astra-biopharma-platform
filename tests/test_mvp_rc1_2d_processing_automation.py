from __future__ import annotations

import sqlite3
from datetime import datetime

import pytest

from app.security import ROLE_PERMISSIONS, required_permission
from app.services.collection_service import delete_collection_item_safely
from app.services.intelligence_flow_service import (
    advance_processing_after_collection,
    create_processing_jobs_for_collection_run,
    run_collection_worker_with_cascade,
    run_processing_worker_once,
)
from app.services.processing import create_processing_job, process_job


NOW = datetime.now().replace(microsecond=0).isoformat()
GOOD_TEXT = "\n\n".join([
    "上海生物医药企业发布研发进展，公开资料显示项目仍处于产业合作评估阶段。",
    "公司计划继续推进临床研究、技术验证和合作伙伴沟通，所有候选事实需要人工审核。",
    "该公开信息包含企业、项目和事件上下文，但不会自动形成关系、资源或商业机会。",
])


def _seed_collection(
    database,
    suffix: str,
    *,
    run_status: str = "success",
    dedup_status: str = "new",
    processing_status: str = "queued",
    text: str = GOOD_TEXT,
    enabled: int = 1,
    pilot: int = 0,
) -> tuple[int, int, int, int]:
    with sqlite3.connect(database) as conn:
        source_id = conn.execute(
            """INSERT INTO v04g_monitoring_sources(
               source_no,name,source_type,url,check_frequency,is_enabled,fetch_mode,
               auto_paused,created_at,updated_at)
               VALUES (?,?, 'website', ?, 'manual', ?, 'web', 0, ?, ?)""",
            (f"SRC-RC12D-{suffix}", f"RC1.2D {suffix}", f"https://{suffix}.example.invalid", enabled, NOW, NOW),
        ).lastrowid
        run_id = conn.execute(
            """INSERT INTO v04g_monitoring_runs(
               run_no,monitoring_source_id,status,started_at,finished_at,http_status,
               content_length,changed,created_at,job_type,trigger_type,queued_item_count)
               VALUES (?,?,?,?,?,200,?,1,?,'collection','rc12d-test',1)""",
            (f"RUN-RC12D-{suffix}", source_id, run_status, NOW, NOW, len(text), NOW),
        ).lastrowid
        snapshot_id = conn.execute(
            """INSERT INTO v04g_source_snapshots(
               snapshot_no,monitoring_source_id,monitoring_run_id,page_title,url,captured_at,
               raw_content,cleaned_text,content_hash,metadata_json,created_at,is_pilot)
               VALUES (?,?,?,?,?,?,?,?,?,'{}',?,?)""",
            (f"SNP-RC12D-{suffix}", source_id, run_id, f"RC1.2D {suffix}",
             f"https://{suffix}.example.invalid/item", NOW, text, text,
             f"hash-{suffix}", NOW, pilot),
        ).lastrowid
        item_id = conn.execute(
            """INSERT INTO v05f_collection_items(
               item_no,monitoring_source_id,monitoring_run_id,snapshot_id,title,normalized_url,
               captured_at,dedup_status,change_status,processing_status,content_hash,created_at,updated_at)
               VALUES (?,?,?,?,?,?, ?,?,'new',?,?,?,?)""",
            (f"ITEM-RC12D-{suffix}", source_id, run_id, snapshot_id, f"RC1.2D {suffix}",
             f"https://{suffix}.example.invalid/item", NOW, dedup_status, processing_status,
             f"hash-{suffix}", NOW, NOW),
        ).lastrowid
    return int(source_id), int(run_id), int(snapshot_id), int(item_id)


def test_collection_success_auto_processes_without_manual_job(temp_database):
    _, run_id, _, item_id = _seed_collection(temp_database, "auto")
    result = advance_processing_after_collection([run_id], db_path=temp_database, operator="auto-test")
    assert result["created"] == 1
    assert result["processing"]["processed"] == 1
    assert result["processing"]["successful"] == 1
    with sqlite3.connect(temp_database) as conn:
        job = conn.execute("SELECT trigger_type,status FROM v05g_processing_jobs WHERE collection_item_id=?", (item_id,)).fetchone()
        item_status = conn.execute("SELECT processing_status FROM v05f_collection_items WHERE id=?", (item_id,)).fetchone()[0]
    assert job[0] == "collection_worker"
    assert job[1] in {"success", "needs_review"}
    assert item_status in {"processed", "needs_review"}


def test_duplicate_runner_and_manual_misclick_are_idempotent(temp_database):
    _, run_id, _, item_id = _seed_collection(temp_database, "idempotent")
    first = advance_processing_after_collection([run_id], db_path=temp_database)
    existing = first["jobs"][0]
    second = advance_processing_after_collection([run_id], db_path=temp_database)
    manual = create_processing_job(item_id=item_id, db_path=temp_database)
    with sqlite3.connect(temp_database) as conn:
        count = conn.execute("SELECT COUNT(*) FROM v05g_processing_jobs WHERE collection_item_id=?", (item_id,)).fetchone()[0]
    assert second["created"] == 0
    assert manual["id"] == existing["id"] and manual["idempotent"] is True
    assert count == 1


def test_duplicate_disabled_and_pilot_collection_are_excluded(temp_database):
    _, duplicate_run, _, _ = _seed_collection(
        temp_database, "duplicate", dedup_status="duplicate", processing_status="ignored",
    )
    _, disabled_run, _, _ = _seed_collection(temp_database, "disabled", enabled=0)
    _, pilot_run, _, _ = _seed_collection(temp_database, "pilot", pilot=1)
    for run_id in (duplicate_run, disabled_run, pilot_run):
        assert create_processing_jobs_for_collection_run(run_id, db_path=temp_database)["created"] == 0


def test_processing_failure_isolated_and_admin_retry_succeeds(temp_database):
    _, _, bad_snapshot, bad_item = _seed_collection(temp_database, "bad", text="")
    _, _, good_snapshot, good_item = _seed_collection(temp_database, "good")
    bad_job = create_processing_job(item_id=bad_item, db_path=temp_database)
    good_job = create_processing_job(item_id=good_item, db_path=temp_database)
    result = run_processing_worker_once(limit=10, db_path=temp_database)
    states = {row["job_id"]: row["status"] for row in result["results"]}
    assert states[bad_job["id"]] == "failed"
    assert states[good_job["id"]] in {"success", "needs_review"}
    with sqlite3.connect(temp_database) as conn:
        conn.execute("UPDATE v05g_processing_jobs SET snapshot_id=? WHERE id=?", (good_snapshot, bad_job["id"]))
    retried = process_job(bad_job["id"], db_path=temp_database)
    assert retried["status"] in {"success", "needs_review"}
    with sqlite3.connect(temp_database) as conn:
        error = conn.execute("SELECT error_type,error_message FROM v05g_processing_jobs WHERE id=?", (bad_job["id"],)).fetchone()
    assert error == (None, None)


def test_pending_processing_survives_restart_cycle(temp_database):
    _, _, _, item_id = _seed_collection(temp_database, "restart")
    job = create_processing_job(item_id=item_id, db_path=temp_database)
    result = run_collection_worker_with_cascade(once=False, limit=20, db_path=temp_database)
    assert result["processed"] == 0
    assert result["processing_jobs_processed"] >= 1
    with sqlite3.connect(temp_database) as conn:
        status = conn.execute("SELECT status FROM v05g_processing_jobs WHERE id=?", (job["id"],)).fetchone()[0]
    assert status in {"success", "needs_review"}


def test_deleted_collection_and_inactive_intelligence_are_not_revived(temp_database):
    _, deleted_run, _, deleted_item = _seed_collection(temp_database, "deleted")
    assert delete_collection_item_safely(deleted_item, actor="rc12d-test", db_path=temp_database)["deleted"] is True
    with pytest.raises(ValueError, match="collection_item_not_found"):
        create_processing_job(item_id=deleted_item, db_path=temp_database)
    assert advance_processing_after_collection([deleted_run], db_path=temp_database)["created"] == 0

    with sqlite3.connect(temp_database) as conn:
        for status in ("withdrawn", "archived"):
            conn.execute(
                """INSERT INTO v06_intelligence_items(
                   title,summary,intel_type,visibility,status,source_name,collected_at,created_at,updated_at)
                   VALUES (?,?, 'brief','public',?,'RC1.2D lifecycle test',?,?,?)""",
                (f"RC1.2D {status}", status, status, NOW, NOW, NOW),
            )
        before = conn.execute("SELECT status,COUNT(*) FROM v06_intelligence_items WHERE source_name='RC1.2D lifecycle test' GROUP BY status ORDER BY status").fetchall()
    advance_processing_after_collection([], db_path=temp_database)
    with sqlite3.connect(temp_database) as conn:
        after = conn.execute("SELECT status,COUNT(*) FROM v06_intelligence_items WHERE source_name='RC1.2D lifecycle test' GROUP BY status ORDER BY status").fetchall()
    assert before == after == [("archived", 1), ("withdrawn", 1)]


def test_processing_admin_writes_require_monitoring_capability_and_viewer_has_none():
    for path in ("/processing/jobs", "/processing/jobs/1/run", "/processing/worker/run-once"):
        assert required_permission(path, "POST") == "manage_monitoring"
    assert "manage_monitoring" in ROLE_PERMISSIONS["operator"]
    assert "manage_monitoring" not in ROLE_PERMISSIONS["viewer"]
