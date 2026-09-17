from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, inspect, or_, select, text
from sqlalchemy.orm import Session

from app.core.similarity import similarity_ratio

from ..models import (
    ActionItem,
    HistoricalEvent,
    Organization,
    Person,
    ProjectPool,
    Relation,
    Resource,
)


def normalize_org_name(value: str | None) -> str:
    text = (value or "").strip()
    text = text.replace("（", "(").replace("）", ")")
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s*([()])\s*", r"\1", text)
    return text.upper()


@dataclass
class DuplicateCheckResult:
    exact: list[Organization]
    normalized: list[Organization]
    similar: list[Organization]

    @property
    def blocks_save(self) -> bool:
        return bool(self.exact or self.normalized)

    @property
    def has_warning(self) -> bool:
        return self.blocks_save or bool(self.similar)


def check_organization_duplicates(
    db: Session, name: str, current_id: int | None = None
) -> DuplicateCheckResult:
    normalized = normalize_org_name(name)
    rows = db.scalars(select(Organization)).all()
    exact: list[Organization] = []
    normalized_matches: list[Organization] = []
    similar: list[Organization] = []
    compact_name = normalized.replace(" ", "")

    for org in rows:
        if current_id and org.id == current_id:
            continue
        org_name = org.standard_name or ""
        org_normalized = normalize_org_name(org_name)
        if org_name == name:
            exact.append(org)
        elif org_normalized == normalized:
            normalized_matches.append(org)
        else:
            compact_existing = org_normalized.replace(" ", "")
            if (
                len(compact_name) >= 6
                and len(compact_existing) >= 6
                and (
                    compact_name in compact_existing
                    or compact_existing in compact_name
                )
            ):
                similar.append(org)

    return DuplicateCheckResult(exact, normalized_matches, similar[:5])


def resolve_owner_organization(db: Session, obj: Any) -> None:
    if not isinstance(obj, ProjectPool):
        return
    raw = (obj.owner_external_id or "").strip()
    if not raw:
        obj.owner_organization_id = None
        return

    existing = db.scalar(select(Organization).where(Organization.external_id == raw))
    if not existing:
        existing = db.scalar(select(Organization).where(Organization.standard_name == raw))
    if existing:
        obj.owner_organization_id = existing.id
        obj.owner_external_id = existing.external_id
        obj.subject_match_method = "exact"
        obj.subject_matched_at = datetime.now()
        if obj.subject_manually_confirmed is None:
            obj.subject_manually_confirmed = True


def organization_reference_count(db: Session, org: Organization) -> int:
    checks = [
        select(func.count()).select_from(Resource).where(Resource.owner_external_id == org.external_id),
        select(func.count()).select_from(HistoricalEvent).where(HistoricalEvent.related_entity == org.external_id),
        select(func.count()).select_from(Relation).where(
            or_(Relation.source_external_id == org.external_id, Relation.target_external_id == org.external_id)
        ),
        select(func.count()).select_from(ActionItem).where(ActionItem.target_external_id == org.external_id),
        select(func.count()).select_from(ProjectPool).where(
            or_(ProjectPool.owner_external_id == org.external_id, ProjectPool.owner_organization_id == org.id)
        ),
    ]
    total = 0
    for stmt in checks:
        try:
            total += db.scalar(stmt) or 0
        except Exception:
            db.rollback()
    return total


@dataclass
class PersonDuplicateCheckResult:
    exact: list[Person]
    possible: list[Person]

    @property
    def blocks_save(self) -> bool:
        return bool(self.exact)


def _normalize_person_field(value: str | None) -> str:
    return re.sub(r"[\s\-_.·•（）()【】\[\]，,]+", "", (value or "").strip().casefold())


