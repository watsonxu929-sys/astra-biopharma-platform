import json
from datetime import datetime

from app.services.fact_candidate_service import FactCandidateService, REVIEW_STATES, now
from app.v04c_review import db_connection


class IntelligenceReviewService(FactCandidateService):
    """Canonical P2.1 candidate review service; inherits the audited state workflow."""

    def edit_article(self, candidate_id: int, *, actor: str, permissions: set[str], title: str,
                     content: str, published_at: str = '', note: str = '', attachments_reviewed: bool = False) -> None:
        if 'review_data' not in permissions:
            raise PermissionError('review_data_required')
        if not title.strip() or not content.strip() or len(title) > 400 or len(content) > 80000:
            raise ValueError('请填写标题与正文（标题最多400字，正文最多80000字）')
        if published_at:
            datetime.fromisoformat(published_at)
            if not note.strip():
                raise ValueError('补充日期时请填写原文依据')
        with db_connection(self.db_path) as conn:
            row = conn.execute("SELECT * FROM v05g_extraction_candidates WHERE id=? AND field_name='article_review'", (candidate_id,)).fetchone()
            if not row:
                raise ValueError('article_candidate_not_found')
            if conn.execute('SELECT 1 FROM p2_intelligence_product_candidates WHERE candidate_id=?', (candidate_id,)).fetchone():
                raise ValueError('已发布内容请通过情报管理编辑')
            payload = json.loads(row['payload_json'] or '{}')
            before = dict(row)
            payload['article_edit'] = {'title': title.strip(), 'content': content.strip(),
                'published_at': published_at or None, 'date_basis': note, 'attachments_reviewed': attachments_reviewed}
            conn.execute("UPDATE v05g_extraction_candidates SET payload_json=?,pipeline_review_status='pending',review_status='pending',reviewed_by=NULL,reviewed_at=NULL,updated_at=? WHERE id=?", (json.dumps(payload, ensure_ascii=False), now(), candidate_id))
            after = dict(conn.execute('SELECT * FROM v05g_extraction_candidates WHERE id=?', (candidate_id,)).fetchone())
            conn.execute('INSERT INTO v05g_candidate_review_history(candidate_id,action,actor,note,before_json,after_json,created_at) VALUES (?,?,?,?,?,?,?)',
                         (candidate_id,'article_edited',actor,note,json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),now()))

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
            if decision == 'approved':
                from app.services.processing.processing_job_service import candidate_detail
                detail = candidate_detail(candidate_id, self.db_path)
                if detail and detail['candidate']['field_name'] == 'article_review' and not detail['article']['assessment']['publishable']:
                    raise ValueError('；'.join(detail['article']['assessment']['gaps']))
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
