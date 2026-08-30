from __future__ import annotations

import sqlite3
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.security import required_permission
from app.services.collection_service import (
    collection_chain_delete_preview,
    collection_item_delete_preview,
    delete_collection_chain_safely,
    delete_collection_item_safely,
)
from app.services.intelligence_product_service import IntelligenceProductService
from app.services.processing import candidate_delete_preview, delete_candidate_safely
from app.services.unified_intelligence_service import UnifiedIntelligenceService


NOW = datetime.now().replace(microsecond=0).isoformat()


def _intelligence(conn: sqlite3.Connection, title: str, status: str = "published") -> int:
    return int(conn.execute(
        "INSERT INTO v06_intelligence_items(title,summary,intel_type,visibility,status,source_name,collected_at,created_at,updated_at,published_at) VALUES (?,?,'brief','public',?,'RC1.2C isolated test',?,?,?,?)",
        (title, title, status, NOW, NOW, NOW, NOW),
    ).lastrowid)


def _raw(conn: sqlite3.Connection, suffix: str) -> tuple[int, int, int]:
    source = conn.execute("SELECT id FROM v04g_monitoring_sources ORDER BY id LIMIT 1").fetchone()[0]
    snapshot_row = conn.execute("SELECT id,monitoring_run_id FROM v04g_source_snapshots ORDER BY id LIMIT 1").fetchone()
    snapshot, run_id = snapshot_row
    item = conn.execute(
        "INSERT INTO v05f_collection_items(item_no,monitoring_source_id,monitoring_run_id,snapshot_id,title,normalized_url,captured_at,dedup_status,processing_status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,'new','queued',?,?)",
        (f"RC12C-{suffix}", source, run_id, snapshot, f"RC1.2C {suffix}", f"https://example.invalid/{suffix}", NOW, NOW, NOW),
    ).lastrowid
    return int(item), int(source), int(snapshot)


def test_intelligence_safe_delete_and_source_independence(temp_database):
    with sqlite3.connect(temp_database) as conn:
        item_id = _intelligence(conn, "RC1.2C safe delete")
        source_count = conn.execute("SELECT COUNT(*) FROM v04g_monitoring_sources").fetchone()[0]
    service = IntelligenceProductService(temp_database)
    preview = service.impact_preview(item_id)
    assert preview["safe_to_delete"] is True
    result = service.delete(item_id, actor="pytest-admin", permissions={"edit_data"})
    assert result["deleted"] is True
    with sqlite3.connect(temp_database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM v06_intelligence_items WHERE id=?", (item_id,)).fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM v04g_monitoring_sources").fetchone()[0] == source_count
        assert conn.execute("SELECT COUNT(*) FROM p2_intelligence_audit_log WHERE entity_id=? AND action='DELETE'", (item_id,)).fetchone()[0] == 1


