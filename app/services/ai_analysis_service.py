from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from datetime import datetime
from pathlib import Path

from app.services.ai import ProviderRegistry
from app.services.ai_budget import AIPilotBudget
from app.services.fact_candidate_service import FactCandidateService
from app.v04c_review import db_connection


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


class AIAnalysisService:
    def __init__(self, db_path: str | Path | None = None, registry: ProviderRegistry | None = None, budget: AIPilotBudget | None = None):
        self.db_path = db_path
        self.registry = registry or ProviderRegistry()
        self.candidates = FactCandidateService(db_path)

        self.budget = budget or AIPilotBudget()
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
        quality_status: str = "accepted",
    ) -> dict:
        provider = self.registry.get(provider_name, fallback=True)
        run_no = f"AIR-{uuid.uuid4().hex[:16].upper()}"
        if provider.name == "openai" and quality_status != "accepted":
            return {"status": "skipped", "error_type": "quality_gate_rejected", "candidate_ids": []}
        self.budget.reserve(provider.name)
        input_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        started = time.perf_counter()

        with db_connection(self.db_path) as conn:
            cur = conn.execute(
                """INSERT INTO p2_ai_analysis_runs(run_no,processing_job_id,snapshot_id,raw_intelligence_id,
                   provider,model,prompt_version,generated_by,status,created_at)
                   VALUES (?,?,?,?,?,?,?,?, 'running',?)""",
                (run_no, processing_job_id, snapshot_id, raw_intelligence_id, provider.name, provider.model, provider.prompt_version, provider.generated_by, now()),
            )
            run_id = int(cur.lastrowid)
            columns = {row[1] for row in conn.execute("PRAGMA table_info(p2_ai_analysis_runs)")}
            if "input_hash" in columns:
                conn.execute(
                    "UPDATE p2_ai_analysis_runs SET input_hash=?,pilot_batch_id=? WHERE id=?",
                    (input_hash, pilot_batch_id, run_id),
                )
        try:
            result = provider.analyze(text, title=title)
            latency_ms = round((time.perf_counter() - started) * 1000)
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
            estimated_cost = self.budget.record_usage(
                result.usage,
                input_cost_per_million=float(os.getenv("OPENAI_INPUT_COST_PER_MILLION", "0") or 0),
                output_cost_per_million=float(os.getenv("OPENAI_OUTPUT_COST_PER_MILLION", "0") or 0),
            ) if result.provider == "openai" else 0.0

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
                columns = {row[1] for row in conn.execute("PRAGMA table_info(p2_ai_analysis_runs)")}
                if "latency_ms" in columns:
                    conn.execute(
                        "UPDATE p2_ai_analysis_runs SET output_hash=?,latency_ms=?,estimated_cost_usd=?,retry_count=?,schema_repair_count=? WHERE id=?",
                        (result_hash, latency_ms, estimated_cost,
                         min(int(result.usage.get("retry_count") or 0), 1),
                         min(int(result.usage.get("schema_repair_count") or 0), 1), run_id),
                    )
            return {"run_id": run_id, "status": "success", "provider": result.provider, "generated_by": result.generated_by, "candidate_ids": [item["id"] for item in created]}
        except Exception as exc:
            with db_connection(self.db_path) as conn:
                conn.execute("UPDATE p2_ai_analysis_runs SET status='failed',error_type=?,error_message=?,finished_at=? WHERE id=?", (exc.__class__.__name__, str(exc)[:800], now(), run_id))
            return {"run_id": run_id, "status": "failed", "error_type": exc.__class__.__name__, "error": str(exc)[:800], "candidate_ids": []}
