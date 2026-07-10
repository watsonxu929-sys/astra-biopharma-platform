from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

GENERIC_PAGE_TITLES = {
    "管理团队", "核心团队", "团队介绍", "董事会", "高管团队", "专家团队",
    "关于我们", "公司简介", "集团简介", "联系我们", "新闻中心", "新闻资讯",
    "项目列表", "项目介绍", "产品中心", "产品列表", "资源中心", "服务中心",
    "企业名录", "机构名录", "首页", "人才招聘", "加入我们",
}

ROLE_KEYWORDS = (
    "创始人", "联合创始人", "董事长", "董事", "总经理", "首席执行官", "联席首席执行官",
    "CEO", "COO", "CTO", "CSO", "CFO", "总裁", "副总裁", "总监", "负责人",
    "合伙人", "研究员", "教授", "院长", "主任", "科学家", "顾问", "经理",
)

NAVIGATION_NOISE = {
    "联系我们", "关于我们", "服务", "新闻", "加入我们", "投资者关系", "使用条款",
    "隐私声明", "媒体中心", "企业文化", "公司历史", "公司荣誉", "可持续发展",
    "商业道德准则", "查看更多", "官方微信", "全球主要分公司",
}

IDENTITY_FIELDS = {
    "people": ["name"],
    "organizations": ["standard_name"],
    "projects": ["name"],
    "events": ["name"],
    "resources": ["owner_external_id", "category"],
    "relations": ["source_external_id", "target_external_id", "relation_type"],
    "actions": ["task", "target_external_id"],
}


@dataclass
class CandidateBlock:
    label: str
    subtitle: str
    text: str

    def to_dict(self) -> dict[str, str]:
        return {"label": self.label, "subtitle": self.subtitle, "text": self.text}


def _lines(text: str) -> list[str]:
    output: list[str] = []
    for raw in text.replace("\r", "\n").splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" \t　")
        if line and (not output or output[-1] != line):
            output.append(line)
    return output


def _strip_title_prefix(value: str) -> str:
    return re.sub(r"^(?:标题|姓名|名称|项目名称|公司名称)[:：]\s*", "", value).strip()


def _person_name_value(line: str) -> str:
    value = _strip_title_prefix(line)
    value = re.sub(r"\s+(?:博士|先生|女士)$", "", value)
    value = re.sub(r"(?:博士|先生|女士)$", "", value)
    return value.strip()


def _looks_like_person_name(line: str) -> bool:
    value = _person_name_value(line)
    if not value or value in GENERIC_PAGE_TITLES or value in NAVIGATION_NOISE:
        return False
    if any(keyword in value for keyword in ROLE_KEYWORDS):
        return False
    if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", value):
        return True
    if re.fullmatch(r"[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,3}", value):
        return True
    return False


def _looks_like_role(line: str) -> bool:
    value = line.strip()
    return 2 <= len(value) <= 120 and any(keyword.lower() in value.lower() for keyword in ROLE_KEYWORDS)


def _is_section_boundary(line: str) -> bool:
    value = _strip_title_prefix(line)
    return value in GENERIC_PAGE_TITLES or value in NAVIGATION_NOISE


def extract_person_candidates(text: str, limit: int = 30) -> list[CandidateBlock]:
    lines = _lines(text)
    source_title = next((line for line in lines[:6] if line.startswith(("标题：", "标题:"))), "")
    starts: list[tuple[int, str, str]] = []
    for index, line in enumerate(lines):
        if not _looks_like_person_name(line):
            continue
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if not _looks_like_role(next_line):
            continue
        starts.append((index, _person_name_value(line), next_line))

    candidates: list[CandidateBlock] = []
    seen: set[str] = set()
    for position, (start, name, role) in enumerate(starts[:limit]):
        if name in seen:
            continue
        end = starts[position + 1][0] if position + 1 < len(starts) else len(lines)
        block_lines = lines[start:end]
        while block_lines and _is_section_boundary(block_lines[-1]):
            block_lines.pop()
        block_text = "\n".join(block_lines).strip()
        if source_title and not block_text.startswith(source_title):
            block_text = f"{source_title}\n{block_text}"
        if len(block_text) < len(name) + len(role) + 5:
            continue
        if len(block_text) > 5000:
            block_text = block_text[:5000]
        candidates.append(CandidateBlock(label=name, subtitle=role, text=block_text))
        seen.add(name)
    return candidates


