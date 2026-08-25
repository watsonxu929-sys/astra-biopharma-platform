from __future__ import annotations

import re
import sqlite3
from typing import Any


SUBJECT_CONFIG = {
    "organization": ("organizations", "external_id", "standard_name"),
    "person": ("people", "external_id", "name"),
    "project": ("projects", "external_id", "name"),
}


def normalize_label(value: str) -> str:
    return re.sub(r"\s+", "", (value or "").strip()).lower()


def match_subject(conn: sqlite3.Connection, subject_type: str, label: str, subject_id: str = "") -> dict[str, Any]:
    config = SUBJECT_CONFIG.get(subject_type)
    if not config:
        return {"status": "new_subject", "method": "unsupported_type", "score": 0, "matches": [], "ambiguity_count": 0}
    table, id_col, label_col = config
    if subject_id:
        row = conn.execute(f"SELECT {id_col}, {label_col} FROM {table} WHERE {id_col}=?", (subject_id,)).fetchone()
        if row:
            return {"status": "confirmed", "method": "exact_system_id", "score": 100, "matches": [dict(row)], "ambiguity_count": 0}
    normalized = normalize_label(label)
    if not normalized:
        return {"status": "new_subject", "method": "empty_label", "score": 0, "matches": [], "ambiguity_count": 0}
    exact_where = f"lower(replace({label_col}, ' ', ''))=?"
    exact_params: tuple[str, ...] = (normalized,)
    exact_select = f"{id_col}, {label_col}"
    if subject_type == "organization":
        exact_where = " OR ".join(
            f"lower(replace(COALESCE({column},''), ' ', ''))=?"
            for column in ("standard_name", "name", "short_name")
        )
        exact_params = (normalized, normalized, normalized)
        exact_select = (
            f"{id_col}, {label_col}, "
            "CASE WHEN lower(replace(COALESCE(standard_name,''),' ',''))=? THEN 'standard_name' "
            "WHEN lower(replace(COALESCE(name,''),' ',''))=? THEN 'name' ELSE 'short_name' END AS matched_via"
        )
        exact_params = (normalized, normalized, *exact_params)
    rows = [
        dict(row)
        for row in conn.execute(
            f"SELECT {exact_select} FROM {table} WHERE is_active=1 AND ({exact_where}) ORDER BY id DESC LIMIT 8",
            exact_params,
        ).fetchall()
    ]
    if len(rows) == 1:
        method = "exact_alias" if rows[0].get("matched_via") in {"name", "short_name"} else "exact_name"
        return {"status": "confirmed", "method": method, "score": 92 if subject_type != "person" else 86, "matches": rows, "ambiguity_count": 0}
    if len(rows) > 1:
        return {"status": "ambiguous", "method": "same_name_multiple", "score": 64, "matches": rows, "ambiguity_count": len(rows)}
    like_where = f"{label_col} LIKE ?"
    like_params: tuple[str, ...] = (f"%{label[:30]}%",)
    if subject_type == "organization":
        like_where = " OR ".join(f"COALESCE({column},'') LIKE ?" for column in ("standard_name", "name", "short_name"))
        like_params = (f"%{label[:30]}%",) * 3
    like_rows = [
        dict(row)
        for row in conn.execute(
            f"SELECT {id_col}, {label_col} FROM {table} WHERE is_active=1 AND ({like_where}) ORDER BY id DESC LIMIT 5",
            like_params,
        ).fetchall()
    ]
    if like_rows:
        return {"status": "candidate", "method": "contains_name", "score": 60, "matches": like_rows, "ambiguity_count": len(like_rows)}
    return {"status": "new_subject", "method": "no_match", "score": 0, "matches": [], "ambiguity_count": 0}
