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


def organization_reference_reasons(db: Session, org: Organization) -> list[str]:
    params = {"id": int(org.id), "sid": str(org.id), "external": org.external_id, "name": org.standard_name}
    checks = [
        ("people", {"organization_network"}, "SELECT COUNT(*) FROM people WHERE organization_network=:name OR organization_network LIKE '%' || :name || '%'", "关联人物"),
        ("p3_canonical_relationships", {"subject_type", "subject_id", "object_type", "object_id"}, "SELECT COUNT(*) FROM p3_canonical_relationships WHERE (subject_type='organization' AND CAST(subject_id AS TEXT) IN (:sid,:external)) OR (object_type='organization' AND CAST(object_id AS TEXT) IN (:sid,:external))", "正式关系"),
        ("core_intelligence_subject_links", {"subject_type", "subject_id"}, "SELECT COUNT(*) FROM core_intelligence_subject_links WHERE subject_type='organization' AND CAST(subject_id AS TEXT) IN (:sid,:external)", "情报主体关联"),
        ("v06_market_resources", {"organization_id"}, "SELECT COUNT(*) FROM v06_market_resources WHERE organization_id=:id", "资源"),
        ("p4_resource_match_candidates", {"recommended_organization_id"}, "SELECT COUNT(*) FROM p4_resource_match_candidates WHERE recommended_organization_id=:id", "资源匹配"),
        ("v06_opportunities", {"organization_id", "target_organization_id", "demand_organization_id", "supply_organization_id"}, "SELECT COUNT(*) FROM v06_opportunities WHERE :id IN (organization_id,target_organization_id,demand_organization_id,supply_organization_id)", "合作机会"),
        ("v04f_club_memberships", {"organization_id"}, "SELECT COUNT(*) FROM v04f_club_memberships WHERE organization_id=:id", "Q-BAY会员"),
        ("v05c_club_event_profiles", {"organizer", "co_organizer"}, "SELECT COUNT(*) FROM v05c_club_event_profiles WHERE organizer=:name OR co_organizer LIKE '%' || :name || '%'", "俱乐部活动"),
        ("v05h_generated_reports", {"title", "summary", "content_markdown"}, "SELECT COUNT(*) FROM v05h_generated_reports WHERE title LIKE '%' || :name || '%' OR summary LIKE '%' || :name || '%' OR content_markdown LIKE '%' || :name || '%'", "报告"),
    ]
    reasons = []
    for table_name, columns, sql, label in checks:
        count = _count_if_available(db, table_name, columns, sql, params)
        if count:
            reasons.append(f"{label} {count} 条")
    if _table_columns(db, "v06_follow_ups") and _table_columns(db, "v06_opportunities"):
        count = int(db.execute(text("""
            SELECT COUNT(*) FROM v06_follow_ups f JOIN v06_opportunities o ON o.id=f.opportunity_id
            WHERE :id IN (o.organization_id,o.target_organization_id,o.demand_organization_id,o.supply_organization_id)
        """), params).scalar() or 0)
        if count:
            reasons.append(f"跟进 {count} 条")
    return reasons


def person_reference_reasons(db: Session, person: Person) -> list[str]:
    params = {"id": int(person.id), "sid": str(person.id), "external": person.external_id, "name": person.name}
    checks = [
        ("p3_canonical_relationships", {"subject_type", "subject_id", "object_type", "object_id"}, "SELECT COUNT(*) FROM p3_canonical_relationships WHERE (subject_type='person' AND CAST(subject_id AS TEXT) IN (:sid,:external)) OR (object_type='person' AND CAST(object_id AS TEXT) IN (:sid,:external))", "正式关系"),
        ("core_intelligence_subject_links", {"subject_type", "subject_id"}, "SELECT COUNT(*) FROM core_intelligence_subject_links WHERE subject_type='person' AND CAST(subject_id AS TEXT) IN (:sid,:external)", "情报主体关联"),
        ("v06_market_resources", {"owner_person_id"}, "SELECT COUNT(*) FROM v06_market_resources WHERE owner_person_id=:id", "资源"),
        ("p4_resource_match_candidates", {"recommended_person_id"}, "SELECT COUNT(*) FROM p4_resource_match_candidates WHERE recommended_person_id=:id", "资源匹配"),
        ("v06_opportunities", {"target_person_id"}, "SELECT COUNT(*) FROM v06_opportunities WHERE target_person_id=:id", "合作机会"),
        ("v04f_club_memberships", {"person_id"}, "SELECT COUNT(*) FROM v04f_club_memberships WHERE person_id=:id", "Q-BAY会员"),
        ("v05c_club_event_profiles", {"guests"}, "SELECT COUNT(*) FROM v05c_club_event_profiles WHERE guests LIKE '%' || :name || '%'", "俱乐部活动"),
    ]
    reasons = []
    for table_name, columns, sql, label in checks:
        count = _count_if_available(db, table_name, columns, sql, params)
        if count:
            reasons.append(f"{label} {count} 条")
    if _table_columns(db, "v06_follow_ups") and _table_columns(db, "v06_opportunities"):
        count = int(db.execute(text("""
            SELECT COUNT(*) FROM v06_follow_ups f JOIN v06_opportunities o ON o.id=f.opportunity_id
            WHERE o.target_person_id=:id
        """), params).scalar() or 0)
        if count:
            reasons.append(f"跟进 {count} 条")
    return reasons
