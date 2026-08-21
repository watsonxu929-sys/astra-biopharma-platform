from __future__ import annotations

import hashlib
import json
import re
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Iterable

from app.services.club_matching_service import match_need_offering
from app.services.relationship_path_service import (
    find_qbay_paths,
    path_to_template_parts,
    resolve_subject,
    table_exists,
)
from app.v04c_review import db_connection, default_db_path
from scripts.migrate_v04h import SCHEMA_SQL

CATEGORY_LABELS = {
    "lead": "线索推进",
    "club_match": "会员供需",
    "resource": "资源匹配",
    "data_quality": "数据治理",
    "relationship": "关系切入",
}
STATUS_LABELS = {
    "new": "待处理",
    "accepted": "已采纳",
    "rejected": "已拒绝",
    "snoozed": "已暂缓",
    "converted": "已转行动",
    "expired": "已失效",
}
GRADE_ORDER = {"C": 1, "B": 2, "A": 3, "S": 4}
BIOMED_KEYWORDS = {
    "创新药", "生物药", "小分子", "大分子", "抗体", "细胞治疗", "基因治疗", "核酸药物",
    "疫苗", "医疗器械", "诊断", "临床", "注册", "申报", "研发", "生产", "工艺", "质谱",
    "CRO", "CDMO", "CMO", "CXO", "融资", "投资", "基金", "园区", "实验室", "厂房", "招商",
    "商务", "BD", "市场", "出海", "医院", "高校", "专家", "供应链", "原料", "设备", "数字化",
    "知识产权", "合规", "法务", "财务", "人才", "招聘", "项目路演", "产业化", "转化医学",
}


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    if not allow_migration:
        return path
    with db_connection(path) as conn:
        conn.executescript(SCHEMA_SQL)
    return path


def json_dump(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def json_load(value: Any, default: Any) -> Any:
    if not value:
        return default
    try:
        return json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return default


def grade_for_score(score: int) -> str:
    if score >= 85:
        return "S"
    if score >= 70:
        return "A"
    if score >= 50:
        return "B"
    return "C"


def _next_no(conn: sqlite3.Connection, prefix: str = "REC") -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04h_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date,
          updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, stamp, now()),
    ).fetchone()
    return f"{prefix}-{stamp}-{int(row['seq_value']):04d}"


def _tokenize(*values: Any) -> set[str]:
    output: set[str] = set()
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        upper_text = text.upper()
        for keyword in BIOMED_KEYWORDS:
            if keyword.upper() in upper_text:
                output.add(keyword.casefold())
        for item in re.split(r"[\s,，;；、|/\\()（）\[\]【】]+", text):
            token = item.strip(" .。:：-_").casefold()
            if 2 <= len(token) <= 24:
                output.add(token)
    return output


def _subject_business_data(conn: sqlite3.Connection, subject_type: str, subject_id: str) -> dict[str, Any] | None:
    subject = resolve_subject(conn, subject_type, subject_id)
    if not subject:
        return None
    if subject_type == "organization":
        row = conn.execute("SELECT * FROM organizations WHERE external_id=?", (subject["external_id"],)).fetchone()
        return {
            **subject,
            "tags": row["industry_tags"] or "",
            "needs": row["needs"] or "",
            "resources": row["resources"] or "",
            "region": row["region"] or "",
            "stage": row["org_type"] or "",
            "status": row["verification_status"] or "",
            "detail_url": f"/organizations/{row['id']}",
        }
    if subject_type == "project":
        row = conn.execute("SELECT * FROM projects WHERE external_id=?", (subject["external_id"],)).fetchone()
        return {
            **subject,
            "tags": row["focus_tags"] or "",
            "needs": row["typical_needs"] or "",
            "resources": "",
            "region": "",
            "stage": row["status"] or row["project_type"] or "",
            "status": row["status"] or "",
            "detail_url": f"/projects/{row['id']}",
        }
    if subject_type == "person":
        row = conn.execute("SELECT * FROM people WHERE external_id=?", (subject["external_id"],)).fetchone()
        return {
            **subject,
            "tags": row["ability_tags"] or "",
            "needs": "",
            "resources": row["value_provided"] or "",
            "region": "",
            "stage": row["public_role"] or "",
            "status": row["verification_status"] or "",
            "detail_url": f"/people/{row['id']}",
        }
    return None


