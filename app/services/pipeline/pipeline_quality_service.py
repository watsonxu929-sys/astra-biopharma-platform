from __future__ import annotations

from pathlib import Path
from typing import Any

from .pipeline_common import db_connection, ensure_schema, next_no, now

ERROR_TYPES = {
    "正文提取错误",
    "页面结构错误",
    "主体拆分错误",
    "姓名错误",
    "机构错误",
    "事件类型错误",
    "时间错误",
    "金额错误",
    "主体匹配错误",
    "重复判断错误",
    "来源证据不足",
}


def create_quality_samples(pipeline_run_id: int, *, ratio: float = 0.2, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    created = 0
    with db_connection(db_path) as conn:
        run = conn.execute("SELECT * FROM v05i_pipeline_runs WHERE id=?", (pipeline_run_id,)).fetchone()
        if not run:
            raise ValueError("pipeline_run_not_found")
        candidates = conn.execute(
            """
            SELECT id, candidate_no FROM v05g_extraction_candidates
            WHERE processing_job_id IN (
              SELECT id FROM v05g_processing_jobs WHERE collection_item_id IN (
                SELECT id FROM v05f_collection_items WHERE monitoring_run_id=?
              )
            )
            ORDER BY id
            """,
            (run["collection_job_id"],),
        ).fetchall()
        step = max(1, int(1 / max(0.05, min(float(ratio or 0.2), 1.0))))
        for idx, row in enumerate(candidates):
            if idx % step != 0:
                continue
            cur = conn.execute(
                """
                INSERT OR IGNORE INTO v05i_pipeline_quality_samples(
                    sample_no, pipeline_run_id, source_id, sample_type, target_table, target_id, target_no, created_at, updated_at
                ) VALUES (?, ?, ?, 'candidate', 'v05g_extraction_candidates', ?, ?, ?, ?)
                """,
                (next_no(conn, "SMP"), pipeline_run_id, run["source_id"], int(row["id"]), row["candidate_no"], now(), now()),
            )
            if cur.rowcount:
                created += 1
    return {"created": created}


def review_quality_sample(sample_id: int, *, correctness: str, error_type: str = "", reviewer: str = "", note: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    if correctness not in {"correct", "incorrect", "partial"}:
        raise ValueError("invalid_correctness")
    if error_type and error_type not in ERROR_TYPES:
        raise ValueError("invalid_error_type")
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05i_pipeline_quality_samples WHERE id=?", (sample_id,)).fetchone()
        if not row:
            raise ValueError("sample_not_found")
        conn.execute(
            """
            UPDATE v05i_pipeline_quality_samples
            SET review_status='reviewed', correctness=?, error_type=?, reviewer=?, review_note=?, reviewed_at=?, updated_at=?
            WHERE id=?
            """,
            (correctness, error_type or None, reviewer or "manual", note[:1000] or None, now(), now(), sample_id),
        )
        return dict(conn.execute("SELECT * FROM v05i_pipeline_quality_samples WHERE id=?", (sample_id,)).fetchone())
