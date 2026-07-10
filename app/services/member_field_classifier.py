from __future__ import annotations

import re
from dataclasses import dataclass

from app.services.member_import_normalizer import clean_text


EXPERTISE_KEYWORDS = (
    "擅长",
    "专注",
    "深耕",
    "从事",
    "负责",
    "核心工作",
    "研究方向",
    "专业领域",
    "CMC",
    "工艺开发",
    "工艺研究",
    "工艺放大",
    "放大",
    "BD",
    "投融资",
    "临床",
    "注册",
    "市场准入",
    "创新药",
)

RESOURCE_KEYWORDS = ("可提供", "能够提供", "拥有资源", "可以对接", "可协助", "可引荐", "可分享", "可支持")
NEED_KEYWORDS = ("希望", "寻求", "需要", "期待", "拟对接", "正在寻找", "合作需求", "融资需求", "场地需求", "人才需求")


@dataclass(frozen=True)
class ClassifiedSentence:
    field: str
    value: str
    confidence: int
    rule: str
    evidence: str


def classify_sentence(sentence: str) -> list[ClassifiedSentence]:
    text = clean_text(sentence).strip(" ，,。；;")
    if not text:
        return []
    has_need = any(key in text for key in NEED_KEYWORDS)
    has_resource = any(key in text for key in RESOURCE_KEYWORDS)
    if has_need and has_resource:
        return _split_need_and_resource(text)
    if has_need:
        return [ClassifiedSentence("cooperation_needs", _strip_prefix(text, NEED_KEYWORDS), 86, "need_keywords", text)]
    if has_resource:
        return [ClassifiedSentence("offered_resources", _strip_prefix(text, RESOURCE_KEYWORDS), 86, "resource_keywords", text)]
    if any(key in text for key in EXPERTISE_KEYWORDS):
        focus = re.search(r"(?:专注|擅长|研究方向|专业领域)\s*([^，,。；;]+)", text)
        if focus:
            return [ClassifiedSentence("expertise_tags", focus.group(1).strip(), 86, "expertise_focus_phrase", text)]
        return [ClassifiedSentence("expertise_tags", extract_expertise_terms(text), 82, "expertise_keywords", text)]
    if len(text) >= 8:
        return [ClassifiedSentence("self_introduction", text, 65, "bio_fallback", text)]
    return []


def extract_expertise_terms(text: str) -> str:
    terms: list[str] = []
    for keyword in EXPERTISE_KEYWORDS:
        if keyword in text and keyword not in {"专注", "深耕", "从事", "负责", "核心工作", "研究方向", "专业领域"}:
            terms.append("工艺放大" if keyword == "放大" else keyword)
    if "工艺研究" in text and "工艺研究" not in terms:
        terms.append("工艺研究")
    if "工艺开发" in text and "工艺开发" not in terms:
        terms.append("工艺开发")
    if not terms:
        return text
    return "、".join(dict.fromkeys(terms))


def _split_need_and_resource(text: str) -> list[ClassifiedSentence]:
    parts: list[ClassifiedSentence] = []
    resource_match = re.search(r"(可提供|能够提供|拥有资源|可以对接|可协助|可引荐|可分享|可支持)(.+)$", text)
    if resource_match:
        resource = resource_match.group(2).strip(" ，,。；;")
        need_part = text[: resource_match.start()].strip(" ，,。；;")
        if need_part:
            parts.append(ClassifiedSentence("cooperation_needs", _strip_prefix(need_part, NEED_KEYWORDS), 86, "need_before_resource", text))
        if resource:
            parts.append(ClassifiedSentence("offered_resources", resource, 88, "resource_after_need", text))
        return parts
    return [ClassifiedSentence("cooperation_needs", _strip_prefix(text, NEED_KEYWORDS), 78, "mixed_need_resource", text)]


def _strip_prefix(text: str, prefixes: tuple[str, ...]) -> str:
    value = text
    for prefix in prefixes:
        value = re.sub(rf"^{re.escape(prefix)}", "", value).strip(" ：:，,")
    return value
