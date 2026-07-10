"""v0.6 Platform services -- network, intelligence, resources, collaboration, search."""
from datetime import datetime
from typing import Any
from sqlalchemy import and_, desc, func, or_, select, text
from sqlalchemy.orm import Session

from app.models_platform import (
    IndustryTag, PersonTag, OrganizationTag, PersonProfile,
    Favorite, Follow, ContactIntent,
    IntelligenceItem, IntelSubscription,
    MarketResource, CooperationOpportunity,
    FollowUp, CollabTask, TimelineEntry,
)
from app.models import Organization, Person


def get_user_person(db: Session, user_id: int | None) -> Person | None:
    """Return the approved Person profile linked to a user, if any."""
    if user_id is None:
        return None
    try:
        row = db.execute(text("""
            SELECT p.id FROM people p
            JOIN identity_link_requests l ON p.id = l.person_id
            WHERE l.user_id = :uid AND l.status = 'approved' AND p.is_active = 1
            ORDER BY l.id DESC LIMIT 1
        """), {"uid": int(user_id)}).mappings().first()
    except Exception:
        return None
    return db.get(Person, int(row["id"])) if row else None

def mask_contact(value: str | None, *, kind: str = "") -> str | None:
    text_value = str(value or "").strip()
    if not text_value:
        return None
    if kind == "email" and "@" in text_value:
        name, domain = text_value.split("@", 1)
        return f"{name[:2]}***@{domain}"
    if kind == "phone":
        digits = "".join(ch for ch in text_value if ch.isdigit())
        if len(digits) >= 7:
            return f"{digits[:3]}****{digits[-4:]}"
    return "***"


def serialize_person_summary(db: Session, person: Person, *, include_contact: bool = False) -> dict[str, Any]:
    profile = get_person_profile(db, person.id)
    tags = get_person_tags(db, person.id)
    data: dict[str, Any] = {
        "id": person.id, "external_id": person.external_id, "name": person.name,
        "public_role": person.public_role, "organization_network": person.organization_network,
        "ability_tags": person.ability_tags, "tags": tags,
        "profile": {
            "title": getattr(profile, "title", None), "bio": getattr(profile, "bio", None),
            "city": getattr(profile, "city", None), "province": getattr(profile, "province", None),
            "cooperation_preferences": getattr(profile, "cooperation_preferences", None),
            "avatar_url": getattr(profile, "avatar_url", None),
            "contact_visibility": getattr(profile, "contact_visibility", "private") if profile else "private",
        },
    }
    if profile and include_contact and profile.contact_visibility != "private":
        data["contact"] = {
            "email": mask_contact(profile.contact_email, kind="email"),
            "phone": mask_contact(profile.contact_phone, kind="phone"),
            "wechat": mask_contact(profile.contact_wechat),
            "visibility": profile.contact_visibility,
        }
    return data


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Identity / Profile
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

def get_person_profile(db: Session, person_id: int) -> PersonProfile | None:
    return db.scalar(select(PersonProfile).where(PersonProfile.person_id == person_id))


def upsert_person_profile(db: Session, person_id: int, **fields) -> PersonProfile:
    profile = get_person_profile(db, person_id)
    if profile:
        for k, v in fields.items():
            if hasattr(profile, k):
                setattr(profile, k, v)
        profile.updated_at = datetime.now()
    else:
        profile = PersonProfile(person_id=person_id, **fields)
        db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def get_person_tags(db: Session, person_id: int) -> list[dict]:
    rows = db.execute(
        select(IndustryTag)
        .join(PersonTag, IndustryTag.id == PersonTag.tag_id)
        .where(PersonTag.person_id == person_id)
    ).scalars().all()
    return [{"id": t.id, "tag_key": t.tag_key, "tag_group": t.tag_group, "label": t.label} for t in rows]


def set_person_tags(db: Session, person_id: int, tag_ids: list[int]):
    """Replace all tags for a person with given tag_ids."""
    db.execute(text("DELETE FROM v06_person_tags WHERE person_id = :pid"), {"pid": person_id})
    for tid in tag_ids:
        db.add(PersonTag(person_id=person_id, tag_id=tid))
    db.commit()


