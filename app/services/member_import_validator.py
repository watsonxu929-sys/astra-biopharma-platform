from __future__ import annotations

import re
from typing import Any

from app.services.member_import_normalizer import clean_text, is_valid_person_name


def validate_import_draft(draft: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    name = clean_text(draft.get("name"))
    confidence = _field_confidence(draft).get("name", 0)
    if not name:
        warnings.append("姓名不能为空；无法从原文中确认姓名时请人工补充")
    elif not is_valid_person_name(name):
        warnings.append("姓名疑似栏目标题、完整句子或包含前后缀，不能直接保存")
    if "本人" in name:
        warnings.append("姓名包含“本人”，请修正为真实姓名")
    if name and confidence and confidence < 60:
        warnings.append("姓名置信度较低，保存前需要人工确认")

    org = clean_text(draft.get("organization_name"))
    title = clean_text(draft.get("title"))
    if not org:
        warnings.append("缺少明确机构，可保留为空并标记待补资料")
    elif _looks_descriptive(org):
        warnings.append("机构字段疑似描述性句子，请清空或人工确认")
    if not title:
        warnings.append("缺少明确职位，可保留为空并标记待补资料")
    elif len(title) > 40 or _looks_descriptive(title):
        warnings.append("职位字段疑似工作内容描述，请清空或人工确认")

    mobile = re.sub(r"\D", "", clean_text(draft.get("mobile")))
    if mobile and len(mobile) not in {11, 12, 13, 14, 15}:
        warnings.append("手机号格式需要核对")
    email = clean_text(draft.get("email"))
    if email and not re.fullmatch(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", email, re.I):
        warnings.append("邮箱格式需要核对")
    return list(dict.fromkeys(warnings))


def _field_confidence(draft: dict[str, Any]) -> dict[str, int]:
    value = draft.get("field_confidence") or {}
    return value if isinstance(value, dict) else {}


def _looks_descriptive(value: str) -> bool:
    return bool(re.search(r"(长期|深耕|聚焦|负责|从事|希望|寻求|提供|拥有|工作|经验|资源|需求).{4,}", value))
