from __future__ import annotations

from typing import Any

from app.services.navigation_service import get_client_navigation


def navigation_for(security: dict[str, Any], path: str) -> dict[str, Any]:
    return get_client_navigation(security, client="web", path=path)
