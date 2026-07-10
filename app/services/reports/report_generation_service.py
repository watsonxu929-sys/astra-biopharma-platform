from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from app.services.api_common import Pagination, normalize_page, paginated
from app.v04c_review import db_connection
from scripts.migrate_v05h import migrate as migrate_v05h

from .report_citation_service import citation, dumps, markdown_citation
from .report_query_service import report_data

REPORT_TYPES = {"daily", "weekly", "monthly", "subject", "track", "financing", "attraction", "qbay"}


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_schema(db_path: str | Path | None = None) -> None:
    migrate_v05h(Path(db_path) if db_path else None, backup=False) if db_path else migrate_v05h(backup=False)


def _next_no(conn, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    table = "v05e_sequence_counters"
    row = conn.execute(
        f"""
        INSERT INTO {table}(seq_key,seq_date,seq_value,updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date, updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, stamp, now()),
    ).fetchone()
    return f"{prefix}-{stamp}-{int(row['seq_value']):04d}"


def default_period(report_type: str) -> tuple[str, str]:
    today = date.today()
    if report_type == "weekly":
        start = today - timedelta(days=6)
    elif report_type == "monthly":
        start = today.replace(day=1)
    else:
        start = today
    return start.isoformat(), today.isoformat()


def create_report_job(*, report_type: str, period_start: str = "", period_end: str = "", filters: dict[str, Any] | None = None, generated_by: str = "manual", db_path: str | Path | None = None) -> dict[str, Any]:
    if report_type not in REPORT_TYPES:
        raise ValueError("invalid_report_type")
    ensure_schema(db_path)
    if not period_start or not period_end:
        period_start, period_end = default_period(report_type)
    ts = now()
    with db_connection(db_path) as conn:
        template = conn.execute("SELECT id FROM v05h_report_templates WHERE report_type=? AND is_enabled=1 ORDER BY id LIMIT 1", (report_type,)).fetchone()
        cur = conn.execute(
            """
            INSERT INTO v05h_report_jobs(job_no,report_type,period_start,period_end,status,template_id,filters_json,generated_by,created_at,updated_at)
            VALUES (?,?,?,?, 'pending', ?, ?, ?, ?, ?)
            """,
            (_next_no(conn, "RJOB"), report_type, period_start, period_end, template["id"] if template else None, json.dumps(filters or {}, ensure_ascii=False), generated_by, ts, ts),
        )
        return dict(conn.execute("SELECT * FROM v05h_report_jobs WHERE id=?", (cur.lastrowid,)).fetchone())


def generate_report(job_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        job = conn.execute("SELECT * FROM v05h_report_jobs WHERE id=?", (job_id,)).fetchone()
        if not job:
            raise ValueError("report_job_not_found")
        conn.execute("UPDATE v05h_report_jobs SET status='running', started_at=?, updated_at=? WHERE id=?", (now(), now(), job_id))
    try:
        filters = json.loads(job["filters_json"] or "{}")
        data = report_data(job["report_type"], job["period_start"] or "", job["period_end"] or "", filters, db_path=db_path)
        title, summary, markdown, html, citations = _render(job, data)
        with db_connection(db_path) as conn:
            ts = now()
            cur = conn.execute(
                """
                INSERT INTO v05h_generated_reports(report_no,report_job_id,title,report_type,period_start,period_end,summary,content_html,content_markdown,citations_json,version,status,created_by,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,1,'draft',?,?,?)
                """,
                (_next_no(conn, "RPT"), job_id, title, job["report_type"], job["period_start"], job["period_end"], summary, html, markdown, dumps(citations), job["generated_by"], ts, ts),
            )
            conn.execute("UPDATE v05h_report_jobs SET status='generated', finished_at=?, updated_at=? WHERE id=?", (ts, ts, job_id))
            return dict(conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (cur.lastrowid,)).fetchone())
    except Exception as exc:
        with db_connection(db_path) as conn:
            conn.execute("UPDATE v05h_report_jobs SET status='failed', error_message=?, finished_at=?, updated_at=? WHERE id=?", (str(exc)[:800], now(), now(), job_id))
        raise


def _render(job: Any, data: dict[str, Any]) -> tuple[str, str, str, str, list[dict[str, Any]]]:
    report_name = {
        "daily": "产业情报日报",
        "weekly": "产业情报周报",
        "monthly": "产业情报月报",
        "subject": "主体情报报告",
        "track": "赛道情报报告",
        "financing": "投融资情报报告",
        "attraction": "招商专题报告",
        "qbay": "Q-BAY资源与需求报告",
    }.get(job["report_type"], "产业情报报告")
    title = f"{report_name}（{_cn_date(job['period_start'] or '')}—{_cn_date(job['period_end'] or '')}）".strip()
    citations: list[dict[str, Any]] = []
    lines = [f"# {title}", "", "## 执行摘要"]
    summary = f"本周期已确认产业信号 {len(data['signals'])} 条，重点事件 {len(data['events'])} 条，待核实事项 {len(data['reviews'])} 条，待加工情报 {data['queued_processing']} 条。"
    lines.append(summary)
    lines.extend(["", "## 核心产业信号"])
    for signal in data["signals"][:20]:
        ref = citation("signal", signal.get("id"), signal.get("title") or signal.get("signal_no") or "")
        citations.append(ref)
        snapshot_ref = citation("snapshot", signal.get("snapshot_id"), "????")
        if snapshot_ref:
            citations.append(snapshot_ref)
        lines.append(f"- {signal.get('title')}?{signal.get('signal_level')}?{markdown_citation(ref)}{markdown_citation(snapshot_ref)}")
        if signal.get("evidence_excerpt"):
            lines.append(f"  证据：{signal.get('evidence_excerpt')}")
    if not data["signals"]:
        lines.append("- 本周期暂无已确认产业信号。")
    lines.extend(["", "## 重点事件"])
    for event in data["events"][:20]:
        ref = citation("event", event.get("external_id") or event.get("id"), event.get("name") or "")
        citations.append(ref)
        lines.append(f"- {event.get('name')} {markdown_citation(ref)}")
    if not data["events"]:
        lines.append("- 所选范围内暂无已确认事件。")
    lines.extend(["", "## 风险与待核实事项"])
    for review in data["reviews"][:15]:
        ref = citation("review", review.get("review_no") or review.get("id"), review.get("field_name") or "")
        citations.append(ref)
        lines.append(f"- {review.get('subject_label') or review.get('subject_id') or '未知主体'}：{review.get('field_name') or review.get('item_type')} {markdown_citation(ref)}")
    if not data["reviews"]:
        lines.append("- 暂无待核实风险事项。")
    lines.extend(["", "## 建议行动", "- 优先复核高等级和严重产业信号，再转化为行动任务。", "- 对外发布前先处理待审核记录和冲突信息。"])
    markdown = "\n".join(lines)
    html = _markdown_to_html(markdown)
    return title, summary, markdown, html, citations


def _markdown_to_html(markdown: str) -> str:
    rows = []
    for line in markdown.splitlines():
        if line.startswith("# "):
            rows.append(f"<h1>{_esc(line[2:])}</h1>")
        elif line.startswith("## "):
            rows.append(f"<h2>{_esc(line[3:])}</h2>")
        elif line.startswith("- "):
            rows.append(f"<p class=\"report-bullet\">{_esc(line[2:])}</p>")
        elif line.startswith("  证据："):
            rows.append(f"<blockquote>{_esc(line.strip())}</blockquote>")
        elif line.strip():
            rows.append(f"<p>{_esc(line)}</p>")
    return "\n".join(rows)


def _esc(value: str) -> str:
    return (value or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _cn_date(value: str) -> str:
    try:
        dt = date.fromisoformat(value)
    except ValueError:
        return value
    return f"{dt.year}年{dt.month}月{dt.day}日"


def list_reports(*, page: int = 1, page_size: int = 20, status: str = "", report_type: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    page, page_size = normalize_page(page, page_size)
    clauses = ["1=1"]
    params: list[Any] = []
    if status:
        clauses.append("status=?")
        params.append(status)
    if report_type:
        clauses.append("report_type=?")
        params.append(report_type)
    where = " AND ".join(clauses)
    with db_connection(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM v05h_generated_reports WHERE {where}", params).fetchone()[0]
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM v05h_generated_reports WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()]
    return paginated(rows, Pagination(page, page_size, total))


def list_report_jobs(*, page: int = 1, page_size: int = 20, status: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    page, page_size = normalize_page(page, page_size)
    clauses = ["1=1"]
    params: list[Any] = []
    if status:
        clauses.append("status=?")
        params.append(status)
    where = " AND ".join(clauses)
    with db_connection(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM v05h_report_jobs WHERE {where}", params).fetchone()[0]
        rows = [dict(r) for r in conn.execute(f"SELECT * FROM v05h_report_jobs WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()]
    return paginated(rows, Pagination(page, page_size, total))


def get_report(report_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone()
        return dict(row) if row else None


def update_report(report_id: int, *, title: str | None = None, summary: str | None = None, content_markdown: str | None = None, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone()
        if not row:
            return None
        new_markdown = content_markdown if content_markdown is not None else row["content_markdown"]
        conn.execute(
            "UPDATE v05h_generated_reports SET title=?, summary=?, content_markdown=?, content_html=?, updated_at=? WHERE id=?",
            (title or row["title"], summary if summary is not None else row["summary"], new_markdown, _markdown_to_html(new_markdown or ""), now(), report_id),
        )
        return dict(conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone())


def _status(report_id: int, status: str, actor: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone()
        if not row:
            return None
        updates = "status=?, updated_at=?"
        params: list[Any] = [status, now()]
        if status == "approved":
            updates += ", reviewed_by=?, reviewed_at=?"
            params.extend([actor, now()])
        if status == "published":
            updates += ", published_at=?"
            params.append(now())
        params.append(report_id)
        conn.execute(f"UPDATE v05h_generated_reports SET {updates} WHERE id=?", params)
        return dict(conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone())


def submit_report(report_id: int, actor: str = "manual", db_path: str | Path | None = None):
    return _status(report_id, "under_review", actor, db_path)


def approve_report(report_id: int, actor: str = "manual", db_path: str | Path | None = None):
    return _status(report_id, "approved", actor, db_path)


def archive_report(report_id: int, actor: str = "manual", db_path: str | Path | None = None):
    return _status(report_id, "archived", actor, db_path)


def report_citations(report_id: int, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    report = get_report(report_id, db_path)
    if not report:
        return []
    try:
        return json.loads(report.get("citations_json") or "[]")
    except json.JSONDecodeError:
        return []

