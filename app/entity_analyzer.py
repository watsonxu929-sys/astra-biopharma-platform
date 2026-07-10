from __future__ import annotations

import re
from typing import Any

from .analyzer import analyze_text
from .services.manual_ingestion import extract_person_candidates, inspect_entity_text

REGIONS = ["上海", "北京", "杭州", "苏州", "南京", "无锡", "宁波", "深圳", "广州", "成都", "武汉", "天津", "重庆"]
ROLES = ["创始人", "联合创始人", "董事长", "总经理", "CEO", "COO", "CTO", "CSO", "CFO", "首席科学家", "教授", "研究员", "主任", "投资人", "合伙人", "项目负责人", "招商代表", "BD", "副总裁", "总裁", "总监", "院长"]
ABILITIES = ["投融资", "园区招商", "项目孵化", "实验室运营", "质谱", "蛋白组学", "代谢组学", "基因组学", "生物信息学", "临床开发", "注册申报", "药物研发", "医疗器械", "成果转化", "并购", "BD", "市场渠道", "CRO", "CDMO", "政策申报", "活动组织", "产业资源"]


def sents(text: str) -> list[str]:
    return [x.strip(" 。；\n\t") for x in re.split(r"[。！？!?；;\n]+", text) if len(x.strip()) >= 3]


def uniq(items: list[str]) -> list[str]:
    output: list[str] = []
    for item in items:
        if item and item not in output:
            output.append(item)
    return output


def region(text: str) -> str:
    return "；".join([item for item in REGIONS if item in text][:3])


def firstline(text: str) -> str:
    lines = [x.strip() for x in text.splitlines() if x.strip()]
    if not lines:
        return ""
    value = re.sub(r"^(姓名|名称|项目名称|公司名称|标题)[:：]\s*", "", lines[0]).rstrip("。")
    if "|" in value:
        value = value.split("|", 1)[0].strip()
    return value if len(value) <= 80 else ""


def orgtype(text: str) -> str:
    rules = [
        ("生物医药企业", ["生物科技", "生物医药", "制药", "药业", "医药"]),
        ("医疗器械企业", ["医疗器械", "器械", "IVD"]),
        ("投资机构", ["资本", "基金", "创投", "投资"]),
        ("园区/孵化器", ["园区", "孵化器", "产业园", "医药港"]),
        ("高校/科研院所", ["大学", "学院", "研究院", "研究所"]),
        ("医院/临床机构", ["医院"]),
        ("CRO/CDMO", ["CRO", "CDMO"]),
    ]
    for key, words in rules:
        if any(word.lower() in text.lower() for word in words):
            return key
    return "待分类"