def _organization_names(text: str) -> list[str]:
    suffixes = (
        "有限责任公司|股份有限公司|有限公司|集团有限公司|集团|研究院|研究所|大学|学院|"
        "医院|基金|资本|创投|产业园|孵化器|实验室|中心"
    )
    pattern = rf"([\u4e00-\u9fffA-Za-z0-9·（）()\-]{{2,45}}?(?:{suffixes}))"
    names: list[str] = []
    for raw in re.findall(pattern, text):
        name = re.sub(r"^(?:加入|曾任|任职于|毕业于|来自|就职于)", "", raw).strip()
        if 3 <= len(name) <= 50 and name not in names:
            names.append(name)
    return names[:30]


def extract_organization_candidates(text: str, limit: int = 20) -> list[CandidateBlock]:
    lines = _lines(text)
    candidates: list[CandidateBlock] = []
    seen: set[str] = set()
    for index, line in enumerate(lines):
        names = _organization_names(line)
        if len(names) != 1 or len(line) > 80:
            continue
        name = names[0]
        if name in seen:
            continue
        following = lines[index + 1:index + 5]
        block = "\n".join([line, *following]).strip()
        if len(block) < 30:
            continue
        candidates.append(CandidateBlock(name, "疑似机构条目", block[:4000]))
        seen.add(name)
        if len(candidates) >= limit:
            break
    return candidates


def extract_candidates(entity_key: str, text: str) -> list[CandidateBlock]:
    if entity_key == "people":
        return extract_person_candidates(text)
    if entity_key == "organizations":
        return extract_organization_candidates(text)
    return []


def inspect_entity_text(entity_key: str, text: str) -> dict[str, Any]:
    value = text.strip()
    lines = _lines(value)
    candidates = extract_candidates(entity_key, value)
    warnings: list[str] = []
    risk_level = "low"
    page_mode = "single_subject"

    title_line = ""
    for line in lines[:5]:
        if line.startswith("标题：") or line.startswith("标题:"):
            title_line = _strip_title_prefix(line).split("|")[0].strip()
            break

    noise_count = sum(1 for line in lines if _strip_title_prefix(line) in NAVIGATION_NOISE)
    date_count = len(re.findall(r"20\d{2}[-/.年]\d{1,2}(?:[-/.月]\d{1,2}日?)?", value))

    if entity_key == "people":
        if len(candidates) >= 2:
            risk_level = "high"
            page_mode = "multiple_subjects"
            warnings.append(f"检测到至少 {len(candidates)} 个人物条目，不能把整页保存成一个人物。")
        elif len(candidates) == 1:
            page_mode = "single_subject"
        elif title_line in GENERIC_PAGE_TITLES or sum(value.lower().count(k.lower()) for k in ROLE_KEYWORDS) >= 4:
            risk_level = "high"
            page_mode = "multiple_subjects"
            warnings.append("页面标题或职位分布显示这可能是团队/名单页，请先截取单个人物内容。")
        else:
            risk_level = "medium"
            page_mode = "uncertain"
            warnings.append("未能稳定识别唯一人物，请重点核对姓名、现任机构和职位。")
    elif entity_key == "organizations":
        org_names = _organization_names(value)
        if len(candidates) >= 2 and len(org_names) >= 3:
            risk_level = "high"
            page_mode = "multiple_subjects"
            warnings.append("检测到多个机构条目，不能把整个名录保存成一家机构。")
        elif len(org_names) >= 6 and len(value) > 1500:
            risk_level = "medium"
            page_mode = "uncertain"
            warnings.append("正文包含较多机构名称，请确认当前页面是否只介绍一家主体。")
    elif entity_key == "events":
        if date_count >= 3 and (len(lines) >= 8 or len(value) >= 300):
            risk_level = "high"
            page_mode = "multiple_subjects"
            warnings.append("页面包含多组日期，疑似新闻/事件列表，请只保留一条事件正文。")
    elif entity_key in {"projects", "resources"}:
        list_markers = sum(value.count(marker) for marker in ("项目一", "项目二", "产品一", "产品二", "01", "02"))
        if list_markers >= 3 and len(value) > 1200:
            risk_level = "medium"
            page_mode = "uncertain"
            warnings.append("内容可能包含多个项目或资源条目，请确认只创建一条记录。")

    if noise_count >= 4:
        warnings.append("正文仍含较多导航文字，建议使用候选条目或手动选中文字分析。")
        if risk_level == "low":
            risk_level = "medium"
            page_mode = "uncertain"

    return {
        "risk_level": risk_level,
        "page_mode": page_mode,
        "fill_allowed": risk_level != "high",
        "warnings": warnings,
        "blocked_fields": IDENTITY_FIELDS.get(entity_key, []) if risk_level == "high" else [],
        "candidates": [candidate.to_dict() for candidate in candidates],
        "line_count": len(lines),
        "character_count": len(value),
        "recommended_action": (
            "请选择下方单条候选，或在原始文字中选中一个主体后点击“分析选中文字”。"
            if risk_level == "high"
            else "可分析并填入，但保存前仍需人工核对。"
        ),
    }