def check_person_duplicates(
    db: Session,
    name: str,
    organization_name: str = "",
    public_role: str = "",
    current_id: int | None = None,
) -> PersonDuplicateCheckResult:
    name_key = _normalize_person_field(name)
    org_key = _normalize_person_field(organization_name)
    role_key = _normalize_person_field(public_role)
    exact: list[Person] = []
    possible: list[Person] = []
    for person in db.scalars(select(Person)).all():
        if current_id and person.id == current_id:
            continue
        if not name_key or _normalize_person_field(person.name) != name_key:
            continue
        if (
            _normalize_person_field(person.organization_network) == org_key
            and _normalize_person_field(person.public_role) == role_key
        ):
            exact.append(person)
        else:
            possible.append(person)
    return PersonDuplicateCheckResult(exact=exact, possible=possible[:5])


def resolve_organization_for_person(db: Session, organization_name: str) -> tuple[str, list[Organization]]:
    value = (organization_name or "").strip()
    if not value:
        return "", []
    result = check_organization_duplicates(db, value)
    exact = [*result.exact, *result.normalized]
    if len(exact) == 1:
        return exact[0].standard_name, []
    if exact:
        return "", exact[:5]
    similar = [
        org for org in db.scalars(select(Organization)).all()
        if similarity_ratio(normalize_org_name(value), normalize_org_name(org.standard_name or "")) >= .78
    ]
    return "", (similar or result.similar)[:5]


def _table_columns(db: Session, table_name: str) -> set[str]:
    inspector = inspect(db.get_bind())
    if not inspector.has_table(table_name):
        return set()
    return {str(column["name"]) for column in inspector.get_columns(table_name)}


def _count_if_available(
    db: Session,
    table_name: str,
    required_columns: set[str],
    sql: str,
    params: dict[str, Any],
) -> int:
    if not required_columns.issubset(_table_columns(db, table_name)):
        return 0
    return int(db.execute(text(sql), params).scalar() or 0)


def _reference_rows_if_available(
    db: Session,
    table_name: str,
    required_columns: set[str],
    sql: str,
    params: dict[str, Any],
) -> list[dict[str, Any]]:
    if not required_columns.issubset(_table_columns(db, table_name)):
        return []
    return [dict(row) for row in db.execute(text(sql), params).mappings().all()]


def _reference_category(
    db: Session,
    params: dict[str, Any],
    *,
    key: str,
    label: str,
    table_name: str,
    required_columns: set[str],
    sql: str,
    url_template: str,
    cleanup_guidance: str,
) -> dict[str, Any]:
    rows = _reference_rows_if_available(db, table_name, required_columns, sql, params)
    items = []
    for row in rows:
        try:
            url = url_template.format(**row)
        except (KeyError, TypeError, ValueError):
            url = ""
        items.append({
            "id": row.get("id"),
            "label": str(row.get("item_label") or f"{label} #{row.get('id')}"),
            "url": url,
        })
    return {
        "key": key,
        "table": table_name,
        "label": label,
        "count": len(rows),
        "items": items,
        "cleanup_guidance": cleanup_guidance,
    }


