from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from app.security import can, current_user
from app.services.identity_link_service import (
    IdentityLinkError,
    approve_link_request,
    cancel_link_request,
    create_link_request,
    identity_context,
    list_link_requests,
    list_person_options,
    reject_link_request,
)

router = APIRouter(tags=["identity"])
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def _require_user(request: Request) -> dict[str, Any]:
    user = current_user(request)
    if not user:
        raise HTTPException(401, "请先登录")
    return user


def _require_reviewer(request: Request) -> dict[str, Any]:
    user = _require_user(request)
    if not can(request, "identity.review_link"):
        raise HTTPException(403, "当前账号没有身份审核权限")
    return user


def _message_url(path: str, *, message: str = "", error: str = "") -> str:
    if message:
        return f"{path}?message={message}"
    if error:
        return f"{path}?error={error}"
    return path


@router.get("/me/identity", response_class=HTMLResponse)
def my_identity_page(request: Request, q: str = Query(""), message: str = Query(""), error: str = Query("")):
    user = _require_user(request)
    return templates.TemplateResponse(
        request=request,
        name="identity.html",
        context={
            "mode": "me",
            "identity": identity_context(int(user["id"])),
            "people": list_person_options(q),
            "q": q,
            "message": message,
            "error": error,
        },
    )


@router.post("/me/person-link", response_class=HTMLResponse)
def request_person_link_page(request: Request, person_id: int = Form(...), reason: str = Form("")):
    user = _require_user(request)
    try:
        create_link_request(int(user["id"]), person_id, reason, user)
        return RedirectResponse(_message_url("/me/identity", message="绑定申请已提交，等待管理员审核。"), status_code=303)
    except IdentityLinkError as exc:
        return RedirectResponse(_message_url("/me/identity", error=exc.message), status_code=303)


@router.post("/me/person-link/cancel", response_class=HTMLResponse)
def cancel_person_link_page(request: Request):
    user = _require_user(request)
    try:
        cancel_link_request(int(user["id"]), user)
        return RedirectResponse(_message_url("/me/identity", message="绑定申请已取消。"), status_code=303)
    except IdentityLinkError as exc:
        return RedirectResponse(_message_url("/me/identity", error=exc.message), status_code=303)


@router.get("/system/identity-link-requests", response_class=HTMLResponse)
def identity_link_requests_page(request: Request, status: str = Query(""), message: str = Query(""), error: str = Query("")):
    _require_reviewer(request)
    return templates.TemplateResponse(
        request=request,
        name="identity.html",
        context={
            "mode": "requests",
            "requests": list_link_requests(status or None),
            "status": status,
            "message": message,
            "error": error,
        },
    )


@router.post("/system/identity-link-requests/{request_id}/approve", response_class=HTMLResponse)
def approve_link_page(request_id: int, request: Request):
    actor = _require_reviewer(request)
    try:
        approve_link_request(request_id, actor)
        return RedirectResponse(_message_url("/system/identity-link-requests", message="绑定申请已通过。"), status_code=303)
    except IdentityLinkError as exc:
        return RedirectResponse(_message_url("/system/identity-link-requests", error=exc.message), status_code=303)


@router.post("/system/identity-link-requests/{request_id}/reject", response_class=HTMLResponse)
def reject_link_page(request_id: int, request: Request, reason: str = Form(...)):
    actor = _require_reviewer(request)
    try:
        reject_link_request(request_id, reason, actor)
        return RedirectResponse(_message_url("/system/identity-link-requests", message="绑定申请已拒绝。"), status_code=303)
    except IdentityLinkError as exc:
        return RedirectResponse(_message_url("/system/identity-link-requests", error=exc.message), status_code=303)
