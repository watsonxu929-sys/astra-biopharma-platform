from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.ai import ProviderRegistry
from app.v04c_review import db_connection

from .fusion_service import APPROVED_EVENT_STATUSES, event_timeline, list_conflicts, now

FINDING_TYPES = {"verified_fact", "inference", "analyst_opinion", "hypothesis", "conflict"}
REPORT_TYPES = {"brief", "company_tracking", "track_brief", "topic_report", "investment_judgment", "event_material"}
RESEARCH_STATUSES = {"draft", "pending_review", "needs_revision", "approved", "published", "archived"}
MISSING = "暂无可靠数据"


def _loads(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def _dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _no(prefix: str) -> str:
    return f"{prefix}-{datetime.now():%Y%m%d}-{uuid.uuid4().hex[:10].upper()}"


def configure_topic(
    topic_id: int,
    *,
    research_scope: str = "",
    keywords: str = "",
    subject_scope: list[dict[str, str]] | None = None,
    responsible_user: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        topic = conn.execute("SELECT * FROM research_topics WHERE id=?", (topic_id,)).fetchone()
        if not topic:
            raise ValueError("topic_not_found")
        conn.execute(
            """UPDATE research_topics SET research_scope=?,keywords=?,subject_scope_json=?,
               responsible_user=?,updated_at=? WHERE id=?""",
            (
                research_scope or None, keywords or None, _dump(subject_scope or []),
                responsible_user or None, now(), topic_id,
            ),
        )
        return dict(conn.execute("SELECT * FROM research_topics WHERE id=?", (topic_id,)).fetchone())


def add_research_question(
    topic_id: int,
    question: str,
    *,
    actor: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if not question.strip():
        raise ValueError("research_question_required")
    ts = now()
    with db_connection(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO p2_3_research_questions(
               topic_id,question,status,created_by,created_at,updated_at)
               VALUES (?,?,'open',?,?,?)""",
            (topic_id, question.strip(), actor, ts, ts),
        )
        return dict(conn.execute("SELECT * FROM p2_3_research_questions WHERE id=?", (cur.lastrowid,)).fetchone())


def _topic_subjects(conn, topic_id: int) -> list[dict[str, Any]]:
    rows = []
    for row in conn.execute("SELECT * FROM research_topic_subjects WHERE topic_id=? ORDER BY id", (topic_id,)):
        item = dict(row)
        table = {"organization": "organizations", "person": "people", "project": "projects"}.get(item["subject_type"])
        if table:
            label_col = "standard_name" if table == "organizations" else "name"
            subject = conn.execute(
                f"SELECT {label_col} label FROM {table} WHERE external_id=? OR CAST(id AS TEXT)=? LIMIT 1",
                (item["subject_id"], item["subject_id"]),
            ).fetchone()
            item["subject_label"] = subject["label"] if subject else item["subject_id"]
        rows.append(item)
    return rows


def topic_workspace(topic_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        topic = conn.execute("SELECT * FROM research_topics WHERE id=?", (topic_id,)).fetchone()
        if not topic:
            raise ValueError("topic_not_found")
        subjects = _topic_subjects(conn, topic_id)
        questions = [dict(r) for r in conn.execute(
            "SELECT * FROM p2_3_research_questions WHERE topic_id=? ORDER BY id DESC", (topic_id,)
        )]
        assertions = [dict(r) for r in conn.execute(
            """SELECT DISTINCT a.* FROM p2_3_fact_assertions a
               LEFT JOIN p2_3_topic_events te ON te.event_id=a.event_id
               WHERE a.topic_id=? OR te.topic_id=?
               ORDER BY a.id DESC""",
            (topic_id, topic_id),
        )]
        findings = [dict(r) for r in conn.execute(
            "SELECT * FROM p2_3_research_findings WHERE topic_id=? ORDER BY id DESC", (topic_id,)
        )]
        reports = [dict(r) for r in conn.execute(
            "SELECT * FROM v05h_generated_reports WHERE topic_id=? ORDER BY id DESC", (topic_id,)
        )]
        evidence_count = conn.execute(
            """SELECT COUNT(*) FROM p2_3_event_evidence ee
               JOIN p2_3_topic_events te ON te.event_id=ee.event_id WHERE te.topic_id=?""",
            (topic_id,),
        ).fetchone()[0]
    events = event_timeline(topic_id=topic_id, db_path=db_path)
    conflicts = list_conflicts(topic_id=topic_id, db_path=db_path)
    return {
        "topic": {**dict(topic), "subject_scope": _loads(topic["subject_scope_json"], [])},
        "subjects": subjects,
        "events": events,
        "timeline": events,
        "assertions": assertions,
        "questions": questions,
        "conflicts": conflicts,
        "findings": findings,
        "reports": reports,
        "counts": {
            "subjects": len(subjects), "events": len(events), "assertions": len(assertions),
            "open_questions": sum(1 for q in questions if q["status"] in {"open", "investigating"}),
            "unresolved_conflicts": sum(1 for c in conflicts if c["status"] != "resolved"),
            "findings": len(findings), "reports": len(reports), "evidence": int(evidence_count),
        },
    }


def create_finding(
    topic_id: int,
    *,
    finding_type: str,
    title: str,
    content: str,
    assertion_ids: list[int] | None = None,
    confidence: int | None = None,
    actor: str = "analyst",
    generated_by: str = "analyst",
    provider: str = "",
    model: str = "",
    prompt_version: str = "",
    is_pilot: bool = False,
    pilot_batch_id: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if finding_type not in FINDING_TYPES:
        raise ValueError("invalid_finding_type")
    if not title.strip() or not content.strip():
        raise ValueError("finding_title_and_content_required")
    assertion_ids = list(dict.fromkeys(int(value) for value in (assertion_ids or [])))
    if finding_type in {"verified_fact", "inference"} and not assertion_ids:
        raise ValueError("finding_assertion_required")
    ts = now()
    with db_connection(db_path) as conn:
        if assertion_ids:
            placeholders = ",".join("?" for _ in assertion_ids)
            rows = conn.execute(
                f"SELECT id,review_status FROM p2_3_fact_assertions WHERE id IN ({placeholders})",
                assertion_ids,
            ).fetchall()
            if len(rows) != len(assertion_ids):
                raise ValueError("assertion_not_found")
            if finding_type == "verified_fact" and any(row["review_status"] != "approved" for row in rows):
                raise ValueError("verified_fact_requires_approved_assertions")
        digest = hashlib.sha256(content.strip().encode("utf-8")).hexdigest()
        cur = conn.execute(
            """INSERT INTO p2_3_research_findings(
               finding_no,topic_id,finding_type,title,content,confidence,status,generated_by,
               provider,model,prompt_version,output_hash,is_pilot,pilot_batch_id,created_by,
               created_at,updated_at)
               VALUES (?,?,?,?,?,?,'draft',?,?,?,?,?,?,?,?,?,?)""",
            (
                _no("RFD"), topic_id, finding_type, title.strip(), content.strip(), confidence,
                generated_by, provider or None, model or None, prompt_version or None, digest,
                int(is_pilot), pilot_batch_id, actor, ts, ts,
            ),
        )
        finding_id = int(cur.lastrowid)
        for assertion_id in assertion_ids:
            conn.execute(
                "INSERT INTO p2_3_finding_assertions(finding_id,assertion_id,relation_type,created_at) VALUES (?,?,'supports',?)",
                (finding_id, assertion_id, ts),
            )
        return dict(conn.execute("SELECT * FROM p2_3_research_findings WHERE id=?", (finding_id,)).fetchone())


def submit_finding(finding_id: int, *, actor: str, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM p2_3_research_findings WHERE id=?", (finding_id,)).fetchone()
        if not row:
            raise ValueError("finding_not_found")
        conn.execute(
            "UPDATE p2_3_research_findings SET status='pending_review',review_note=?,updated_at=? WHERE id=?",
            (f"submitted_by:{actor}", now(), finding_id),
        )
        return dict(conn.execute("SELECT * FROM p2_3_research_findings WHERE id=?", (finding_id,)).fetchone())


def review_finding(
    finding_id: int,
    *,
    decision: str,
    actor: str,
    note: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if decision not in {"approved", "needs_revision", "archived"}:
        raise ValueError("invalid_finding_review_decision")
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM p2_3_research_findings WHERE id=?", (finding_id,)).fetchone()
        if not row or row["status"] != "pending_review":
            raise ValueError("finding_not_pending_review")
        conn.execute(
            """UPDATE p2_3_research_findings SET status=?,reviewed_by=?,reviewed_at=?,
               review_note=?,updated_at=? WHERE id=?""",
            (decision, actor, now(), note or None, now(), finding_id),
        )
        return dict(conn.execute("SELECT * FROM p2_3_research_findings WHERE id=?", (finding_id,)).fetchone())


def _event_metrics(conn, organization_id: str) -> tuple[list[dict[str, Any]], int]:
    events = [dict(r) for r in conn.execute(
        """SELECT DISTINCT e.* FROM p2_3_industry_events e
           JOIN p2_3_event_subjects es ON es.event_id=e.id
           WHERE es.subject_type='organization' AND es.subject_id=?
             AND e.status IN ('approved','published')
           ORDER BY COALESCE(e.occurred_at,e.created_at) DESC""",
        (organization_id,),
    )]
    evidence = sum(int(row[0]) for row in conn.execute(
        """SELECT COUNT(*) FROM p2_3_event_evidence ee
           JOIN p2_3_event_subjects es ON es.event_id=ee.event_id
           JOIN p2_3_industry_events e ON e.id=ee.event_id
           WHERE es.subject_type='organization' AND es.subject_id=?
             AND e.status IN ('approved','published') GROUP BY ee.event_id""",
        (organization_id,),
    ))
    return events, evidence


def compare_companies_research(
    organization_ids: list[str],
    *,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ids = list(dict.fromkeys(value.strip() for value in organization_ids if value.strip()))
    if len(ids) < 2 or len(ids) > 8:
        raise ValueError("company_count_must_be_2_to_8")
    rows = []
    with db_connection(db_path) as conn:
        for organization_id in ids:
            org = conn.execute(
                "SELECT * FROM organizations WHERE external_id=? OR CAST(id AS TEXT)=? LIMIT 1",
                (organization_id, organization_id),
            ).fetchone()
            if not org:
                raise ValueError("organization_not_found")
            oid = org["external_id"]
            events, evidence_count = _event_metrics(conn, oid)
            products = sorted({
                r["subject_label"] or r["subject_id"] for r in conn.execute(
                    """SELECT es2.subject_id,es2.subject_label FROM p2_3_event_subjects es1
                       JOIN p2_3_event_subjects es2 ON es2.event_id=es1.event_id AND es2.subject_type='product'
                       JOIN p2_3_industry_events e ON e.id=es1.event_id
                       WHERE es1.subject_type='organization' AND es1.subject_id=?
                         AND e.status IN ('approved','published')""",
                    (oid,),
                )
            })
            stages = sorted({event["stage"] for event in events if event.get("stage")})
            event_types = [str(event.get("event_type") or "").lower() for event in events]
            conflicts = conn.execute(
                """SELECT COUNT(*) FROM p2_3_fact_conflicts
                   WHERE subject_type='organization' AND subject_id=? AND status<>'dismissed'""",
                (oid,),
            ).fetchone()[0]
            fields = [org["region"], org["industry_tags"], products, stages, events, evidence_count]
            completeness = round(sum(bool(value) for value in fields) / len(fields) * 100)
            rows.append({
                "organization_id": oid,
                "name": org["standard_name"],
                "region": org["region"] or MISSING,
                "technology": org["industry_tags"] or MISSING,
                "products": products or [MISSING],
                "clinical_stages": stages or [MISSING],
                "financing_events": sum("financ" in value or "融资" in value for value in event_types),
                "cooperation_events": sum("cooper" in value or "partner" in value or "合作" in value for value in event_types),
                "recent_events": events[:5],
                "risk_count": int(conflicts) + sum(bool(event.get("has_conflict")) for event in events),
                "data_completeness": completeness,
                "evidence_count": evidence_count,
                "core_team": MISSING,
            })
    return {"companies": rows, "missing_label": MISSING}


def compare_track_research(track_keyword: str, db_path: str | Path | None = None) -> dict[str, Any]:
    keyword = track_keyword.strip()
    with db_connection(db_path) as conn:
        organizations = [dict(row) for row in conn.execute(
            "SELECT external_id,standard_name,industry_tags FROM organizations WHERE industry_tags LIKE ? ORDER BY standard_name",
            (f"%{keyword}%",),
        )]
        ids = [row["external_id"] for row in organizations]
        events: list[dict[str, Any]] = []
        for oid in ids:
            rows, _ = _event_metrics(conn, oid)
            events.extend(rows)
        products = sorted({row["subject_label"] or row["subject_id"] for row in conn.execute(
            """SELECT DISTINCT es.subject_id,es.subject_label FROM p2_3_event_subjects es
               JOIN p2_3_industry_events e ON e.id=es.event_id
               WHERE es.subject_type='product' AND e.status IN ('approved','published')"""
        )})
    event_types: dict[str, int] = {}
    for event in events:
        event_types[event["event_type"]] = event_types.get(event["event_type"], 0) + 1
    return {
        "track": keyword,
        "participating_companies": organizations,
        "key_products": products or [MISSING],
        "technology_routes": sorted({row.get("industry_tags") for row in organizations if row.get("industry_tags")}) or [MISSING],
        "event_distribution": event_types,
        "financing_trend": sum("financ" in key.lower() or "融资" in key for key in event_types),
        "clinical_progress": sum("clinical" in key.lower() or "临床" in key for key in event_types),
        "policy_impact": MISSING,
        "risks_and_opportunities": MISSING if not events else "需结合已审核事件人工研判",
        "evidence_event_count": len({event["id"] for event in events}),
    }


def _finding_assertions(conn, finding_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        """SELECT a.* FROM p2_3_fact_assertions a
           JOIN p2_3_finding_assertions fa ON fa.assertion_id=a.id WHERE fa.finding_id=?""",
        (finding_id,),
    )]


def _citations_for_finding(conn, finding_id: int) -> list[dict[str, Any]]:
    return [dict(r) for r in conn.execute(
        """SELECT DISTINCT a.id assertion_id,a.event_id,ee.id event_evidence_id,
                  ee.snapshot_id,ee.source_organization,ee.source_title,ee.published_at,
                  ee.source_url,ee.evidence_excerpt,ee.page_number,ee.locator_json,ee.captured_at
           FROM p2_3_finding_assertions fa
           JOIN p2_3_fact_assertions a ON a.id=fa.assertion_id
           JOIN p2_3_assertion_evidence ae ON ae.assertion_id=a.id
           JOIN p2_3_event_evidence ee ON ee.id=ae.event_evidence_id
           WHERE fa.finding_id=?""",
        (finding_id,),
    )]


def create_research_report(
    topic_id: int,
    *,
    report_type: str = "topic_report",
    created_by: str = "analyst",
    pilot_batch_id: str | None = None,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if report_type not in REPORT_TYPES:
        raise ValueError("invalid_research_report_type")
    ts = now()
    with db_connection(db_path) as conn:
        topic = conn.execute("SELECT * FROM research_topics WHERE id=?", (topic_id,)).fetchone()
        if not topic:
            raise ValueError("topic_not_found")
        findings = [dict(r) for r in conn.execute(
            "SELECT * FROM p2_3_research_findings WHERE topic_id=? AND status='approved' ORDER BY id",
            (topic_id,),
        )]
        questions = [dict(r) for r in conn.execute(
            "SELECT * FROM p2_3_research_questions WHERE topic_id=? AND status IN ('open','investigating') ORDER BY id",
            (topic_id,),
        )]
        conflicts = [dict(r) for r in conn.execute(
            "SELECT * FROM p2_3_fact_conflicts WHERE topic_id=? AND status<>'resolved' ORDER BY id",
            (topic_id,),
        )]
        title = f"{topic['name']}研究报告草稿"
        summary = f"已审核研究发现 {len(findings)} 条，待验证问题 {len(questions)} 条，未解决冲突 {len(conflicts)} 条。"
        cur = conn.execute(
            """INSERT INTO v05h_generated_reports(
               report_no,title,report_type,summary,content_markdown,citations_json,version,status,
               created_by,created_at,updated_at,topic_id,research_status,research_report_type,
               citation_completeness,current_version_no,pilot_batch_id)
               VALUES (?,?, 'subject', ?, '', '[]',1,'draft',?,?,?,?,?,?,0,1,?)""",
            (_no("RPT"), title, summary, created_by, ts, ts, topic_id, "draft", report_type, pilot_batch_id),
        )
        report_id = int(cur.lastrowid)
        section_specs: list[tuple[str, str, str, int | None]] = [
            ("summary", "执行摘要", summary, None),
        ]
        type_map = {
            "verified_fact": ("fact", "事实"), "inference": ("inference", "推断"),
            "analyst_opinion": ("opinion", "观点"), "hypothesis": ("to_verify", "待验证"),
            "conflict": ("to_verify", "冲突"),
        }
        for finding in findings:
            section_type, label = type_map[finding["finding_type"]]
            section_specs.append((section_type, f"【{label}】{finding['title']}", finding["content"], finding["id"]))
        for question in questions:
            section_specs.append(("to_verify", "【待验证】研究问题", question["question"], None))
        for conflict in conflicts:
            section_specs.append((
                "to_verify", "【待验证】来源冲突",
                f"{conflict['field_name']}：{conflict['value_a']} / {conflict['value_b']}", None,
            ))

        markdown_rows = [f"# {title}"]
        flat_citations: list[dict[str, Any]] = []
        for order, (section_type, section_title, content, finding_id) in enumerate(section_specs, start=1):
            citations = _citations_for_finding(conn, finding_id) if finding_id else []
            needs_citation = section_type in {"fact", "inference"}
            section_cur = conn.execute(
                """INSERT INTO p2_3_report_sections(
                   report_id,section_order,section_type,title,content_markdown,finding_id,
                   citation_complete,created_at,updated_at)
                   VALUES (?,?,?,?,?,?,?, ?,?)""",
                (report_id, order, section_type, section_title, content, finding_id, int(bool(citations) or not needs_citation), ts, ts),
            )
            section_id = int(section_cur.lastrowid)
            markdown_rows.extend(["", f"## {section_title}", content])
            for index, citation in enumerate(citations, start=1):
                digest = hashlib.sha256(
                    f"{section_id}|{citation['event_evidence_id']}|{citation['evidence_excerpt']}".encode("utf-8")
                ).hexdigest()
                conn.execute(
                    """INSERT OR IGNORE INTO p2_3_report_citations(
                       report_id,section_id,finding_id,assertion_id,event_id,event_evidence_id,
                       snapshot_id,source_organization,source_title,published_at,source_url,
                       evidence_excerpt,page_number,locator_json,captured_at,citation_hash,created_at)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (
                        report_id, section_id, finding_id, citation["assertion_id"], citation["event_id"],
                        citation["event_evidence_id"], citation["snapshot_id"], citation["source_organization"],
                        citation["source_title"], citation["published_at"], citation["source_url"],
                        citation["evidence_excerpt"], citation["page_number"], citation["locator_json"],
                        citation["captured_at"], digest, ts,
                    ),
                )
                markdown_rows.append(f"[{index}] {citation['evidence_excerpt']}（{citation['source_title'] or citation['source_url']}）")
                flat_citations.append(citation)
        markdown = "\n".join(markdown_rows)
        conn.execute(
            "UPDATE v05h_generated_reports SET content_markdown=?,citations_json=? WHERE id=?",
            (markdown, _dump(flat_citations), report_id),
        )
    check_report_citations(report_id, db_path=db_path)
    save_report_version(report_id, change_note="initial research draft", actor=created_by, db_path=db_path)
    return get_research_report(report_id, db_path=db_path) or {}


def check_report_citations(report_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT * FROM p2_3_report_sections WHERE report_id=? ORDER BY section_order", (report_id,)
        )]
        required = [row for row in rows if row["section_type"] in {"fact", "inference"}]
        complete = [row for row in required if row["citation_complete"]]
        rate = 1.0 if not required else len(complete) / len(required)
        conn.execute(
            "UPDATE v05h_generated_reports SET citation_completeness=?,updated_at=? WHERE id=?",
            (rate, now(), report_id),
        )
    return {"required_sections": len(required), "complete_sections": len(complete), "rate": rate, "complete": rate == 1.0}


def save_report_version(
    report_id: int,
    *,
    change_note: str,
    actor: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        report = conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone()
        if not report:
            raise ValueError("report_not_found")
        next_version = int(conn.execute(
            "SELECT COALESCE(MAX(version_no),0)+1 FROM p2_3_report_versions WHERE report_id=?", (report_id,)
        ).fetchone()[0])
        sections = [dict(r) for r in conn.execute(
            "SELECT * FROM p2_3_report_sections WHERE report_id=? ORDER BY section_order", (report_id,)
        )]
        citations = [dict(r) for r in conn.execute(
            "SELECT * FROM p2_3_report_citations WHERE report_id=? ORDER BY section_id,id", (report_id,)
        )]
        cur = conn.execute(
            """INSERT INTO p2_3_report_versions(
               report_id,version_no,title,summary,content_markdown,sections_json,citations_json,
               change_note,created_by,created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                report_id, next_version, report["title"], report["summary"], report["content_markdown"],
                _dump(sections), _dump(citations), change_note, actor, now(),
            ),
        )
        conn.execute(
            "UPDATE v05h_generated_reports SET current_version_no=?,version=?,updated_at=? WHERE id=?",
            (next_version, next_version, now(), report_id),
        )
        return dict(conn.execute("SELECT * FROM p2_3_report_versions WHERE id=?", (cur.lastrowid,)).fetchone())


def submit_research_report(report_id: int, *, actor: str, db_path: str | Path | None = None) -> dict[str, Any]:
    check = check_report_citations(report_id, db_path=db_path)
    if not check["complete"]:
        raise ValueError("report_citations_incomplete")
    with db_connection(db_path) as conn:
        report = conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone()
        if not report or report["research_status"] not in {"draft", "needs_revision"}:
            raise ValueError("report_not_submittable")
        conn.execute(
            """UPDATE v05h_generated_reports SET research_status='pending_review',status='under_review',
               revision_note=?,updated_at=? WHERE id=?""",
            (f"submitted_by:{actor}", now(), report_id),
        )
    return get_research_report(report_id, db_path=db_path) or {}


def review_research_report(
    report_id: int,
    *,
    decision: str,
    actor: str,
    note: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if decision not in {"approved", "needs_revision"}:
        raise ValueError("invalid_report_review_decision")
    with db_connection(db_path) as conn:
        report = conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone()
        if not report or report["research_status"] != "pending_review":
            raise ValueError("report_not_pending_review")
        legacy_status = "approved" if decision == "approved" else "draft"
        conn.execute(
            """UPDATE v05h_generated_reports SET research_status=?,status=?,reviewed_by=?,
               reviewed_at=?,revision_note=?,updated_at=? WHERE id=?""",
            (decision, legacy_status, actor, now(), note or None, now(), report_id),
        )
    return get_research_report(report_id, db_path=db_path) or {}


def publish_research_report(report_id: int, *, actor: str, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        report = conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone()
        if not report or report["research_status"] != "approved":
            raise ValueError("only_approved_report_can_publish")
        conn.execute(
            """UPDATE v05h_generated_reports SET research_status='published',status='published',
               published_by=?,published_at=?,updated_at=? WHERE id=?""",
            (actor, now(), now(), report_id),
        )
    return get_research_report(report_id, db_path=db_path) or {}


def get_research_report(report_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with db_connection(db_path) as conn:
        report = conn.execute("SELECT * FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone()
        if not report:
            return None
        item = dict(report)
        item["sections"] = [dict(r) for r in conn.execute(
            "SELECT * FROM p2_3_report_sections WHERE report_id=? ORDER BY section_order", (report_id,)
        )]
        item["citations"] = [dict(r) for r in conn.execute(
            "SELECT * FROM p2_3_report_citations WHERE report_id=? ORDER BY section_id,id", (report_id,)
        )]
        item["versions"] = [dict(r) for r in conn.execute(
            "SELECT * FROM p2_3_report_versions WHERE report_id=? ORDER BY version_no DESC", (report_id,)
        )]
        return item


def delete_research_report(report_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        report = conn.execute("SELECT id,research_status FROM v05h_generated_reports WHERE id=?", (report_id,)).fetchone()
        if not report:
            return {"deleted": False}
        if report["research_status"] in {"published", "archived"}:
            raise ValueError("published_report_cannot_be_deleted")
        evidence_before = conn.execute("SELECT COUNT(*) FROM p2_3_event_evidence").fetchone()[0]
        conn.execute("DELETE FROM v05h_generated_reports WHERE id=?", (report_id,))
        evidence_after = conn.execute("SELECT COUNT(*) FROM p2_3_event_evidence").fetchone()[0]
        if evidence_before != evidence_after:
            raise RuntimeError("report_delete_must_not_delete_evidence")
    return {"deleted": True, "evidence_preserved": True}


class ResearchAgentService:
    prompt_version = "research_synthesis_v1@1.0.0"

    def __init__(self, db_path: str | Path | None = None, registry: ProviderRegistry | None = None):
        self.db_path = db_path
        self.registry = registry or ProviderRegistry()

    def generate_draft(self, topic_id: int, *, provider_name: str = "rule", actor: str = "agent") -> dict[str, Any]:
        provider = self.registry.get(provider_name, fallback=True)
        with db_connection(self.db_path) as conn:
            facts = [dict(r) for r in conn.execute(
                """SELECT DISTINCT a.* FROM p2_3_fact_assertions a
                   LEFT JOIN p2_3_topic_events te ON te.event_id=a.event_id
                   WHERE (a.topic_id=? OR te.topic_id=?) AND a.review_status='approved'
                   ORDER BY a.id LIMIT 50""",
                (topic_id, topic_id),
            )]
            run_no = _no("RAG")
            cur = conn.execute(
                """INSERT INTO p2_3_research_agent_runs(
                   run_no,topic_id,provider,model,prompt_version,input_fact_ids_json,status,
                   review_status,created_at)
                   VALUES (?,?,?,?,?,?,'running','draft',?)""",
                (
                    run_no, topic_id, provider.name, provider.model, self.prompt_version,
                    _dump([row["id"] for row in facts]), now(),
                ),
            )
            run_id = int(cur.lastrowid)
        if not facts:
            with db_connection(self.db_path) as conn:
                conn.execute(
                    "UPDATE p2_3_research_agent_runs SET status='failed',error_type='approved_facts_required',finished_at=? WHERE id=?",
                    (now(), run_id),
                )
            return {"run_id": run_id, "status": "failed", "error_type": "approved_facts_required"}
        fact_text = "\n".join(
            f"FACT-{row['id']}: {row['subject_label'] or row['subject_id']} {row['predicate']} {row['object_value'] or row['numeric_value'] or ''}"
            for row in facts
        )
        try:
            result = provider.analyze(
                fact_text,
                title="Research draft based only on approved fact assertions",
                source_url="internal://p2-3-approved-facts",
            )
            content = result.summary or fact_text[:1000]
            finding = create_finding(
                topic_id, finding_type="inference", title="研究Agent草稿",
                content=content, assertion_ids=[row["id"] for row in facts], actor=actor,
                generated_by=result.generated_by, provider=result.provider, model=result.model,
                prompt_version=self.prompt_version, db_path=self.db_path,
            )
            digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
            with db_connection(self.db_path) as conn:
                conn.execute(
                    """UPDATE p2_3_research_agent_runs SET status='success',output_hash=?,
                       finished_at=? WHERE id=?""",
                    (digest, now(), run_id),
                )
            return {
                "run_id": run_id, "status": "success", "finding_id": finding["id"],
                "provider": result.provider, "model": result.model,
                "prompt_version": self.prompt_version, "review_status": "draft",
            }
        except Exception as exc:
            with db_connection(self.db_path) as conn:
                conn.execute(
                    "UPDATE p2_3_research_agent_runs SET status='failed',error_type=?,finished_at=? WHERE id=?",
                    (exc.__class__.__name__, now(), run_id),
                )
            return {"run_id": run_id, "status": "failed", "error_type": exc.__class__.__name__}
