from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

ALLOWED_CANDIDATE_TYPES = {"organization", "person", "project", "product", "event", "relationship", "resource", "need", "risk", "opportunity", "field"}


class SchemaValidationError(ValueError):
    pass


@dataclass(frozen=True)
class FactCandidateOutput:
    candidate_type: str
    value: str
    evidence_excerpt: str
    confidence_score: int
    subject_type: str | None = None
    subject_label: str | None = None
    event_type: str | None = None
    fields: dict[str, Any] = field(default_factory=dict)
    char_start: int | None = None
    char_end: int | None = None
    page_number: int | None = None
    table_number: str | None = None

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> "FactCandidateOutput":
        try:
            candidate = cls(
                candidate_type=str(value["candidate_type"]).strip(),
                value=str(value["value"]).strip(),
                evidence_excerpt=str(value["evidence_excerpt"]).strip(),
                confidence_score=int(value["confidence_score"]),
                subject_type=(str(value.get("subject_type")).strip() or None) if value.get("subject_type") is not None else None,
                subject_label=(str(value.get("subject_label")).strip() or None) if value.get("subject_label") is not None else None,
                event_type=(str(value.get("event_type")).strip() or None) if value.get("event_type") is not None else None,
                fields=dict(value.get("fields") or {}),
                char_start=int(value["char_start"]) if value.get("char_start") is not None else None,
                char_end=int(value["char_end"]) if value.get("char_end") is not None else None,
                page_number=int(value["page_number"]) if value.get("page_number") is not None else None,
                table_number=str(value["table_number"]) if value.get("table_number") is not None else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise SchemaValidationError("invalid_fact_candidate_shape") from exc
        if candidate.candidate_type not in ALLOWED_CANDIDATE_TYPES:
            raise SchemaValidationError("invalid_candidate_type")
        if not candidate.value or not candidate.evidence_excerpt:
            raise SchemaValidationError("candidate_value_and_evidence_required")
        if not 0 <= candidate.confidence_score <= 100:
            raise SchemaValidationError("confidence_out_of_range")
        if candidate.char_start is not None and candidate.char_end is not None and candidate.char_end < candidate.char_start:
            raise SchemaValidationError("invalid_evidence_range")
        return candidate


@dataclass(frozen=True)
class AnalysisResult:
    summary: str = ""
    event_classification: str = "unknown"
    entities: list[dict[str, Any]] = field(default_factory=list)
    candidates: list[FactCandidateOutput] = field(default_factory=list)
    importance: int = 1
    research_outline: list[str] = field(default_factory=list)
    generated_by: str = "rule"
    provider: str = "rule"
    model: str = ""
    prompt_version: str = "p2.1-v1"
    usage: dict[str, Any] = field(default_factory=dict)
    raw_result: str = ""

    @classmethod
    def from_mapping(cls, value: dict[str, Any], **provenance: Any) -> "AnalysisResult":
        if not isinstance(value, dict):
            raise SchemaValidationError("analysis_result_must_be_object")
        candidates = [FactCandidateOutput.from_mapping(item) for item in value.get("candidates", [])]
        importance = int(value.get("importance", 1))
        if not 1 <= importance <= 5:
            raise SchemaValidationError("importance_out_of_range")
        return cls(
            summary=str(value.get("summary") or ""),
            event_classification=str(value.get("event_classification") or "unknown"),
            entities=list(value.get("entities") or []),
            candidates=candidates,
            importance=importance,
            research_outline=[str(item) for item in value.get("research_outline") or []],
            usage=dict(value.get("usage") or {}),
            raw_result=str(value.get("raw_result") or ""),
            **provenance,
        )
