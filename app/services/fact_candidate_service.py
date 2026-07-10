from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from app.services.evidence_service import EvidenceService
from app.services.processing.processing_job_service import _next_no
from app.v04c_review import db_connection

REVIEW_STATES = {"pending", "approved", "rejected", "merged", "needs_review"}


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


class FactCandidateService:
    def __init__(self, db_path: str | Path | None = None):
        self.db_path = db_path
        self.evidence = EvidenceService(db_path)

    def create(
        self,
        *,
        processing_job_id: int,
        snapshot_id: int,
        candidate_type: str,
        value: str,
        evidence_excerpt: str,
        confidence_score: int,
        generated_by: str,
        provider: str,
        model: str,
        prompt_version: str,
        subject_type: str | None = None,
        subject_label: str | None = None,
        event_type: str | None = None,
        fields: dict[str, Any] | None = None,
        char_start: int | None = None,
        char_end: int | None = None,
        page_number: int | None = None,
        table_number: str | None = None,
        is_pilot: bool = False,
        pilot_batch_id: str | None = None,
    ) -> dict[str, Any]:
        score = max(0, min(100, int(confidence_score)))
        digest = hashlib.sha256(json.dumps({"type": candidate_type, "value": value, "evidence": evidence_excerpt, "provider": provider, "model": model}, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()
        with db_connection(self.db_path) as conn:
            job = conn.execute("SELECT * FROM v05g_processing_jobs WHERE id=?", (processing_job_id,)).fetchone()
            if not job:
                raise ValueError("processing_job_not_found")
            snapshot = conn.execute("SELECT * FROM v04g_source_snapshots WHERE id=?", (snapshot_id,)).fetchone()
            if not snapshot:
                raise ValueError("snapshot_not_found")
            existing = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE processing_job_id=? AND result_hash=?", (processing_job_id, digest)).fetchone()
            if existing:
                candidate = dict(existing)
            else:
                cur = conn.execute(
                    """
                    INSERT INTO v05g_extraction_candidates(
                        candidate_no,processing_job_id,collection_item_id,snapshot_id,candidate_type,
                        subject_type,subject_label,field_name,raw_value,normalized_value,payload_json,
                        evidence_excerpt,source_url,source_title,source_position,extraction_rule,fact_level,
                        confidence_score,confidence_level,validation_status,review_status,warning_json,
                        content_hash,created_at,updated_at,generated_by,provider,model,prompt_version,
                        result_hash,pipeline_review_status,is_pilot,pilot_batch_id
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        _next_no(conn, "CND"), processing_job_id, job["collection_item_id"], snapshot_id,
                        candidate_type, subject_type, subject_label, event_type, value, value,
                        json.dumps(fields or {}, ensure_ascii=False), evidence_excerpt, snapshot["url"],
                        snapshot["page_title"], json.dumps({"char_start": char_start, "char_end": char_end, "page_number": page_number, "table_number": table_number}, ensure_ascii=False),
                        f"{provider}:{model}:{prompt_version}", "fact", score,
                        "high" if score >= 80 else "medium" if score >= 50 else "low", "valid", "pending", "[]",
                        digest, now(), now(), generated_by, provider, model, prompt_version, digest, "pending",
                        int(is_pilot), pilot_batch_id,
                    ),
                )
                candidate = dict(conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (cur.lastrowid,)).fetchone())
        self.evidence.link_candidate(candidate["id"], snapshot_id, excerpt=evidence_excerpt, char_start=char_start, char_end=char_end, page_number=page_number, table_number=table_number, locator={"provider": provider, "model": model, "prompt_version": prompt_version})
        return candidate

    def review(self, candidate_id: int, *, decision: str, actor: str, permissions: set[str], reason: str = "", final_value: str = "", merged_into_candidate_id: int | None = None) -> dict[str, Any]:
        if "review_data" not in permissions:
            raise PermissionError("review_data_required")
        if decision not in REVIEW_STATES - {"pending"}:
            raise ValueError("unsupported_decision")
        if decision == "rejected" and not reason.strip():
            raise ValueError("rejection_reason_required")
        if decision == "merged" and not merged_into_candidate_id:
            raise ValueError("merge_target_required")
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (candidate_id,)).fetchone()
            if not row:
                raise ValueError("candidate_not_found")
            if merged_into_candidate_id and not conn.execute("SELECT 1 FROM v05g_extraction_candidates WHERE id=?", (merged_into_candidate_id,)).fetchone():
                raise ValueError("merge_target_not_found")
            before = dict(row)
            legacy_status = "rejected" if decision == "merged" else decision
            reviewed_value = final_value.strip() or row["normalized_value"]
            conn.execute(
                """UPDATE v05g_extraction_candidates SET pipeline_review_status=?,review_status=?,normalized_value=?,review_note=?,
                   rejection_reason=?,merged_into_candidate_id=?,reviewed_by=?,reviewed_at=?,updated_at=? WHERE id=?""",
                (decision, legacy_status, reviewed_value, reason or None, reason or None if decision == "rejected" else None, merged_into_candidate_id, actor, now(), now(), candidate_id),
            )
            after = dict(conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (candidate_id,)).fetchone())
            conn.execute("INSERT INTO v05g_candidate_review_history(candidate_id,action,actor,note,before_json,after_json,created_at) VALUES (?,?,?,?,?,?,?)", (candidate_id, decision, actor, reason or None, json.dumps(before, ensure_ascii=False, default=str), json.dumps(after, ensure_ascii=False, default=str), now()))
            conn.execute("INSERT INTO p2_intelligence_audit_log(entity_type,entity_id,action,actor,before_json,after_json,note,created_at) VALUES ('fact_candidate',?,?,?,?,?,?,?)", (candidate_id, decision, actor, json.dumps(before, ensure_ascii=False, default=str), json.dumps(after, ensure_ascii=False, default=str), reason or None, now()))
            return after
