from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Iterable


EVENT_RULES = [
    ("融资与资本", ["融资", "投资", "领投", "跟投", "募资", "A轮", "B轮", "天使轮", "Pre-A", "定增"]),
    ("研发与临床", ["临床", "IND", "入组", "首例", "试验", "研发进展", "临床前"]),
    ("注册与监管", ["获批", "批准", "注册证", "受理", "NMPA", "FDA", "备案"]),
    ("BD与许可交易", ["License", "授权", "许可", "联合开发", "合作开发", "权益"]),
    ("并购与股权变动", ["并购", "收购", "控股", "股权转让", "合并"]),
    ("产能与空间", ["研发中心", "生产基地", "扩产", "搬迁", "实验室", "中试基地", "厂房"]),
    ("组织与人才", ["任命", "加盟", "加入", "离任", "招聘", "扩招", "裁员"]),
    ("科研与知识产权", ["论文", "专利", "成果转化", "技术转让", "获奖"]),
    ("市场与商业合作", ["订单", "采购", "入院", "渠道合作", "商业化合作"]),
    ("政策与园区", ["政策", "申报", "公示", "园区", "招商", "落地", "签约"]),
    ("会议与品牌", ["论坛", "峰会", "路演", "访谈", "会议", "活动"]),
    ("风险与异常", ["诉讼", "暂停", "失败", "终止", "召回", "处罚", "经营异常"]),
]

TAG_RULES = [
    ("创新药", ["创新药", "新药", "候选药物", "药物研发"]),
    ("小分子药物", ["小分子"]),
    ("抗体药物", ["抗体", "单抗", "双抗"]),
    ("ADC", ["ADC", "抗体偶联"]),
    ("细胞治疗", ["CAR-T", "TCR-T", "细胞治疗", "NK细胞", "干细胞"]),
    ("基因治疗", ["基因治疗", "基因编辑", "AAV"]),
    ("核酸药物", ["siRNA", "ASO", "mRNA", "核酸药物"]),
    ("AI制药", ["AI制药", "人工智能药物", "计算药物", "药物发现AI"]),
    ("合成生物学", ["合成生物", "细胞工厂", "生物制造"]),
    ("医疗器械", ["医疗器械", "器械", "手术机器人", "植入", "介入"]),
    ("IVD", ["IVD", "体外诊断", "诊断试剂", "POCT"]),
    ("生命科学工具", ["生命科学工具", "科研仪器", "试剂耗材"]),
    ("质谱", ["质谱", "LC-MS", "MS/MS"]),
    ("蛋白组学", ["蛋白组", "蛋白质组"]),
    ("基因组学", ["基因组", "测序"]),
    ("CRO", ["CRO", "临床研究组织", "研发外包"]),
    ("CDMO", ["CDMO", "委托生产", "工艺开发"]),
]

NEED_RULES = [
    ("资金", ["融资", "资金", "投资", "募资"]),
    ("空间", ["扩招", "研发中心", "实验室", "搬迁", "扩产", "生产基地"]),
    ("研发服务", ["临床前", "药效", "药代", "毒理", "CMC", "注册申报"]),
    ("临床资源", ["临床试验", "入组", "医院", "PI", "受试者"]),
    ("产业化", ["中试", "扩产", "生产基地", "工艺放大", "GMP"]),
    ("市场渠道", ["商业化", "渠道", "入院", "经销", "市场推广"]),
    ("技术合作", ["授权", "联合开发", "技术转让", "成果转化"]),
    ("人才", ["招聘", "扩招", "人才", "首席科学家"]),
    ("政策与落地", ["园区", "落地", "政策", "申报", "招商"]),
    ("品牌与活动", ["论坛", "路演", "访谈", "活动"]),
]

ACTION_MAP = {
    "资金": "核实融资阶段、计划金额和材料授权，匹配投资机构或产业方。",
    "空间": "联系项目方确认团队人数、实验类型、面积、时间和预算。",
    "研发服务": "确认具体研发里程碑，匹配CRO、检测或注册服务资源。",
    "临床资源": "确认适应症、临床阶段和目标医院，准备临床资源对接。",
    "产业化": "评估中试、生产、质量体系和区域政策需求，安排园区诊断。",
    "市场渠道": "确认产品准入和渠道目标，匹配医院、药企或经销资源。",
    "技术合作": "确认知识产权、合作方式和授权区域，匹配产业合作方。",
    "人才": "确认岗位、时间和团队缺口，匹配人才及招聘资源。",
    "政策与落地": "核实注册、研发和生产安排，形成上海—钱塘落地路径。",
    "品牌与活动": "评估访谈、路演或闭门会价值，准备邀请提纲。",
}

FACT_KEYWORDS = [
    "宣布", "完成", "获得", "获批", "签署", "启动", "进入", "计划",
    "融资", "投资", "临床", "注册", "合作", "建设", "成立", "发布",
]


@dataclass
class AnalysisResult:
    title: str
    event_date: str
    published_at: str
    organizations: list[str]
    event_type: str
    industry_tags: list[str]
    amount: str
    facts: list[str]
    potential_needs: list[str]
    recommended_actions: list[str]
    source_grade: str
    confidence: float
    manual_review_reasons: list[str]

    def to_dict(self):
        return asdict(self)


