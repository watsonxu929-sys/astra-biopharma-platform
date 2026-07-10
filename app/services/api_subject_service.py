from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.api_common import Pagination, normalize_page, paginated
from app.v04c_review import db_connection

SUBJECTS = {
    "organization": {
        "table": "organizations",
        "name": "standard_name",
        "tags": "industry_tags",
        "status": "verification_status",
        "region": "region",
        "web": "/subjects/organization/{external_id}",
    },
    "person": {
        "table": "people",
        "name": "name",
        "tags": "ability_tags",
        "status": "verification_status",
        "region": None,
        "web": "/subjects/person/{external_id}",
    },
    "project": {
        "table": "projects",
        "name": "name",
        "tags": "focus_tags",
        "status": "status",
        "region": None,
        "web": "/subjects/project/{external_id}",
    },
}


def normalize_subject_type(value: str) -> str:
    aliases = {"org": "organization", "organizations": "organization", "people": "person", "projects": "project"}
    return aliases.get((value or "").strip().lower(), (value or "").strip().lower())


def _ref(subject_type: str, row: dict[str, Any]) -> dict[str, Any]:
    cfg = SUBJECTS[subject_type]
    return {
        "subject_type": subject_type,
        "id": row["id"],
        "external_id": row["external_id"],
        "name": row[cfg["name"]],
        "tags": row.get(cfg["tags"]) if cfg["tags"] else None,
        "status": "inactive" if not row.get("is_active", 1) else row.get(cfg["status"]),
        "is_active": bool(row.get("is_active", 1)),
        "api_url": f"/api/v1/subjects/{subject_type}/{row['external_id']}",
        "web_url": cfg["web"].format(external_id=row["external_id"]),
    }


def subject_exists(conn, subject_type: str, subject_id: str) -> bool:
    subject_type = normalize_subject_type(subject_type)
    cfg = SUBJECTS.get(subject_type)
    if not cfg:
        return False
    row = conn.execute(f"SELECT 1 FROM {cfg['table']} WHERE external_id=? OR id=?", (subject_id, int(subject_id) if str(subject_id).isdigit() else -1)).fetchone()
    return bool(row)