def _review_stats(conn: sqlite3.Connection, subject_id: str) -> dict[str, int]:
    if not table_exists(conn, "v04c_review_items"):
        return {"open_count": 0, "conflict_count": 0}
    row = conn.execute(
        """
        SELECT COUNT(*) AS open_count,
               SUM(CASE WHEN item_type='conflict' THEN 1 ELSE 0 END) AS conflict_count
        FROM v04c_review_items
        WHERE subject_id=? AND status IN ('pending','in_review','deferred')
        """,
        (subject_id,),
    ).fetchone()
    return {
        "open_count": int(row["open_count"] or 0),
        "conflict_count": int(row["conflict_count"] or 0),
    }


def _active_offerings(conn: sqlite3.Connection, limit: int = 300) -> list[dict[str, Any]]:
    if not all(table_exists(conn, table) for table in ("v04f_club_offerings", "v04f_club_memberships")):
        return []
    rows = conn.execute(
        """
        SELECT
          o.*,
          m.member_no,
          p.external_id AS person_external_id,
          p.name AS person_name,
          org.external_id AS organization_external_id,
          org.standard_name AS organization_name
        FROM v04f_club_offerings o
        JOIN v04f_club_memberships m ON m.id=o.membership_id
        JOIN people p ON p.id=m.person_id
        LEFT JOIN organizations org ON org.id=m.organization_id
        WHERE o.status='active' AND m.status='active'
        ORDER BY o.updated_at DESC, o.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def _active_needs(conn: sqlite3.Connection, limit: int = 300) -> list[dict[str, Any]]:
    if not all(table_exists(conn, table) for table in ("v04f_club_needs", "v04f_club_memberships")):
        return []
    rows = conn.execute(
        """
        SELECT
          n.*,
          m.member_no,
          p.external_id AS person_external_id,
          p.name AS person_name,
          org.external_id AS organization_external_id,
          org.standard_name AS organization_name
        FROM v04f_club_needs n
        JOIN v04f_club_memberships m ON m.id=n.membership_id
        JOIN people p ON p.id=m.person_id
        LEFT JOIN organizations org ON org.id=m.organization_id
        WHERE n.status='active' AND m.status='active'
          AND (n.valid_until IS NULL OR n.valid_until='' OR n.valid_until>=?)
        ORDER BY n.updated_at DESC, n.id DESC
        LIMIT ?
        """,
        (date.today().isoformat(), limit),
    ).fetchall()
    return [dict(row) for row in rows]


def _path_endpoint_ids(paths: Iterable[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for path in paths:
        member = path.get("member") or {}
        for key in ("person_external_id", "organization_external_id"):
            if member.get(key):
                result.add(str(member[key]))
    return result


def _resource_fit(
    subject: dict[str, Any], offering: dict[str, Any], reachable_ids: set[str]
) -> dict[str, Any] | None:
    target_tokens = _tokenize(subject.get("tags"), subject.get("needs"), subject.get("stage"))
    offering_tokens = _tokenize(
        offering.get("title"), offering.get("description"), offering.get("offering_type"), offering.get("industry_tags")
    )
    overlap = sorted(target_tokens & offering_tokens)
    if not overlap:
        return None
    score = min(55, 20 + len(overlap) * 7)
    reasons = ["命中需求/赛道标签：" + "、".join(overlap[:8])]
    risks: list[str] = []
    if subject.get("region") and offering.get("region"):
        if str(subject["region"]).casefold() == str(offering["region"]).casefold():
            score += 10
            reasons.append("地区一致。")
        else:
            risks.append("双方地区不同，需确认跨区域合作可行性。")
    member_ids = {offering.get("person_external_id"), offering.get("organization_external_id")}
    if any(value and value in reachable_ids for value in member_ids):
        score += 20
        reasons.append("供给方已处于目标主体的真实关系切入路径中。")
    elif offering.get("person_external_id"):
        score += 5
        reasons.append("供给方为已登记 Q-BAY 会员，可人工发起联系。")
    if offering.get("description"):
        score += 5
    score = max(0, min(100, score))
    if score < 35:
        return None
    return {
        "score": score,
        "grade": grade_for_score(score),
        "overlap": overlap,
        "reasons": reasons,
        "risks": risks,
    }


def _candidate_path_for_pair(
    left: dict[str, Any], right: dict[str, Any], relation_label: str
) -> list[dict[str, Any]]:
    left_node = {
        "type": "person",
        "type_label": "会员",
        "external_id": left.get("person_external_id") or left.get("member_no"),
        "name": left.get("person_name") or left.get("member_no"),
        "profile_url": f"/subjects/person/{left.get('person_external_id')}" if left.get("person_external_id") else "",
    }
    right_node = {
        "type": "person",
        "type_label": "会员",
        "external_id": right.get("person_external_id") or right.get("member_no"),
        "name": right.get("person_name") or right.get("member_no"),
        "profile_url": f"/subjects/person/{right.get('person_external_id')}" if right.get("person_external_id") else "",
    }
    return [{
        "nodes": [left_node, right_node],
        "edges": [{"relation_type": relation_label, "direction": "out", "direction_label": "候选", "relation_no": ""}],
        "member": {
            "member_no": right.get("member_no"),
            "person_name": right.get("person_name"),
            "person_external_id": right.get("person_external_id"),
            "organization_external_id": right.get("organization_external_id"),
            "organization_name": right.get("organization_name"),
        },
        "edge_count": 1,
        "summary": f"{left_node['name']} 与 {right_node['name']} 存在{relation_label}候选，尚未形成正式关系。",
        "candidate_only": True,
    }]


def _lead_candidates(conn: sqlite3.Connection, limit: int) -> list[dict[str, Any]]:
    if not table_exists(conn, "v04f_lead_records"):
        return []
    leads = conn.execute(
        """
        SELECT * FROM v04f_lead_records
        WHERE status='active'
        ORDER BY system_score DESC, updated_at DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    offerings = _active_offerings(conn)
    candidates: list[dict[str, Any]] = []
    for lead in leads:
        subject = _subject_business_data(conn, lead["subject_type"], lead["subject_id"])
        if not subject:
            continue
        scoring = json_load(lead["scoring_json"], {})
        reasons = list(scoring.get("positive_reasons") or [])
        risks = list(scoring.get("negative_reasons") or [])
        missing = list(scoring.get("missing_data") or [])
        path_result = find_qbay_paths(conn, lead["subject_type"], lead["subject_id"], max_edges=3, max_paths=8)
        paths = path_result["paths"]
        score = int(lead["system_score"] or 0)
        if paths:
            boost = min(10, 4 + len(paths) * 2)
            score += boost
            reasons.append(f"存在 {len(paths)} 条基于真实关系的 Q-BAY 会员切入路径。")
        else:
            risks.append("暂未找到基于已确认关系的 Q-BAY 会员切入路径。")
        reachable_ids = _path_endpoint_ids(paths)
        fits = []
        for offering in offerings:
            fit = _resource_fit(subject, offering, reachable_ids)
            if fit:
                fits.append((fit["score"], offering, fit))
        fits.sort(key=lambda item: item[0], reverse=True)
        if fits:
            score += min(10, fits[0][0] // 10)
            reasons.append(f"发现 {len(fits)} 项会员资源候选，最高匹配 {fits[0][0]} 分。")
        score = max(0, min(100, score))
        metadata = {
            "lead_id": lead["id"],
            "lead_no": lead["lead_no"],
            "funnel_stage": lead["funnel_stage"],
            "owner": lead["owner"],
            "subject_name": subject["name"],
            "subject_profile_url": subject["profile_url"],
            "subject_detail_url": subject["detail_url"],
            "lead_url": f"/leads/{lead['id']}",
            "resource_candidate_count": len(fits),
        }
        candidates.append({
            "key": f"lead:{lead['id']}",
            "category": "lead",
            "subject_type": lead["subject_type"],
            "subject_id": subject["external_id"],
            "secondary_subject_type": None,
            "secondary_subject_id": None,
            "title": f"优先推进：{subject['name']}",
            "summary": f"当前漏斗阶段为“{lead['funnel_stage']}”，综合建议等级 {grade_for_score(score)}。",
            "score": score,
            "grade": grade_for_score(score),
            "reasons": reasons or ["该主体已进入有效线索池。"],
            "risks": risks,
            "missing": missing,
            "paths": paths,
            "metadata": metadata,
            "source_type": "v04f_lead",
            "source_id": str(lead["id"]),
        })

        review = _review_stats(conn, subject["external_id"])
        if review["open_count"]:
            urgency = min(100, max(55, int(lead["system_score"] or 0) + review["open_count"] * 5))
            candidates.append({
                "key": f"data_quality:lead:{lead['id']}",
                "category": "data_quality",
                "subject_type": lead["subject_type"],
                "subject_id": subject["external_id"],
                "secondary_subject_type": None,
                "secondary_subject_id": None,
                "title": f"先处理数据风险：{subject['name']}",
                "summary": f"该线索有 {review['open_count']} 条待审核记录，其中冲突 {review['conflict_count']} 条。",
                "score": urgency,
                "grade": grade_for_score(urgency),
                "reasons": ["主体已进入线索经营，但待审核信息可能影响业务判断。"],
                "risks": [f"待审核 {review['open_count']} 条；冲突 {review['conflict_count']} 条。"],
                "missing": [],
                "paths": [],
                "metadata": {
                    **metadata,
                    "review_url": f"/review?q={subject['external_id']}",
                    "open_review_count": review["open_count"],
                    "conflict_count": review["conflict_count"],
                },
                "source_type": "v04c_review",
                "source_id": subject["external_id"],
            })

        for fit_score, offering, fit in fits[:3]:
            target_paths = [
                path for path in paths
                if (path.get("member") or {}).get("person_external_id") == offering.get("person_external_id")
                or (path.get("member") or {}).get("organization_external_id") == offering.get("organization_external_id")
            ]
            if not target_paths:
                target_paths = _candidate_path_for_pair(
                    {
                        "person_external_id": subject["external_id"],
                        "person_name": subject["name"],
                        "member_no": subject["external_id"],
                    },
                    offering,
                    "资源匹配",
                )
            candidates.append({
                "key": f"resource:{lead['id']}:{offering['id']}",
                "category": "resource",
                "subject_type": lead["subject_type"],
                "subject_id": subject["external_id"],
                "secondary_subject_type": "person",
                "secondary_subject_id": offering.get("person_external_id"),
                "title": f"资源匹配：{subject['name']} ↔ {offering['title']}",
                "summary": f"Q-BAY 会员 {offering.get('person_name') or offering.get('member_no')} 可提供“{offering['title']}”。",
                "score": fit_score,
                "grade": fit["grade"],
                "reasons": fit["reasons"],
                "risks": fit["risks"],
                "missing": [],
                "paths": target_paths[:3],
                "metadata": {
                    **metadata,
                    "offering_id": offering["id"],
                    "offering_no": offering["offering_no"],
                    "offering_title": offering["title"],
                    "offering_member_no": offering.get("member_no"),
                    "offering_person_name": offering.get("person_name"),
                    "offering_person_url": f"/subjects/person/{offering.get('person_external_id')}" if offering.get("person_external_id") else "",
                    "club_member_url": f"/club/members/{offering['membership_id']}",
                },
                "source_type": "v04f_club_offering",
                "source_id": str(offering["id"]),
            })
    return candidates


def _club_match_candidates(conn: sqlite3.Connection, pair_limit: int = 2500) -> list[dict[str, Any]]:
    needs = _active_needs(conn, limit=100)
    offerings = _active_offerings(conn, limit=100)
    candidates: list[dict[str, Any]] = []
    tested = 0
    for need in needs:
        ranked = []
        for offering in offerings:
            if tested >= pair_limit:
                break
            tested += 1
            result = match_need_offering(need, offering)
            if result:
                ranked.append((result["score"], offering, result))
        ranked.sort(key=lambda item: item[0], reverse=True)
        for score, offering, result in ranked[:5]:
            paths = _candidate_path_for_pair(need, offering, "供需匹配")
            candidates.append({
                "key": f"club_match:{need['id']}:{offering['id']}",
                "category": "club_match",
                "subject_type": "person",
                "subject_id": need.get("person_external_id"),
                "secondary_subject_type": "person",
                "secondary_subject_id": offering.get("person_external_id"),
                "title": f"会员供需：{need['title']} ↔ {offering['title']}",
                "summary": f"需求方 {need.get('person_name')} 与供给方 {offering.get('person_name')} 的候选匹配。",
                "score": score,
                "grade": result["grade"],
                "reasons": result["reasons"],
                "risks": ["该结果仅为候选匹配，确认前不会建立双方关系。"],
                "missing": result["missing"],
                "paths": paths,
                "metadata": {
                    "need_id": need["id"],
                    "need_no": need["need_no"],
                    "need_title": need["title"],
                    "need_member_no": need.get("member_no"),
                    "need_member_url": f"/club/members/{need['membership_id']}",
                    "offering_id": offering["id"],
                    "offering_no": offering["offering_no"],
                    "offering_title": offering["title"],
                    "offering_member_no": offering.get("member_no"),
                    "offering_member_url": f"/club/members/{offering['membership_id']}",
                    "matches_url": "/club/matches",
                },
                "source_type": "v04f_club_pair",
                "source_id": f"{need['id']}:{offering['id']}",
            })
        if tested >= pair_limit:
            break
    return candidates


def _relationship_candidates(conn: sqlite3.Connection, lead_limit: int = 200) -> list[dict[str, Any]]:
    if not table_exists(conn, "v04f_lead_records"):
        return []
    leads = conn.execute(
        "SELECT * FROM v04f_lead_records WHERE status='active' ORDER BY system_score DESC LIMIT ?",
        (lead_limit,),
    ).fetchall()
    candidates: list[dict[str, Any]] = []
    for lead in leads:
        subject = _subject_business_data(conn, lead["subject_type"], lead["subject_id"])
        if not subject:
            continue
        path_result = find_qbay_paths(conn, lead["subject_type"], lead["subject_id"], max_edges=3, max_paths=10)
        paths = path_result["paths"]
        if not paths:
            continue
        best_edges = min(path["edge_count"] for path in paths)
        score = min(100, 55 + max(0, 3 - best_edges) * 10 + min(15, len(paths) * 3))
        candidates.append({
            "key": f"relationship:{lead['subject_type']}:{subject['external_id']}",
            "category": "relationship",
            "subject_type": lead["subject_type"],
            "subject_id": subject["external_id"],
            "secondary_subject_type": "person",
            "secondary_subject_id": (paths[0].get("member") or {}).get("person_external_id"),
            "title": f"关系切入：{subject['name']}",
            "summary": f"已找到 {len(paths)} 条真实关系路径，最短 {best_edges} 层。",
            "score": score,
            "grade": grade_for_score(score),
            "reasons": [
                f"最短路径为 {best_edges} 层，未通过名称猜测关系。",
                f"可触达 {len({(p.get('member') or {}).get('member_no') for p in paths})} 位 Q-BAY 会员。",
            ],
            "risks": ["关系路径仅代表已登记关系，实际联系前仍需人工确认关系有效性。"],
            "missing": [],
            "paths": paths,
            "metadata": {
                "lead_id": lead["id"],
                "lead_url": f"/leads/{lead['id']}",
                "subject_name": subject["name"],
                "subject_profile_url": subject["profile_url"],
                "path_explorer_url": f"/recommendations/path?subject_type={lead['subject_type']}&subject_id={subject['external_id']}",
            },
            "source_type": "relations",
            "source_id": subject["external_id"],
        })
    return candidates


def _upsert_candidate(conn: sqlite3.Connection, candidate: dict[str, Any]) -> tuple[int, bool]:
    row = conn.execute(
        "SELECT * FROM v04h_recommendations WHERE recommendation_key=?",
        (candidate["key"],),
    ).fetchone()
    ts = now()
    payload = (
        candidate["category"],
        candidate.get("subject_type"),
        candidate.get("subject_id"),
        candidate.get("secondary_subject_type"),
        candidate.get("secondary_subject_id"),
        candidate["title"],
        candidate.get("summary"),
        int(candidate.get("score") or 0),
        candidate.get("grade") or grade_for_score(int(candidate.get("score") or 0)),
        json_dump(candidate.get("reasons") or []),
        json_dump(candidate.get("risks") or []),
        json_dump(candidate.get("missing") or []),
        json_dump(candidate.get("paths") or []),
        json_dump(candidate.get("metadata") or {}),
        candidate.get("source_type"),
        candidate.get("source_id"),
        ts,
        ts,
    )
    if row:
        conn.execute(
            """
            UPDATE v04h_recommendations SET
              category=?, subject_type=?, subject_id=?, secondary_subject_type=?, secondary_subject_id=?,
              title=?, summary=?, score=?, grade=?, reasons_json=?, risks_json=?, missing_json=?,
              path_json=?, metadata_json=?, source_type=?, source_id=?, generated_at=?, updated_at=?
            WHERE id=?
            """,
            (*payload, row["id"]),
        )
        return int(row["id"]), False
    recommendation_no = _next_no(conn)
    cur = conn.execute(
        """
        INSERT INTO v04h_recommendations(
          recommendation_no, recommendation_key, category, subject_type, subject_id,
          secondary_subject_type, secondary_subject_id, title, summary, score, grade,
          reasons_json, risks_json, missing_json, path_json, metadata_json, source_type,
          source_id, status, generated_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', ?, ?)
        """,
        (recommendation_no, candidate["key"], *payload[:-2], ts, ts),
    )
    return int(cur.lastrowid), True


def refresh_recommendations(
    db_path: str | Path | None = None,
    *,
    lead_limit: int = 200,
    pair_limit: int = 2500,
) -> dict[str, Any]:
    ensure_schema(db_path)
    generated_at = now()
    with db_connection(db_path) as conn:
        candidates = [
            *_lead_candidates(conn, lead_limit),
            *_club_match_candidates(conn, pair_limit),
            *_relationship_candidates(conn, lead_limit),
        ]
        keys: set[str] = set()
        created = updated = 0
        by_category: dict[str, int] = {}
        for candidate in candidates:
            if candidate["key"] in keys:
                continue
            keys.add(candidate["key"])
            _, is_new = _upsert_candidate(conn, candidate)
            created += int(is_new)
            updated += int(not is_new)
            by_category[candidate["category"]] = by_category.get(candidate["category"], 0) + 1

        if keys:
            placeholders = ",".join("?" for _ in keys)
            conn.execute(
                f"""
                UPDATE v04h_recommendations
                SET status='expired', updated_at=?
                WHERE status IN ('new','snoozed')
                  AND recommendation_key NOT IN ({placeholders})
                """,
                (generated_at, *sorted(keys)),
            )
        else:
            conn.execute(
                "UPDATE v04h_recommendations SET status='expired', updated_at=? WHERE status IN ('new','snoozed')",
                (generated_at,),
            )
        return {
            "generated_at": generated_at,
            "candidate_count": len(keys),
            "created": created,
            "updated": updated,
            "by_category": by_category,
        }


def recommendation_stats(conn: sqlite3.Connection) -> dict[str, int]:
    row = conn.execute(
        """
        SELECT
          COUNT(*) AS total,
          SUM(CASE WHEN status='new' THEN 1 ELSE 0 END) AS new_count,
          SUM(CASE WHEN status='accepted' THEN 1 ELSE 0 END) AS accepted_count,
          SUM(CASE WHEN status='converted' THEN 1 ELSE 0 END) AS converted_count,
          SUM(CASE WHEN status='rejected' THEN 1 ELSE 0 END) AS rejected_count,
          SUM(CASE WHEN score>=70 AND status IN ('new','accepted') THEN 1 ELSE 0 END) AS high_count,
          SUM(CASE WHEN path_json IS NOT NULL AND path_json NOT IN ('','[]') AND status IN ('new','accepted') THEN 1 ELSE 0 END) AS path_count
        FROM v04h_recommendations
        """
    ).fetchone()
    return {key: int(row[key] or 0) for key in row.keys()}


def list_recommendations(
    conn: sqlite3.Connection,
    *,
    q: str = "",
    category: str = "",
    status: str = "open",
    min_score: int = 0,
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    clauses = ["score>=?"]
    params: list[Any] = [max(0, min(100, min_score))]
    if q.strip():
        clauses.append("(recommendation_no LIKE ? OR title LIKE ? OR summary LIKE ? OR subject_id LIKE ?)")
        term = f"%{q.strip()}%"
        params.extend([term, term, term, term])
    if category in CATEGORY_LABELS:
        clauses.append("category=?")
        params.append(category)
    if status == "open":
        clauses.append("status IN ('new','accepted','snoozed')")
    elif status in STATUS_LABELS:
        clauses.append("status=?")
        params.append(status)
    where = " AND ".join(clauses)
    total = int(conn.execute(f"SELECT COUNT(*) FROM v04h_recommendations WHERE {where}", params).fetchone()[0])
    pages = max(1, (total + page_size - 1) // page_size)
    current = min(max(1, page), pages)
    rows = conn.execute(
        f"""
        SELECT * FROM v04h_recommendations
        WHERE {where}
        ORDER BY CASE status WHEN 'new' THEN 0 WHEN 'accepted' THEN 1 WHEN 'snoozed' THEN 2 ELSE 3 END,
                 score DESC, updated_at DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        (*params, page_size, (current - 1) * page_size),
    ).fetchall()
    items = []
    for row in rows:
        item = hydrate_recommendation(row)
        items.append(item)
    return {"items": items, "total": total, "page": current, "pages": pages}


def hydrate_recommendation(row: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    data = dict(row)
    data["category_label"] = CATEGORY_LABELS.get(data["category"], data["category"])
    data["status_label"] = STATUS_LABELS.get(data["status"], data["status"])
    data["reasons"] = json_load(data.get("reasons_json"), [])
    data["risks"] = json_load(data.get("risks_json"), [])
    data["missing"] = json_load(data.get("missing_json"), [])
    data["paths"] = json_load(data.get("path_json"), [])
    data["metadata"] = json_load(data.get("metadata_json"), {})
    data["path_parts"] = [path_to_template_parts(path) for path in data["paths"]]
    data["primary_reason"] = data["reasons"][0] if data["reasons"] else "暂无解释"
    data["subject_profile_url"] = data["metadata"].get("subject_profile_url")
    if not data["subject_profile_url"] and data.get("subject_type") and data.get("subject_id"):
        data["subject_profile_url"] = f"/subjects/{data['subject_type']}/{data['subject_id']}"
    return data


def recommendation_detail(conn: sqlite3.Connection, recommendation_id: int) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM v04h_recommendations WHERE id=?", (recommendation_id,)).fetchone()
    if not row:
        return None
    item = hydrate_recommendation(row)
    item["feedback"] = [
        dict(entry)
        for entry in conn.execute(
            "SELECT * FROM v04h_feedback_events WHERE recommendation_id=? ORDER BY created_at DESC, id DESC",
            (recommendation_id,),
        ).fetchall()
    ]
    return item


def update_decision(
    recommendation_id: int,
    status: str,
    *,
    actor: str = "manual",
    reason: str = "",
    snoozed_until: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_schema(db_path)
    allowed = {"accepted", "rejected", "snoozed", "new"}
    if status not in allowed:
        raise ValueError("无效处理状态")
    if status == "rejected" and not reason.strip():
        raise ValueError("拒绝推荐时必须填写原因")
    if status == "snoozed" and not snoozed_until:
        snoozed_until = (date.today() + timedelta(days=7)).isoformat()
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v04h_recommendations WHERE id=?", (recommendation_id,)).fetchone()
        if not row:
            raise ValueError("推荐记录不存在")
        ts = now()
        conn.execute(
            """
            UPDATE v04h_recommendations
            SET status=?, decision_reason=?, snoozed_until=?, decided_at=?, updated_at=?
            WHERE id=?
            """,
            (status, reason.strip() or None, snoozed_until or None, ts, ts, recommendation_id),
        )
        conn.execute(
            "INSERT INTO v04h_feedback_events(recommendation_id,old_status,new_status,actor,reason,created_at) VALUES (?,?,?,?,?,?)",
            (recommendation_id, row["status"], status, actor or "manual", reason.strip() or None, ts),
        )
        return hydrate_recommendation(conn.execute("SELECT * FROM v04h_recommendations WHERE id=?", (recommendation_id,)).fetchone())


def _next_action_no(conn: sqlite3.Connection) -> str:
    if not table_exists(conn, "v04f_sequence_counters"):
        conn.execute(
            "CREATE TABLE IF NOT EXISTS v04f_sequence_counters(seq_key TEXT PRIMARY KEY, seq_date TEXT NOT NULL, seq_value INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL)"
        )
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v04f_sequence_counters(seq_key,seq_date,seq_value,updated_at)
        VALUES ('ACT',?,1,?)
        ON CONFLICT(seq_key) DO UPDATE SET
          seq_value=CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
          seq_date=excluded.seq_date,
          updated_at=excluded.updated_at
        RETURNING seq_value
        """,
        (stamp, now()),
    ).fetchone()
    return f"ACT-{stamp}-{int(row['seq_value']):04d}"


def create_action_from_recommendation(
    recommendation_id: int,
    *,
    owner: str = "项目负责人",
    deadline: str = "",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    return {"created": False, "reason": "legacy_action_writer_frozen", "canonical_entry": "/collaboration"}


def subject_recommendations(
    conn: sqlite3.Connection, subject_type: str, subject_id: str, limit: int = 8
) -> list[dict[str, Any]]:
    if not table_exists(conn, "v04h_recommendations"):
        return []
    rows = conn.execute(
        """
        SELECT * FROM v04h_recommendations
        WHERE subject_type=? AND subject_id=? AND status IN ('new','accepted','snoozed')
        ORDER BY score DESC, updated_at DESC LIMIT ?
        """,
        (subject_type, subject_id, limit),
    ).fetchall()
    return [hydrate_recommendation(row) for row in rows]


def fingerprint_payload(value: Any) -> str:
    return hashlib.sha256(json_dump(value).encode("utf-8")).hexdigest()
