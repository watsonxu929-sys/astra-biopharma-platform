from __future__ import annotations

import json
import os

from .base import AIProvider, ProviderUnavailable
from .schemas import AnalysisResult


class OpenAIProvider(AIProvider):
    name = "openai"
    prompt_version = "p2.1-openai-v1"
    generated_by = "ai"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5-mini")

    @property
    def available(self) -> bool:
        return bool(os.getenv("OPENAI_API_KEY"))

    def analyze(self, text: str, *, title: str = "", source_url: str = "") -> AnalysisResult:
        if not self.available:
            raise ProviderUnavailable("openai_api_key_unavailable")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise ProviderUnavailable("openai_sdk_unavailable") from exc
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        response = client.responses.create(
            model=self.model,
            input=[
                {"role": "system", "content": "Return JSON only with summary, event_classification, entities, candidates, importance, research_outline. Every candidate requires evidence_excerpt and confidence_score. Do not publish or modify canonical records."},
                {"role": "user", "content": json.dumps({"title": title, "source_url": source_url, "text": text[:30000]}, ensure_ascii=False)},
            ],
        )
        payload = json.loads(response.output_text)
        payload["raw_result"] = response.output_text
        usage = getattr(response, "usage", None)
        payload["usage"] = usage.model_dump() if usage and hasattr(usage, "model_dump") else {}
        return AnalysisResult.from_mapping(payload, generated_by=self.generated_by, provider=self.name, model=self.model, prompt_version=self.prompt_version)
