from __future__ import annotations

from pathlib import Path
from typing import Any

from .pipeline_common import db_connection, ensure_schema


def _rate(numerator: int, denominator: int) -> float:
    return round((float(numerator) / float(denominator)) * 100, 2) if denominator else 0.0


def quality_metrics(db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        runs = conn.execute("SELECT COUNT(*) FROM v05i_pipeline_runs").fetchone()[0]
        completed = conn.execute("SELECT COUNT(*) FROM v05i_pipeline_runs WHERE status='completed'").fetchone()[0]
        failed = conn.execute("SELECT COUNT(*) FROM v05i_pipeline_runs WHERE status='failed'").fetchone()[0]
        collection_total = conn.execute("SELECT COUNT(*) FROM v04g_monitoring_runs WHERE COALESCE(job_type,'collection')='collection'").fetchone()[0]
        collection_success = conn.execute("SELECT COUNT(*) FROM v04g_monitoring_runs WHERE COALESCE(job_type,'collection')='collection' AND status IN ('success','partial','unchanged')").fetchone()[0]
        item_total = conn.execute("SELECT COUNT(*) FROM v05f_collection_items").fetchone()[0]
        new_items = conn.execute("SELECT COUNT(*) FROM v05f_collection_items WHERE dedup_status IN ('new','changed')").fetchone()[0]
        duplicates = conn.execute("SELECT COUNT(*) FROM v05f_collection_items WHERE dedup_status IN ('duplicate','unchanged')").fetchone()[0]
        empty_items = conn.execute("SELECT COUNT(*) FROM v05f_collection_items WHERE warning_json LIKE '%empty_content%'").fetchone()[0]
        processing_total = conn.execute("SELECT COUNT(*) FROM v05g_processing_jobs").fetchone()[0]
        processing_success = conn.execute("SELECT COUNT(*) FROM v05g_processing_jobs WHERE status IN ('success','needs_review')").fetchone()[0]
        candidates = conn.execute("SELECT COUNT(*) FROM v05g_extraction_candidates").fetchone()[0]
        matches = conn.execute("SELECT COUNT(*) FROM v05g_subject_match_candidates WHERE status='confirmed'").fetchone()[0]
        ambiguous = conn.execute("SELECT COUNT(*) FROM v05g_subject_match_candidates WHERE status='ambiguous'").fetchone()[0]
        approved = conn.execute("SELECT COUNT(*) FROM v05g_extraction_candidates WHERE review_status IN ('approved','applied')").fetchone()[0]
        applied = conn.execute("SELECT COUNT(*) FROM v05g_candidate_application_logs WHERE result='success'").fetchone()[0]
        signals = conn.execute("SELECT COUNT(*) FROM v05e_industry_signals").fetchone()[0]
        reports = conn.execute("SELECT COUNT(*) FROM v05h_generated_reports WHERE status IN ('draft','under_review','approved','published')").fetchone()[0]
        avg_duration = conn.execute("SELECT AVG(strftime('%s',finished_at)-strftime('%s',started_at)) FROM v05i_pipeline_runs WHERE started_at IS NOT NULL AND finished_at IS NOT NULL").fetchone()[0] or 0
        avg_conf = conn.execute("SELECT AVG(confidence_score) FROM v05g_extraction_candidates").fetchone()[0] or 0
    return {
        "source_success_rate": _rate(collection_success, collection_total),
        "collection_new_item_rate": _rate(new_items, item_total),
        "duplicate_rate": _rate(duplicates, item_total),
        "empty_content_rate": _rate(empty_items, item_total),
        "processing_success_rate": _rate(processing_success, processing_total),
        "structure_confidence_average": round(float(avg_conf), 2),
        "candidate_per_item": round(float(candidates) / float(item_total), 2) if item_total else 0,
        "subject_match_rate": _rate(matches, candidates),
        "ambiguous_match_rate": _rate(ambiguous, candidates),
        "review_approval_rate": _rate(approved, candidates),
        "apply_success_rate": _rate(applied, approved),
        "signal_generation_rate": _rate(signals, max(candidates, 1)),
        "report_completion_rate": _rate(reports, runs),
        "average_pipeline_duration": round(float(avg_duration), 2),
        "pipeline_completed_rate": _rate(completed, runs),
        "pipeline_failed_rate": _rate(failed, runs),
    }