def test_protected_delete_preserves_opportunity_followup_and_core_objects(temp_database):
    with sqlite3.connect(temp_database) as conn:
        item_id = _intelligence(conn, "RC1.2C protected")
        opportunity_id = conn.execute("INSERT INTO v06_opportunities(title,opp_type,initiator_id,source_intelligence_id,status,created_at,updated_at) VALUES (?,'cooperation',1,?,'active',?,?)", ("RC1.2C opportunity", item_id, NOW, NOW)).lastrowid
        follow_id = conn.execute("INSERT INTO v06_follow_ups(opportunity_id,content,created_by,followed_at,created_at) VALUES (?,?,1,?,?)", (opportunity_id, "RC1.2C follow", NOW, NOW)).lastrowid
        before = {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in ("organizations", "people", "v06_market_resources", "p3_canonical_relationships")}
    result = IntelligenceProductService(temp_database).delete(item_id, actor="pytest-admin", permissions={"edit_data"})
    assert result["deleted"] is False
    assert result["protected"]["opportunities"] == 1
    assert result["protected"]["follow_ups"] == 1
    with sqlite3.connect(temp_database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM v06_intelligence_items WHERE id=?", (item_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM v06_opportunities WHERE id=?", (opportunity_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM v06_follow_ups WHERE id=?", (follow_id,)).fetchone()[0] == 1
        assert before == {table: conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0] for table in before}


def test_withdraw_archive_restore_and_feed_visibility(temp_database):
    with sqlite3.connect(temp_database) as conn:
        withdrawn_id = _intelligence(conn, "RC1.2C withdraw")
        archived_id = _intelligence(conn, "RC1.2C archive")
    service = IntelligenceProductService(temp_database)
    service.transition(withdrawn_id, "withdraw", actor="operator", permissions={"edit_data"})
    service.transition(archived_id, "archive", actor="operator", permissions={"edit_data"})
    engine = create_engine(f"sqlite:///{temp_database.as_posix()}")
    with Session(engine) as session:
        ids = {row.id for row in UnifiedIntelligenceService(session).list(page_size=100)["items"]}
        assert withdrawn_id not in ids
        assert archived_id not in ids
    service.transition(withdrawn_id, "restore", actor="operator", permissions={"edit_data"})
    service.transition(archived_id, "restore", actor="operator", permissions={"edit_data"})
    with sqlite3.connect(temp_database) as conn:
        assert {row[0] for row in conn.execute("SELECT status FROM v06_intelligence_items WHERE id IN (?,?)", (withdrawn_id, archived_id))} == {"published"}
        assert conn.execute("SELECT COUNT(*) FROM p2_intelligence_audit_log WHERE entity_id IN (?,?) AND action IN ('WITHDRAW','ARCHIVE','RESTORE')", (withdrawn_id, archived_id)).fetchone()[0] == 4


def test_bulk_delete_partial_success(temp_database):
    with sqlite3.connect(temp_database) as conn:
        ids = [_intelligence(conn, f"RC1.2C bulk {index}") for index in range(5)]
        conn.execute("INSERT INTO core_intelligence_subject_links(intelligence_item_id,subject_type,subject_id,created_at) VALUES (?,'organization',1,?)", (ids[-1], NOW))
    result = IntelligenceProductService(temp_database).bulk(ids, "delete", actor="admin", permissions={"edit_data"})
    assert result["success"] == 4
    assert result["failed"] == 1
    with sqlite3.connect(temp_database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM v06_intelligence_items WHERE id=?", (ids[-1],)).fetchone()[0] == 1


def test_historical_report_preserved_and_blocks_delete(temp_database):
    with sqlite3.connect(temp_database) as conn:
        item_id = _intelligence(conn, "RC1.2C report history")
        report_id = conn.execute("INSERT INTO v05h_generated_reports(report_no,title,report_type,content_markdown,citations_json,status,created_at,updated_at) VALUES (?,?,?,?,?,'published',?,?)", (f"R-{item_id}", "历史报告", "fixed", f"见 /intelligence/{item_id}", "[]", NOW, NOW)).lastrowid
    service = IntelligenceProductService(temp_database)
    service.transition(item_id, "withdraw", actor="operator", permissions={"edit_data"})
    assert service.delete(item_id, actor="operator", permissions={"edit_data"})["deleted"] is False
    with sqlite3.connect(temp_database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone()[0] == 1


def test_raw_collection_delete_safety_and_chain_cleanup(temp_database):
    with sqlite3.connect(temp_database) as conn:
        raw_id, source_id, snapshot_id = _raw(conn, "raw-safe")
    assert collection_item_delete_preview(raw_id, temp_database)["safe_to_delete"] is True
    assert delete_collection_item_safely(raw_id, actor="operator", db_path=temp_database)["deleted"] is True
    with sqlite3.connect(temp_database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM v04g_monitoring_sources WHERE id=?", (source_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM v04g_source_snapshots WHERE id=?", (snapshot_id,)).fetchone()[0] == 1
        raw_id, source_id, snapshot_id = _raw(conn, "chain-safe")
        job_id = conn.execute("INSERT INTO v05g_processing_jobs(job_no,collection_item_id,snapshot_id,status,created_at,updated_at) VALUES (?,?,?,'failed',?,?)", (f"JOB-{raw_id}", raw_id, snapshot_id, NOW, NOW)).lastrowid
        conn.execute("INSERT INTO v05g_extraction_candidates(candidate_no,processing_job_id,collection_item_id,snapshot_id,candidate_type,review_status,pipeline_review_status,content_hash,created_at,updated_at) VALUES (?,?,?,?,?,'rejected','rejected',?,?,?)", (f"CAN-{raw_id}", job_id, raw_id, snapshot_id, "event", f"hash-{raw_id}", NOW, NOW))
    preview = collection_chain_delete_preview(raw_id, temp_database)
    assert preview["safe_to_delete"] is False
    assert preview["chain_safe_to_delete"] is True
    assert delete_collection_chain_safely(raw_id, actor="admin", db_path=temp_database)["deleted"] is True
    with sqlite3.connect(temp_database) as conn:
        assert conn.execute("SELECT COUNT(*) FROM v04g_monitoring_sources WHERE id=?", (source_id,)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM v04g_source_snapshots WHERE id=?", (snapshot_id,)).fetchone()[0] == 1


def test_candidate_delete_safety(temp_database):
    with sqlite3.connect(temp_database) as conn:
        raw_id, _, snapshot_id = _raw(conn, "candidate")
        job_id = conn.execute("INSERT INTO v05g_processing_jobs(job_no,collection_item_id,snapshot_id,status,created_at,updated_at) VALUES (?,?,?,'success',?,?)", (f"JOB-C-{raw_id}", raw_id, snapshot_id, NOW, NOW)).lastrowid
        safe_id = conn.execute("INSERT INTO v05g_extraction_candidates(candidate_no,processing_job_id,collection_item_id,snapshot_id,candidate_type,review_status,pipeline_review_status,content_hash,created_at,updated_at) VALUES (?,?,?,?,?,'rejected','rejected',?,?,?)", (f"CAN-S-{raw_id}", job_id, raw_id, snapshot_id, "event", f"hash-safe-{raw_id}", NOW, NOW)).lastrowid
        protected_id = conn.execute("INSERT INTO v05g_extraction_candidates(candidate_no,processing_job_id,collection_item_id,snapshot_id,candidate_type,review_status,pipeline_review_status,content_hash,created_at,updated_at) VALUES (?,?,?,?,?,'approved','approved',?,?,?)", (f"CAN-P-{raw_id}", job_id, raw_id, snapshot_id, "event", f"hash-protected-{raw_id}", NOW, NOW)).lastrowid
    assert candidate_delete_preview(safe_id, temp_database)["safe_to_delete"] is True
    assert delete_candidate_safely(safe_id, actor="reviewer", db_path=temp_database)["deleted"] is True
    assert candidate_delete_preview(protected_id, temp_database)["safe_to_delete"] is False


def test_viewer_dangerous_post_permissions_are_not_view_permissions():
    for path in (
        "/intelligence/1/lifecycle", "/intelligence/1/delete", "/intelligence/manage/bulk",
        "/collection/items/1/delete", "/collection/items/1/cleanup-chain",
        "/processing/candidates/1/delete",
    ):
        assert required_permission(path, "POST") in {"edit_data", "manage_monitoring", "review_data"}
