from __future__ import annotations

import re
from typing import Any

BIOPHARMA_KEYWORDS = [
    "生物医药", "生物技术",
    "药物", "药品", "疫苗", "抗体", "疫苗", "临床试验", "临床", "FDA", "EMA", "NMPA",
    "药品监督", "制药", "生物制药", "医疗器械", "诊断", "基因", "RNA", "DNA", "蛋白",
    "小分子", "大分子", "化药", "中药", "仿制药", "创新药", "上市", "批准", "注册",
    "IND", "NDA", "BLA", "CTA", "上市许可", "医保", "集采", "一致性评价",
    "biopharma", "pharmaceutical", "medicine", "drug", "clinical trial", "vaccine",
    "antibody", "protein", "gene", "therapy", "treatment", "disease", "medical",
    "healthcare", "health", "research", "biotechnology", "biotech", "pharmacy",
    "regulatory", "approval", "marketing", "authorization", "orphan", "generic",
]

LOW_QUALITY_PATTERNS = [
    (r"^登录|^请登录|^Sign In|^Login", "login_page"),
    (r"404|Not Found|页面不存在", "not_found"),
    (r"免责声明|Disclaimer|免责声明", "disclaimer_only"),
    (r"导航|导航栏|菜单|Menu|Navigation", "navigation_only"),
    (r"cookie|Cookie|隐私政策|Privacy", "cookie_banner"),
    (r"请输入验证码|captcha|验证码", "captcha_required"),
]

GENERIC_PAGE_TITLES = (
    "contact", "careers", "about", "history", "strategy", "leadership",
    "stories", "mediaroom", "media releases", "press announcements",
    "press releases", "research & innovation", "clinicaltrials.gov",
)


def check_content_quality(title: str, text: str, url: str = "") -> dict[str, Any]:
    checks = _run_all_checks(title, text, url)
    status, reason = _determine_status(checks)
    return {
        "quality_status": status,
        "quality_reason": reason,
        "checks": checks,
        "is_accepted": status == "accepted",
    }


def _run_all_checks(title: str, text: str, url: str) -> dict[str, bool]:
    return {
        "has_title": bool(title and len(title.strip()) >= 5),
        "has_content": bool(text and len(text.strip()) >= 50),
        "content_length_ok": len(text.strip()) >= 100,
        "is_not_login": not re.search(r"验证码|captcha|access denied|访问被拒绝|^\s*(?:请登录|sign in|login)", title + '\n' + text[:600], re.IGNORECASE),
        "is_not_error": "404" not in text[:200] and "Not Found" not in text[:200],
        "is_not_navigation_only": not _is_navigation_only(text),
        "is_specific_article": _is_specific_article_title(title),
        "has_biopharma_content": _has_biopharma_keywords(title, text),
        "has_published_time": bool(_find_published_time(text)),
        "is_not_duplicate": True,
    }


def _determine_status(checks: dict[str, bool]) -> tuple[str, str]:
    if not checks["has_title"]:
        return "low_quality", "缺少有效标题"
    if not checks["has_content"]:
        return "insufficient_content", "正文内容不足"
    if not checks["content_length_ok"]:
        return "low_quality", "正文过短(少于100字符)"
    if not checks["is_not_login"]:
        return "access_denied", "需要登录或验证"
    if not checks["is_not_error"]:
        return "parse_failed", "页面不存在或错误"
    if not checks["is_not_navigation_only"]:
        return "low_quality", "导航页或菜单页"
    if not checks["is_specific_article"]:
        return "low_quality", "栏目页或通用页面"
    if not checks["has_biopharma_content"]:
        return "irrelevant", "与生物医药产业无关"
    return "accepted", "通过质量检查"


def _is_specific_article_title(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", (title or "").strip().lower())
    parts = [part.strip(" -|") for part in normalized.split("|")]
    return not any(
        term == normalized
        or term in parts
        or any(part.startswith(f"{term} ") for part in parts)
        for term in GENERIC_PAGE_TITLES
    )


def _is_navigation_only(text: str) -> bool:
    cleaned = text.strip()[:500]
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) < 3:
        return len(cleaned) < 100
    if sum(len(line) for line in lines if len(line) < 20) > sum(len(line) for line in lines) * 0.7:
        return True
    return False


