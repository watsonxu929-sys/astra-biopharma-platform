from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

from app.security import auth_disabled, permissions_for

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class Pagination:
    page: int
    page_size: int
    total: int

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    def to_dict(self) -> dict[str, int]:
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total": self.total,
            "total_pages": max(0, math.ceil(self.total / self.page_size)) if self.total else 0,
        }


def normalize_page(page: int = 1, page_size: int = DEFAULT_PAGE_SIZE) -> tuple[int, int]:
    page = max(1, int(page or 1))
    page_size = max(1, min(int(page_size or DEFAULT_PAGE_SIZE), MAX_PAGE_SIZE))
    return page, page_size


def paginated(data: list[dict[str, Any]], pagination: Pagination, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": data, "pagination": pagination.to_dict(), "meta": meta or {}}


def single(data: dict[str, Any] | None, meta: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"data": data, "meta": meta or {}}


def api_error(status_code: int, code: str, message: str, details: dict[str, Any] | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code, "message": message, "details": details or {}}})


def raise_api_error(status_code: int, code: str, message: str, details: dict[str, Any] | None = None) -> None:
    raise HTTPException(status_code=status_code, detail={"code": code, "message": message, "details": details or {}})


def api_user(request: Request) -> dict[str, Any]:
    user = getattr(request.state, "current_user", None)
    if not user:
        raise_api_error(401, "AUTH_REQUIRED", "请先登录后访问 API")
    return user


def require_permission(request: Request, permission: str) -> dict[str, Any]:
    user = api_user(request)
    if auth_disabled():
        return user
    if permission not in permissions_for(user):
        raise_api_error(403, "FORBIDDEN", "当前账号没有访问该 API 的权限")
    return user


def current_scope(request: Request) -> dict[str, Any]:
    user = getattr(request.state, "current_user", None)
    return {
        "authenticated": bool(user),
        "username": user.get("username") if user else None,
        "role": user.get("role") if user else None,
        "permissions": sorted(permissions_for(user)) if user else [],
        "auth_disabled": auth_disabled(),
    }


def iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.replace(microsecond=0).isoformat()
    return str(value)

