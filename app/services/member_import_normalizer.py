from __future__ import annotations

import re
from typing import Any


INVALID_HEADINGS = {
    "管理团队",
    "核心团队",
    "会员名单",
    "团队介绍",
    "关于我们",
    "联系方式",
    "参会名单",
    "签到表",
    "个人简介",
    "专家介绍",
}

ORG_SUFFIXES = (
    "有限公司",
    "股份有限公司",
    "集团",
    "公司",
    "大学",
    "学院",
    "医院",
    "研究院",
    "研究所",
    "中心",
    "基金",
    "园区",
    "协会",
    "实验室",
    "药业",
    "生物科技",
)

TITLE_TERMS = (
    "董事长",
    "总经理",
    "CEO",
    "首席执行官",
    "创始人",
    "联合创始人",
    "副总裁",
    "总监",
    "BD负责人",
    "BD总监",
    "投资总监",
    "研发负责人",
    "科学家",
    "教授",
    "主任",
    "合伙人",
    "负责人",
)

ORG_SEMANTIC_WORDS = (
    "就职于",
    "任职于",
    "来自",
    "所在单位",
    "所在机构",
    "公司",
    "学校",
    "医院",
    "研究院",
    "中心",
    "基金",
    "园区",
    "集团",
)

MOBILE_RE = re.compile(r"(?<!\d)(?:\+?86[-\s]?)?1[3-9]\d{9}(?!\d)")
EMAIL_RE = re.compile(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", re.I)
HAN_NAME_RE = re.compile(r"^[\u4e00-\u9fff·]{2,5}$")
EN_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z .'-]{1,80}$")


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).replace("\u3000", " ").replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    return "\n".join(line.strip() for line in text.splitlines()).strip()


def split_sentences(text: str) -> list[str]:
    text = clean_text(text)
    parts = re.split(r"[。；;！？!?]\s*|\n+", text)
    return [part.strip(" ，,") for part in parts if part.strip(" ，,")]


def normalize_name(value: str) -> tuple[str, int, str]:
    text = clean_text(value).strip("：:，,。；; ")
    text = re.sub(r"^(本人是?|我是|我叫|申请人|联系人|会员姓名|姓名)\s*[:：]?\s*", "", text)
    text = re.sub(r"(先生|女士|博士|老师|教授)$", "", text)
    text = text.strip("：:，,。；; ")
    if is_valid_person_name(text):
        return text, 95, "name_normalize"
    return "", 0, "invalid_name"


def is_valid_person_name(value: str) -> bool:
    text = clean_text(value)
    if not text or text in INVALID_HEADINGS:
        return False
    if "本人" in text:
        return False
    if any(term in text for term in TITLE_TERMS):
        return False
    if any(suffix in text for suffix in ORG_SUFFIXES):
        return False
    if re.search(r"[，,。；;:：/\\（）()]", text):
        return False
    if len(text) > 80:
        return False
    return bool(HAN_NAME_RE.fullmatch(text) or EN_NAME_RE.fullmatch(text))


def extract_name(text: str) -> tuple[str, int, str, str]:
    source = clean_text(text)
    for pattern, rule in [
        (r"(?:姓名|会员姓名|联系人|申请人)\s*[:：]\s*([\u4e00-\u9fff·]{2,5}|[A-Za-z][A-Za-z .'-]{1,80})", "explicit_name_label"),
        (r"(?:本人是?|我是|我叫)\s*([\u4e00-\u9fff·]{2,5}|[A-Za-z][A-Za-z .'-]{1,80})", "self_statement"),
        (r"^([\u4e00-\u9fff·]{2,5}|[A-Za-z][A-Za-z .'-]{1,80})[，,：:]\s*", "leading_name_phrase"),
    ]:
        match = re.search(pattern, source, re.I)
        if match:
            name, confidence, _ = normalize_name(match.group(1))
            if name:
                return name, confidence, rule, match.group(0)
    first = source.splitlines()[0].strip() if source.splitlines() else source
    name, confidence, _ = normalize_name(first)
    if name and (first.startswith(("本人", "我是", "我叫")) or re.fullmatch(r"[\u4e00-\u9fff·]{2,5}", first)):
        return name, 85 if first.startswith(("本人", "我是", "我叫")) else 70, "first_line_name_candidate", first
    return "", 0, "no_explicit_name", ""


def extract_contacts(text: str) -> dict[str, str]:
    mobile = MOBILE_RE.search(text)
    email = EMAIL_RE.search(text)
    return {
        "mobile": re.sub(r"\D", "", mobile.group())[-11:] if mobile else "",
        "email": email.group() if email else "",
    }


def extract_org_and_title(text: str) -> tuple[str, int, str, str, int, str, str]:
    source = clean_text(text)
    org = ""
    org_conf = 0
    org_rule = ""
    org_evidence = ""
    title = ""
    title_conf = 0
    title_rule = ""

    suffix_pattern = "|".join(re.escape(s) for s in sorted(ORG_SUFFIXES, key=len, reverse=True))
    title_pattern = "|".join(re.escape(t) for t in sorted(TITLE_TERMS, key=len, reverse=True))

    labeled_org = re.search(r"(?:所在单位|所在机构|公司|单位|机构)\s*[:：]\s*([^，,。；;\n]{2,80})", source)
    if labeled_org:
        candidate = labeled_org.group(1).strip()
        org = _trim_org(candidate, suffix_pattern)
        org_conf, org_rule, org_evidence = 95, "explicit_org_label", labeled_org.group(0)

    if not org:
        semantic = re.search(
            rf"(?:现任|就职于|任职于|来自|供职于|服务于)\s*([^，,。；;\n]{{2,80}}(?:{suffix_pattern}))",
            source,
        )
        if semantic:
            org = semantic.group(1).strip()
            org_conf, org_rule, org_evidence = 92, "org_semantic_sentence", semantic.group(0)

    if not org:
        exact = re.search(rf"([^，,。；;\n]{{2,80}}(?:{suffix_pattern}))", source)
        if exact and any(word in source for word in ORG_SEMANTIC_WORDS):
            org = exact.group(1).strip()
            org_conf, org_rule, org_evidence = 78, "org_suffix_with_semantic_word", exact.group(0)

    labeled_title = re.search(r"(?:职位|职务|岗位|角色|头衔)\s*[:：]\s*([^，,。；;\n]{2,40})", source)
    if labeled_title:
        candidate = labeled_title.group(1).strip()
        if _looks_like_title(candidate, title_pattern):
            title = candidate
            title_conf, title_rule = 94, "explicit_title_label"

    if not title:
        role = re.search(rf"({title_pattern})", source, re.I)
        if role:
            title = role.group(1)
            title_conf, title_rule = 84, "title_dictionary"

    if len(title) > 40 or re.search(r"(聚焦|负责|从事|深耕|拥有|希望|提供).{8,}", title):
        title = ""
        title_conf = 0
        title_rule = "rejected_work_sentence"

    return org, org_conf, org_rule, org_evidence, title, title_conf, title_rule


def _trim_org(candidate: str, suffix_pattern: str) -> str:
    matches = list(re.finditer(rf"(.+(?:{suffix_pattern}))", candidate))
    if not matches:
        return candidate.strip()
    return max((match.group(1).strip() for match in matches), key=len)


def _looks_like_title(candidate: str, title_pattern: str) -> bool:
    if len(candidate) > 40:
        return False
    if re.search(r"(聚焦|深耕|希望|提供|对接|资源|项目).{4,}", candidate):
        return False
    return bool(re.search(title_pattern, candidate, re.I))
