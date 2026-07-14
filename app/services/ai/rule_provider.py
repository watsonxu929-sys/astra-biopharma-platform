from __future__ import annotations

import re

from .base import AIProvider
from .schemas import AnalysisResult, FactCandidateOutput


class RuleProvider(AIProvider):
    name = "rule"
    model = "deterministic-rules"
    prompt_version = "t2-rule-v1"
    generated_by = "rule"

    EVENT_TYPE_MAP = {
        "financing": ("融资事件", ["融资", "募资", "投资", "A轮", "B轮", "Pre-A", "IPO", "funding", "series"]),
        "approval": ("监管审批", ["获批", "批准", "注册", "IND", "NDA", "上市申请", "approved", "approval", "marketing authorization"]),
        "cooperation": ("许可合作", ["合作", "签约", "授权", "license", "collaboration", "共建", "partnership"]),
        "clinical": ("临床进展", ["临床", "入组", "III期", "II期", "I期", "试验", "clinical trial", "phase"]),
        "recruitment": ("人事变动", ["任命", "聘任", "离职", "人事", "appointment", "resignation"]),
        "product_launch": ("产品发布", ["上市", "发布", "推出", "launch", "release"]),
        "tech_progress": ("技术进展", ["突破", "进展", "研究发现", "技术", "研发", "breakthrough"]),
        "merger": ("并购交易", ["并购", "收购", "M&A", "acquisition", "merger"]),
        "policy": ("政策发布", ["政策", "通知", "办法", "规定", "regulation", "policy"]),
        "conference": ("行业活动", ["会议", "论坛", "峰会", "研讨会", "conference", "summit"]),
        "corporate": ("企业动态", ["成立", "更名", "重组", "退市", "入选", "榜单", "corporate"]),
    }

    def analyze(self, text: str, *, title: str = "", source_url: str = "") -> AnalysisResult:
        clean = re.sub(r"\s+", " ", text or "").strip()
        event_type, event_label = self._detect_event(clean)
        summary = self._generate_summary(title, clean, event_label)
        candidates = []
        if event_type != "unknown" and clean:
            keyword_info = self._find_keyword_context(clean, event_type)
            if keyword_info:
                candidates.append(FactCandidateOutput(candidate_type="event", value=event_label, event_type=event_type, evidence_excerpt=keyword_info["excerpt"], confidence_score=75, char_start=keyword_info["start"], char_end=keyword_info["end"], fields={"source_url": source_url}))
        entities = self._extract_entities(clean)
        importance = self._calculate_importance(event_type)
        return AnalysisResult(summary=summary, event_classification=event_type, event_label=event_label, entities=entities, candidates=candidates, importance=importance, research_outline=["事件概览", "相关主体", "证据与待核实事项"], generated_by=self.generated_by, provider=self.name, model=self.model, prompt_version=self.prompt_version)

    def _detect_event(self, text: str) -> tuple[str, str]:
        priority_order = ["approval", "clinical", "financing", "merger", "cooperation", "product_launch", "tech_progress", "corporate", "policy", "conference", "recruitment"]
        lowered = text.lower()
        for event_type in priority_order:
            label, keywords = self.EVENT_TYPE_MAP.get(event_type, (event_type, []))
            if any(keyword.lower() in lowered for keyword in keywords):
                return event_type, label
        return "unknown", "其他"

    def _generate_summary(self, title: str, text: str, event_label: str) -> str:
        if not text:
            return title[:160] if title else "内容为空"
        if event_label != "其他":
            first_paragraph = self._find_first_meaningful_paragraph(text)
            if first_paragraph:
                summary = f"{event_label}：{first_paragraph}"
            else:
                summary = f"{event_label}：{text[:120]}"
        else:
            first_paragraph = self._find_first_meaningful_paragraph(text)
            summary = first_paragraph if first_paragraph else text[:160]
        if title and not title[:50] in summary:
            summary = f"{title[:50]}。{summary}"
        return self._trim_to_length(summary, 80, 160)

    def _find_first_meaningful_paragraph(self, text: str) -> str:
        sentences = re.split(r"[。.!?；;\n]+", text)
        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) >= 20 and not self._is_heading_or_noise(sentence):
                return sentence
        return ""

    def _is_heading_or_noise(self, text: str) -> bool:
        noise_patterns = [
            r"^[\d一二三四五六七八九十]+[、.)]",
            r"^\s*$",
            r"^免责声明",
            r"^版权所有",
            r"^返回首页",
            r"^上一篇|下一篇",
        ]
        for pattern in noise_patterns:
            if re.match(pattern, text):
                return True
        return len(text) < 10

    def _trim_to_length(self, text: str, min_len: int, max_len: int) -> str:
        text = re.sub(r"\s+", " ", text).strip()
        if len(text) <= max_len:
            return text
        truncated = text[:max_len]
        last_period = truncated.rfind("。")
        last_comma = truncated.rfind("，")
        if last_period > min_len:
            return truncated[:last_period+1]
        elif last_comma > min_len:
            return truncated[:last_comma+1]
        return truncated

    def _find_keyword_context(self, text: str, event_type: str) -> dict | None:
        _, keywords = self.EVENT_TYPE_MAP.get(event_type, (event_type, []))
        lowered = text.lower()
        for keyword in keywords:
            pos = lowered.find(keyword.lower())
            if pos >= 0:
                start = max(0, pos - 50)
                end = min(len(text), pos + len(keyword) + 150)
                return {"excerpt": text[start:end], "start": start, "end": end}
        return None

    def _extract_entities(self, text: str) -> list[dict]:
        entities = []
        seen_labels = set()
        org_pattern = r"[\u4e00-\u9fffA-Za-z0-9·（）()]{2,40}(?:公司|集团|研究院|大学|医院)"
        for match in re.finditer(org_pattern, text):
            label = match.group(0)
            if label not in seen_labels:
                seen_labels.add(label)
                entities.append({"type": "organization", "label": label})
        eng_org_pattern = r"[A-Za-z0-9 .&-]{2,50}(?:Inc\.|Ltd\.|Corporation|Agency)"
        for match in re.finditer(eng_org_pattern, text):
            label = match.group(0).strip()
            if label not in seen_labels:
                seen_labels.add(label)
                entities.append({"type": "organization", "label": label})
        if re.search(r"\bFDA\b", text) and "FDA" not in seen_labels:
            entities.insert(0, {"type": "organization", "label": "FDA"})
        if re.search(r"\bEMA\b", text) and "EMA" not in seen_labels:
            entities.insert(0, {"type": "organization", "label": "EMA"})
        return entities[:5]

    def _calculate_importance(self, event_type: str) -> int:
        if event_type in {"approval", "clinical", "financing", "merger"}:
            return 4
        if event_type in {"cooperation", "product_launch", "tech_progress"}:
            return 3
        if event_type in {"policy", "corporate"}:
            return 2
        return 1