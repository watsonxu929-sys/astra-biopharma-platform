from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from app.services.api_common import current_scope, single

from . import auth, client, club_operations, clubs, collection, dashboard, events, identity, intelligence, investment_assessments, membership_person_link, membership_user_link, navigation, network, organizations, pipeline, processing, relationships, reports, research, resources, opportunities, search, signals, subjects, system, watchlists
from . import entity_network, golden_loop, research_fusion

router = APIRouter(prefix="/api/v1", tags=["API v1"])


@router.get("/health", summary="API health check", description="Return API v1 health status without exposing system secrets.")
def health():
    return {"ok": True, "api_version": "v1", "system_version": "v0.6D", "server_time": datetime.now().replace(microsecond=0).isoformat()}


@router.get("/version", summary="API version", description="Return public API version metadata.")
def version():
    return {"api_version": "v1", "system_version": "v0.6D", "server_time": datetime.now().replace(microsecond=0).isoformat()}


@router.get("/meta", summary="API metadata", description="Return supported subject types, filters, pagination defaults and current auth scope.")
def meta(request: Request):
    return single({
        "api_version": "v1",
        "system_version": "v0.6D",
        "supported_subject_types": ["organization", "person", "project"],
        "supported_filters": ["page", "page_size", "sort", "order", "q", "subject_type", "status", "region", "industry", "signal_type", "signal_level"],
        "pagination": {"default_page_size": 20, "max_page_size": 100},
        "server_time": datetime.now().replace(microsecond=0).isoformat(),
        "auth_scope": current_scope(request),
    })


@router.get("/me", summary="Current API user", description="Return the same-domain session user scope used by API v1.")
def me(request: Request):
    scope = current_scope(request)
    if not scope["authenticated"]:
        raise HTTPException(status_code=401, detail={"code": "AUTH_REQUIRED", "message": "鐠囧嘲鍘涢惂璇茬秿閸氬氦顔栭梻?API", "details": {}})
    return single(scope)


router.include_router(auth.router)
router.include_router(client.router)
router.include_router(clubs.router)
router.include_router(club_operations.router)
router.include_router(network.router)
router.include_router(identity.router)
router.include_router(subjects.router)
router.include_router(search.router)
router.include_router(intelligence.router)
router.include_router(resources.router)
router.include_router(opportunities.router)
router.include_router(golden_loop.router)
router.include_router(events.router)
router.include_router(relationships.router)
router.include_router(signals.router)
router.include_router(watchlists.router)
router.include_router(dashboard.router)
router.include_router(collection.router)
router.include_router(processing.router)
router.include_router(reports.router)
router.include_router(navigation.router)
router.include_router(pipeline.router)
router.include_router(research.router)
router.include_router(research_fusion.router)
router.include_router(entity_network.router)
router.include_router(investment_assessments.router)
router.include_router(system.router)
router.include_router(membership_person_link.router)
router.include_router(membership_user_link.router)
router.include_router(organizations.router)