def organization_reference_details(db: Session, org: Organization) -> list[dict[str, Any]]:
    params = {"id": int(org.id), "sid": str(org.id), "external": org.external_id, "name": org.standard_name}
    specs = [
        ("people", "关联人物", "people", {"id", "name", "organization_network"}, "SELECT id,name AS item_label FROM people WHERE organization_network=:name OR organization_network LIKE '%' || :name || '%' ORDER BY id", "/admin/people/{id}", "先修正错误的所属机构关联；真实任职历史应保留。"),
        ("user_links", "组织账号绑定", "organization_user_links", {"id", "organization_id", "user_id", "status"}, "SELECT id,user_id,'账号 #' || user_id || '（' || status || '）' AS item_label FROM organization_user_links WHERE organization_id=:id ORDER BY id", "/admin/users/{user_id}", "有效绑定可使用现有组织账号管理解除；历史绑定应保留并停用主体。"),
        ("membership_links", "组织会员绑定", "organization_membership_links", {"id", "organization_id", "membership_id", "status"}, "SELECT id,membership_id,'会员绑定 #' || membership_id || '（' || status || '）' AS item_label FROM organization_membership_links WHERE organization_id=:id ORDER BY id", "/club/members/{membership_id}", "有效错误绑定可在会员管理修正；历史绑定不应物理删除。"),
        ("user_roles", "组织角色授权", "organization_user_roles", {"id", "organization_id", "user_id", "status"}, "SELECT id,user_id,'账号 #' || user_id || '（' || status || '）' AS item_label FROM organization_user_roles WHERE organization_id=:id ORDER BY id", "/admin/users/{user_id}", "有效错误授权可使用现有权限管理撤销；授权历史应保留。"),
        ("tags", "主体标签", "v06_organization_tags", {"id", "organization_id", "tag_id"}, "SELECT id,:external AS external_id,'主体标签 #' || tag_id AS item_label FROM v06_organization_tags WHERE organization_id=:id ORDER BY id", "/network/entities/organization/{external_id}", "标签属于主体档案组成部分；当前不单独物理清理，建议停用主体。"),
        ("relationships", "正式关系", "p3_canonical_relationships", {"id", "subject_type", "subject_id", "object_type", "object_id", "review_status"}, "SELECT id,'正式关系 #' || id AS item_label FROM p3_canonical_relationships WHERE COALESCE(review_status,'')<>'archived' AND ((subject_type='organization' AND CAST(subject_id AS TEXT) IN (:sid,:external)) OR (object_type='organization' AND CAST(object_id AS TEXT) IN (:sid,:external))) ORDER BY id", "/network/relationships/{id}", "真实历史建议保留主体；仅错误或测试关系可在关系详情归档。"),
        ("intelligence", "情报主体关联", "core_intelligence_subject_links", {"id", "intelligence_item_id", "subject_type", "subject_id"}, "SELECT id,intelligence_item_id,'情报 #' || intelligence_item_id AS item_label FROM core_intelligence_subject_links WHERE subject_type='organization' AND CAST(subject_id AS TEXT) IN (:sid,:external) ORDER BY id", "/intelligence/{intelligence_item_id}", "需要在现有情报主体治理流程中核对，不直接级联清理。"),
        ("resources", "资源关联", "v06_market_resources", {"id", "title", "organization_id"}, "SELECT id,COALESCE(title,'资源 #' || id) AS item_label FROM v06_market_resources WHERE organization_id=:id ORDER BY id", "/resources/{id}", "仅资源详情确认无下游记录时可安全删除；否则关闭归档。"),
        ("matches", "资源匹配", "p4_resource_match_candidates", {"id", "recommended_organization_id"}, "SELECT id,'匹配 #' || id AS item_label FROM p4_resource_match_candidates WHERE recommended_organization_id=:id ORDER BY id", "/matches/{id}", "匹配结果属于业务证据，不随主体删除。"),
        ("opportunities", "合作机会", "v06_opportunities", {"id", "title", "organization_id", "target_organization_id", "demand_organization_id", "supply_organization_id"}, "SELECT id,COALESCE(title,'机会 #' || id) AS item_label FROM v06_opportunities WHERE :id IN (organization_id,target_organization_id,demand_organization_id,supply_organization_id) ORDER BY id", "/opportunities/{id}", "机会应按现有流程关闭或保留，不物理删除。"),
        ("memberships", "俱乐部会员", "v04f_club_memberships", {"id", "member_no", "organization_id"}, "SELECT id,COALESCE(member_no,'会员 #' || id) AS item_label FROM v04f_club_memberships WHERE organization_id=:id ORDER BY id", "/club/members/{id}", "错误绑定可在会员详情修正；退出会员使用现有停用/退出流程。"),
        ("events", "俱乐部活动", "v05c_club_event_profiles", {"id", "event_no", "organizer", "co_organizer"}, "SELECT id,COALESCE(event_no,'活动 #' || id) AS item_label FROM v05c_club_event_profiles WHERE organizer=:name OR co_organizer LIKE '%' || :name || '%' ORDER BY id", "/club/events/{id}", "真实活动历史应保留。"),
        ("reports", "报告", "v05h_generated_reports", {"id", "title", "summary", "content_markdown"}, "SELECT id,COALESCE(title,'报告 #' || id) AS item_label FROM v05h_generated_reports WHERE title LIKE '%' || :name || '%' OR summary LIKE '%' || :name || '%' OR content_markdown LIKE '%' || :name || '%' ORDER BY id", "/reports/{id}", "报告引用属于正式历史，不随主体删除。"),
    ]
    details = [
        _reference_category(db, params, key=key, label=label, table_name=table, required_columns=columns, sql=sql, url_template=url, cleanup_guidance=guidance)
        for key, label, table, columns, sql, url, guidance in specs
    ]
    if _table_columns(db, "v06_follow_ups") and _table_columns(db, "v06_opportunities"):
        rows = [dict(row) for row in db.execute(text("""
            SELECT f.id,f.opportunity_id,COALESCE(NULLIF(f.content,''),'跟进 #' || f.id) AS item_label
            FROM v06_follow_ups f JOIN v06_opportunities o ON o.id=f.opportunity_id
            WHERE :id IN (o.organization_id,o.target_organization_id,o.demand_organization_id,o.supply_organization_id)
            ORDER BY f.id
        """), params).mappings().all()]
    else:
        rows = []
    details.insert(6, {"key": "follow_ups", "label": "跟进事项", "count": len(rows), "items": [
        {"id": row["id"], "label": str(row["item_label"]), "url": f"/opportunities/{row['opportunity_id']}"} for row in rows
    ], "cleanup_guidance": "跟进记录不得随主体删除；请保留主体或在机会中继续处理。"})
    return _classify_subject_references(db, org, "organization", details)


