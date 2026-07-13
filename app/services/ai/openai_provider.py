from __future__ import annotations

import json
import os

import time
from .base import AIProvider, ProviderUnavailable
from .prompts import combined_analysis_prompt
from .schemas import AnalysisResult, SchemaValidationError


class OpenAIProvider(AIProvider):
    name = "openai"
    generated_by = "ai"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5-mini")
        self.prompt_version, self.system_prompt = combined_analysis_prompt()

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
        request = {"title": title, "source_url": source_url, "text": text[:30000]}

        def call(messages: list[dict]) -> object:
            last_error: Exception | None = None
            for attempt in range(2):
                try:
                    return client.responses.create(model=self.model, input=messages)
                except Exception as exc:
                    last_error = exc
                    status = getattr(exc, "status_code", None)
                    if attempt or status not in {408, 429, 500, 502, 503, 504}:
                        raise
                    time.sleep(1.0)
            raise last_error or RuntimeError("openai_request_failed")

        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
        ]
        response = call(messages)
        repair_count = 0
        try:
            payload = json.loads(response.output_text)
            result = AnalysisResult.from_mapping(
                payload, generated_by=self.generated_by, provider=self.name,
                model=self.model, prompt_version=self.prompt_version,
            )
        except (json.JSONDecodeError, SchemaValidationError, TypeError, ValueError):
            repair_count = 1
            response = call([
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": "Repair this invalid output once. Return JSON only: " + response.output_text[:20000]},
            ])
            payload = json.loads(response.output_text)
            result = AnalysisResult.from_mapping(
                payload, generated_by=self.generated_by, provider=self.name,
                model=self.model, prompt_version=self.prompt_version,
            )
        usage = getattr(response, "usage", None)
        usage_data = usage.model_dump() if usage and hasattr(usage, "model_dump") else {}
        usage_data["schema_repair_count"] = repair_count
        return AnalysisResult(**{
            **result.__dict__, "usage": usage_data, "raw_result": response.output_text
        })
