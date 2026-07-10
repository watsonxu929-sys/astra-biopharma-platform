from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import Organization, Person, Relation
from .id_generator import assign_system_id


def normalize_name(value: str | None) -> str:
    return re.sub(r"[\s　]+", "", (value or "").strip()).lower()


def lookup_organizations(db: Session, query: str, limit: int = 10) -> list[Organization]:
    value = (query or "").strip()
    if not value:
        return []
    lowered = value.lower()
    exact_first = db.scalars(
        select(Organization)
        .where(
            Organization.is_active.is_(True),
            or_(
                func.lower(func.trim(Organization.external_id)) == lowered,
                func.lower(func.trim(Organization.standard_name)) == lowered,
            ),
        )
        .order_by(Organization.standard_name)
        .limit(limit)
    ).all()
    if exact_first:
        return list(exact_first)

    pattern = f"%{value}%"
    rows = db.scalars(
        select(Organization)
        .where(
            Organization.is_active.is_(True),
            or_(
                Organization.external_id.like(pattern),
                Organization.standard_name.like(pattern),
            ),
        )
        .order_by(Organization.standard_name)
        .limit(limit)
    ).all()
    return list(rows)


def resolve_organization(db: Session, reference: str | None) -> tuple[Organization | None, list[Organization]]:
    value = (reference or "").strip()
    if not value:
        return None, []
    candidates = lookup_organizations(db, value, limit=10)
    lowered = value.lower()
    exact = [
        row
        for row in candidates
        if (row.external_id or "").strip().lower() == lowered
        or (row.standard_name or "").strip().lower() == lowered
    ]
    if len(exact) == 1:
        return exact[0], candidates
    return None, candidates


def person_has_org_relation(
    db: Session,
    person_external_id: str,
    organization_external_id: str,
    relation_types: tuple[str, ...] = ("任职", "创立", "董事", "顾问", "管理"),
) -> bool:
    row = db.scalar(
        select(Relation.id).where(
            Relation.is_active.is_(True),
            Relation.source_external_id == person_external_id,
            Relation.target_external_id == organization_external_id,
            Relation.relation_type.in_(relation_types),
        )
    )
    return row is not None


def person_organization_names(db: Session, person_external_id: str) -> list[str]:
    org_ids = db.scalars(
        select(Relation.target_external_id).where(
            Relation.is_active.is_(True),
            Relation.source_external_id == person_external_id,
            Relation.relation_type.in_(("任职", "创立", "董事", "顾问", "管理")),
        )
    ).all()
    if not org_ids:
        return []
    rows = db.scalars(
        select(Organization).where(
            Organization.is_active.is_(True),
            Organization.external_id.in_(list(org_ids)),
        )
    ).all()
    return [row.standard_name for row in rows]


def ensure_person_organization_relation(
    db: Session,
    *,
    person: Person,
    organization: Organization,
    relation_type: str = "任职",
    public_role: str = "",
    source_url: str = "",
    source_title: str = "",
    source_text: str = "",
) -> tuple[Relation, bool]:
    existing = db.scalar(
        select(Relation).where(
            Relation.is_active.is_(True),
            Relation.source_external_id == person.external_id,
            Relation.target_external_id == organization.external_id,
            Relation.relation_type == relation_type,
        )
    )
    if existing:
        return existing, False

    evidence_parts = []
    if public_role.strip():
        evidence_parts.append(f"职位：{public_role.strip()}")
    if source_title.strip():
        evidence_parts.append(f"来源标题：{source_title.strip()}")
    if source_url.strip():
        evidence_parts.append(f"来源链接：{source_url.strip()}")

    relation = Relation(
        external_id="",
        source_external_id=person.external_id,
        relation_type=relation_type or "任职",
        target_external_id=organization.external_id,
        period=None,
        evidence_source="\n".join(evidence_parts) or "团队页批量采集人工确认",
        visibility="内部",
        verification_status="待核验",
        source_url=source_url.strip()[:2000] or None,
        source_type="公开网页（批量人工核对）",
        source_title=source_title.strip()[:300] or None,
        source_text=source_text.strip()[:10000] or None,
        captured_at=datetime.now(),
        analyzed_at=datetime.now(),
        model_version="local-rule-v0.4D4",
        manually_confirmed=True,
        auto_generated_fields="external_id,人物-机构关联",
        confirmed_fields="批量人物逐条核对并统一关联机构",
        is_active=True,
    )
    assign_system_id(db, relation, "relations")
    db.add(relation)
    db.commit()
    db.refresh(relation)
    return relation, True


def relation_view_rows(db: Session, relations: list[Relation]) -> list[dict[str, Any]]:
    ids = {
        value
        for relation in relations
        for value in (relation.source_external_id, relation.target_external_id)
        if value
    }
    organizations = {
        row.external_id: row
        for row in db.scalars(select(Organization).where(Organization.external_id.in_(ids))).all()
    } if ids else {}
    people = {
        row.external_id: row
        for row in db.scalars(select(Person).where(Person.external_id.in_(ids))).all()
    } if ids else {}

    def subject(external_id: str) -> dict[str, Any]:
        org = organizations.get(external_id)
        if org:
            return {
                "external_id": external_id,
                "label": org.standard_name,
                "kind": "机构",
                "url": f"/organizations/{org.id}",
            }
        person = people.get(external_id)
        if person:
            return {
                "external_id": external_id,
                "label": person.name,
                "kind": "人物",
                "url": f"/people/{person.id}",
            }
        return {
            "external_id": external_id,
            "label": external_id or "未知主体",
            "kind": "未知",
            "url": None,
        }

    output: list[dict[str, Any]] = []
    for relation in relations:
        output.append({
            "relation": relation,
            "source": subject(relation.source_external_id),
            "target": subject(relation.target_external_id),
        })
    return output