def get_person_full_profile(db: Session, person_id: int) -> dict:
    """Combine Person + PersonProfile + tags."""
    person = db.get(Person, person_id)
    if not person:
        return {}
    profile = get_person_profile(db, person_id)
    tags = get_person_tags(db, person_id)
    return {
        "person": person,
        "profile": profile,
        "tags": tags,
        "user_types": [t for t in tags if t["tag_group"] == "user_type"],
        "industry_directions": [t for t in tags if t["tag_group"] == "industry_direction"],
        "capabilities": [t for t in tags if t["tag_group"] == "capability"],
        "needs": [t for t in tags if t["tag_group"] == "need"],
    }


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Tag management
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

def list_tags(db: Session, tag_group: str | None = None) -> list[IndustryTag]:
    stmt = select(IndustryTag).where(IndustryTag.is_active == True).order_by(IndustryTag.tag_group, IndustryTag.sort_order)
    if tag_group:
        stmt = stmt.where(IndustryTag.tag_group == tag_group)
    return list(db.scalars(stmt).all())


def seed_default_tags(db: Session):
    """Seed default industry tags. Idempotent."""
    defaults = {
        "user_type": [
            "Founder", "Executive", "Researcher", "Clinician", "Technical Expert",
            "Investor", "FA", "Broker", "Secondary Market Researcher", "Government",
            "Park??", "Incubator", "Industrial Service", "CRO/CDMO", "Regulatory Service",
            "Instrument Supplier", "Lab Service", "University", "Hospital", "Sales", "BD",
            "Job Seeker", "Consultant", "Freelancer", "Association", "Media", "Conference Organizer", "Other",
        ],
        "industry_direction": [
            "Innovative Drug", "Biologic", "Chemical Drug", "TCM", "Medical Device", "Diagnostics",
            "Gene and Cell Therapy", "Synthetic Biology", "AI Drug Discovery", "Healthcare Service",
            "Research Service", "Lab Construction", "Instrument and Consumables", "Industrial Investment",
            "Park and Attraction", "Other",
        ],
        "capability": [
            "Drug Discovery", "Preclinical Research", "Clinical Research", "Regulatory Filing",
            "Quality Management", "Manufacturing Process", "Business Development", "Financing",
            "Market Access", "Sales Channel", "Government Affairs", "Park Attraction",
            "Lab Construction", "Instrument Application", "Industry Research",
        ],
        "need": [
            "Find Financing", "Find Project", "Find Technology", "Find Expert", "Find Customer",
            "Find Channel", "Find Supplier", "Find Site", "Find Talent", "Find Job",
            "Find Partner", "Find Park Policy",
        ],
    }
    for group, labels in defaults.items():
        for i, label in enumerate(labels):
            tag_key = f"{group}:{label}"
            existing = db.scalar(select(IndustryTag).where(IndustryTag.tag_key == tag_key))
            if not existing:
                db.add(IndustryTag(tag_key=tag_key, tag_group=group, label=label, sort_order=i))
    db.commit()


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Favorites
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

def toggle_favorite(db: Session, user_id: int, target_type: str, target_id: int) -> dict:
    existing = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.target_type == target_type,
            Favorite.target_id == target_id,
        )
    )
    if existing:
        db.delete(existing)
        db.commit()
        return {"favorited": False}
    db.add(Favorite(user_id=user_id, target_type=target_type, target_id=target_id))
    db.commit()
    return {"favorited": True}


def is_favorited(db: Session, user_id: int, target_type: str, target_id: int) -> bool:
    return db.scalar(
        select(func.count()).select_from(Favorite).where(
            Favorite.user_id == user_id,
            Favorite.target_type == target_type,
            Favorite.target_id == target_id,
        )
    ) > 0


