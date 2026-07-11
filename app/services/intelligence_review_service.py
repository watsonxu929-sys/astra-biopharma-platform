import json

from app.services.fact_candidate_service import FactCandidateService, REVIEW_STATES, now
from app.v04c_review import db_connection


class IntelligenceReviewService(FactCandidateService):
    """Canonical P2.1 candidate review service; inherits the audited state workflow."""

    def submit_candidate(self, candidate_id: int, *, actor: str, permissions: set[str]) -> dict:
        if "review_data" not in permissions:
            raise PermissionError("review_data_required")
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (candidate_id,)).fetchone()
            if not row:
                raise ValueError("candidate_not_found")
            if not conn.execute("SELECT 1 FROM p2_fact_candidate_evidence WHERE candidate_id=? LIMIT 1", (candidate_id,)).fetchone():
                raise ValueError("candidate_evidence_required")
            before = dict(row)
            conn.execute(
                "UPDATE v05g_extraction_candidates SET pipeline_review_status='pending',review_status='pending',updated_at=? WHERE id=?",
                (now(), candidate_id),
            )
            after = dict(conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=?", (candidate_id,)).fetchone())
            conn.execute(
                "INSERT INTO v05g_candidate_review_history(candidate_id,action,actor,note,before_json,after_json,created_at) VALUES (?,?,?,?,?,?,?)",
                (candidate_id, "submitted", actor, "提交 P2.1 情报审核", json.dumps(before, ensure_ascii=False, default=str), json.dumps(after, ensure_ascii=False, default=str), now()),
            )
            conn.execute(
                "INSERT INTO p2_intelligence_audit_log(entity_type,entity_id,action,actor,before_json,after_json,note,created_at) VALUES ('fact_candidate',?,?,?,?,?,?,?)",
                (candidate_id, "submitted", actor, json.dumps(before, ensure_ascii=False, default=str), json.dumps(after, ensure_ascii=False, default=str), "提交 P2.1 情报审核", now()),
            )
            return after

    def review_candidate(
        self,
        candidate_id: int,
        *,
        decision: str,
        actor: str,
        permissions: set[str],
        note: str = "",
        final_value: str = "",
    ) -> dict:
        with db_connection(self.db_path) as conn:
            has_evidence_table = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='p2_fact_candidate_evidence'"
            ).fetchone()
            has_evidence = bool(
                has_evidence_table
                and conn.execute(
                    "SELECT 1 FROM p2_fact_candidate_evidence WHERE candidate_id=? LIMIT 1",
                    (candidate_id,),
                ).fetchone()
            )
        if has_evidence:
            return self.review(
                candidate_id, decision=decision, actor=actor, permissions=permissions,
                reason=note, final_value=final_value,
            )
        if "review_data" not in permissions:
            raise PermissionError("review_data_required")
        from app.services.processing.processing_job_service import review_candidate as review_legacy_candidate
        return review_legacy_candidate(
            candidate_id, decision=decision, actor=actor, note=note,
            final_value=final_value, db_path=self.db_path,
        )
