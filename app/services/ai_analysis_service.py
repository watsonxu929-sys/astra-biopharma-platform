from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime
from pathlib import Path

from app.services.ai import ProviderRegistry
from app.services.fact_candidate_service import FactCandidateService
from app.v04c_review import db_connection


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


class AIAnalysisService:
    def __init__(self, db_path: str | Path | None = None, registry: ProviderRegistry | None = None):
        self.db_path = db_path
        self.registry = registry or ProviderRegistry()
        self.candidates = FactCandidateService(db_path)

    def analyze(
        self,
        *,
        processing_job_id: int,
        snapshot_id: int,
        text: str,
        title: str = "",
        provider_name: str = "rule",
        raw_intelligence_id: int | None = None,
        is_pilot: bool = False,
        pilot_batch_id: str | None = None,
    ) -> dict:
        provider = self.registry.get(provider_name, fallback=True)
        run_no = f"AIR-{uuid.uuid4().hex[:16].upper()}"
        with db_connection(self.db_path) as conn:
            cur = conn.execute(
                """INSERT INTO p2_ai_analysis_runs(run_no,processing_job_id,snapshot_id,raw_intelligence_id,
                   provider,model,prompt_version,generated_by,status,created_at)
                   VALUES (?,?,?,?,?,?,?,?, 'running',?)""",
                (run_no, processing_job_id, snapshot_id, raw_intelligence_id, provider.name, provider.model, provider.prompt_version, provider.generated_by, now()),
            )
            run_id = int(cur.lastrowid)
        try:
            result = provider.analyze(text, title=title)
            result_dict = {
                "summary": result.summary,
                "event_classification": result.event_classification,
                "importance": result.importance,
                "entities": result.entities,
                "candidates": [candidate.__dict__ for candidate in result.candidates],
                "research_outline": result.research_outline,
            }
            result_json = json.dumps(result_dict, ensure_ascii=False, sort_keys=True, default=str)
            result_hash = hashlib.sha256(result_json.encode("utf-8")).hexdigest()
            created = []
            for item in result.candidates:
                created.append(self.candidates.create(
                    processing_job_id=processing_job_id, snapshot_id=snapshot_id,
                    candidate_type=item.candidate_type, value=item.value,
                    evidence_excerpt=item.evidence_excerpt, confidence_score=item.confidence_score,
                    generated_by=result.generated_by, provider=result.provider, model=result.model,
                    prompt_version=result.prompt_version, subject_type=item.subject_type,
                    subject_label=item.subject_label, event_type=item.event_type, fields=item.fields,
                    char_start=item.char_start, char_end=item.char_end, page_number=item.page_number,
                    table_number=item.table_number,
                    is_pilot=is_pilot, pilot_batch_id=pilot_batch_id,
                ))
            with db_connection(self.db_path) as conn:
                conn.execute("UPDATE p2_ai_analysis_runs SET status='success',token_usage_json=?,result_hash=?,raw_result=?,finished_at=? WHERE id=?", (json.dumps(result.usage, ensure_ascii=False), result_hash, result.raw_result or result_json, now(), run_id))
            return {"run_id": run_id, "status": "success", "provider": result.provider, "generated_by": result.generated_by, "candidate_ids": [item["id"] for item in created]}
        except Exception as exc:
            with db_connection(self.db_path) as conn:
                conn.execute("UPDATE p2_ai_analysis_runs SET status='failed',error_type=?,error_message=?,finished_at=? WHERE id=?", (exc.__class__.__name__, str(exc)[:800], now(), run_id))
            return {"run_id": run_id, "status": "failed", "error_type": exc.__class__.__name__, "error": str(exc)[:800], "candidate_ids": []}
