from __future__ import annotations

from typing import Any

from app.platform.capability_registry import filter_capabilities, list_capabilities

PRIMARY_ORDER = ["workspace", "network", "intelligence", "resources", "club"]
CLIENTS = {"web", "app", "miniprogram", "admin"}


def _permissions(context: dict[str, Any] | None) -> set[str]:
    context = context or {}
    return set(context.get("permissions") or [])


def _allowed_capabilities(context: dict[str, Any] | None, *, client: str = "web") -> list[dict[str, Any]]:
    context = context or {}
    return filter_capabilities(_permissions(context), client=client, auth_disabled=bool(context.get("auth_disabled")))


def _nav_item(cap: dict[str, Any], path: str = "") -> dict[str, Any]:
    route = cap.get("web_route") or "#"
    clean_route = route.split("?", 1)[0]
    legacy = cap.get("legacy_routes") or []
    if "?" in route:
        active = False
    else:
        active = bool(path and (path == clean_route or (clean_route != "/" and path.startswith(clean_route)) or any(path.startswith(str(item).split("?", 1)[0]) for item in legacy)))
    return {
        "key": cap["capability_key"],
        "capability_key": cap["capability_key"],
        "label": cap["name"],
        "name": cap["name"],
        "short_name": cap.get("short_name") or cap["name"],
        "endpoint": route,
        "route": route,
        "api_prefix": cap.get("api_prefix", ""),
        "icon_key": cap.get("icon_key", "circle"),
        "category": cap.get("category", ""),
        "parent_key": cap.get("parent_key"),
        "status": cap.get("status", "active"),
        "order": cap.get("order", 0),
        "required_permission": cap.get("required_permission", ""),
        "permissions_summary": {"required_permission": cap.get("required_permission", ""), "required_context": cap.get("required_context", "")},
        "badge_count": 0,
        "active": active,
    }


def get_primary_navigation(context: dict[str, Any] | None, path: str = "/", *, client: str = "web") -> list[dict[str, Any]]:
    caps = _allowed_capabilities(context, client=client)
    by_key = {cap["capability_key"]: cap for cap in caps}
    result = []
    for key in PRIMARY_ORDER:
        cap = by_key.get(key)
        if cap:
            result.append(_nav_item(cap, path))
    return result[:5]


def get_secondary_navigation(context: dict[str, Any] | None, active_category: str | None = None, path: str = "/", *, client: str = "web") -> list[dict[str, Any]]:
    active_category = active_category or resolve_active_capability(path).get("category") or "workspace"
    caps = [cap for cap in _allowed_capabilities(context, client=client) if cap.get("category") == active_category and cap.get("parent_key")]
    return [_nav_item(cap, path) for cap in sorted(caps, key=lambda item: item.get("order", 0))]


def get_account_navigation(context: dict[str, Any] | None, path: str = "/", *, client: str = "web") -> list[dict[str, Any]]:
    caps = [cap for cap in _allowed_capabilities(context, client=client) if cap.get("category") == "account"]
    return [_nav_item(cap, path) for cap in sorted(caps, key=lambda item: item.get("order", 0))]


def get_admin_navigation(context: dict[str, Any] | None, path: str = "/", *, client: str = "web") -> list[dict[str, Any]]:
    caps = [cap for cap in _allowed_capabilities(context, client="admin" if client == "admin" else "web") if cap.get("category") == "admin"]
    return [_nav_item(cap, path) for cap in sorted(caps, key=lambda item: item.get("order", 0))]


def get_client_navigation(context: dict[str, Any] | None, *, client: str = "web", path: str = "/") -> dict[str, Any]:
    client = client if client in CLIENTS else "web"
    active = resolve_active_capability(path)
    active_category = active.get("category") if active else "workspace"
    active_key = active.get("capability_key") if active else "workspace"
    primary = get_primary_navigation(context, path, client=client)
    secondary = get_secondary_navigation(context, active_category, path, client=client)
    for item in primary:
        item["active"] = item.get("category") == active_category
    for item in secondary:
        item["active"] = item.get("key") == active_key
    return {
        "client": client,
        "primary": primary,
        "secondary": secondary,
        "account": get_account_navigation(context, path, client=client),
        "admin": get_admin_navigation(context, path, client=client),
        "active": active,
    }


def resolve_active_capability(path: str) -> dict[str, Any]:
    path = path or "/"
    best: dict[str, Any] | None = None
    best_len = -1
    for cap in list_capabilities():
        routes = [cap.get("web_route") or ""] + list(cap.get("legacy_routes") or [])
        for route in routes:
            if not route:
                continue
            clean = route.split("?", 1)[0]
            if path == clean or (clean != "/" and path.startswith(clean)):
                if len(clean) > best_len:
                    best = cap
                    best_len = len(clean)
    return best or {"capability_key": "workspace", "category": "workspace", "web_route": "/platform"}


def validate_registered_routes(app: Any | None = None) -> list[str]:
    if app is None:
        from app.main import app as fastapi_app
        app = fastapi_app
    registered: set[str] = set()
    for route in getattr(app, "routes", []):
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            for ctx in contexts():
                registered.add(getattr(ctx, "path", ""))
        else:
            registered.add(getattr(route, "path", ""))
    errors: list[str] = []
    for cap in list_capabilities():
        route = (cap.get("web_route") or "").split("?", 1)[0]
        if not route or route == "#" or cap.get("status") in {"planned", "disabled"}:
            continue
        if route not in registered and not any(route.startswith(prefix) for prefix in ["/resources", "/intelligence", "/network", "/opportunities", "/workspace", "/club", "/member", "/review", "/collection", "/processing", "/reports", "/signals", "/research", "/system", "/admin"]):
            errors.append(f"unregistered route for {cap['capability_key']}: {route}")
    return errors


