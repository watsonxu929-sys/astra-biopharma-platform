from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session


PREFIX_BY_ENTITY = {
    "organizations": "ORG",
    "people": "PER",
    "projects": "PRJ",
    "resources": "RES",
    "events": "EVT",
    "relations": "REL",
    "actions": "ACT",
}

VALID_ID_PATTERN = re.compile(r"^[A-Z]{3}-\d{8}-\d{6}$")


def is_valid_system_id(value: str | None) -> bool:
    return bool(value and VALID_ID_PATTERN.match(value))


def next_system_id(db: Session, model: Any, prefix: str, day: str | None = None) -> str:
    today = day or datetime.now().strftime("%Y%m%d")
    stem = f"{prefix}-{today}-"
    existing = db.scalars(
        select(model.external_id).where(model.external_id.like(f"{stem}%"))
    ).all()
    max_seq = 0
    for value in existing:
        if not value:
            continue
        tail = str(value).replace(stem, "", 1)
        if tail.isdigit():
            max_seq = max(max_seq, int(tail))
    return f"{stem}{max_seq + 1:06d}"


def assign_system_id(db: Session, obj: Any, entity_key: str) -> None:
    if is_valid_system_id(getattr(obj, "external_id", None)):
        return
    prefix = PREFIX_BY_ENTITY[entity_key]
    obj.external_id = next_system_id(db, obj.__class__, prefix)