def list_favorites(db: Session, user_id: int, target_type: str | None = None) -> list[Favorite]:
    stmt = select(Favorite).where(Favorite.user_id == user_id).order_by(desc(Favorite.created_at))
    if target_type:
        stmt = stmt.where(Favorite.target_type == target_type)
    return list(db.scalars(stmt).all())


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Follows
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

def toggle_follow(db: Session, user_id: int, target_type: str, target_id: int) -> dict:
    existing = db.scalar(
        select(Follow).where(
            Follow.user_id == user_id,
            Follow.target_type == target_type,
            Follow.target_id == target_id,
        )
    )
    if existing:
        db.delete(existing)
        db.commit()
        return {"following": False}
    db.add(Follow(user_id=user_id, target_type=target_type, target_id=target_id))
    db.commit()
    return {"following": True}


def is_following(db: Session, user_id: int, target_type: str, target_id: int) -> bool:
    return db.scalar(
        select(func.count()).select_from(Follow).where(
            Follow.user_id == user_id,
            Follow.target_type == target_type,
            Follow.target_id == target_id,
        )
    ) > 0


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Contact Intents
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

def create_contact_intent(db: Session, from_user_id: int, target_type: str, target_id: int, intent_type: str, message: str) -> ContactIntent:
    ci = ContactIntent(
        from_user_id=from_user_id,
        target_type=target_type,
        target_id=target_id,
        intent_type=intent_type,
        message=message,
    )
    db.add(ci)
    db.commit()
    db.refresh(ci)
    return ci


def respond_contact_intent(db: Session, intent_id: int, status: str, response_message: str, responded_by: int) -> ContactIntent | None:
    ci = db.get(ContactIntent, intent_id)
    if not ci:
        return None
    ci.status = status
    ci.response_message = response_message
    ci.responded_at = datetime.now()
    ci.responded_by = responded_by
    db.commit()
    return ci


def list_contact_intents(db: Session, user_id: int, direction: str = "sent") -> list[ContactIntent]:
    if direction == "sent":
        stmt = select(ContactIntent).where(ContactIntent.from_user_id == user_id).order_by(desc(ContactIntent.created_at))
    else:
        stmt = select(ContactIntent).where(ContactIntent.target_id == user_id).order_by(desc(ContactIntent.created_at))
    return list(db.scalars(stmt).all())


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Person Discovery & Recommendations (rule-based)
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

def discover_people(
    db: Session,
    current_user_id: int | None = None,
    name: str = "",
    user_type: str = "",
    industry_direction: str = "",
    capability: str = "",
    need: str = "",
    organization: str = "",
    region: str = "",
    member_status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    """Filtered person discovery with profile and tag enrichment."""
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or 20), 100))
    stmt = select(Person).where(Person.is_active == True)
    if name:
        stmt = stmt.where(or_(Person.name.contains(name), Person.public_role.contains(name), Person.organization_network.contains(name)))
    if organization:
        stmt = stmt.where(Person.organization_network.contains(organization))
    if region:
        person_ids = db.execute(select(PersonProfile.person_id).where(or_(PersonProfile.city.contains(region), PersonProfile.province.contains(region)))).scalars().all()
        stmt = stmt.where(Person.id.in_(person_ids) if person_ids else False)
    for group, value in (("user_type", user_type), ("industry_direction", industry_direction), ("capability", capability), ("need", need)):
        if value:
            tag_ids = [t.id for t in list_tags(db, group) if value in t.label]
            if tag_ids:
                person_ids = db.execute(select(PersonTag.person_id).where(PersonTag.tag_id.in_(tag_ids))).scalars().all()
                stmt = stmt.where(Person.id.in_(person_ids) if person_ids else False)
    if member_status:
        rows = db.execute(text("SELECT person_id FROM v04f_club_memberships WHERE status = :status AND person_id IS NOT NULL"), {"status": member_status}).fetchall()
        member_person_ids = [int(row[0]) for row in rows]
        stmt = stmt.where(Person.id.in_(member_person_ids) if member_person_ids else False)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    people = list(db.scalars(stmt.order_by(Person.name).offset((page - 1) * page_size).limit(page_size)).all())
    items = []
    for person in people:
        item = serialize_person_summary(db, person)
        item["profile_model"] = get_person_profile(db, person.id)
        items.append(item)
    return {
        "items": items, "total": total, "page": page, "page_size": page_size,
        "applied_filters": {"keyword": name, "industry_type": user_type, "industry_direction": industry_direction, "capability_tag": capability, "need_tag": need, "organization_id": "", "organization": organization, "region": region, "membership_status": member_status},
    }


