from __future__ import annotations

import re
from typing import Any

from app.services.member_field_classifier import classify_sentence
from app.services.member_import_normalizer import (
    clean_text,
    extract_contacts,
    extract_name,
    extract_org_and_title,
    is_valid_person_name,
    split_sentences,
)


CANONICAL_FIELDS = [
    "name",
    "organization_name",
    "title",
    "mobile",
    "email",
    "wechat",
    "city",
    "industry_tags",
    "expertise_tags",
    "offered_resources",
    "cooperation_needs",
    "self_introduction",
    "referral_source",
    "referrer_name",
    "preferred_contact_method",
    "member_level",
    "member_status",
    "owner",
]

HEADER_ALIASES: dict[str, set[str]] = {
    "name": {"姓名", "会员姓名", "联系人", "申请人", "名字", "name", "membername", "contact"},
    "organization_name": {"机构", "公司", "单位", "所在企业", "所在机构", "所在单位", "organization", "company", "employer"},
    "title": {"职位", "职务", "岗位", "角色", "头衔", "title", "position", "role"},
    "mobile": {"手机", "手机号", "电话", "联系电话", "联系方式", "mobile", "phone", "tel"},
    "email": {"邮箱", "电子邮箱", "email", "mail", "e-mail"},
    "wechat": {"微信", "微信号", "wechat", "weixin"},
    "city": {"城市", "地区", "所在地", "区域", "city", "region", "location"},
    "industry_tags": {"关注赛道", "行业标签", "赛道", "行业", "产业方向", "industry", "industrytags"},
    "expertise_tags": {"专业能力", "能力标签", "专长", "专业方向", "expertise", "skills", "ability"},
    "offered_resources": {"可提供资源", "资源", "供给", "优势资源", "offeredresources", "offering", "resources"},
    "cooperation_needs": {"合作需求", "当前需求", "需求", "希望对接", "cooperationneeds", "needs", "demand"},
    "self_introduction": {"个人简介", "简介", "自我介绍", "背景", "bio", "introduction", "profile"},
    "referral_source": {"来源", "加入来源", "渠道", "referralsource", "source"},
    "referrer_name": {"推荐人", "引荐人", "referrer", "introducedby"},
    "preferred_contact_method": {"联系偏好", "希望联系方式", "preferredcontactmethod", "contactpreference"},
    "member_level": {"会员等级", "等级", "memberlevel", "level"},
    "member_status": {"会员状态", "状态", "memberstatus", "status"},
    "owner": {"负责人", "运营负责人", "owner", "manager"},
}


def canonical_field(header: Any) -> str | None:
    normalized = _normalize_header(header)
    if not normalized:
        return None
    for field, aliases in HEADER_ALIASES.items():
        if normalized in {_normalize_header(item) for item in aliases}:
            return field
    return None


def default_draft() -> dict[str, Any]:
    draft = {field: "" for field in CANONICAL_FIELDS}
    draft.update(
        {
            "member_level": "standard",
            "member_status": "active",
            "source_locator": "",
            "source_text": "",
            "warnings": [],
            "image_bytes": None,
            "image_name": "",
            "source_structure": "unrecognized",
            "detected_headers": [],
            "person_block_count": 0,
            "parser_confidence": 0,
            "field_confidence": {},
            "field_evidence": {},
            "quality_flags": [],
        }
    )
    return draft


def parse_text_to_drafts(text: str, *, locator_prefix: str = "粘贴文本") -> list[dict[str, Any]]:
    text = "" if text is None else str(text).replace("\u3000", " ").replace("\r\n", "\n").replace("\r", "\n").strip()
    if "\\t" in text:
        text = text.replace("\\t", "\t")
    if not text:
        return []

    lines = [line for line in text.splitlines() if line.strip()]
    if len(lines) >= 2 and any("\t" in line for line in lines[:3]):
        parsed = table_rows_to_drafts([line.split("\t") for line in lines], locator_prefix=locator_prefix)
        if parsed:
            return parsed

    blocks = split_person_blocks(text)
    drafts = [_parse_person_block(block, f"{locator_prefix}第{idx}段", len(blocks)) for idx, block in enumerate(blocks, start=1)]
    return drafts or [_unrecognized_draft(text, locator_prefix)]


