from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, desc, func, or_, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from ..models import (
    ActionItem,
    HistoricalEvent,
    Organization,
    Person,
    ProjectPool,
    RawIntelligence,
    Relation,
    Resource,
)


@dataclass(frozen=True)
class SubjectConfig:
    key: str
    label: str
    model: Any
    name_attr: str
    detail_url: str
    edit_url: str
    tag_attr: str | None = None
    status_attr: str | None = None


SUBJECT_CONFIGS: dict[str, SubjectConfig] = {
    "organization": SubjectConfig(
        "organization", "企业/机构", Organization, "standard_name",
        "/organizations/{id}", "/manage/organizations/{id}/edit",
        "industry_tags", "verification_status",
    ),
    "person": SubjectConfig(
        "person", "人物", Person, "name",
        "/people/{id}", "/manage/people/{id}/edit",
        "ability_tags", "verification_status",
    ),
    "project": SubjectConfig(
        "project", "项目", ProjectPool, "name",
        "/projects/{id}", "/manage/projects/{id}/edit",
        "focus_tags", "status",
    ),
}

REVIEW_TYPE_ALIASES = {
    "organization": ["org", "organization", "organizations"],
    "person": ["person", "people"],
    "project": ["project", "projects"],
}


def normalize_subject_type(subject_type: str) -> str:
    value = (subject_type or "").strip().lower()
    aliases = {"org": "organization", "organizations": "organization", "people": "person", "projects": "project"}
    return aliases.get(value, value)


def subject_url(subject_type: str, external_id: str) -> str:
    return f"/subjects/{normalize_subject_type(subject_type)}/{external_id}"


def _value(row: Any, attr: str, default: Any = "") -> Any:
    return getattr(row, attr, default)


def _label(subject_type: str, row: Any) -> str:
    cfg = SUBJECT_CONFIGS[subject_type]
    return str(_value(row, cfg.name_attr, "") or _value(row, "external_id", "") or "")


def _status(subject_type: str, row: Any) -> str:
    cfg = SUBJECT_CONFIGS[subject_type]
    if getattr(row, "is_active", True) is False:
        return "已停用"
    attr = cfg.status_attr or "verification_status"
    return str(_value(row, attr, "") or "未标记")


def _subject_ref(subject_type: str, row: Any) -> dict[str, Any]:
    cfg = SUBJECT_CONFIGS[subject_type]
    external_id = str(getattr(row, "external_id", ""))
    return {
        "type": subject_type,
        "type_label": cfg.label,
        "external_id": external_id,
        "name": _label(subject_type, row),
        "status": _status(subject_type, row),
        "tags": str(_value(row, cfg.tag_attr, "") or "") if cfg.tag_attr else "",
        "is_active": bool(getattr(row, "is_active", True)),
        "profile_url": subject_url(subject_type, external_id),
        "detail_url": cfg.detail_url.format(id=row.id),
        "edit_url": cfg.edit_url.format(id=row.id),
        "row": row,
    }


def get_subject(db: Session, subject_type: str, subject_id: str) -> dict[str, Any] | None:
    subject_type = normalize_subject_type(subject_type)
    cfg = SUBJECT_CONFIGS.get(subject_type)
    if not cfg:
        raise ValueError("unsupported_subject_type")
    value = (subject_id or "").strip()
    if not value:
        return None
    conditions = [cfg.model.external_id == value]
    if value.isdigit():
        conditions.append(cfg.model.id == int(value))
    row = db.scalar(select(cfg.model).where(or_(*conditions)).limit(1))
    return _subject_ref(subject_type, row) if row else None


def _all_subject_maps(db: Session, external_ids: set[str]) -> dict[str, dict[str, Any]]:
    if not external_ids:
        return {}
    output: dict[str, dict[str, Any]] = {}
    for subject_type, cfg in SUBJECT_CONFIGS.items():
        rows = db.scalars(select(cfg.model).where(cfg.model.external_id.in_(external_ids))).all()
        for row in rows:
            output[row.external_id] = _subject_ref(subject_type, row)
    return output


