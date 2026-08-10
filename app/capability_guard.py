from __future__ import annotations

from pathlib import Path

from fastapi import Request
from fastapi.responses import JSONResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.schema_preflight import CapabilityStatus, get_schema_preflight


templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))

P3_PREFIXES = (
    "/network/graph", "/network/governance", "/network/entities/", "/network/products/",
    "/network/resolution-candidates", "/network/merges", "/network/relationship-candidates",
    "/network/relationships", "/network/paths", "/network/recommendations",
    "/network/connection-candidates", "/network/timeline", "/api/v1/entity-network",
)
P4_PREFIXES = ("/club/operations", "/club/relationship-candidates", "/club/leads", "/api/v1/club")
P5_PREFIXES = ("/collaboration", "/api/v1/opportunities")
RESEARCH_PREFIXES = ("/research/fusion", "/api/v1/research-fusion")


def capability_for_path(path: str) -> str | None:
    if path.startswith(P3_PREFIXES):
        return "industry_relationships"
    if path.startswith(P4_PREFIXES):
        return "club_operations"
    if path.startswith(P5_PREFIXES):
        return "business_collaboration"
    if path.startswith(RESEARCH_PREFIXES):
        return "research_fusion"
    if path.startswith("/resources/matching") or path.startswith("/club/matches"):
        return "resource_matching"
    if path.startswith("/club/events/") and any(part in path for part in ("/checkin", "/undo-checkin", "/checkin-token", "/feedback", "/followup-action", "/relationship-candidates")):
        return "club_operations"
    if path == "/club" or path.startswith("/club/"):
        return "club_operations"
    return None


def unavailable_response(request: Request, status: CapabilityStatus):
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=503,
            content={
                "error": "capability_unavailable",
                "capability": status.name,
                "message": "\u8be5\u6a21\u5757\u5c1a\u672a\u5b8c\u6210\u6570\u636e\u5e93\u63a5\u5165",
                "missing_tables": list(status.missing_tables),
            },
        )
    return templates.TemplateResponse(
        request=request,
        name="capability_unavailable.html",
        context={"request": request, "capability": status},
        status_code=503,
    )


class CapabilityGuardMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        name = capability_for_path(request.url.path)
        if name:
            status = get_schema_preflight().capability(name)
            if not status.enabled:
                return unavailable_response(request, status)
        return await call_next(request)
