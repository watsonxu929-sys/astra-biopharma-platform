from __future__ import annotations

from pathlib import Path
from typing import Any

from app.database import SessionLocal
from app.services.unified_search_service import UnifiedSearchService


def search_all(q: str, *, per_type_limit: int = 10, db_path: str | Path | None = None) -> dict[str, Any]:
    q = (q or "").strip()
    per_type_limit = max(1, min(int(per_type_limit or 10), 30))
    if not q:
        return {"q": "", "groups": [], "total": 0}
    db = SessionLocal()
    try:
        result = UnifiedSearchService(db).search(q, limit=per_type_limit)
        groups = []
        for group in result.get("groups", []):
            rows = []
            for item in group.get("items", []):
                rows.append({
                    "code": item.get("canonical_id") or str(item.get("id", "")),
                    "canonical_id": item.get("canonical_id"),
                    "title": item.get("title"),
                    "summary": item.get("summary") or "",
                    "status": item.get("status") or "",
                    "api_url": item.get("api_url") or "",
                    "web_url": item.get("url") or "",
                    "url": item.get("url") or "",
                })
            if rows:
                groups.append({"key": group.get("type"), "label": group.get("label"), "results": rows, "items": rows, "count": len(rows)})
        return {"q": q, "groups": groups, "total": sum(group["count"] for group in groups)}
    finally:
        db.close()