def _has_biopharma_keywords(title: str, text: str) -> bool:
    combined = (title + " " + text).lower()
    # Specific biomedical context, not generic "research/marketing/上市" counts.
    return bool(re.search(
        r'生物医药|生物技术|生物医学|合成生物|药物|药品|制药|创新药|疫苗|抗体|临床|医疗器械|诊断|'
        r'癌症|肿瘤|传染病|心脑血管|疾病防治|基因|细胞治疗|代谢调节|'
        r'\b(?:biopharma|pharmaceuticals?|biotechnology|biotech|drugs?|medicines?|vaccines?|antibod(?:y|ies)|'
        r'clinical|therap(?:y|ies)|diagnostic|disease|cancer|fda|ema|nmpa|rna|dna)\b', combined, re.I))


def _find_published_time(text: str) -> str | None:
    patterns = [
        r"(\d{4})[\-年](\d{1,2})[\-月](\d{1,2})[日号]",
        r"(\d{4})[\-/.](\d{1,2})[\-/.](\d{1,2})",
        r"Published:\s*(\d{4})[\-/.](\d{1,2})[\-/.](\d{1,2})",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0)
    return None


QUALITY_STATUS_LABELS = {
    "accepted": "通过",
    "pending": "待检查",
    "duplicate": "重复",
    "low_quality": "低质量",
    "insufficient_content": "内容不足",
    "access_denied": "访问受限",
    "parse_failed": "解析失败",
    "irrelevant": "无关内容",
    "needs_manual_review": "需人工判断",
}


class QualityResult:
    def __init__(self, status: str, reason: str, accepted: bool):
        self.status = status
        self.reason = reason
        self.accepted_for_analysis = accepted


def article_review_quality(title: str, text: str, url: str, published_at: str = "", metadata: dict | None = None) -> dict:
    """Independent relevance, completeness and business context; never an opportunity score."""
    metadata = metadata or {}
    combined = title + '\n' + text
    quality = check_content_quality(title, text, url)
    gaps = []
    if not url.startswith(('http://', 'https://')):
        gaps.append('来源缺失或不是公开网页')
    if not quality['is_accepted']:
        gaps.append(quality['quality_reason'])
    if len(text.strip()) < 200:
        gaps.append('正文不完整：不足200字符')
    actions = re.search(r'申报|截止|获批|批准|批件|修订|试验|入组|融资|收购|签署|协议|扩建|新建|采购|招标|启动|发布|结果|公布|完成|approved|approval|results|trial|phase|announc|launch|acquisition|agreement|funding|invest', combined, re.I)
    if not actions:
        gaps.append('事件不明确：需要补充具体发生的事项')
    attachments = metadata.get('attachments') or []
    if attachments and not metadata.get('attachments_reviewed'):
        gaps.append('附件待核查：尚未确认附件是否包含关键事实')
    warnings = [] if published_at else ['原始发布时间待核对；采集时间不是发布时间']
    from .article_facts import analyze_article
    facts = analyze_article(title, text, url, published_at, metadata)
    if not facts['relevant']:
        gaps.append('未取得具体生物医药关联')
    if not facts['specific']:
        gaps.append('具体事件事实待核对')
    if facts['publication']['label']:
        warnings.append(facts['publication']['label'])
    return {'relevant': facts['relevant'], 'gaps': list(dict.fromkeys(gaps)),
            'warnings': list(dict.fromkeys(warnings)), 'reasons': [facts['reason']],
            # Existing consumers use this broad purpose; review routing uses facts.view.
            'reading_use': '业务优先处理' if facts['view']=='priority' else '行业观察',
            'facts': facts, 'publishable': not gaps}


def assess_content_quality(
    title: str,
    text: str,
    source_url: str = "",
    published_at: str = "",
    language: str = "",
    duplicate_score: float = 0.0,
    http_status: int = 200,
) -> QualityResult:
    result = check_content_quality(title, text, source_url)
    if duplicate_score >= 0.9:
        return QualityResult("duplicate", "重复内容", False)
    return QualityResult(result["quality_status"], result["quality_reason"], result["is_accepted"])
