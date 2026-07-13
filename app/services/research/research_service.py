from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from app.i18n import translate_status, translate_type, with_labels
from app.services.api_common import Pagination, normalize_page, paginated
from app.services.reports.report_generation_service import _next_no as next_report_no
from app.services.reports.report_generation_service import create_report_job

from .common import db_connection, dumps, ensure_schema, label_row, loads, next_no, now, org_by_id, table_exists

TOPIC_TYPES = {"track", "region", "company_group", "technology", "investment", "investment_attraction", "custom"}


def create_topic(*, name: str, description: str = "", topic_type: str = "custom", track_tags: str = "", region_filters: str = "", period_start: str = "", period_end: str = "", owner_id: int | None = None, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    topic_type = topic_type if topic_type in TOPIC_TYPES else "custom"
    ts = now()
    with db_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO research_topics(topic_no,name,description,topic_type,status,track_tags,region_filters,subject_types,period_start,period_end,owner_id,created_at,updated_at)
            VALUES (?, ?, ?, ?, 'draft', ?, ?, 'organization,person,project', ?, ?, ?, ?, ?)
            """,
            (next_no(conn, "RSH"), name.strip(), description.strip() or None, topic_type, track_tags or None, region_filters or None, period_start or None, period_end or None, owner_id, ts, ts),
        )
        return _topic_dict(conn.execute("SELECT * FROM research_topics WHERE id=?", (cur.lastrowid,)).fetchone())


def list_topics(*, page: int = 1, page_size: int = 20, status: str = "", topic_type: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    page, page_size = normalize_page(page, page_size)
    clauses = ["1=1"]
    params: list[Any] = []
    if status:
        clauses.append("status=?")
        params.append(status)
    if topic_type:
        clauses.append("topic_type=?")
        params.append(topic_type)
    where = " AND ".join(clauses)
    with db_connection(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM research_topics WHERE {where}", params).fetchone()[0]
        rows = [_topic_dict(r) for r in conn.execute(f"SELECT * FROM research_topics WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()]
    return paginated(rows, Pagination(page, page_size, int(total)))


def get_topic(topic_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM research_topics WHERE id=?", (topic_id,)).fetchone()
        return _topic_dict(row) if row else None


def add_topic_subject(topic_id: int, subject_type: str, subject_id: str, *, inclusion_type: str = "manual", reason: str = "", source: str = "", added_by: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    if subject_type not in {"organization", "person", "project"}:
        raise ValueError("unsupported_subject_type")
    if inclusion_type not in {"manual", "rule", "imported", "recommended"}:
        inclusion_type = "manual"
    with db_connection(db_path) as conn:
        topic = conn.execute("SELECT * FROM research_topics WHERE id=?", (topic_id,)).fetchone()
        if not topic:
            raise ValueError("topic_not_found")
        table = {"organization": "organizations", "person": "people", "project": "projects"}[subject_type]
        row = conn.execute(f"SELECT external_id FROM {table} WHERE external_id=? OR CAST(id AS TEXT)=?", (subject_id, subject_id)).fetchone()
        if not row:
            raise ValueError("subject_not_found")
        conn.execute(
            """
            INSERT OR IGNORE INTO research_topic_subjects(topic_id,subject_type,subject_id,inclusion_type,reason,source,added_by,created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (topic_id, subject_type, row["external_id"], inclusion_type, reason or None, source or None, added_by or None, now()),
        )
        return dict(conn.execute("SELECT * FROM research_topic_subjects WHERE topic_id=? AND subject_type=? AND subject_id=?", (topic_id, subject_type, row["external_id"])).fetchone())


def remove_topic_subject(topic_id: int, subject_type: str, subject_id: str, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        conn.execute("DELETE FROM research_topic_subjects WHERE topic_id=? AND subject_type=? AND subject_id=?", (topic_id, subject_type, subject_id))
    return {"removed": True}


def refresh_topic(topic_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    metrics = topic_dashboard(topic_id, db_path=db_path)
    ts = now()
    with db_connection(db_path) as conn:
        conn.execute(
            "INSERT INTO research_snapshots(topic_id,snapshot_at,subject_count,event_count,signal_count,metrics_json,source_version,created_at) VALUES (?, ?, ?, ?, ?, ?, 'v0.5J', ?)",
            (topic_id, ts, metrics["counts"]["subjects"], metrics["counts"]["events"], metrics["counts"]["signals"], dumps(metrics), ts),
        )
        conn.execute("UPDATE research_topics SET status='active', last_refreshed_at=?, updated_at=? WHERE id=?", (ts, ts, topic_id))
    return metrics


def archive_topic(topic_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        conn.execute("UPDATE research_topics SET status='archived', updated_at=? WHERE id=?", (now(), topic_id))
    return get_topic(topic_id, db_path=db_path) or {}


def topic_dashboard(topic_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        subjects = _topic_subjects(conn, topic_id)
        org_ids = [s["subject_id"] for s in subjects if s["subject_type"] == "organization"]
        all_ids = [s["subject_id"] for s in subjects]
        events = _events_for_ids(conn, all_ids)
        signals = _signals_for_ids(conn, all_ids)
        counts = {
            "subjects": len(subjects),
            "organizations": sum(1 for s in subjects if s["subject_type"] == "organization"),
            "people": sum(1 for s in subjects if s["subject_type"] == "person"),
            "projects": sum(1 for s in subjects if s["subject_type"] == "project"),
            "events": len(events),
            "signals": len(signals),
            "financing_events": sum(1 for e in events if "融资" in str(e.get("event_type") or "") or "financ" in str(e.get("event_type") or "").lower()),
            "cooperation_events": sum(1 for e in events if "合作" in str(e.get("event_type") or "")),
            "risk_signals": sum(1 for s in signals if s.get("signal_type") == "risk" or s.get("signal_level") in {"critical", "high"}),
        }
        latest = events[:10]
        important = subjects[:10]
        completeness = 0 if not org_ids else int(sum(_org_completeness(conn, oid) for oid in org_ids) / len(org_ids))
    return {"counts": counts, "latest_events": latest, "important_subjects": important, "data_completeness": completeness, "source_coverage": "数据不足" if not events and not signals else "已有系统来源"}


def topic_timeline(topic_id: int, *, event_type: str = "", signal_level: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        if table_exists(conn, "p2_3_industry_events"):
            from .fusion_service import event_timeline
            rows = event_timeline(topic_id=topic_id, event_type=event_type, db_path=db_path)
            return {"data": [{"kind": "event", **row} for row in rows]}
        ids = [s["subject_id"] for s in _topic_subjects(conn, topic_id)]
        events = _events_for_ids(conn, ids)
        if event_type:
            events = [e for e in events if e.get("event_type") == event_type]
        signals = _signals_for_ids(conn, ids)
        if signal_level:
            signals = [s for s in signals if s.get("signal_level") == signal_level]
    rows = [{"kind": "event", **e} for e in events] + [{"kind": "signal", **s} for s in signals]
    rows.sort(key=lambda r: str(r.get("event_date") or r.get("occurred_at") or r.get("created_at") or ""), reverse=True)
    return {"data": rows}


def topic_signals(topic_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        ids = [s["subject_id"] for s in _topic_subjects(conn, topic_id)]
        return {"data": [_signal_label(r) for r in _signals_for_ids(conn, ids)]}


def topic_network(topic_id: int, *, limit: int = 120, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        ids = [s["subject_id"] for s in _topic_subjects(conn, topic_id)]
        if not ids:
            return {"nodes": [], "edges": [], "truncated": False}
        placeholders = ",".join("?" for _ in ids)
        rows = conn.execute(
            f"SELECT * FROM relations WHERE COALESCE(is_active,1)=1 AND (source_external_id IN ({placeholders}) OR target_external_id IN ({placeholders})) ORDER BY id DESC LIMIT ?",
            [*ids, *ids, limit + 1],
        ).fetchall()
    edges = [dict(r) for r in rows[:limit]]
    nodes = sorted({e.get("source_external_id") for e in edges} | {e.get("target_external_id") for e in edges})
    return {"nodes": [{"id": n, "label": n} for n in nodes if n], "edges": edges, "truncated": len(rows) > limit}


def compare_companies(org_ids: list[str], *, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    unique = []
    for oid in org_ids:
        if oid not in unique:
            unique.append(oid)
    if len(unique) < 2 or len(unique) > 8:
        raise ValueError("company_count_must_be_2_to_8")
    rows = []
    with db_connection(db_path) as conn:
        for oid in unique:
            org = org_by_id(conn, oid)
            if not org:
                raise ValueError("organization_not_found")
            events = _events_for_ids(conn, [org["external_id"]])
            signals = _signals_for_ids(conn, [org["external_id"]])
            row = {
                "organization_id": org["external_id"],
                "name": org["standard_name"],
                "region": org["region"] or "无公开信息",
                "stage": org["org_type"] or "无公开信息",
                "track": org["industry_tags"] or "无公开信息",
                "website": org["source_url"] if "source_url" in org.keys() and org["source_url"] else "无公开信息",
                "event_count": len(events),
                "signal_count": len(signals),
                "financing_events": sum(1 for e in events if "融资" in str(e.get("event_type") or "")),
                "risk_signals": sum(1 for s in signals if s.get("signal_level") in {"critical", "high"}),
                "data_range": "系统已确认数据",
                "updated_at": org["created_at"] if "created_at" in org.keys() else "待核实",
                "missing": _missing_org_fields(dict(org)),
                "scores": _company_scores(dict(org), events, signals),
            }
            rows.append(row)
    return {"companies": rows, "notes": ["未披露信息显示为无公开信息，不解释为没有。", "本版本不生成企业总分，仅展示独立维度评分。"]}


def tracks(*, window: str = "30d", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        orgs = [dict(r) for r in conn.execute("SELECT external_id, standard_name, industry_tags, region FROM organizations WHERE COALESCE(is_active,1)=1").fetchall()]
        result: dict[str, dict[str, Any]] = {}
        for org in orgs:
            tags = [t.strip() for t in str(org.get("industry_tags") or "未分类").replace("；", ";").split(";") if t.strip()] or ["未分类"]
            for tag in tags:
                row = result.setdefault(tag, {"track_key": tag, "track_label": tag, "organization_count": 0, "event_count": 0, "signal_count": 0})
                row["organization_count"] += 1
                row["event_count"] += len(_events_for_ids(conn, [org["external_id"]]))
                row["signal_count"] += len(_signals_for_ids(conn, [org["external_id"]]))
    return {"data": list(result.values()), "window": window}


def track_detail(track_key: str, *, window: str = "30d", db_path: str | Path | None = None) -> dict[str, Any]:
    data = tracks(window=window, db_path=db_path)["data"]
    row = next((r for r in data if r["track_key"] == track_key), None)
    if not row:
        return {"track_key": track_key, "conclusion": "样本量不足，暂不形成趋势判断", "data": {}}
    conclusion = "样本量不足，暂不形成趋势判断" if row["event_count"] < 3 else "已有明确统计样本，可继续人工研判"
    return {"track_key": track_key, "window": window, "data": row, "trend": {"current_window": window, "sample_count": row["event_count"], "conclusion": conclusion, "confidence": "低" if row["event_count"] < 3 else "中"}}


def create_topic_report(topic_id: int, *, created_by: str = "manual", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    topic = get_topic(topic_id, db_path=db_path)
    if not topic:
        raise ValueError("topic_not_found")
    dashboard = topic_dashboard(topic_id, db_path=db_path)
    timeline = topic_timeline(topic_id, db_path=db_path)["data"]
    signals = topic_signals(topic_id, db_path=db_path)["data"]
    today = date.today().isoformat()
    report_type = "attraction" if topic.get("topic_type") == "investment_attraction" else "track"
    job = create_report_job(report_type=report_type, period_start=topic.get("period_start") or today, period_end=topic.get("period_end") or today, filters={"topic_id": topic_id}, generated_by=created_by, db_path=db_path)
    citations = [{"type": "research_topic", "id": topic_id, "ref": topic.get("topic_no")}]
    citations.extend({"type": "event", "id": item.get("external_id") or item.get("id"), "ref": item.get("name") or item.get("title")} for item in timeline[:20] if item.get("kind") == "event")
    citations.extend({"type": "signal", "id": item.get("signal_no") or item.get("id"), "ref": item.get("title")} for item in signals[:20])
    markdown = _topic_report_markdown(topic, dashboard, timeline, signals)
    summary = f"专题覆盖主体 {dashboard['counts']['subjects']} 个、事件 {dashboard['counts']['events']} 条、信号 {dashboard['counts']['signals']} 条。"
    return _insert_research_report(job, title=f"{topic['name']}专题研究报告", summary=summary, markdown=markdown, citations=list(citations), created_by=created_by, db_path=db_path)


def create_company_compare_report(org_ids: list[str], *, created_by: str = "manual", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    compare = compare_companies(org_ids, db_path=db_path)
    today = date.today().isoformat()
    names = "、".join(company["name"] for company in compare["companies"])
    job = create_report_job(report_type="subject", period_start=today, period_end=today, filters={"organization_ids": [c["organization_id"] for c in compare["companies"]]}, generated_by=created_by, db_path=db_path)
    citations = [{"type": "organization", "id": c["organization_id"], "ref": c["name"]} for c in compare["companies"]]
    lines = [f"# 企业对比报告：{names}", "", "## 研究范围", names, "", "## 对比说明", "本报告为研究草稿，仅使用系统已确认主体、事件和信号。未披露字段显示为无公开信息，不解释为没有。", "", "## 企业对比"]
    for company in compare["companies"]:
        lines.extend([
            f"### {company['name']}",
            f"- 地区：{company['region']}",
            f"- 赛道：{company['track']}",
            f"- 阶段：{company['stage']}",
            f"- 事件数量：{company['event_count']}",
            f"- 信号数量：{company['signal_count']}",
            f"- 缺失字段：{'、'.join(company['missing']) if company['missing'] else '已确认'}",
            "",
        ])
    lines.extend(["## 评分边界", "本报告不生成企业总分，仅展示独立维度评分。", "", "## 来源和引用", "引用见报告中心引用区。"])
    markdown = "\n".join(lines)
    summary = f"对比企业 {len(compare['companies'])} 家：{names}。"
    return _insert_research_report(job, title=f"企业对比报告：{names}", summary=summary, markdown=markdown, citations=citations, created_by=created_by, db_path=db_path)


def _insert_research_report(job: dict[str, Any], *, title: str, summary: str, markdown: str, citations: list[dict[str, Any]], created_by: str, db_path: str | Path | None = None) -> dict[str, Any]:
    html = markdown.replace("\n", "<br>")
    ts = now()
    with db_connection(db_path) as conn:
        cur = conn.execute(
            """
            INSERT INTO v05h_generated_reports(report_no,report_job_id,title,report_type,period_start,period_end,summary,content_html,content_markdown,citations_json,version,status,created_by,created_at,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,1,'draft',?,?,?)
            """,
            (next_report_no(conn, "RPT"), job["id"], title, job["report_type"], job["period_start"], job["period_end"], summary, html, markdown, dumps(citations), created_by, ts, ts),
        )
        conn.execute("UPDATE v05h_report_jobs SET status='generated', started_at=COALESCE(started_at, ?), finished_at=?, updated_at=? WHERE id=?", (ts, ts, ts, job["id"]))
        return dict(conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (cur.lastrowid,)).fetchone())


def _topic_report_markdown(topic: dict[str, Any], dashboard: dict[str, Any], timeline: list[dict[str, Any]], signals: list[dict[str, Any]]) -> str:
    counts = dashboard["counts"]
    lines = [
        f"# {topic['name']}专题研究报告",
        "",
        "## 研究范围",
        f"- 专题类型：{topic.get('topic_type_label')}",
        f"- 数据周期：{topic.get('period_start') or '未限定'} 至 {topic.get('period_end') or '未限定'}",
        "",
        "## 样本说明",
        f"主体 {counts['subjects']} 个，企业 {counts['organizations']} 家，事件 {counts['events']} 条，信号 {counts['signals']} 条。",
        "",
        "## 执行摘要",
        "本报告为研究草稿，所有结论需结合引用和人工复核确认。",
        "",
        "## 重点事件",
    ]
    for item in timeline[:10]:
        lines.append(f"- {item.get('name') or item.get('title') or '待核实'}：{item.get('fact_summary') or item.get('summary') or '待核实'}")
    if not timeline:
        lines.append("- 数据不足")
    lines.extend(["", "## 产业信号"])
    for item in signals[:10]:
        lines.append(f"- {item.get('title') or '待核实'}：{item.get('signal_level_label') or item.get('signal_level') or '待核实'}")
    if not signals:
        lines.append("- 暂无信号")
    lines.extend(["", "## 风险与待核实事项", "未找到引用的事实不得作为确定结论；数据不足项保持待核实。", "", "## 来源和引用", "引用见报告中心引用区。"])
    return "\n".join(lines)


def _topic_dict(row) -> dict[str, Any]:
    data = dict(row)
    data["status_label"] = translate_status(data.get("status"), "research_topic")
    data["topic_type_label"] = translate_type(data.get("topic_type"))
    return data


def _topic_subjects(conn, topic_id: int) -> list[dict[str, Any]]:
    rows = [dict(r) for r in conn.execute("SELECT * FROM research_topic_subjects WHERE topic_id=? ORDER BY id", (topic_id,)).fetchall()]
    for row in rows:
        row["subject_type_label"] = translate_type(row["subject_type"])
        row["inclusion_type_label"] = translate_type(row["inclusion_type"])
    return rows


def _events_for_ids(conn, ids: list[str]) -> list[dict[str, Any]]:
    if not ids or not table_exists(conn, "events"):
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(f"SELECT * FROM events WHERE COALESCE(is_active,1)=1 AND related_entity IN ({placeholders}) ORDER BY COALESCE(event_date, created_at) DESC LIMIT 200", ids).fetchall()
    return [dict(r) for r in rows]


def _signals_for_ids(conn, ids: list[str]) -> list[dict[str, Any]]:
    if not ids or not table_exists(conn, "v05e_industry_signals"):
        return []
    placeholders = ",".join("?" for _ in ids)
    rows = conn.execute(f"SELECT * FROM v05e_industry_signals WHERE subject_id IN ({placeholders}) ORDER BY id DESC LIMIT 200", ids).fetchall()
    return [_signal_label(r) for r in rows]


def _signal_label(row) -> dict[str, Any]:
    data = dict(row)
    data["signal_level_label"] = translate_status(data.get("signal_level"), "signal_level")
    data["status_label"] = translate_status(data.get("status"))
    return data


def _org_completeness(conn, oid: str) -> int:
    row = org_by_id(conn, oid)
    if not row:
        return 0
    fields = [row["standard_name"], row["region"], row["industry_tags"], row["org_type"]]
    return int(sum(1 for value in fields if value) / len(fields) * 100)


def _missing_org_fields(org: dict[str, Any]) -> list[str]:
    fields = {"region": "注册地区", "industry_tags": "所属赛道", "org_type": "发展阶段"}
    return [label for key, label in fields.items() if not org.get(key)]


def _company_scores(org: dict[str, Any], events: list[dict[str, Any]], signals: list[dict[str, Any]]) -> dict[str, Any]:
    completeness = 100 - len(_missing_org_fields(org)) * 25
    return {
        "信息完整度": {"score": max(0, completeness), "basis": "基于地区、赛道、阶段等字段完整度"},
        "近期活跃度": {"score": min(100, len(events) * 20), "basis": f"系统正式事件 {len(events)} 条"},
        "资本活跃度": {"score": min(100, sum(1 for e in events if '融资' in str(e.get('event_type') or '')) * 30), "basis": "基于已确认融资事件"},
        "招商匹配度": {"score": None if not org.get("industry_tags") else 60, "basis": "仅作维度评分，不形成总分"},
        "风险关注度": {"score": min(100, sum(1 for s in signals if s.get('signal_level') in {'critical','high'}) * 30), "basis": "高等级风险信号数量"},
    }