def list_subjects(
    *,
    subject_type: str = "",
    q: str = "",
    status: str = "",
    region: str = "",
    industry: str = "",
    inactive: str = "",
    page: int = 1,
    page_size: int = 20,
    sort: str = "name",
    order: str = "asc",
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    page, page_size = normalize_page(page, page_size)
    selected = normalize_subject_type(subject_type) if subject_type else ""
    types = [selected] if selected else list(SUBJECTS)
    if any(t not in SUBJECTS for t in types):
        raise ValueError("unsupported_subject_type")
    sort = sort if sort in {"name", "created_at", "external_id", "status"} else "name"
    order_sql = "DESC" if order.lower() == "desc" else "ASC"
    q_like = f"%{q.strip()}%"
    tag_like = f"%{industry.strip()}%"
    region_like = f"%{region.strip()}%"
    all_items: list[dict[str, Any]] = []
    total = 0
    with db_connection(db_path) as conn:
        for st in types:
            cfg = SUBJECTS[st]
            clauses = []
            params: list[Any] = []
            if q.strip():
                clauses.append(f"(external_id LIKE ? OR {cfg['name']} LIKE ? OR COALESCE({cfg['tags']},'') LIKE ?)")
                params.extend([q_like, q_like, q_like])
            if status.strip():
                clauses.append(f"{cfg['status']}=?")
                params.append(status.strip())
            if inactive in {"0", "false", "no"}:
                clauses.append("COALESCE(is_active,1)=1")
            elif inactive in {"1", "true", "yes"}:
                clauses.append("COALESCE(is_active,1)=0")
            if industry.strip() and cfg["tags"]:
                clauses.append(f"COALESCE({cfg['tags']},'') LIKE ?")
                params.append(tag_like)
            if region.strip() and cfg["region"]:
                clauses.append(f"COALESCE({cfg['region']},'') LIKE ?")
                params.append(region_like)
            where = " AND ".join(clauses) if clauses else "1=1"
            count = int(conn.execute(f"SELECT COUNT(*) FROM {cfg['table']} WHERE {where}", params).fetchone()[0])
            total += count
            sort_col = cfg["name"] if sort == "name" else (cfg["status"] if sort == "status" else sort)
            rows = conn.execute(
                f"SELECT * FROM {cfg['table']} WHERE {where} ORDER BY {sort_col} {order_sql}, id {order_sql} LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
            all_items.extend(_ref(st, dict(r)) for r in rows)
    return paginated(all_items[:page_size], Pagination(page, page_size, total), {"subject_types": types})


def get_subject(subject_type: str, subject_id: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    subject_type = normalize_subject_type(subject_type)
    cfg = SUBJECTS.get(subject_type)
    if not cfg:
        raise ValueError("unsupported_subject_type")
    with db_connection(db_path) as conn:
        row = conn.execute(f"SELECT * FROM {cfg['table']} WHERE external_id=? OR id=? LIMIT 1", (subject_id, int(subject_id) if str(subject_id).isdigit() else -1)).fetchone()
        if not row:
            return None
        data = dict(row)
        ref = _ref(subject_type, data)
        external_id = data["external_id"]
        relation_count = conn.execute("SELECT COUNT(*) FROM relations WHERE COALESCE(is_active,1)=1 AND (source_external_id=? OR target_external_id=?)", (external_id, external_id)).fetchone()[0]
        event_count = conn.execute("SELECT COUNT(*) FROM events WHERE COALESCE(is_active,1)=1 AND related_entity=?", (external_id,)).fetchone()[0]
        action_count = conn.execute("SELECT COUNT(*) FROM actions WHERE COALESCE(is_active,1)=1 AND target_external_id=?", (external_id,)).fetchone()[0]
        review_count = 0
        if conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='v04c_review_items'").fetchone():
            review_count = conn.execute("SELECT COUNT(*) FROM v04c_review_items WHERE subject_id=? AND status IN ('pending','in_review','deferred')", (external_id,)).fetchone()[0]
        fields = [data.get(cfg["name"]), data.get(cfg["tags"]), data.get(cfg["status"]), data.get("source_url")]
        completeness = int(100 * sum(1 for x in fields if x not in (None, "")) / len(fields))
        return {
            **ref,
            "fields": {k: data.get(k) for k in ["org_type", "region", "industry_tags", "public_role", "organization_network", "ability_tags", "project_type", "focus_tags", "typical_needs", "status", "verification_status", "created_at"] if k in data},
            "completeness": completeness,
            "summaries": {"relationships": relation_count, "events": event_count, "actions": action_count, "reviews": review_count},
            "recent_updated_at": data.get("created_at"),
        }


def subject_collection(subject_type: str, subject_id: str, kind: str, *, page: int = 1, page_size: int = 20, db_path: str | Path | None = None) -> dict[str, Any]:
    subject = get_subject(subject_type, subject_id, db_path)
    if not subject:
        return paginated([], Pagination(page, page_size, 0), {"subject_found": False})
    page, page_size = normalize_page(page, page_size)
    external_id = subject["external_id"]
    with db_connection(db_path) as conn:
        if kind == "relationships":
            where = "COALESCE(is_active,1)=1 AND (source_external_id=? OR target_external_id=?)"
            params = [external_id, external_id]
            total = conn.execute(f"SELECT COUNT(*) FROM relations WHERE {where}", params).fetchone()[0]
            rows = conn.execute(f"SELECT id,external_id,source_external_id,relation_type,target_external_id,period,verification_status FROM relations WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()
        elif kind == "timeline":
            where = "COALESCE(is_active,1)=1 AND related_entity=?"
            params = [external_id]
            total = conn.execute(f"SELECT COUNT(*) FROM events WHERE {where}", params).fetchone()[0]
            rows = conn.execute(f"SELECT id,external_id,event_date,name,event_type,fact_summary,verification_status FROM events WHERE {where} ORDER BY COALESCE(event_date,created_at) DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()
        elif kind == "sources":
            total = 0
            rows = []
            for table, title in [("raw_intelligence", "title")]:
                total += conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {title} LIKE ?", (f"%{external_id}%",)).fetchone()[0]
                rows.extend(conn.execute(f"SELECT id,{title} AS title,source_type,created_at FROM {table} WHERE {title} LIKE ? ORDER BY id DESC LIMIT ? OFFSET ?", (f"%{external_id}%", page_size, (page - 1) * page_size)).fetchall())
        elif kind == "actions":
            where = "COALESCE(is_active,1)=1 AND target_external_id=?"
            params = [external_id]
            total = conn.execute(f"SELECT COUNT(*) FROM actions WHERE {where}", params).fetchone()[0]
            rows = conn.execute(f"SELECT id,external_id,task,owner,priority,status,suggested_deadline FROM actions WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?", [*params, page_size, (page - 1) * page_size]).fetchall()
        elif kind == "reviews" and conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='v04c_review_items'").fetchone():
            aliases = {
                "organization": ["org", "organization", "organizations"],
                "person": ["person", "people"],
                "project": ["project", "projects"],
            }.get(subject["subject_type"], [subject["subject_type"]])
            placeholders = ",".join("?" for _ in aliases)
            where = f"subject_id=? AND subject_type IN ({placeholders})"
            params = [external_id, *aliases]
            total = conn.execute(f"SELECT COUNT(*) FROM v04c_review_items WHERE {where}", params).fetchone()[0]
            rows = conn.execute(
                f"SELECT id,review_no,item_type,field_name,current_value,candidate_value,status,created_at FROM v04c_review_items WHERE {where} ORDER BY id DESC LIMIT ? OFFSET ?",
                [*params, page_size, (page - 1) * page_size],
            ).fetchall()
        else:
            total = 0
            rows = []
        return paginated([dict(r) for r in rows], Pagination(page, page_size, int(total)), {"subject": subject})