def organization_reference_reasons(db: Session, org: Organization) -> list[str]:
    return [f"{item['label']} {item['count']} 条" for item in organization_reference_details(db, org) if item["count"] and item["classification"] == "BUSINESS_HISTORY"]


def person_reference_details(db: Session, person: Person) -> list[dict[str, Any]]:
    params = {"id": int(person.id), "sid": str(person.id), "external": person.external_id, "name": person.name}
    specs = [
        ("relationships", "正式关系", "p3_canonical_relationships", {"id", "subject_type", "subject_id", "object_type", "object_id", "review_status"}, "SELECT id,'正式关系 #' || id AS item_label FROM p3_canonical_relationships WHERE COALESCE(review_status,'')<>'archived' AND ((subject_type='person' AND CAST(subject_id AS TEXT) IN (:sid,:external)) OR (object_type='person' AND CAST(object_id AS TEXT) IN (:sid,:external))) ORDER BY id", "/network/relationships/{id}", "真实历史建议保留人物，不要硬删除；仅错误或测试关系可在关系详情归档。"),
        ("identity_links", "身份绑定申请", "identity_link_requests", {"id", "person_id", "user_id", "status"}, "SELECT id,user_id,'账号 #' || user_id || '（' || status || '）' AS item_label FROM identity_link_requests WHERE person_id=:id ORDER BY id", "/system/identity-link-requests", "待处理申请可在身份绑定审核中处理；审核历史应保留并停用人物。"),
        ("profile", "人物扩展档案", "v06_person_profiles", {"id", "person_id"}, "SELECT id,person_id,'人物扩展档案 #' || id AS item_label FROM v06_person_profiles WHERE person_id=:id ORDER BY id", "/network/people/{person_id}", "扩展档案属于人物主数据，不单独物理清理；建议停用人物。"),
        ("tags", "人物标签", "v06_person_tags", {"id", "person_id", "tag_id"}, "SELECT id,person_id,'人物标签 #' || tag_id AS item_label FROM v06_person_tags WHERE person_id=:id ORDER BY id", "/network/people/{person_id}", "标签属于人物档案组成部分；当前不单独物理清理，建议停用人物。"),
        ("intelligence", "情报主体关联", "core_intelligence_subject_links", {"id", "intelligence_item_id", "subject_type", "subject_id"}, "SELECT id,intelligence_item_id,'情报 #' || intelligence_item_id AS item_label FROM core_intelligence_subject_links WHERE subject_type='person' AND CAST(subject_id AS TEXT) IN (:sid,:external) ORDER BY id", "/intelligence/{intelligence_item_id}", "需要在现有情报主体治理流程中核对，不直接级联清理。"),
        ("resources", "资源关联", "v06_market_resources", {"id", "title", "owner_person_id"}, "SELECT id,COALESCE(title,'资源 #' || id) AS item_label FROM v06_market_resources WHERE owner_person_id=:id ORDER BY id", "/resources/{id}", "仅资源详情确认无下游记录时可安全删除；否则关闭归档。"),
        ("matches", "资源匹配", "p4_resource_match_candidates", {"id", "recommended_person_id"}, "SELECT id,'匹配 #' || id AS item_label FROM p4_resource_match_candidates WHERE recommended_person_id=:id ORDER BY id", "/matches/{id}", "匹配结果属于业务证据，不随人物删除。"),
        ("opportunities", "合作机会", "v06_opportunities", {"id", "title", "target_person_id"}, "SELECT id,COALESCE(title,'机会 #' || id) AS item_label FROM v06_opportunities WHERE target_person_id=:id ORDER BY id", "/opportunities/{id}", "机会应按现有流程关闭或保留，不物理删除。"),
        ("memberships", "俱乐部会员", "v04f_club_memberships", {"id", "member_no", "person_id"}, "SELECT id,COALESCE(member_no,'会员 #' || id) AS item_label FROM v04f_club_memberships WHERE person_id=:id ORDER BY id", "/club/members/{id}", "错误绑定可在会员详情修正；退出会员使用现有停用/退出流程。"),
        ("events", "俱乐部活动", "v05c_club_event_profiles", {"id", "event_no", "guests"}, "SELECT id,COALESCE(event_no,'活动 #' || id) AS item_label FROM v05c_club_event_profiles WHERE guests LIKE '%' || :name || '%' ORDER BY id", "/club/events/{id}", "真实活动历史应保留。"),
    ]
    details = [
        _reference_category(db, params, key=key, label=label, table_name=table, required_columns=columns, sql=sql, url_template=url, cleanup_guidance=guidance)
        for key, label, table, columns, sql, url, guidance in specs
    ]
    if _table_columns(db, "v06_follow_ups") and _table_columns(db, "v06_opportunities"):
        rows = [dict(row) for row in db.execute(text("""
            SELECT f.id,f.opportunity_id,COALESCE(NULLIF(f.content,''),'跟进 #' || f.id) AS item_label
            FROM v06_follow_ups f JOIN v06_opportunities o ON o.id=f.opportunity_id
            WHERE o.target_person_id=:id
            ORDER BY f.id
        """), params).mappings().all()]
    else:
        rows = []
    details.insert(5, {"key": "follow_ups", "label": "跟进事项", "count": len(rows), "items": [
        {"id": row["id"], "label": str(row["item_label"]), "url": f"/opportunities/{row['opportunity_id']}"} for row in rows
    ], "cleanup_guidance": "跟进记录不得随人物删除；请保留人物或在机会中继续处理。"})
    return _classify_subject_references(db, person, "person", details)


