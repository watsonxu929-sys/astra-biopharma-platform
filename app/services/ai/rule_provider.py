from __future__ import annotations

import re

from .base import AIProvider
from .schemas import AnalysisResult, FactCandidateOutput


class RuleProvider(AIProvider):
    name = "rule"
    model = "deterministic-rules"
    prompt_version = "p2.2-rule-v2"
    generated_by = "rule"

    EVENT_RULES = (("融资", "financing"), ("获批", "approval"), ("批准", "approval"), ("合作", "cooperation"), ("临床", "clinical_progress"), ("招聘", "recruitment"), ("入选", "recognition"))
    EVENT_RULES = EVENT_RULES + (
        ("approved", "regulatory_approval"),
        ("approval", "regulatory_approval"),
        ("financing", "financing"),
        ("funding", "financing"),
        ("clinical trial", "clinical_progress"),
        ("partnership", "cooperation"),
        ("recruiting", "recruitment"),
    )

    def analyze(self, text: str, *, title: str = "", source_url: str = "") -> AnalysisResult:
        clean = re.sub(r"\s+", " ", text or "").strip()
        event_type = next((event for keyword, event in self.EVENT_RULES if keyword in clean), "unknown")
        candidates = []
        if event_type != "unknown" and clean:
            keyword = next(keyword for keyword, event in self.EVENT_RULES if event == event_type and keyword in clean)
            pos = clean.find(keyword)
            start = max(0, pos - 100)
            end = min(len(clean), pos + 300)
            candidates.append(FactCandidateOutput(candidate_type="event", value=event_type, event_type=event_type, evidence_excerpt=clean[start:end], confidence_score=75, char_start=start, char_end=end, fields={"source_url": source_url}))
        entities = [{"type": "organization", "label": match.group(0)} for match in re.finditer(r"[\u4e00-\u9fffA-Za-z0-9·（）()]{2,40}(?:公司|集团|研究院|大学|医院)", clean)][:20]
        entities.extend(
            {"type": "organization", "label": match.group(0).strip()}
            for match in re.finditer(r"[A-Za-z0-9 .&-]{2,50}(?:Inc\.|Ltd\.|Corporation|Agency)", clean)
        )
        if re.search(r"\bFDA\b", clean) and not any(item.get("label") == "FDA" for item in entities):
            entities.insert(0, {"type": "organization", "label": "FDA"})

        return AnalysisResult(summary=clean[:300], event_classification=event_type, entities=entities, candidates=candidates, importance=3 if event_type in {"financing", "approval", "clinical_progress"} else 2, research_outline=["事件概览", "相关主体", "证据与待核实事项"], generated_by=self.generated_by, provider=self.name, model=self.model, prompt_version=self.prompt_version)