def relation_rows(db: Session, subject: dict[str, Any], limit: int = 30) -> list[dict[str, Any]]:
    external_id = subject["external_id"]
    rows = db.scalars(
        select(Relation)
        .where(
            Relation.is_active.is_(True),
            or_(Relation.source_external_id == external_id, Relation.target_external_id == external_id),
        )
        .order_by(desc(Relation.created_at), Relation.id.desc())
        .limit(limit)
    ).all()
    ids = {r.source_external_id for r in rows} | {r.target_external_id for r in rows}
    refs = _all_subject_maps(db, {x for x in ids if x})
    output = []
    seen: set[int] = set()
    for rel in rows:
        if rel.id in seen:
            continue
        seen.add(rel.id)
        outgoing = rel.source_external_id == external_id
        other_id = rel.target_external_id if outgoing else rel.source_external_id
        output.append({
            "relation": rel,
            "direction": "outgoing" if outgoing else "incoming",
            "direction_label": "对外关系" if outgoing else "对内关系",
            "other": refs.get(other_id, {
                "type": "unknown",
                "type_label": "未知主体",
                "external_id": other_id,
                "name": other_id or "未知主体",
                "profile_url": None,
                "detail_url": None,
            }),
            "detail_url": f"/relations?q={rel.external_id}",
        })
    return output


