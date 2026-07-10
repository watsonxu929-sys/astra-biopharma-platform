from __future__ import annotations

import ipaddress
import re
import socket
from dataclasses import dataclass, asdict
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


@dataclass
class WebExtractResult:
    url: str
    title: str
    published_at: str
    text: str
    content_length: int

    def to_dict(self):
        return asdict(self)


BLOCKED_HOSTS = {
    "localhost",
    "127.0.0.1",
    "0.0.0.0",
    "::1",
}


def _is_public_host(hostname: str) -> bool:
    if not hostname or hostname.lower() in BLOCKED_HOSTS:
        return False

    try:
        addresses = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return False

    for address in addresses:
        ip_text = address[4][0]
        try:
            ip = ipaddress.ip_address(ip_text)
        except ValueError:
            return False

        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False

    return True


def validate_public_url(url: str) -> str:
    url = url.strip()
    parsed = urlparse(url)

    if parsed.scheme not in {"http", "https"}:
        raise ValueError("只支持 http 或 https 网页链接。")

    if not parsed.hostname or not _is_public_host(parsed.hostname):
        raise ValueError("该地址不是可访问的公网网页。")

    return url


def _meta_content(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        node = soup.find("meta", attrs={"property": key})
        if node and node.get("content"):
            return node["content"].strip()

        node = soup.find("meta", attrs={"name": key})
        if node and node.get("content"):
            return node["content"].strip()

    return ""


def _extract_published_at(soup: BeautifulSoup, text: str) -> str:
    value = _meta_content(
        soup,
        "article:published_time",
        "og:published_time",
        "publishdate",
        "pubdate",
        "date",
        "timestamp",
    )
    if value:
        match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", value)
        if match:
            y, m, d = map(int, match.groups())
            return f"{y:04d}-{m:02d}-{d:02d}"

    for pattern in [
        r"(20\d{2})年(\d{1,2})月(\d{1,2})日",
        r"(20\d{2})[-/.](\d{1,2})[-/.](\d{1,2})",
    ]:
        match = re.search(pattern, text[:3000])
        if match:
            y, m, d = map(int, match.groups())
            return f"{y:04d}-{m:02d}-{d:02d}"

    return ""


def _clean_html(soup: BeautifulSoup) -> None:
    for tag in soup(
        [
            "script",
            "style",
            "noscript",
            "svg",
            "canvas",
            "iframe",
            "form",
            "header",
            "nav",
            "footer",
            "aside",
            "button",
        ]
    ):
        tag.decompose()

    for selector in [
        ".advertisement",
        ".ads",
        ".ad",
        ".share",
        ".social",
        ".recommend",
        ".related",
        ".comment",
        "#comments",
        ".breadcrumb",
        ".breadcrumbs",
        ".sidebar",
        ".side-nav",
        ".subnav",
        ".language-switcher",
        "[class*='breadcrumb']",
        "[class*='footer']",
        "[class*='header-nav']",
    ]:
        for node in soup.select(selector):
            node.decompose()


def _best_content_node(soup: BeautifulSoup):
    candidates = []

    for selector in [
        "article",
        "main",
        "[role='main']",
        ".article-content",
        ".article-body",
        ".content",
        ".post-content",
        ".news-content",
        "#article-content",
        "#content",
    ]:
        for node in soup.select(selector):
            text = node.get_text("\n", strip=True)
            if len(text) >= 150:
                candidates.append((len(text), node))

    if candidates:
        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates[0][1]

    return soup.body or soup


def fetch_and_extract(url: str) -> WebExtractResult:
    url = validate_public_url(url)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 Chrome/124 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }

    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=httpx.Timeout(15.0, connect=8.0),
            headers=headers,
        ) as client:
            response = client.get(url)
            response.raise_for_status()
    except httpx.TimeoutException as exc:
        raise ValueError("网页读取超时，请直接复制正文。") from exc
    except httpx.HTTPStatusError as exc:
        raise ValueError(
            f"网页返回状态码 {exc.response.status_code}，请直接复制正文。"
        ) from exc
    except httpx.HTTPError as exc:
        raise ValueError("网页读取失败，请检查链接或直接复制正文。") from exc

    content_type = response.headers.get("content-type", "").lower()
    if "text/html" not in content_type and "application/xhtml+xml" not in content_type:
        raise ValueError("该链接不是普通网页，当前版本无法读取。")

    html = response.text
    if len(html) > 5_000_000:
        raise ValueError("网页内容过大，当前版本暂不处理。")

    soup = BeautifulSoup(html, "html.parser")
    title = (
        _meta_content(soup, "og:title", "twitter:title")
        or (soup.title.get_text(" ", strip=True) if soup.title else "")
    )

    _clean_html(soup)
    node = _best_content_node(soup)

    lines = []
    for raw_line in node.get_text("\n", strip=True).splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if len(line) >= 2:
            lines.append(line)

    deduplicated = []
    seen_short: dict[str, int] = {}
    for line in lines:
        if deduplicated and line == deduplicated[-1]:
            continue
        if len(line) <= 30:
            count = seen_short.get(line, 0)
            if count >= 1:
                continue
            seen_short[line] = count + 1
        deduplicated.append(line)

    text = "\n".join(deduplicated)
    if len(text) < 50:
        raise ValueError("未提取到足够正文，请直接复制网页正文。")

    text = text[:80_000]
    published_at = _extract_published_at(soup, text)

    return WebExtractResult(
        url=str(response.url),
        title=title[:300],
        published_at=published_at,
        text=text,
        content_length=len(text),
    )