def person_reference_reasons(db: Session, person: Person) -> list[str]:
    return [f"{item['label']} {item['count']} 条" for item in person_reference_details(db, person) if item["count"] and item["classification"] == "BUSINESS_HISTORY"]


def _classify_subject_references(db, subject, kind, details):
    """Allowlisted business-impact policy; unrecognised references remain protected."""
    params = {"id": subject.id, "sid": str(subject.id), "external": subject.external_id, "kind": kind}
    extras = [
        ("aliases", "主体别名", "p3_entity_aliases", "entity_type=:kind AND entity_id IN (:sid,:external)"),
        ("identifiers", "主体外部标识（保留）", "p3_entity_external_identifiers", "entity_type=:kind AND entity_id IN (:sid,:external)"),
        ("redirects", "主体合并历史（保留）", "p3_entity_redirects", "entity_type=:kind AND status='active' AND (source_entity_id IN (:sid,:external) OR target_entity_id IN (:sid,:external))"),
        ("favorites", "收藏", "v06_favorites", "target_type=:kind AND target_id=:id"),
        ("follows", "关注", "v06_follows", "target_type=:kind AND target_id=:id"),
        ("knowledge", "知识关联", "knowledge_links", "target_type=:kind AND target_id=:id"),
        ("room_bookings", "会议室预约历史", "club_facility_bookings", f"{kind}_id=:id"),
        ("applications", "会员申请历史", "v04f_club_applications", f"matched_{kind}_id=:id"),
    ]
    if kind == "person":
        extras.append(("accounts", "账号人物绑定", "v05a_users", "person_id=:id"))
        if _table_columns(db, "v05h_generated_reports"):
            params["name"] = subject.name
            extras.append(("reports", "报告引用", "v05h_generated_reports", "title LIKE '%' || :name || '%' OR summary LIKE '%' || :name || '%' OR content_markdown LIKE '%' || :name || '%'"))
    for key, label, table, where in extras:
        columns = _table_columns(db, table)
        if not columns or (key == "accounts" and "person_id" not in columns):
            continue
        rows = db.execute(text(f"SELECT id FROM {table} WHERE {where}"), params).scalars().all()
        details.append({"key": key, "label": label, "table": table, "count": len(rows), "items": [
            {"id": i, "label": f"{label} #{i}", "url": f"/reports/{i}" if key == "reports" else f"/admin/club-facilities/bookings/{i}" if key == "room_bookings" else ""} for i in rows]})
    owned = {"profile", "tags", "aliases", "favorites", "follows"}
    detachable = {"identity_links", "accounts", "user_links", "membership_links", "user_roles", "memberships", "knowledge"}
    for category in details:
        key = category["key"]
        classification = "OWNED_METADATA" if key in owned else "DETACHABLE_ASSOCIATION" if key in detachable else "BUSINESS_HISTORY"
        category["classification"] = classification
        if classification == "OWNED_METADATA":
            category["cleanup_guidance"] = "主体附属资料，删除主体时自动清理。"
        elif classification == "DETACHABLE_ASSOCIATION":
            category["cleanup_guidance"] = "解除主体绑定；保留账号、会员、知识及操作历史。"
        else:
            category.setdefault("cleanup_guidance", "正式历史不随主体删除；请保留或停用主体。")
    # Only exact current employer bindings can be detached; free-text/multiple employers are protected.
    for category in list(details):
        safe = []
        if category["key"] == "people":
            safe = [i for i in category["items"] if db.execute(text("SELECT organization_network FROM people WHERE id=:id"), {"id": i["id"]}).scalar() == subject.standard_name]
        elif category["key"] == "resources":
            from app.services.unified_resource_service import UnifiedResourceService
            service = UnifiedResourceService(db)
            for item in category["items"]:
                status = db.execute(text("SELECT status FROM v06_market_resources WHERE id=:id"), {"id": item["id"]}).scalar()
                if status == "draft" and not any(service.reference_counts(item["id"]).values()):
                    safe.append(item)
        if safe:
            details.append({**category, "key": category["key"] + "_detach", "items": safe, "count": len(safe),
                            "classification": "DETACHABLE_ASSOCIATION", "cleanup_guidance": "仅解除当前归属，保留人物/草稿资源本身。"})
            safe_ids = {i["id"] for i in safe}
            category["items"] = [i for i in category["items"] if i["id"] not in safe_ids]
            category["count"] = len(category["items"])
    return details