def table_rows_to_drafts(rows: list[list[Any]], *, locator_prefix: str = "表格") -> list[dict[str, Any]]:
    clean_rows = [[clean_text(cell) for cell in row] for row in rows]
    clean_rows = [row for row in clean_rows if any(row)]
    if not clean_rows:
        return []
    header_index = 0
    best_mapping: dict[int, str] = {}
    for idx, row in enumerate(clean_rows[:10]):
        mapping = {col: field for col, value in enumerate(row) if (field := canonical_field(value))}
        if len(mapping) > len(best_mapping):
            header_index, best_mapping = idx, mapping
    if len(best_mapping) >= 2:
        return _parse_mapped_rows(clean_rows, best_mapping, header_index, locator_prefix)

    drafts: list[dict[str, Any]] = []
    for row_no, row in enumerate(clean_rows, start=1):
        source = "\n".join(cell for cell in row if cell)
        if not source:
            continue
        draft = _parse_person_block(source, f"{locator_prefix}第{row_no}行", 1)
        draft["source_structure"] = "非标准表格"
        draft["warnings"].append("未识别到可靠表头，未按列顺序猜测机构或职位；请在映射工作台人工确认字段")
        drafts.append(draft)
    return drafts


def split_person_blocks(text: str) -> list[str]:
    text = clean_text(text)
    blocks = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
    if len(blocks) > 1:
        return blocks
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    explicit_starts = [idx for idx, line in enumerate(lines) if re.search(r"^(姓名|会员姓名|联系人|申请人|本人|我是|我叫)\s*[:：]?", line)]
    if len(explicit_starts) > 1:
        result = []
        for pos, start in enumerate(explicit_starts):
            end = explicit_starts[pos + 1] if pos + 1 < len(explicit_starts) else len(lines)
            result.append("\n".join(lines[start:end]))
        return result
    numbered = [idx for idx, line in enumerate(lines) if re.match(r"^\s*\d+[.、]\s*(姓名[:：]|[\u4e00-\u9fff·]{2,5}\b)", line)]
    if len(numbered) > 1:
        result = []
        for pos, start in enumerate(numbered):
            end = numbered[pos + 1] if pos + 1 < len(numbered) else len(lines)
            result.append("\n".join(re.sub(r"^\s*\d+[.、]\s*", "", item) for item in lines[start:end]))
        return result
    return [text]


def _parse_mapped_rows(rows: list[list[str]], mapping: dict[int, str], header_index: int, locator_prefix: str) -> list[dict[str, Any]]:
    drafts: list[dict[str, Any]] = []
    headers = [rows[header_index][idx] for idx in sorted(mapping)]
    for row_no, row in enumerate(rows[header_index + 1 :], start=header_index + 2):
        draft = default_draft()
        for col, field in mapping.items():
            if col < len(row):
                draft[field] = row[col]
                if row[col]:
                    draft["field_confidence"][field] = 95
                    draft["field_evidence"][field] = [{"locator": f"{locator_prefix}第{row_no}行", "rule": "explicit_header", "text": row[col]}]
        if not any(draft.get(field) for field in ("name", "organization_name", "mobile", "email", "self_introduction")):
            continue
        draft["source_structure"] = "标准表格"
        draft["detected_headers"] = headers
        draft["person_block_count"] = 1
        draft["parser_confidence"] = 92
        draft["source_locator"] = f"{locator_prefix}第{row_no}行"
        draft["source_text"] = " | ".join(cell for cell in row if cell)
        contacts = extract_contacts(draft["source_text"])
        for field in ("mobile", "email"):
            if not draft.get(field) and contacts.get(field):
                draft[field] = contacts[field]
                draft["field_confidence"][field] = 88
        drafts.append(draft)
    return drafts


