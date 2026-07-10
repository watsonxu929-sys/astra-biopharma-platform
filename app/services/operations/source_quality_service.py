from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from app.services.tasks.task_common import db_connection, next_uid, now


METRIC_LABELS = {
    "source_success_rate": "来源成功率",
    "page_fetch_success_rate": "页面抓取成功率",
    "new_item_rate": "新增内容率",
    "duplicate_rate": "重复率",
    "empty_content_rate": "空正文率",
    "review_approval_rate": "审核通过率",
    "average_processing_time": "平均加工耗时",
    "average_pipeline_time": "平均流水线耗时",
}


def calculate_source_health_scores(*, db_path: str | Path | None = None) -> dict[str, Any]:
    created = 0
    with db_connection(db_path) as conn:
        if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='v04g_monitoring_sources'").fetchone():
            return {"created": 0, "message": "暂无来源表"}
        sources = conn.execute("SELECT * FROM v04g_monitoring_sources ORDER BY id LIMIT 200").fetchall()
        for source in sources:
            runs = []
            if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='v04g_monitoring_runs'").fetchone():
                run_columns = _columns(conn, "v04g_monitoring_runs")
                fk = "source_id" if "source_id" in run_columns else "monitoring_source_id"
                runs = conn.execute(f"SELECT * FROM v04g_monitoring_runs WHERE {fk}=? ORDER BY id DESC LIMIT 20", (source["id"],)).fetchall()
            total = len(runs)
            success = sum(1 for r in runs if str(r["status"]) in {"success", "unchanged", "partial"})
            success_rate = (success / total) if total else None
            score = int((success_rate or 0) * 70 + (30 if total else 10))
            grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 50 else "D"
            conn.execute(
                """
                INSERT INTO source_health_scores(source_id,source_key,source_name,lifecycle_status,source_grade,health_score,credibility_score,success_rate,quality_score,last_run_at,needs_attention,metrics_json,calculated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (source["id"], source["external_id"] if "external_id" in source.keys() else str(source["id"]), source["name"], _source_lifecycle(source), grade, score, score, success_rate, None, runs[0]["started_at"] if runs and "started_at" in runs[0].keys() else None, int(score < 50), json.dumps({"run_count": total, "success_count": success}, ensure_ascii=False), now()),
            )
            created += 1
    return {"created": created}


def quality_metrics(*, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        source_total = _count(conn, "v04g_monitoring_sources")
        source_columns = _columns(conn, "v04g_monitoring_sources")
        if "status" in source_columns:
            active_sources = _count_where(conn, "v04g_monitoring_sources", "status IN ('active','enabled')")
        elif "is_enabled" in source_columns:
            active_sources = _count_where(conn, "v04g_monitoring_sources", "is_enabled=1")
        else:
            active_sources = source_total
        collection_items = _count(conn, "v05f_collection_items")
        samples = _count(conn, "source_quality_samples")
        reviewed_samples = _count_where(conn, "source_quality_samples", "correctness!='pending'")
        success_rate = None
        if conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='v04g_monitoring_runs'").fetchone():
            total = _count(conn, "v04g_monitoring_runs")
            success = _count_where(conn, "v04g_monitoring_runs", "status IN ('success','unchanged','partial')")
            success_rate = success / total if total else None
    metrics = {
        "source_success_rate": {"label": METRIC_LABELS["source_success_rate"], "value": success_rate, "sample_size": source_total},
        "new_item_rate": {"label": METRIC_LABELS["new_item_rate"], "value": None, "sample_size": collection_items, "note": "样本不足" if collection_items < 1 else ""},
        "review_approval_rate": {"label": METRIC_LABELS["review_approval_rate"], "value": None, "sample_size": reviewed_samples, "note": "准确率必须基于人工样本"},
        "source_total": source_total,
        "active_sources": active_sources,
        "quality_samples": samples,
    }
    return metrics


def create_quality_report(*, created_by: str = "manual", db_path: str | Path | None = None) -> dict[str, Any]:
    metrics = quality_metrics(db_path=db_path)
    end = date.today()
    start = end - timedelta(days=6)
    lines = [
        "# 数据质量周报草稿",
        "",
        f"周期：{start.isoformat()} 至 {end.isoformat()}",
        "",
        f"- 来源总数：{metrics['source_total']}",
        f"- 活跃来源：{metrics['active_sources']}",
        f"- 质量样本：{metrics['quality_samples']}",
        "- 准确率说明：未人工抽样的指标不伪装为准确率。",
        "",
        "## 改进建议",
        "优先处理连续失败来源、空正文来源和规则变更后的低置信度样本。",
    ]
    with db_connection(db_path) as conn:
        report_no = next_uid(conn, "QREP")
        conn.execute(
            "INSERT INTO quality_reports(report_no,period_start,period_end,metrics_json,sample_refs_json,content_markdown,created_by,created_at,updated_at) VALUES (?, ?, ?, ?, '[]', ?, ?, ?, ?)",
            (report_no, start.isoformat(), end.isoformat(), json.dumps(metrics, ensure_ascii=False), "\n".join(lines), created_by, now(), now()),
        )
        return dict(conn.execute("SELECT * FROM quality_reports WHERE report_no=?", (report_no,)).fetchone())


def _count(conn, table: str) -> int:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _count_where(conn, table: str, where: str) -> int:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
        return 0
    return int(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {where}").fetchone()[0])


def _columns(conn, table: str) -> set[str]:
    if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone():
        return set()
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}


def _source_lifecycle(source) -> str:
    keys = set(source.keys())
    if "status" in keys:
        return str(source["status"])
    if "is_enabled" in keys:
        return "active" if int(source["is_enabled"] or 0) else "inactive"
    return "pilot"
