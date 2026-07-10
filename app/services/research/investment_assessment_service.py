from __future__ import annotations

from pathlib import Path
from typing import Any

from app.i18n import translate_status
from app.services.api_common import Pagination, normalize_page, paginated
from app.v04f_operations import get_or_create_lead

from .common import db_connection, dumps, ensure_schema, loads, next_no, now, org_by_id


def list_assessments(*, page: int = 1, page_size: int = 20, status: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    page, page_size = normalize_page(page, page_size)
    where = "status=?" if status else "1=1"
    params = [status] if status else []
    with db_connection(db_path) as conn:
        total = conn.execute(f"SELECT COUNT(*) FROM investment_assessments WHERE {where}", params).fetchone()[0]
        rows = [_assessment_dict(r) for r in conn.execute(f"SELECT * FROM investment_assessments WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()]
    return paginated(rows, Pagination(page, page_size, int(total)))


def get_assessment(assessment_id: int, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM investment_assessments WHERE id=?", (assessment_id,)).fetchone()
        return _assessment_dict(row) if row else None


def generate_assessment(organization_id: str, *, topic_id: int | None = None, assessment_type: str = "single_company", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        org = org_by_id(conn, organization_id)
        if not org:
            raise ValueError("organization_not_found")
        data = _score_org(conn, dict(org))
        ts = now()
        cur = conn.execute(
            """
            INSERT INTO investment_assessments(
                assessment_no, organization_id, topic_id, assessment_type, regional_type, track, stage,
                score_total, score_breakdown_json, grade, qbay_fit, qiantang_rental_fit, qiantang_land_fit,
                constraints_json, opportunities_json, relationship_clues_json, recommended_actions_json,
                source_refs_json, data_gaps_json, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'generated', ?, ?)
            """,
            (
                next_no(conn, "IAS"),
                org["external_id"],
                topic_id,
                assessment_type,
                data["regional_type"],
                data["track"],
                data["stage"],
                data["score_total"],
                dumps(data["score_breakdown"]),
                data["grade"],
                data["qbay_fit"],
                data["qiantang_rental_fit"],
                data["qiantang_land_fit"],
                dumps(data["constraints"]),
                dumps(data["opportunities"]),
                dumps(data["relationship_clues"]),
                dumps(data["recommended_actions"]),
                dumps(data["source_refs"]),
                dumps(data["data_gaps"]),
                ts,
                ts,
            ),
        )
        return _assessment_dict(conn.execute("SELECT * FROM investment_assessments WHERE id=?", (cur.lastrowid,)).fetchone())


def approve_assessment(assessment_id: int, *, actor: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM investment_assessments WHERE id=?", (assessment_id,)).fetchone()
        if not row:
            raise ValueError("assessment_not_found")
        conn.execute("UPDATE investment_assessments SET status='approved', reviewed_by=?, reviewed_at=?, updated_at=? WHERE id=?", (actor or "manual", now(), now(), assessment_id))
        return _assessment_dict(conn.execute("SELECT * FROM investment_assessments WHERE id=?", (assessment_id,)).fetchone())


def reject_assessment(assessment_id: int, *, actor: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        conn.execute("UPDATE investment_assessments SET status='rejected', reviewed_by=?, reviewed_at=?, updated_at=? WHERE id=?", (actor or "manual", now(), now(), assessment_id))
        row = conn.execute("SELECT * FROM investment_assessments WHERE id=?", (assessment_id,)).fetchone()
        if not row:
            raise ValueError("assessment_not_found")
        return _assessment_dict(row)


def convert_assessment_to_lead(assessment_id: int, *, actor: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM investment_assessments WHERE id=?", (assessment_id,)).fetchone()
        if not row:
            raise ValueError("assessment_not_found")
        if row["status"] != "approved":
            raise RuntimeError("assessment_not_approved")
        lead = get_or_create_lead("organization", row["organization_id"], owner=actor, db_path=db_path)
        conn.execute("UPDATE investment_assessments SET lead_id=?, updated_at=? WHERE id=?", (lead["id"], now(), assessment_id))
        return {"lead": lead, "assessment": _assessment_dict(conn.execute("SELECT * FROM investment_assessments WHERE id=?", (assessment_id,)).fetchone())}


def _assessment_dict(row) -> dict[str, Any]:
    data = dict(row)
    data["status_label"] = translate_status(data.get("status"), "assessment")
    for key in ["score_breakdown_json", "constraints_json", "opportunities_json", "relationship_clues_json", "recommended_actions_json", "source_refs_json", "data_gaps_json"]:
        data[key.replace("_json", "")] = loads(data.get(key), [] if key != "score_breakdown_json" else {})
    return data


def _score_org(conn, org: dict[str, Any]) -> dict[str, Any]:
    tags = org.get("industry_tags") or ""
    region = org.get("region") or ""
    stage = org.get("org_type") or ""
    gaps = []
    if not tags:
        gaps.append("缺少所属赛道")
    if not region:
        gaps.append("缺少注册地区或经营地区")
    if not stage:
        gaps.append("缺少发展阶段")
    regional_type = "钱塘/Q-BAY本地资源型" if any(k in region for k in ["钱塘", "Q-BAY", "上海"]) else "异地潜在招商型"
    if regional_type == "钱塘/Q-BAY本地资源型":
        grade = "R"
    elif len(gaps) >= 2:
        grade = "UNVERIFIED"
    else:
        grade = "B" if any(k in tags for k in ["创新药", "细胞", "基因", "ADC", "医疗器械"]) else "C"
    breakdown = {
        "赛道匹配": 18 if tags else 0,
        "发展信号": 10 if stage else 4,
        "空间/载体匹配": 12 if region else 6,
        "窗口期": 8,
        "关系可达性": _relation_score(conn, org["external_id"]),
        "信息完整度": max(0, 20 - len(gaps) * 7),
        "招引阻力": 0,
    }
    score = sum(v for v in breakdown.values() if isinstance(v, int))
    return {
        "regional_type": regional_type,
        "track": tags or "待核实",
        "stage": stage or "待核实",
        "score_total": None if grade in {"R", "UNVERIFIED"} else score,
        "score_breakdown": breakdown,
        "grade": grade,
        "qbay_fit": "适合进一步核实" if tags else "数据不足",
        "qiantang_rental_fit": "可评估租赁载体" if grade not in {"UNVERIFIED"} else "数据不足",
        "qiantang_land_fit": "需确认产业化和产能需求",
        "constraints": ["信息不足需补充"] if gaps else [],
        "opportunities": ["存在招商跟进窗口"] if grade in {"A", "B", "C"} else [],
        "relationship_clues": ["需核实投资方、园区或Q-BAY关系入口"],
        "recommended_actions": ["补充公开来源", "人工核实空间需求", "审核后再转招商线索"],
        "source_refs": [{"type": "organization", "id": org["external_id"], "title": org["standard_name"]}],
        "data_gaps": gaps,
    }


def _relation_score(conn, external_id: str) -> int:
    count = conn.execute("SELECT COUNT(*) FROM relations WHERE COALESCE(is_active,1)=1 AND (source_external_id=? OR target_external_id=?)", (external_id, external_id)).fetchone()[0]
    return min(10, int(count) * 2)
