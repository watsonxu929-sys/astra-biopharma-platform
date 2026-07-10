from app.services.fact_candidate_service import FactCandidateService, REVIEW_STATES
from app.v04c_review import db_connection


class IntelligenceReviewService(FactCandidateService):
    """Canonical P2.1 candidate review service; inherits the audited state workflow."""

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