def recommend_people(db: Session, current_user_id: int | None, limit: int = 12) -> list[dict]:
    """Rule-based person recommendations with readable reasons."""
    my_person = get_user_person(db, current_user_id)
    recommendation_type = "personalized" if my_person else "public_hot"
    my_tags = get_person_tags(db, my_person.id) if my_person else []
    exclude_id = my_person.id if my_person else -1
    people = list(db.scalars(select(Person).where(Person.is_active == True, Person.id != exclude_id).limit(200)).all())
    recommendations = []
    for person in people:
        score = 0
        reasons = []
        person_tags = get_person_tags(db, person.id)
        person_profile = get_person_profile(db, person.id)
        my_dirs = {t["tag_key"] for t in my_tags if t["tag_group"] == "industry_direction"}
        their_dirs = {t["tag_key"] for t in person_tags if t["tag_group"] == "industry_direction"}
        common_dirs = my_dirs & their_dirs
        if common_dirs:
            score += 30
            reasons.append("shared industry direction")
        my_needs = {t["tag_key"] for t in my_tags if t["tag_group"] == "need"}
        their_caps = {t["tag_key"] for t in person_tags if t["tag_group"] == "capability"}
        matched_caps = my_needs & their_caps
        if matched_caps:
            score += 40
            reasons.append("need matches capability")
        my_caps = {t["tag_key"] for t in my_tags if t["tag_group"] == "capability"}
        their_needs = {t["tag_key"] for t in person_tags if t["tag_group"] == "need"}
        matched_needs = my_caps & their_needs
        if matched_needs:
            score += 40
            reasons.append("capability matches need")
        if my_person and person.organization_network and my_person.organization_network and person.organization_network == my_person.organization_network:
            score += 20
            reasons.append("capability matches need")
        if not my_person:
            score += 10
            reasons.append("\u516c\u5f00\u6d3b\u8dc3\u4ea7\u4e1a\u4eba\u7269")
        if current_user_id:
            existing_contact = db.scalar(select(func.count()).select_from(ContactIntent).where(ContactIntent.from_user_id == current_user_id, ContactIntent.target_type == "person", ContactIntent.target_id == person.id, ContactIntent.status == "accepted"))
            if existing_contact and existing_contact > 0:
                score -= 50
        if score > 0:
            matched_ids = {tag["id"] for tag in my_tags} & {tag["id"] for tag in person_tags}
            recommendations.append({"person_id": person.id, "person": serialize_person_summary(db, person), "name": person.name, "public_role": person.public_role, "organization_network": person.organization_network, "tags": person_tags, "profile": person_profile, "score": score, "reasons": reasons, "matched_tags": [t["label"] for t in person_tags if t["id"] in matched_ids], "recommendation_type": recommendation_type})
    recommendations.sort(key=lambda x: x["score"], reverse=True)
    return recommendations[:limit]


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Intelligence
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