def _generic_identity_error(value: str) -> str | None:
    normalized = _strip_title_prefix(value).split("|")[0].strip()
    if normalized in GENERIC_PAGE_TITLES or normalized in NAVIGATION_NOISE:
        return f"“{normalized}”是栏目名称，不是可保存的主体名称。"
    return None


def validate_entity_submission(entity_key: str, values: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []

    identity_key = {
        "people": "name",
        "organizations": "standard_name",
        "projects": "name",
        "events": "name",
    }.get(entity_key)
    identity_value = str(values.get(identity_key) or "").strip() if identity_key else ""

    if identity_value:
        generic_error = _generic_identity_error(identity_value)
        if generic_error:
            errors.append(generic_error)

    if entity_key == "people" and identity_value:
        if len(identity_value) > 40:
            errors.append("人物姓名过长，疑似把标题或多人名单填入姓名字段。")
        if re.search(r"[；;、,/]|\s{2,}", identity_value):
            errors.append("人物姓名中包含多人分隔符，请每次只保存一个人物。")
        if any(keyword.lower() in identity_value.lower() for keyword in ROLE_KEYWORDS):
            errors.append("人物姓名中包含职位名称，请将姓名与职位分开填写。")

        role = str(values.get("public_role") or "")
        network = str(values.get("organization_network") or "")
        if len(role) > 220 or role.count("；") + role.count(";") >= 5:
            warnings.append("公开角色字段过长，可能混入了多个人物职位。")
        if len(network) > 500 or network.count("；") + network.count(";") >= 8:
            warnings.append("当前机构/网络字段包含大量机构，可能混入教育或历史任职经历。")

    if entity_key == "organizations" and len(identity_value) > 100:
        errors.append("机构标准名称过长，疑似把简介填入名称字段。")
    if entity_key in {"projects", "events"} and len(identity_value) > 200:
        warnings.append("名称较长，请确认没有把整段摘要填入名称字段。")

    source_text = str(values.get("source_text") or "").strip()
    diagnostics = inspect_entity_text(entity_key, source_text) if len(source_text) >= 10 else None
    if diagnostics and diagnostics["risk_level"] == "high":
        warnings.extend(diagnostics["warnings"])

    unique_errors = list(dict.fromkeys(errors))
    unique_warnings = list(dict.fromkeys(warnings))
    return {
        "errors": unique_errors,
        "warnings": unique_warnings,
        "requires_confirmation": bool(unique_warnings),
        "diagnostics": diagnostics,
    }