def _parse_person_block(block: str, locator: str, block_count: int) -> dict[str, Any]:
    draft = default_draft()
    draft["source_locator"] = locator
    draft["source_text"] = block
    draft["source_structure"] = "多人简介" if block_count > 1 else "单人简介"
    draft["person_block_count"] = block_count
    draft["parser_confidence"] = 75

    for line in block.splitlines():
        pair = re.match(r"^\s*([^:：]{1,24})\s*[:：]\s*(.*?)\s*$", line)
        if not pair:
            continue
        field = canonical_field(pair.group(1))
        if field:
            draft[field] = pair.group(2).strip()
            draft["field_confidence"][field] = 95
            draft["field_evidence"].setdefault(field, []).append({"locator": locator, "rule": "explicit_label", "text": line})

    name, score, rule, evidence = extract_name(block)
    if name and not draft.get("name"):
        draft["name"] = name
        draft["field_confidence"]["name"] = score
        draft["field_evidence"].setdefault("name", []).append({"locator": locator, "rule": rule, "text": evidence})

    contacts = extract_contacts(block)
    for field in ("mobile", "email"):
        if contacts.get(field) and not draft.get(field):
            draft[field] = contacts[field]
            draft["field_confidence"][field] = 88
            draft["field_evidence"].setdefault(field, []).append({"locator": locator, "rule": "contact_regex", "text": contacts[field]})

    org, org_conf, org_rule, org_evidence, title, title_conf, title_rule = extract_org_and_title(block)
    if org and not draft.get("organization_name"):
        draft["organization_name"] = org
        draft["field_confidence"]["organization_name"] = org_conf
        draft["field_evidence"].setdefault("organization_name", []).append({"locator": locator, "rule": org_rule, "text": org_evidence})
    if title and not draft.get("title"):
        draft["title"] = title
        draft["field_confidence"]["title"] = title_conf
        draft["field_evidence"].setdefault("title", []).append({"locator": locator, "rule": title_rule, "text": title})

    for sentence in split_sentences(block):
        for item in classify_sentence(sentence):
            if item.field in {"self_introduction", "expertise_tags"} and draft.get(item.field):
                draft[item.field] = _join_unique(draft[item.field], item.value)
            elif not draft.get(item.field):
                draft[item.field] = item.value
            draft["field_confidence"][item.field] = max(int(draft["field_confidence"].get(item.field, 0)), item.confidence)
            draft["field_evidence"].setdefault(item.field, []).append({"locator": locator, "rule": item.rule, "text": item.evidence})

    if block and not draft.get("self_introduction"):
        draft["self_introduction"] = block
        draft["field_confidence"]["self_introduction"] = 55
        draft["field_evidence"].setdefault("self_introduction", []).append({"locator": locator, "rule": "raw_retained", "text": block})

    if not is_valid_person_name(draft.get("name", "")):
        draft["quality_flags"].append("name_needs_manual_confirmation")
        if not draft.get("name"):
            draft["warnings"].append("未识别到明确姓名，未编造姓名；请人工补充")
        else:
            draft["warnings"].append("姓名置信度不足或格式异常，请人工确认")
    if not draft.get("organization_name"):
        draft["warnings"].append("缺少明确机构，未自动填充")
    if not draft.get("title"):
        draft["warnings"].append("缺少明确职位，未自动填充")
    return draft


def _unrecognized_draft(text: str, locator: str) -> dict[str, Any]:
    draft = default_draft()
    draft["source_locator"] = locator
    draft["source_text"] = text
    draft["self_introduction"] = text
    draft["source_structure"] = "无法识别"
    draft["warnings"].append("文本结构无法识别，已保留原文等待人工选择解析模式")
    return draft


def _join_unique(current: str, value: str) -> str:
    items = [item.strip() for part in (current, value) for item in re.split(r"[、;,，；]\s*", part or "") if item.strip()]
    return "、".join(dict.fromkeys(items))


def _normalize_header(value: Any) -> str:
    return re.sub(r"[\s_\-—:：/\\（）()\[\]【】]+", "", clean_text(value).lower())
