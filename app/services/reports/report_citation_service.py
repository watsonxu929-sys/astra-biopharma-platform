from __future__ import annotations

import json
from typing import Any


def citation(ref_type: str, ref_id: str | int | None, label: str = "") -> dict[str, Any]:
    if ref_id in (None, ""):
        return {}
    prefix = {"signal": "SIG", "event": "EVT", "snapshot": "SRC", "review": "RVW", "candidate": "CND"}.get(ref_type, ref_type.upper())
    return {"ref": f"{prefix}-{ref_id}", "type": ref_type, "id": str(ref_id), "label": label or f"{ref_type} {ref_id}"}


def markdown_citation(item: dict[str, Any]) -> str:
    if not item:
        return ""
    return f"[{item['ref']}]"


def dumps(items: list[dict[str, Any]]) -> str:
    return json.dumps([item for item in items if item], ensure_ascii=False)