def _current_organization(text: str, organizations: list[str]) -> str:
    for line in text.splitlines()[:5]:
        if line.startswith(("标题：", "标题:")) and "|" in line:
            tail = line.split("|", 1)[1].strip()
            if 2 <= len(tail) <= 35:
                return tail

    patterns = [
        r"(?:加入|加盟)([\u4e00-\u9fa5A-Za-z0-9·（）()\-]{2,35}?)(?:前|之前|以来|后)",
        r"现任([\u4e00-\u9fa5A-Za-z0-9·（）()\-]{2,35}?)(?:董事长|总裁|总经理|首席|副总裁|总监|负责人)",
        r"任职于([\u4e00-\u9fa5A-Za-z0-9·（）()\-]{2,35})(?:[，,。；;]|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            value = match.group(1).strip(" ，,。；;")
            if 2 <= len(value) <= 35:
                return value

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 2 and "，" in lines[1]:
        suffix = lines[1].split("，", 1)[1].strip()
        if 2 <= len(suffix) <= 30 and any(x in suffix for x in ["药业", "制药", "医药", "集团", "公司", "研究院", "大学", "医院"]):
            return suffix

    return organizations[0] if organizations else ""


def _person_value_summary(text: str) -> str:
    selected: list[str] = []
    for sentence in sents(text):
        if sentence.startswith(("标题：", "标题:")):
            continue
        if any(word in sentence for word in ["拥有", "负责", "擅长", "经验", "领域", "领导", "创建", "建立", "开发", "管理", "推动", "赋能"]):
            if not any(word in sentence for word in ["毕业于", "获得学士", "获得硕士", "获得博士", "获学位"]):
                selected.append(sentence)
        if len(selected) >= 5:
            break
    return "\n".join(uniq(selected))


def analyze_organization(text: str) -> dict[str, Any]:
    generic = analyze_text(text)
    sentences = sents(text)
    return {
        "external_id": "",
        "standard_name": generic.organizations[0] if generic.organizations else firstline(text),
        "org_type": orgtype(text),
        "region": region(text),
        "industry_tags": "；".join(generic.industry_tags),
        "resources": "\n".join([x for x in sentences if any(w in x for w in ["拥有", "提供", "具备", "建有", "设有", "可提供"])][:5]),
        "needs": "\n".join([x for x in sentences if any(w in x for w in ["需要", "寻求", "计划", "拟", "希望", "需求"])][:5] or generic.potential_needs),
        "relationship_source": "链接/文字辅助拆分",
        "visibility": "内部",
        "verification_status": "待核验",
    }


def analyze_person(text: str) -> dict[str, Any]:
    generic = analyze_text(text)
    candidates = extract_person_candidates(text)

    name = ""
    role = ""
    working_text = text
    if len(candidates) == 1:
        candidate = candidates[0]
        name = candidate.label
        role = candidate.subtitle
        working_text = candidate.text
    else:
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        if lines:
            raw_name = re.sub(r"^(?:姓名|标题)[:：]\s*", "", lines[0]).split("|", 1)[0].strip()
            raw_name = re.sub(r"\s*(?:博士|先生|女士)$", "", raw_name)
            if re.fullmatch(r"[\u4e00-\u9fa5]{2,4}|[A-Z][A-Za-z.'-]+(?:\s+[A-Z][A-Za-z.'-]+){1,3}", raw_name):
                name = raw_name
        if len(lines) >= 2 and len(lines[1]) <= 120:
            role = lines[1]

    if not role:
        role_sentences = [sentence for sentence in sents(working_text) if any(item.lower() in sentence.lower() for item in ROLES)]
        role = role_sentences[0] if role_sentences else ""

    organization = _current_organization(working_text, generic.organizations)
    return {
        "external_id": "",
        "name": name,
        "public_role": role,
        "organization_network": organization,
        "ability_tags": "；".join(uniq([item for item in ABILITIES if item.lower() in working_text.lower()])),
        "value_provided": _person_value_summary(working_text),
        "relationship_source": "链接/文字辅助拆分",
        "visibility": "内部",
        "verification_status": "待核验",
    }


def analyze_project(text: str) -> dict[str, Any]:
    generic = analyze_text(text)
    project_type = "创新药项目" if any(x in text for x in ["创新药", "候选药物", "ADC"]) else (
        "医疗器械项目" if "医疗器械" in text else (
            "IVD项目" if "IVD" in text or "体外诊断" in text else (
                "成果转化项目" if "成果转化" in text else "待分类"
            )
        )
    )
    sentences = sents(text)
    return {
        "external_id": "",
        "name": firstline(text) or generic.title,
        "project_type": project_type,
        "owner_external_id": generic.organizations[0] if generic.organizations else "",
        "focus_tags": "；".join(generic.industry_tags),
        "typical_needs": "\n".join([x for x in sentences if any(w in x for w in ["需要", "需求", "寻求", "融资", "合作", "落地", "实验室"])][:6] or generic.potential_needs),
        "target_actions": "\n".join(generic.recommended_actions[:6]),
        "visibility": "内部",
        "status": "待整理",
    }


def analyze_resource(text: str) -> dict[str, Any]:
    generic = analyze_text(text)
    category = next((x for x in ["空间", "实验室", "共享平台", "仪器设备", "资金", "基金", "政策", "临床资源", "CRO", "CDMO", "检测", "注册", "渠道", "人才", "媒体", "活动", "路演", "园区", "生产基地"] if x in text), "待分类资源")
    return {
        "external_id": "",
        "owner_external_id": generic.organizations[0] if generic.organizations else "",
        "category": category,
        "description": text.strip(),
        "region": region(text),
        "applicable_to": "；".join(generic.industry_tags),
        "visibility": "内部",
        "verification_status": "待核验",
    }


def analyze_event(text: str) -> dict[str, Any]:
    generic = analyze_text(text)
    return {
        "external_id": "",
        "event_date": generic.event_date,
        "name": generic.title,
        "event_type": generic.event_type,
        "related_entity": generic.organizations[0] if generic.organizations else "",
        "fact_summary": "\n".join(generic.facts),
        "system_use": "潜在需求：" + "；".join(generic.potential_needs) + "\n建议动作：" + "\n".join(generic.recommended_actions),
        "visibility": "内部",
        "verification_status": "待核验",
    }


def analyze_relation(text: str) -> dict[str, Any]:
    generic = analyze_text(text)
    organizations = generic.organizations
    relation_type = next((x for x in ["投资", "合作", "授权", "任职", "创立", "联合开发", "入驻", "孵化", "顾问", "供应", "并购", "签约", "战略合作"] if x in text), "待判断关系")
    return {
        "external_id": "",
        "source_external_id": organizations[0] if len(organizations) > 0 else "",
        "relation_type": relation_type,
        "target_external_id": organizations[1] if len(organizations) > 1 else "",
        "period": generic.event_date,
        "evidence_source": text.strip(),
        "visibility": "内部",
        "verification_status": "待核验",
    }


def analyze_action(text: str) -> dict[str, Any]:
    generic = analyze_text(text)
    return {
        "external_id": "",
        "task": generic.recommended_actions[0] if generic.recommended_actions else firstline(text) or "人工核实该事项并记录结果",
        "target_external_id": generic.organizations[0] if generic.organizations else "",
        "completion_standard": "完成信息核实、资源匹配或沟通，并记录结果。",
        "owner": "项目负责人",
        "priority": "P1",
        "status": "未开始",
        "suggested_deadline": "",
    }


MAP = {
    "organizations": analyze_organization,
    "people": analyze_person,
    "projects": analyze_project,
    "resources": analyze_resource,
    "events": analyze_event,
    "relations": analyze_relation,
    "actions": analyze_action,
}


def analyze_entity(entity_key: str, text: str) -> dict[str, Any]:
    if entity_key not in MAP:
        raise ValueError(f"不支持的数据类型：{entity_key}")
    diagnostics = inspect_entity_text(entity_key, text)
    fields = MAP[entity_key](text)
    if not diagnostics["fill_allowed"]:
        for field_name in diagnostics["blocked_fields"]:
            if field_name in fields:
                fields[field_name] = ""
    return fields
