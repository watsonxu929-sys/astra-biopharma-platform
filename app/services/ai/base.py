from __future__ import annotations

from abc import ABC, abstractmethod

from .schemas import AnalysisResult


class ProviderUnavailable(RuntimeError):
    pass


class AIProvider(ABC):
    name = "base"
    model = ""
    prompt_version = "p2.1-v1"
    generated_by = "ai"

    @property
    def available(self) -> bool:
        return True

    @abstractmethod
    def analyze(self, text: str, *, title: str = "", source_url: str = "") -> AnalysisResult:
        raise NotImplementedError

    def summarize(self, text: str, **context) -> str:
        return self.analyze(text, **context).summary

    def classify_event(self, text: str, **context) -> str:
        return self.analyze(text, **context).event_classification

    def extract_entities(self, text: str, **context) -> list[dict]:
        return self.analyze(text, **context).entities

    def extract_fact_candidates(self, text: str, **context) -> list:
        return self.analyze(text, **context).candidates

    def assess_importance(self, text: str, **context) -> int:
        return self.analyze(text, **context).importance

    def generate_research_outline(self, text: str, **context) -> list[str]:
        return self.analyze(text, **context).research_outline
