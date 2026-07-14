from __future__ import annotations

import re
from typing import Any

BIOPHARMA_KEYWORDS = [
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
        "is_not_login": not any(re.search(pattern, text, re.IGNORECASE) for pattern, _ in LOW_QUALITY_PATTERNS),
        "is_not_error": "404" not in text[:200] and "Not Found" not in text[:200],
        "is_not_navigation_only": not _is_navigation_only(text),
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
    if not checks["has_biopharma_content"]:
        return "irrelevant", "与生物医药产业无关"
    return "accepted", "通过质量检查"


def _is_navigation_only(text: str) -> bool:
    cleaned = text.strip()[:500]
    lines = [line.strip() for line in cleaned.splitlines() if line.strip()]
    if len(lines) < 3:
        return True
    if sum(1 for line in lines if len(line) < 20) > len(lines) * 0.7:
        return True
    return False


def _has_biopharma_keywords(title: str, text: str) -> bool:
    combined = (title + " " + text).lower()
    count = sum(1 for keyword in BIOPHARMA_KEYWORDS if keyword.lower() in combined)
    return count >= 2


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