def list_intelligence(
    db: Session,
    user_id: int | None = None,
    intel_type: str = "",
    industry_direction: str = "",
    q: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    stmt = select(IntelligenceItem).where(
        IntelligenceItem.status == "published",
        IntelligenceItem.visibility.in_(["public", "organization"]),
    )
    if intel_type:
        stmt = stmt.where(IntelligenceItem.intel_type == intel_type)
    if industry_direction:
        stmt = stmt.where(IntelligenceItem.industry_directions.contains(industry_direction))
    if q:
        stmt = stmt.where(
            or_(
                IntelligenceItem.title.contains(q),
                IntelligenceItem.summary.contains(q),
                IntelligenceItem.content.contains(q),
            )
        )
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(db.scalars(stmt.order_by(desc(IntelligenceItem.published_at), desc(IntelligenceItem.created_at)).offset((page - 1) * page_size).limit(page_size)).all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def personalized_feed(db: Session, user_id: int, limit: int = 20) -> list[dict]:
    """Generate rule-based personalized intelligence feed."""
    if not user_id:
        items = list(db.scalars(
            select(IntelligenceItem).where(IntelligenceItem.status == "published", IntelligenceItem.visibility == "public")
            .order_by(desc(IntelligenceItem.published_at)).limit(limit)
        ).all())
        return [{"item": i, "reason": "鍏紑鎯呮姤"} for i in items]

    tags = get_person_tags(db, user_id)
    my_dirs = [t["label"] for t in tags if t["tag_group"] == "industry_direction"]
    results = []

    all_items = list(db.scalars(
        select(IntelligenceItem).where(
            IntelligenceItem.status == "published",
            IntelligenceItem.visibility.in_(["public", "organization"]),
        ).order_by(desc(IntelligenceItem.published_at)).limit(200)
    ).all())

    for item in all_items:
        score = 0
        reasons = []
        if my_dirs and item.industry_directions:
            for d in my_dirs:
                if d in (item.industry_directions or ""):
                    score += 30
                    reasons.append(f"industry direction: {d}")
                    break
        if item.importance >= 4:
            score += 20
            reasons.append("important intelligence")
        if item.credibility >= 4:
            score += 10
        results.append({"item": item, "score": score, "reasons": reasons})

    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:limit]


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Market Resources
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

def list_market_resources(
    db: Session,
    direction: str = "",
    resource_type: str = "",
    q: str = "",
    industry_direction: str = "",
    region: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    stmt = select(MarketResource).where(MarketResource.status == "published")
    if direction:
        stmt = stmt.where(MarketResource.direction == direction)
    if resource_type:
        stmt = stmt.where(MarketResource.resource_type == resource_type)
    if q:
        stmt = stmt.where(
            or_(MarketResource.title.contains(q), MarketResource.summary.contains(q), MarketResource.description.contains(q))
        )
    if industry_direction:
        stmt = stmt.where(MarketResource.industry_direction.contains(industry_direction))
    if region:
        stmt = stmt.where(MarketResource.region.contains(region))
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    items = list(db.scalars(stmt.order_by(desc(MarketResource.created_at)).offset((page - 1) * page_size).limit(page_size)).all())
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def match_resources(db: Session, resource_id: int, limit: int = 10) -> list[dict]:
    """Rule-based supply-demand matching."""
    resource = db.get(MarketResource, resource_id)
    if not resource:
        return []

    opposite = "demand" if resource.direction == "supply" else "supply"
    candidates = list(db.scalars(
        select(MarketResource).where(
            MarketResource.direction == opposite,
            MarketResource.status == "published",
            MarketResource.id != resource_id,
        ).limit(100)
    ).all())

    matches = []
    for c in candidates:
        score = 0
        reasons = []
        if c.resource_type == resource.resource_type:
            score += 40
            reasons.append("same resource type")
        if resource.industry_direction and c.industry_direction:
            r_dirs = set((resource.industry_direction or "").split(";"))
            c_dirs = set((c.industry_direction or "").split(";"))
            common = r_dirs & c_dirs
            if common:
                score += 30
                reasons.append("shared industry direction")
        if resource.region and c.region and resource.region in (c.region or ""):
            score += 20
            reasons.append("same region")
        if resource.tags and c.tags:
            r_tags = set((resource.tags or "").split(";"))
            c_tags = set((c.tags or "").split(";"))
            common = r_tags & c_tags
            if common:
                score += 10
                reasons.append("shared tags")
        if c.valid_until and c.valid_until < datetime.now():
            continue  # expired
        if score > 0:
            matches.append({"resource": c, "score": score, "reasons": reasons})

    matches.sort(key=lambda x: x["score"], reverse=True)
    return matches[:limit]


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Opportunities
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

def create_opportunity(db: Session, **fields) -> CooperationOpportunity:
    opp = CooperationOpportunity(**fields)
    db.add(opp)
    db.commit()
    db.refresh(opp)
    # Add timeline entry
    db.add(TimelineEntry(
        opportunity_id=opp.id,
        event_type="created",
        description=f"Opportunity {opp.title} created",
        actor_id=fields.get("initiator_id"),
    ))
    db.commit()
    return opp


def update_opportunity_stage(db: Session, opp_id: int, stage: str, actor_id: int) -> CooperationOpportunity | None:
    opp = db.get(CooperationOpportunity, opp_id)
    if not opp:
        return None
    old_stage = opp.stage
    opp.stage = stage
    db.add(TimelineEntry(
        opportunity_id=opp_id,
        event_type="stage_change",
        description=f"Stage changed from {old_stage} to {stage}",
        actor_id=actor_id,
    ))
    db.commit()
    return opp


def get_opportunity_timeline(db: Session, opp_id: int) -> list[TimelineEntry]:
    return list(db.scalars(
        select(TimelineEntry).where(TimelineEntry.opportunity_id == opp_id).order_by(desc(TimelineEntry.created_at))
    ).all())


def create_follow_up(db: Session, **fields) -> FollowUp:
    fu = FollowUp(**fields)
    db.add(fu)
    db.commit()
    db.refresh(fu)
    # Add timeline entry
    db.add(TimelineEntry(
        opportunity_id=fields["opportunity_id"],
        event_type="follow_up",
        description=("Follow-up: " + str(fields.get("content", ""))[:100]),
        actor_id=fields.get("created_by"),
    ))
    db.commit()
    return fu


def create_collab_task(db: Session, **fields) -> CollabTask:
    task = CollabTask(**fields)
    db.add(task)
    db.commit()
    db.refresh(task)
    if task.opportunity_id:
        db.add(TimelineEntry(
            opportunity_id=task.opportunity_id,
            event_type="task",
            description=f"Task created: {task.title}",
            actor_id=fields.get("created_by"),
        ))
        db.commit()
    return task


def list_user_tasks(db: Session, user_id: int, status: str = "") -> list[CollabTask]:
    stmt = select(CollabTask).where(
        or_(CollabTask.owner_id == user_id, CollabTask.participants.contains(str(user_id)))
    ).order_by(desc(CollabTask.created_at))
    if status:
        stmt = stmt.where(CollabTask.status == status)
    return list(db.scalars(stmt).all())


# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?
#  Unified Search
# 鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺愨晲鈺?

def unified_search(db: Session, q: str, limit: int = 10) -> dict:
    """Search across people, organizations, intelligence, resources, opportunities."""
    if not q or len(q.strip()) < 1:
        return {"q": q, "groups": [], "total": 0}

    results = {}
    q_term = f"%{q.strip()}%"

    # People
    people = list(db.scalars(
        select(Person).where(Person.is_active == True, Person.name.contains(q.strip())).limit(limit)
    ).all())
    results["people"] = {
        "label": "浜т笟浜虹墿",
        "items": [{"id": p.id, "title": p.name, "summary": f"{p.public_role or ''} | {p.organization_network or ''}", "url": f"/network/people/{p.id}"} for p in people],
    }

    # Organizations
    orgs = list(db.scalars(
        select(Organization).where(Organization.is_active == True, Organization.standard_name.contains(q.strip())).limit(limit)
    ).all())
    results["organizations"] = {
        "label": "Organizations",
        "items": [{"id": o.id, "title": o.standard_name, "summary": f"{o.org_type or ''} | {o.region or ''}", "url": f"/network/organizations/{o.id}"} for o in orgs],
    }

    # Intelligence
    intel = list(db.scalars(
        select(IntelligenceItem).where(
            IntelligenceItem.status == "published",
            or_(IntelligenceItem.title.contains(q.strip()), IntelligenceItem.summary.contains(q.strip())),
        ).limit(limit)
    ).all())
    results["intelligence"] = {
        "label": "Intelligence",
        "items": [{"id": i.id, "title": i.title, "summary": (i.summary or "")[:100], "url": f"/intelligence/{i.id}"} for i in intel],
    }

    # Resources
    res = list(db.scalars(
        select(MarketResource).where(
            MarketResource.status == "published",
            or_(MarketResource.title.contains(q.strip()), MarketResource.summary.contains(q.strip())),
        ).limit(limit)
    ).all())
    results["resources"] = {
        "label": "Resources",
        "items": [{"id": r.id, "title": r.title, "summary": f"{r.direction} | {r.resource_type}", "url": f"/resources/{r.id}"} for r in res],
    }

    # Opportunities
    opps = list(db.scalars(
        select(CooperationOpportunity).where(
            CooperationOpportunity.status == "active",
            CooperationOpportunity.title.contains(q.strip()),
        ).limit(limit)
    ).all())
    results["opportunities"] = {
        "label": "Opportunities",
        "items": [{"id": o.id, "title": o.title, "summary": f"{o.opp_type} | {o.stage}", "url": f"/opportunities/{o.id}"} for o in opps],
    }

    groups = [v for v in results.values() if v["items"]]
    total = sum(len(g["items"]) for g in groups)
    return {"q": q, "groups": groups, "total": total}

# v0.6C unified-domain wrappers. Keep legacy import names stable while routing writes/reads through canonical services.
def _is_admin_user(user: dict | None) -> bool:
    return bool(user and str(user.get("role")) == "admin")


def _user_linked_person_id(db: Session, user_id: int) -> int | None:
    row = db.execute(text("""
        SELECT p.id FROM people p
        JOIN identity_link_requests l ON p.id=l.person_id
        WHERE l.user_id=:uid AND l.status='approved' AND p.is_active=1
        ORDER BY l.id DESC LIMIT 1
    """), {"uid": int(user_id)}).mappings().first()
    return int(row["id"]) if row else None


def _user_can_handle_target(db: Session, user_id: int, target_type: str, target_id: int) -> bool:
    if target_type == "person":
        return _user_linked_person_id(db, user_id) == int(target_id)
    if target_type == "organization":
        row = db.execute(text("SELECT 1 FROM organization_user_links WHERE user_id=:uid AND organization_id=:oid AND status='active'"), {"uid": int(user_id), "oid": int(target_id)}).first()
        return row is not None
    if target_type == "user":
        return int(user_id) == int(target_id)
    return False


def create_contact_intent(db: Session, from_user_id: int, target_type: str, target_id: int, intent_type: str, message: str) -> ContactIntent:
    target_type = (target_type or "person").strip()
    target_id = int(target_id or 0)
    if target_id <= 0 or target_type not in {"person", "organization", "user"}:
        raise ValueError("invalid contact target")
    if target_type == "person" and _user_linked_person_id(db, int(from_user_id)) == target_id:
        raise PermissionError("cannot create contact intent to yourself")
    status = "pending" if target_type != "person" or db.execute(text("SELECT 1 FROM identity_link_requests WHERE person_id=:pid AND status='approved'"), {"pid": target_id}).first() else "platform_pending"
    ci = ContactIntent(from_user_id=from_user_id, target_type=target_type, target_id=target_id, intent_type=intent_type, message=message, status=status)
    db.add(ci); db.commit(); db.refresh(ci)
    return ci


def respond_contact_intent(db: Session, intent_id: int, status: str, response_message: str, responded_by: int) -> ContactIntent | None:
    ci = db.get(ContactIntent, int(intent_id))
    if not ci:
        return None
    if ci.status != "pending":
        raise PermissionError("contact intent is not pending")
    if not _user_can_handle_target(db, int(responded_by), ci.target_type, int(ci.target_id)):
        raise PermissionError("only the real receiver can respond to this contact intent")
    if status not in {"accepted", "declined", "ignored", "cancelled"}:
        raise ValueError("invalid contact intent status")
    ci.status = status
    ci.response_message = response_message
    ci.responded_at = datetime.now()
    ci.responded_by = responded_by
    db.commit(); db.refresh(ci)
    return ci


def list_contact_intents(db: Session, user_id: int, direction: str = "sent") -> list[ContactIntent]:
    if direction == "sent":
        stmt = select(ContactIntent).where(ContactIntent.from_user_id == user_id).order_by(desc(ContactIntent.created_at))
    else:
        person_id = _user_linked_person_id(db, int(user_id))
        clauses = [ContactIntent.target_type == "user", ContactIntent.target_id == int(user_id)]
        if person_id:
            clauses.append(and_(ContactIntent.target_type == "person", ContactIntent.target_id == person_id))
        stmt = select(ContactIntent).where(or_(*clauses)).order_by(desc(ContactIntent.created_at))
    return list(db.scalars(stmt).all())


def list_intelligence(db: Session, user_id: int | None = None, intel_type: str = "", industry_direction: str = "", q: str = "", page: int = 1, page_size: int = 20) -> dict:
    from app.services.unified_intelligence_service import UnifiedIntelligenceService
    return UnifiedIntelligenceService(db).list(user_id=user_id, intel_type=intel_type, industry_direction=industry_direction, q=q, page=page, page_size=page_size)


def personalized_feed(db: Session, user_id: int | None, limit: int = 20) -> list[dict]:
    from app.services.unified_intelligence_service import UnifiedIntelligenceService
    items = UnifiedIntelligenceService(db).list(user_id=user_id, page=1, page_size=limit)["items"]
    return [{"item": item, "reason": "unified_feed"} for item in items]


def list_market_resources(db: Session, direction: str = "", resource_type: str = "", q: str = "", industry_direction: str = "", region: str = "", page: int = 1, page_size: int = 20) -> dict:
    from app.services.unified_resource_service import UnifiedResourceService
    return UnifiedResourceService(db).list(direction=direction, resource_type=resource_type, q=q, industry_direction=industry_direction, region=region, page=page, page_size=page_size)


def match_resources(db: Session, resource_id: int, limit: int = 10) -> list[dict]:
    from app.services.unified_resource_service import UnifiedResourceService
    return UnifiedResourceService(db).match(resource_id, limit=limit)


def create_opportunity(db: Session, **fields) -> CooperationOpportunity:
    from app.services.unified_opportunity_service import UnifiedOpportunityService
    actor = int(fields.pop("initiator_id"))
    return UnifiedOpportunityService(db).create(actor_user_id=actor, fields=fields)


def update_opportunity_stage(db: Session, opp_id: int, stage: str, actor_id: int) -> CooperationOpportunity | None:
    from app.services.unified_opportunity_service import UnifiedOpportunityService
    return UnifiedOpportunityService(db).update_stage(opp_id, actor_user_id=int(actor_id), stage=stage)


def get_opportunity_timeline(db: Session, opp_id: int) -> list[TimelineEntry]:
    from app.services.unified_opportunity_service import UnifiedOpportunityService
    return UnifiedOpportunityService(db).timeline(opp_id, user_id=None, is_admin=True)


def create_follow_up(db: Session, **fields) -> FollowUp:
    from app.services.unified_opportunity_service import UnifiedOpportunityService
    opp_id = int(fields.pop("opportunity_id"))
    actor = int(fields.pop("created_by"))
    return UnifiedOpportunityService(db).create_follow_up(opp_id=opp_id, actor_user_id=actor, fields=fields)


def create_collab_task(db: Session, **fields) -> CollabTask:
    from app.services.unified_opportunity_service import UnifiedOpportunityService
    opp_id = int(fields.pop("opportunity_id")) if fields.get("opportunity_id") else 0
    actor = int(fields.pop("created_by"))
    owner = int(fields.pop("owner_id"))
    return UnifiedOpportunityService(db).create_task(opp_id=opp_id, actor_user_id=actor, owner_id=owner, fields=fields)


def unified_search(db: Session, q: str, limit: int = 10) -> dict:
    from app.services.unified_search_service import UnifiedSearchService
    return UnifiedSearchService(db).search(q, limit=limit)