def reference_fingerprint(details):
    import hashlib
    import json
    payload = [(d["key"], d["classification"], sorted(i["id"] for i in d["items"])) for d in details]
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def delete_subject(db, subject, *, actor, actor_user_id=None, archive_relationship_ids=(), reason="", permissions=frozenset(), preview_token=None):
    """One transaction. Check history before any cleanup; caller commits or rolls back."""
    import sqlite3
    from fastapi import HTTPException
    from app.services.canonical_relationship_service import CanonicalRelationshipService
    from app.services.club_operations_service import ClubMembershipService, record_audit
    from app.services.unified_resource_service import UnifiedResourceService
    kind = "person" if isinstance(subject, Person) else "organization"
    conn = db.connection().connection.driver_connection
    if not conn.in_transaction:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
    details = person_reference_details(db, subject) if kind == "person" else organization_reference_details(db, subject)
    if preview_token is not None and preview_token != reference_fingerprint(details):
        raise HTTPException(409, "引用已变化或缺少影响预览，请刷新页面重新确认")
    selected = set(archive_relationship_ids)
    relationships = {i["id"] for d in details if d["key"] == "relationships" for i in d["items"]}
    if not selected.issubset(relationships) or (selected and ("review_data" not in permissions or not reason.strip())):
        raise HTTPException(409, "关系选择已变化或未确认原因，请刷新后重新核对")
    blocked = [d for d in details if d["count"] and d["classification"] == "BUSINESS_HISTORY"
               and not (d["key"] == "relationships" and relationships <= selected)]
    if blocked:
        raise HTTPException(409, "存在正式历史：" + "；".join(f"{d['label']} {d['count']}条" for d in blocked) + "。建议停用并保留历史。")
    factory = conn.row_factory
    conn.row_factory = sqlite3.Row
    path = db.get_bind().url.database
    try:
        before = {"id": subject.id, "external_id": subject.external_id, "name": subject.name if kind == "person" else subject.standard_name}
        for rid in selected:
            CanonicalRelationshipService(path).archive(rid, actor=actor, permissions=set(permissions), reason=reason, connection=conn)
        snapshots = []
        for category in details:
            if category["classification"] == "BUSINESS_HISTORY":
                continue
            for item in category["items"]:
                table, key, identifier = category["table"], category["key"], item["id"]
                # Never put credentials or private account fields into the cleanup audit.
                columns = "id,person_id" if key == "accounts" else "*"
                row = conn.execute(f"SELECT {columns} FROM {table} WHERE id=?", (identifier,)).fetchone()
                snapshots.append({"type": key, "before": dict(row)})
                if key == "memberships":
                    ClubMembershipService(path).detach_subject(identifier, subject_type=kind, subject_id=subject.id, conn=conn, actor=actor, actor_user_id=actor_user_id)
                elif key == "accounts":
                    conn.execute("UPDATE v05a_users SET person_id=NULL,session_version=session_version+1 WHERE id=?", (identifier,))
                elif key == "people_detach":
                    conn.execute("UPDATE people SET organization_network=NULL WHERE id=?", (identifier,))
                elif key == "resources_detach":
                    UnifiedResourceService(db).detach_subject(identifier, subject_type=kind, subject_id=subject.id)
                else:
                    conn.execute(f"DELETE FROM {table} WHERE id=?", (identifier,))
        record_audit(conn, action="subject.safe_delete", target_type=kind, target_id=subject.id,
                     actor=actor, actor_user_id=actor_user_id, before={**before, "dependencies": snapshots},
                     after={"deleted": True, "archived_relationships": sorted(selected)}, reason=reason or "管理员安全删除")
        db.delete(subject)
        db.flush()
    finally:
        conn.row_factory = factory
