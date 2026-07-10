from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Person
from app.services.api_common import require_permission, single
from app.services.platform_service import discover_people, get_user_person, recommend_people, serialize_person_summary

router = APIRouter(prefix="/network", tags=["Platform Network"])


@router.get("/people")
def list_people(
    request: Request,
    keyword: str = Query(""),
    industry_type: str = Query(""),
    industry_direction: str = Query(""),
    capability_tag: str = Query(""),
    need_tag: str = Query(""),
    organization_id: int | None = Query(None),
    region: str = Query(""),
    membership_status: str = Query(""),
    page: int = Query(1),
    page_size: int = Query(20),
    db: Session = Depends(get_db),
):
    user = require_permission(request, "view_internal")
    organization = ""
    result = discover_people(
        db,
        current_user_id=int(user["id"]),
        name=keyword,
        user_type=industry_type,
        industry_direction=industry_direction,
        capability=capability_tag,
        need=need_tag,
        organization=organization,
        region=region,
        member_status=membership_status,
        page=page,
        page_size=page_size,
    )
    items = []
    for item in result["items"]:
        safe = {k: v for k, v in item.items() if k != "profile_model"}
        items.append(safe)
    applied = dict(result.get("applied_filters") or {})
    applied["organization_id"] = organization_id
    return {
        "items": items,
        "total": result["total"],
        "page": result["page"],
        "page_size": result["page_size"],
        "applied_filters": applied,
    }


@router.get("/people/{person_id}")
def person_detail(person_id: int, request: Request, db: Session = Depends(get_db)):
    require_permission(request, "view_internal")
    person = db.get(Person, person_id)
    if not person or not person.is_active:
        raise HTTPException(status_code=404, detail={"code": "PERSON_NOT_FOUND", "message": "\u4eba\u7269\u4e0d\u5b58\u5728", "details": {}})
    return single({"person": serialize_person_summary(db, person, include_contact=True)})


@router.get("/recommendations/people")
def people_recommendations(request: Request, db: Session = Depends(get_db), limit: int = Query(12)):
    user = require_permission(request, "view_internal")
    current_person = get_user_person(db, int(user["id"]))
    recs = recommend_people(db, int(user["id"]), limit=max(1, min(limit, 50)))
    return single({
        "has_person_profile": bool(current_person),
        "recommendation_type": "personalized" if current_person else "public_hot",
        "guidance": None if current_person else "\u5b8c\u5584\u4ea7\u4e1a\u8eab\u4efd\u753b\u50cf\u540e\u53ef\u83b7\u5f97\u66f4\u7cbe\u51c6\u63a8\u8350",
        "items": [
            {"person": rec.get("person"), "score": rec.get("score"), "reasons": rec.get("reasons") or [], "matched_tags": rec.get("matched_tags") or [], "recommendation_type": rec.get("recommendation_type")}
            for rec in recs
        ],
    })