def related_collections(db: Session, subject: dict[str, Any], relations: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    buckets = {"organizations": [], "people": [], "projects": []}
    seen = {key: set() for key in buckets}

    def add(ref: dict[str, Any]) -> None:
        key = {"organization": "organizations", "person": "people", "project": "projects"}.get(ref.get("type"))
        if key and ref["external_id"] not in seen[key] and ref["external_id"] != subject["external_id"]:
            seen[key].add(ref["external_id"])
            buckets[key].append(ref)

    for row in relations:
        add(row["other"])

    if subject["type"] == "organization":
        org = subject["row"]
        project_rows = db.scalars(
            select(ProjectPool)
            .where(
                ProjectPool.is_active.is_(True),
                or_(ProjectPool.owner_organization_id == org.id, ProjectPool.owner_external_id == org.external_id),
            )
            .order_by(ProjectPool.name)
            .limit(20)
        ).all()
        for row in project_rows:
            add(_subject_ref("project", row))
    elif subject["type"] == "project":
        project = subject["row"]
        owner = None
        if project.owner_organization_id:
            owner = db.get(Organization, project.owner_organization_id)
        if not owner and project.owner_external_id:
            owner = db.scalar(select(Organization).where(Organization.external_id == project.owner_external_id))
        if owner:
            add(_subject_ref("organization", owner))

    return buckets


def event_timeline(db: Session, subject: dict[str, Any], limit: int = 30) -> list[dict[str, Any]]:
    external_id = subject["external_id"]
    clauses = [HistoricalEvent.related_entity == external_id]
    if subject["type"] == "organization":
        clauses.append(HistoricalEvent.related_organization_id == subject["row"].id)
    rows = db.scalars(
        select(HistoricalEvent)
        .where(HistoricalEvent.is_active.is_(True), or_(*clauses))
        .order_by(desc(HistoricalEvent.created_at), HistoricalEvent.id.desc())
        .limit(limit)
    ).all()
    items = []
    seen: set[str] = set()
    for row in rows:
        key = row.external_id or f"event:{row.id}"
        if key in seen:
            continue
        seen.add(key)
        items.append({
            "occurred_at": row.event_date or row.created_at,
            "item_type": "event",
            "type_label": "事件",
            "title": row.name,
            "summary": row.fact_summary or row.system_use or "",
            "source_type": row.source_type or "",
            "source_id": row.external_id,
            "detail_url": f"/events/{row.id}",
        })
    return items


def resource_rows(db: Session, subject: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    clauses = [Resource.owner_external_id == subject["external_id"]]
    if subject["type"] == "organization":
        clauses.append(Resource.owner_organization_id == subject["row"].id)
    rows = db.scalars(
        select(Resource)
        .where(Resource.is_active.is_(True), or_(*clauses))
        .order_by(Resource.category, Resource.external_id)
        .limit(limit)
    ).all()
    return [{
        "name": row.description or row.category or row.external_id,
        "category": row.category or "未分类",
        "owner": row.owner_external_id,
        "value": row.applicable_to or row.description or "",
        "status": row.verification_status,
        "relation_label": "直接关联",
        "detail_url": f"/resources/{row.id}",
        "row": row,
    } for row in rows]


def action_rows(db: Session, subject: dict[str, Any], limit: int = 20) -> list[ActionItem]:
    clauses = [ActionItem.target_external_id == subject["external_id"]]
    if subject["type"] == "organization":
        clauses.append(ActionItem.target_organization_id == subject["row"].id)
    return db.scalars(
        select(ActionItem)
        .where(ActionItem.is_active.is_(True), or_(*clauses))
        .order_by(ActionItem.status, ActionItem.priority, ActionItem.id.desc())
        .limit(limit)
    ).all()


def source_rows(db: Session, subject: dict[str, Any], limit: int = 20) -> list[dict[str, Any]]:
    rows = []
    row = subject["row"]
    if any(getattr(row, attr, None) for attr in ("source_url", "source_title", "source_text", "source_type")):
        rows.append({
            "title": getattr(row, "source_title", None) or f"{subject['name']} 主体来源",
            "url": getattr(row, "source_url", None),
            "source_type": getattr(row, "source_type", None) or "主体记录",
            "captured_at": getattr(row, "captured_at", None) or getattr(row, "created_at", None),
            "snippet": (getattr(row, "source_text", None) or "")[:240],
            "detail_url": subject["detail_url"],
        })
    token = subject["external_id"]
    intelligence = db.scalars(
        select(RawIntelligence)
        .where(or_(RawIntelligence.title.like(f"%{token}%"), RawIntelligence.content.like(f"%{token}%")))
        .order_by(desc(RawIntelligence.created_at))
        .limit(max(0, limit - len(rows)))
    ).all()
    for item in intelligence:
        rows.append({
            "title": item.title,
            "url": item.source_url,
            "source_type": item.source_type,
            "captured_at": item.created_at,
            "snippet": (item.content or "")[:240],
            "detail_url": f"/intelligence/{item.id}",
        })
    return rows[:limit]


def review_summary(db: Session, subject: dict[str, Any]) -> dict[str, Any]:
    aliases = REVIEW_TYPE_ALIASES.get(subject["type"], [subject["type"]])
    try:
        data = db.execute(
            text(
                """
                SELECT
                  COUNT(*) AS open_count,
                  SUM(CASE WHEN item_type='conflict' THEN 1 ELSE 0 END) AS conflict_count,
                  SUM(CASE WHEN item_type LIKE '%relation%' THEN 1 ELSE 0 END) AS pending_relation_count,
                  MAX(updated_at) AS latest_review_at
                FROM v04c_review_items
                WHERE subject_id = :subject_id
                  AND subject_type IN :subject_types
                  AND status IN ('pending','in_review','deferred')
                """
            ).bindparams(bindparam("subject_types", expanding=True)),
            {"subject_id": subject["external_id"], "subject_types": tuple(aliases)},
        ).mappings().first()
    except Exception:
        data = None
    return {
        "open_count": int(data["open_count"] or 0) if data else 0,
        "conflict_count": int(data["conflict_count"] or 0) if data else 0,
        "pending_relation_count": int(data["pending_relation_count"] or 0) if data else 0,
        "latest_review_at": data["latest_review_at"] if data else None,
        "url": f"/review?q={subject['external_id']}",
    }


def completeness(subject: dict[str, Any], related: dict[str, list[dict[str, Any]]], sources: list[dict[str, Any]]) -> dict[str, Any]:
    row = subject["row"]
    if subject["type"] == "organization":
        checks = [
            ("名称", bool(getattr(row, "standard_name", None))),
            ("简介/主体类型", bool(getattr(row, "org_type", None) or getattr(row, "needs", None))),
            ("所属赛道/标签", bool(getattr(row, "industry_tags", None))),
            ("地区", bool(getattr(row, "region", None))),
            ("联系人或核心人物", bool(related["people"])),
            ("来源", bool(sources)),
        ]
    elif subject["type"] == "person":
        checks = [
            ("姓名", bool(getattr(row, "name", None))),
            ("当前机构", bool(getattr(row, "organization_network", None) or related["organizations"])),
            ("公开职位", bool(getattr(row, "public_role", None))),
            ("简介/价值", bool(getattr(row, "value_provided", None))),
            ("标签", bool(getattr(row, "ability_tags", None))),
            ("来源", bool(sources)),
        ]
    else:
        checks = [
            ("名称", bool(getattr(row, "name", None))),
            ("项目状态/类型", bool(getattr(row, "status", None) or getattr(row, "project_type", None))),
            ("所属企业", bool(getattr(row, "owner_external_id", None) or related["organizations"])),
            ("负责人/行动", bool(getattr(row, "target_actions", None) or related["people"])),
            ("简介/需求", bool(getattr(row, "typical_needs", None) or getattr(row, "focus_tags", None))),
            ("来源", bool(sources)),
        ]
    done = [label for label, ok in checks if ok]
    missing = [label for label, ok in checks if not ok]
    return {
        "percent": int(round(len(done) * 100 / len(checks))) if checks else 0,
        "completed": done,
        "missing": missing,
        "suggestions": [f"补充{label}" for label in missing[:4]],
    }


def relation_paths(db: Session, subject: dict[str, Any], direct: list[dict[str, Any]], limit: int = 20) -> list[list[dict[str, Any]]]:
    paths: list[list[dict[str, Any]]] = []
    seen: set[tuple[str, ...]] = set()

    def add_path(nodes: list[dict[str, Any]], relation_labels: list[str]) -> None:
        key = tuple([nodes[0]["external_id"], *relation_labels, nodes[-1]["external_id"]])
        if key not in seen and len(paths) < limit:
            seen.add(key)
            paths.append([{"node": nodes[0]}, {"relation": relation_labels[0]}, {"node": nodes[1]}] if len(nodes) == 2 else [
                {"node": nodes[0]}, {"relation": relation_labels[0]}, {"node": nodes[1]},
                {"relation": relation_labels[1]}, {"node": nodes[2]},
            ])

    for row in direct:
        other = row["other"]
        if other.get("type") == "unknown":
            continue
        add_path([subject, other], [row["relation"].relation_type])
        if len(paths) >= limit:
            break
        second_rows = relation_rows(db, other, limit=8)
        for second in second_rows:
            third = second["other"]
            if third.get("external_id") in {subject["external_id"], other["external_id"]}:
                continue
            if third.get("type") == "unknown":
                continue
            add_path([subject, other, third], [row["relation"].relation_type, second["relation"].relation_type])
            if len(paths) >= limit:
                break
    return paths


def timeline(db: Session, subject: dict[str, Any], events: list[dict[str, Any]], actions: list[ActionItem], relations: list[dict[str, Any]], sources: list[dict[str, Any]], limit: int = 30) -> list[dict[str, Any]]:
    items = list(events)
    for row in actions:
        items.append({
            "occurred_at": row.created_at,
            "item_type": "action",
            "type_label": "行动",
            "title": row.task,
            "summary": row.completion_standard or row.status,
            "source_type": row.source_type or "",
            "source_id": row.external_id,
            "detail_url": f"/actions?q={row.external_id}",
        })
    for row in relations:
        rel = row["relation"]
        items.append({
            "occurred_at": rel.created_at,
            "item_type": "relation",
            "type_label": "关系",
            "title": f"{rel.relation_type}：{row['other']['name']}",
            "summary": rel.evidence_source or "",
            "source_type": rel.source_type or "",
            "source_id": rel.external_id,
            "detail_url": row["detail_url"],
        })
    for row in sources:
        items.append({
            "occurred_at": row["captured_at"],
            "item_type": "source",
            "type_label": "来源",
            "title": row["title"],
            "summary": row["snippet"],
            "source_type": row["source_type"],
            "source_id": row["url"] or "",
            "detail_url": row["detail_url"],
        })
    items.append({
        "occurred_at": getattr(subject["row"], "created_at", None),
        "item_type": "subject",
        "type_label": "主体",
        "title": "主体记录创建",
        "summary": subject["external_id"],
        "source_type": "系统记录",
        "source_id": subject["external_id"],
        "detail_url": subject["detail_url"],
    })

    def sort_key(item: dict[str, Any]) -> tuple[int, str]:
        value = item.get("occurred_at")
        if isinstance(value, datetime):
            return (1, value.isoformat())
        if value:
            return (1, str(value))
        return (0, "")

    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items:
        key = (str(item.get("item_type")), str(item.get("source_id") or item.get("title")))
        unique.setdefault(key, item)
    return sorted(unique.values(), key=sort_key, reverse=True)[:limit]


def subject_profile(db: Session, subject_type: str, subject_id: str) -> dict[str, Any]:
    subject = get_subject(db, subject_type, subject_id)
    if not subject:
        return {"found": False, "subject_type": normalize_subject_type(subject_type), "subject_id": subject_id}
    direct = relation_rows(db, subject)
    related = related_collections(db, subject, direct)
    events = event_timeline(db, subject)
    resources = resource_rows(db, subject)
    actions = action_rows(db, subject)
    sources = source_rows(db, subject)
    return {
        "found": True,
        "subject": subject,
        "relations": direct,
        "related": related,
        "events": events,
        "resources": resources,
        "actions": actions,
        "sources": sources,
        "review": review_summary(db, subject),
        "completeness": completeness(subject, related, sources),
        "paths": relation_paths(db, subject, direct),
        "timeline": timeline(db, subject, events, actions, direct, sources),
        "stats": {
            "relations": len(direct),
            "people": len(related["people"]),
            "organizations": len(related["organizations"]),
            "projects": len(related["projects"]),
            "events": len(events),
            "resources": len(resources),
            "actions": len(actions),
            "sources": len(sources),
        },
    }


def _apply_filters(stmt: Any, subject_type: str, q: str, tag: str, status: str, missing_core: bool) -> Any:
    cfg = SUBJECT_CONFIGS[subject_type]
    model = cfg.model
    if q:
        token = f"%{q}%"
        clauses = [model.external_id.like(token), getattr(model, cfg.name_attr).like(token)]
        if cfg.tag_attr:
            clauses.append(func.coalesce(getattr(model, cfg.tag_attr), "").like(token))
        stmt = stmt.where(or_(*clauses))
    if tag and cfg.tag_attr:
        stmt = stmt.where(func.coalesce(getattr(model, cfg.tag_attr), "").like(f"%{tag}%"))
    if status:
        if status == "inactive":
            stmt = stmt.where(model.is_active.is_(False))
        elif cfg.status_attr:
            stmt = stmt.where(getattr(model, cfg.status_attr) == status)
    if missing_core:
        name_col = getattr(model, cfg.name_attr)
        clauses = [or_(name_col.is_(None), name_col == "")]
        if subject_type == "organization":
            clauses.append(or_(Organization.org_type.is_(None), Organization.org_type == ""))
            clauses.append(or_(Organization.industry_tags.is_(None), Organization.industry_tags == ""))
        elif subject_type == "person":
            clauses.append(or_(Person.public_role.is_(None), Person.public_role == ""))
            clauses.append(or_(Person.organization_network.is_(None), Person.organization_network == ""))
        elif subject_type == "project":
            clauses.append(or_(ProjectPool.owner_external_id.is_(None), ProjectPool.owner_external_id == ""))
            clauses.append(or_(ProjectPool.project_type.is_(None), ProjectPool.project_type == ""))
        stmt = stmt.where(or_(*clauses))
    return stmt


def subject_center(db: Session, subject_type: str = "", q: str = "", tag: str = "", status: str = "", has_review: str = "", missing_core: bool = False, page: int = 1, page_size: int = 20) -> dict[str, Any]:
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 50))
    current_type = normalize_subject_type(subject_type) if subject_type else ""
    if current_type and current_type not in SUBJECT_CONFIGS:
        raise ValueError("unsupported_subject_type")
    types = [current_type] if current_type else list(SUBJECT_CONFIGS)
    per_type: dict[str, int] = {}
    total = 0
    candidates: list[dict[str, Any]] = []
    for st in types:
        cfg = SUBJECT_CONFIGS[st]
        base = _apply_filters(select(cfg.model), st, q.strip(), tag.strip(), status.strip(), missing_core)
        count = db.scalar(select(func.count()).select_from(base.subquery())) or 0
        per_type[st] = int(count)
        total += int(count)
    offset = (page - 1) * page_size
    remaining = page_size
    skipped = offset
    for st in types:
        count = per_type[st]
        if skipped >= count:
            skipped -= count
            continue
        cfg = SUBJECT_CONFIGS[st]
        stmt = _apply_filters(select(cfg.model), st, q.strip(), tag.strip(), status.strip(), missing_core)
        rows = db.scalars(
            stmt.order_by(getattr(cfg.model, cfg.name_attr), cfg.model.id).offset(skipped).limit(remaining)
        ).all()
        candidates.extend(_subject_ref(st, row) for row in rows)
        remaining -= len(rows)
        skipped = 0
        if remaining <= 0:
            break

    for item in candidates:
        rev = review_summary(db, item)
        item["review_open_count"] = rev["open_count"]
        item["completeness"] = completeness(item, related_collections(db, item, relation_rows(db, item, limit=10)), source_rows(db, item, limit=3))["percent"]
    if has_review in {"yes", "no"}:
        want = has_review == "yes"
        candidates = [item for item in candidates if bool(item["review_open_count"]) == want]
    return {
        "items": candidates,
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, (total + page_size - 1) // page_size),
        "filters": {"subject_type": current_type, "q": q, "tag": tag, "status": status, "has_review": has_review, "missing_core": missing_core},
        "subject_labels": {key: cfg.label for key, cfg in SUBJECT_CONFIGS.items()},
        "counts": per_type,
    }
