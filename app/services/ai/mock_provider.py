from __future__ import annotations

from typing import Any

from .base import AIProvider
from .schemas import AnalysisResult


class MockProvider(AIProvider):
    name = "mock"
    model = "test-double"
    prompt_version = "p2.1-mock-v1"
    generated_by = "mock"

    def __init__(self, result: dict[str, Any] | None = None):
        self.result = result or {"summary": "mock summary", "event_classification": "unknown", "importance": 1, "candidates": []}

    def analyze(self, text: str, *, title: str = "", source_url: str = "") -> AnalysisResult:
        return AnalysisResult.from_mapping(self.result, generated_by=self.generated_by, provider=self.name, model=self.model, prompt_version=self.prompt_version)
