from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PromptDefinition:
    prompt_id: str
    version: str
    scenario: str
    input_fields: tuple[str, ...]
    output_schema: str
    change_note: str
    created_at: str
    instruction: str


_COMMON = {
    "version": "1.0.0",
    "input_fields": ("title", "source_url", "text"),
    "created_at": "2026-07-11",
}

PROMPTS = {
    "summarize_v1": PromptDefinition(
        prompt_id="summarize_v1", scenario="evidence-bound summary",
        output_schema="summary:string", change_note="initial controlled pilot",
        instruction="Summarize only claims explicitly supported by the supplied text.", **_COMMON,
    ),
    "event_classification_v1": PromptDefinition(
        prompt_id="event_classification_v1", scenario="biopharma event classification",
        output_schema="event_classification:string", change_note="initial controlled pilot",
        instruction="Classify the principal biopharma event; use unknown when evidence is insufficient.", **_COMMON,
    ),
    "entity_extraction_v1": PromptDefinition(
        prompt_id="entity_extraction_v1", scenario="organization and person extraction",
        output_schema="entities:[{type,name,evidence_excerpt}]", change_note="initial controlled pilot",
        instruction="Extract named entities verbatim and attach a supporting excerpt.", **_COMMON,
    ),
    "fact_candidate_v1": PromptDefinition(
        prompt_id="fact_candidate_v1", scenario="reviewable fact candidates",
        output_schema="candidates:[FactCandidateOutput]", change_note="initial controlled pilot",
        instruction="Create candidates only when each value has a verbatim evidence excerpt; never publish.", **_COMMON,
    ),
    "importance_assessment_v1": PromptDefinition(
        prompt_id="importance_assessment_v1", scenario="importance score",
        output_schema="importance:integer[1,5]", change_note="initial controlled pilot",
        instruction="Score importance from 1 to 5 using only regulatory, clinical, financing, product or industry impact.", **_COMMON,
    ),
}


def get_prompt(prompt_id: str) -> PromptDefinition:
    return PROMPTS[prompt_id]


def combined_analysis_prompt() -> tuple[str, str]:
    ordered = tuple(PROMPTS.values())
    version = "+".join(f"{item.prompt_id}@{item.version}" for item in ordered)
    instructions = "\n".join(f"- {item.instruction}" for item in ordered)
    schema = (
        "Return one JSON object with summary, event_classification, entities, candidates, "
        "importance, and research_outline. Every candidate requires candidate_type, value, "
        "evidence_excerpt and confidence_score. Do not modify canonical records."
    )
    return version, f"{schema}\n{instructions}"