def _unique(items: Iterable[str]) -> list[str]:
    seen = set()
    output = []
    for item in items:
        item = item.strip()
        if item and item not in seen:
            seen.add(item)
            output.append(item)
    return output


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[。！？!?；;])|\n+", text)
    return [p.strip(" \t\r\n。；") for p in parts if len(p.strip()) >= 6]


def extract_date(text: str) -> str:
    patterns = [
        r"(20\d{2})年([01]?\d)月([0-3]?\d)日",
        r"(20\d{2})[-/.]([01]?\d)[-/.]([0-3]?\d)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            y, m, d = map(int, match.groups())
            try:
                return datetime(y, m, d).strftime("%Y-%m-%d")
            except ValueError:
                continue
    year_month = re.search(r"(20\d{2})年([01]?\d)月", text)
    if year_month:
        return f"{int(year_month.group(1)):04d}-{int(year_month.group(2)):02d}"
    return ""


def extract_organizations(text: str) -> list[str]:
    suffixes = (
        "有限责任公司|股份有限公司|有限公司|集团有限公司|集团|"
        "研究院|研究所|大学|学院|医院|基金|资本|创投|产业园|孵化器|实验室"
    )
    pattern = rf"(?<![\u4e00-\u9fa5A-Za-z0-9])([\u4e00-\u9fa5A-Za-z0-9·（）()\-]{{2,40}}?(?:{suffixes}))"
    matches = re.findall(pattern, text)
    cleaned = []
    for name in matches:
        name = re.sub(r"^(近日|日前|据悉|其中|同时|此外|本次|该|由)", "", name).strip()
        if 3 <= len(name) <= 50:
            cleaned.append(name)
    return _unique(cleaned)[:10]


def extract_amount(text: str) -> str:
    patterns = [
        r"(?:融资|投资|交易金额|金额)[^\d]{0,12}((?:人民币|美元|港元)?\s*\d+(?:\.\d+)?\s*(?:亿元|万元|亿美元|万美元|亿|万))",
        r"(\d+(?:\.\d+)?\s*(?:亿元|万元|亿美元|万美元))",
        r"(数千万(?:元|美元)?|数亿元|近亿元|超亿元)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I)
        if match:
            return re.sub(r"\s+", "", match.group(1))
    return ""


def choose_event_type(text: str) -> str:
    scores = []
    lower = text.lower()
    for name, keywords in EVENT_RULES:
        score = sum(1 for keyword in keywords if keyword.lower() in lower)
        scores.append((score, name))
    scores.sort(reverse=True)
    return scores[0][1] if scores and scores[0][0] else "其他"


def extract_tags(text: str) -> list[str]:
    lower = text.lower()
    return [
        name for name, keywords in TAG_RULES
        if any(keyword.lower() in lower for keyword in keywords)
    ]


def extract_needs(text: str) -> list[str]:
    lower = text.lower()
    return [
        name for name, keywords in NEED_RULES
        if any(keyword.lower() in lower for keyword in keywords)
    ]


def extract_facts(text: str) -> list[str]:
    sentences = _sentences(text)
    selected = [
        sentence for sentence in sentences
        if any(keyword in sentence for keyword in FACT_KEYWORDS)
    ]
    if not selected:
        selected = sentences
    return _unique(selected)[:6]


def generate_title(text: str, organizations: list[str], event_type: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and 6 <= len(lines[0]) <= 80:
        return lines[0].rstrip("。")
    first = _sentences(text)
    if first and len(first[0]) <= 80:
        return first[0]
    if organizations:
        return f"{organizations[0]}：{event_type}"
    return f"未命名情报：{event_type}"


def source_grade(source_type: str) -> str:
    mapping = {
        "监管/政府": "A",
        "企业官方": "B",
        "会议活动": "C",
        "行业媒体": "C",
        "人工录入": "D",
        "内部线索": "E",
    }
    return mapping.get(source_type, "D")


def analyze_text(text: str, source_type: str = "人工录入") -> AnalysisResult:
    clean_text = re.sub(r"\r\n?", "\n", text).strip()
    organizations = extract_organizations(clean_text)
    event_type = choose_event_type(clean_text)
    tags = extract_tags(clean_text)
    needs = extract_needs(clean_text)
    event_date = extract_date(clean_text)
    amount = extract_amount(clean_text)
    facts = extract_facts(clean_text)
    actions = [ACTION_MAP[n] for n in needs if n in ACTION_MAP]

    confidence_parts = [
        bool(organizations),
        bool(event_date),
        event_type != "其他",
        bool(tags),
        bool(facts),
    ]
    confidence = round(0.45 + sum(confidence_parts) * 0.1, 2)
    confidence = min(confidence, 0.95)

    review_reasons = []
    if not organizations:
        review_reasons.append("未识别出明确主体，请人工填写。")
    if not event_date:
        review_reasons.append("未识别出事件日期，请区分事件发生日与发布日期。")
    if event_type in {"融资与资本", "并购与股权变动", "注册与监管", "风险与异常"}:
        review_reasons.append("该事件属于必须人工复核类型。")
    if confidence < 0.75:
        review_reasons.append("结构化置信度较低，建议重点审核。")

    return AnalysisResult(
        title=generate_title(clean_text, organizations, event_type),
        event_date=event_date,
        published_at="",
        organizations=organizations,
        event_type=event_type,
        industry_tags=tags,
        amount=amount,
        facts=facts,
        potential_needs=needs,
        recommended_actions=actions[:6],
        source_grade=source_grade(source_type),
        confidence=confidence,
        manual_review_reasons=_unique(review_reasons),
    )
