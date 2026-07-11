from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any

QUALITY_STATUSES = {
    "accepted",
    "low_quality",
    "duplicate",
    "access_denied",
    "parse_failed",
    "insufficient_content",
    "needs_manual_review",
}

_NAVIGATION_TERMS = (
    "cookie policy",
    "privacy policy",
    "terms of use",
    "skip to main content",
    "subscribe",
    "sign up",
    "all rights reserved",
    "网站地图",
    "隐私政策",
    "联系我们",
)
_ERROR_TERMS = ("page not found", "access denied", "service unavailable", "404 not found", "页面不存在", "访问被拒绝")
_LOGIN_TERMS = ("sign in", "log in", "forgot password", "验证码", "请输入密码", "登录后查看")
_DISCLAIMER_TERMS = ("disclaimer", "免责声明", "not medical advice")


@dataclass(frozen=True)
class ContentQualityResult:
    status: str
    accepted_for_analysis: bool
    score: int
    title_present: bool
    body_length: int
    published_at_credible: bool
    source_clear: bool
    language: str
    duplicate_score: float
    noise_ratio: float
    suspected_error_page: bool
    suspected_login_page: bool
    disclaimer_only: bool
    has_body: bool
    reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _credible_date(value: str | None) -> bool:
    if not value:
        return False
    text = str(value).strip()[:32]
    for candidate in (text, text.replace("Z", "+00:00")):
        try:
            year = datetime.fromisoformat(candidate).year
            return 1990 <= year <= datetime.now().year + 1
        except ValueError:
            continue
    match = re.search(r"\b(19|20)\d{2}\b", text)
    return bool(match and 1990 <= int(match.group(0)) <= datetime.now().year + 1)


def _ratio(text: str, terms: tuple[str, ...]) -> float:
    lowered = text.lower()
    hits = sum(lowered.count(term.lower()) * len(term) for term in terms)
    return min(1.0, hits / max(len(text), 1))


def assess_content_quality(
    *,
    title: str = "",
    text: str = "",
    source_url: str = "",
    published_at: str | None = None,
    language: str = "",
    duplicate_score: float = 0.0,
    http_status: int | None = 200,
    parse_error: str = "",
) -> ContentQualityResult:
    clean = re.sub(r"\s+", " ", text or "").strip()
    lowered = clean.lower()
    title_present = bool((title or "").strip())
    source_clear = source_url.startswith(("http://", "https://", "inline:"))
    noise_ratio = _ratio(clean, _NAVIGATION_TERMS)
    suspected_error = bool(http_status in {401, 403, 404, 410, 429, 500, 502, 503} or any(term in lowered for term in _ERROR_TERMS))
    suspected_login = any(term in lowered for term in _LOGIN_TERMS)
    disclaimer_only = len(clean) < 600 and any(term in lowered for term in _DISCLAIMER_TERMS)
    has_body = len(clean) >= 80
    reasons: list[str] = []

    if parse_error:
        status = "parse_failed"
        reasons.append(parse_error[:200])
    elif http_status in {401, 403} or suspected_login:
        status = "access_denied"
        reasons.append("access_or_login_page")
    elif duplicate_score >= 0.98:
        status = "duplicate"
        reasons.append("duplicate_content")
    elif suspected_error:
        status = "low_quality"
        reasons.append("suspected_error_page")
    elif not has_body or disclaimer_only:
        status = "insufficient_content"
        reasons.append("body_too_short_or_disclaimer_only")
    elif not title_present or not source_clear or noise_ratio > 0.18:
        status = "needs_manual_review"
        if not title_present:
            reasons.append("missing_title")
        if not source_clear:
            reasons.append("unclear_source")
        if noise_ratio > 0.18:
            reasons.append("high_navigation_noise")
    elif len(clean) < 240 or noise_ratio > 0.10:
        status = "low_quality"
        reasons.append("limited_or_noisy_content")
    else:
        status = "accepted"

    score = 100
    score -= 20 if not title_present else 0
    score -= 25 if not has_body else 0
    score -= 15 if not source_clear else 0
    score -= round(noise_ratio * 100)
    score -= 35 if suspected_error or suspected_login else 0
    score = max(0, min(100, score))
    accepted = status == "accepted"
    return ContentQualityResult(
        status=status,
        accepted_for_analysis=accepted,
        score=score,
        title_present=title_present,
        body_length=len(clean),
        published_at_credible=_credible_date(published_at),
        source_clear=source_clear,
        language=(language or "unknown")[:40],
        duplicate_score=max(0.0, min(float(duplicate_score), 1.0)),
        noise_ratio=round(noise_ratio, 4),
        suspected_error_page=suspected_error,
        suspected_login_page=suspected_login,
        disclaimer_only=disclaimer_only,
        has_body=has_body,
        reasons=reasons,
    )
