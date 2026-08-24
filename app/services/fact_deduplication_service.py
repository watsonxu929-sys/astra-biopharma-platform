from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from app.v04c_review import db_connection
from app.core.similarity import similarity_ratio


def normalized_title(value: str) -> str:
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", (value or "").casefold())


def title_similarity(left: str, right: str) -> float:
    return similarity_ratio(normalized_title(left), normalized_title(right))


def event_dedup_key(subject: str, event_type: str, event_date: str) -> str:
    payload = "|".join((normalized_title(subject), event_type.strip().casefold(), event_date.strip()[:10]))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class FactConflictService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path

    def register(
        self,
        *,
        pilot_batch_id: str,
        subject_type: str,
        subject_label: str,
        field_name: str,
        left_candidate_id: int,
        right_candidate_id: int,
        left_value: str,
        right_value: str,
        evidence: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        if (left_value or "").strip() == (right_value or "").strip():
            return None
        key = hashlib.sha256(
            f"{subject_type}|{normalized_title(subject_label)}|{field_name}".encode("utf-8")
        ).hexdigest()
        with db_connection(self.db_path) as conn:
            conn.execute(
                """INSERT OR IGNORE INTO p2_2_fact_conflicts(
                   pilot_batch_id,conflict_key,subject_type,subject_label,field_name,
                   left_candidate_id,right_candidate_id,left_value,right_value,status,evidence_json,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,'needs_manual_review',?,datetime('now','localtime'))""",
                (pilot_batch_id, key, subject_type, subject_label, field_name,
                 left_candidate_id, right_candidate_id, left_value, right_value,
                 json.dumps(evidence, ensure_ascii=False)),
            )
            row = conn.execute(
                "SELECT * FROM p2_2_fact_conflicts WHERE conflict_key=? AND left_candidate_id=? AND right_candidate_id=?",
                (key, left_candidate_id, right_candidate_id),
            ).fetchone()
            return dict(row) if row else None
