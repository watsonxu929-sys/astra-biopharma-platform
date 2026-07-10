from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..models import (
    ActionItem,
    HistoricalEvent,
    Organization,
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
