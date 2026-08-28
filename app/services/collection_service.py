from __future__ import annotations

import hashlib
import csv
import html
import json
import io
import logging
import re
import secrets
import sqlite3
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

import feedparser
import httpx
from bs4 import BeautifulSoup

from app.core.content_extraction import extract_main_text
from app.services.collectors import PlaywrightAdapter, PlaywrightCollectionError, PlaywrightUnavailable
from app.services.processing.content_quality_service import check_content_quality, assess_content_quality, QUALITY_STATUS_LABELS
from app.v04c_review import db_connection, default_db_path
from scripts.migrate_v05f import migrate as migrate_v05f

USER_AGENT = "QBAY-Industry-Intelligence-Bot/0.5F"
_logger = logging.getLogger(__name__)
TRACKING_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content", "from", "share", "spm"}
SOURCE_TYPES = {"rss", "api", "webpage", "list_page", "dynamic_page", "manual_url_list"}
COLLECTION_MODES = {"http", "rss", "api", "playwright", "auto"}
JOB_STATUSES = {"pending", "running", "success", "partial", "unchanged", "failed", "skipped", "cancelled"}
COLLECTION_STATUS_LABELS = {
    "pending": "排队中",
    "queued": "排队中",
    "running": "运行中",
    "success": "成功",
    "partial": "部分成功",
    "partial_success": "部分成功",
    "unchanged": "无变化",
    "completed": "已完成",
    "failed": "失败",
    "skipped": "已跳过",
    "cancelled": "已取消",
    "source_disabled": "数据源已暂停",
    "robots_denied": "被网站 robots 规则限制",
    "network_error": "网络错误",
    "parse_error": "解析失败",
    "duplicate": "重复内容",
    "duplicate_running_job": "已有运行中的任务",
    "playwright_unavailable": "浏览器采集暂不可用",
    "FETCH_FAILED": "抓取失败",
    "PARSE_FAILED": "解析失败",
    "EXTRACTION_EMPTY": "正文为空",
    "DUPLICATE": "重复内容",
    "SUCCESS": "成功",
    "new": "新增",
    "changed": "有变化",
    "ignored": "已忽略",
    "processed": "已处理",
    "needs_review": "需要审核",
}
COLLECTION_EXPLANATIONS = {
    "success": "任务已完成，新增、变化、重复和排队数量见本行统计。",
    "partial": "任务部分完成，请查看失败数量和失败原因。",
    "partial_success": "任务部分完成，请查看失败数量和失败原因。",
    "failed": "任务执行失败，错误类型和错误信息已记录。",
    "skipped": "任务被跳过，请查看具体原因。",
    "source_disabled": "该数据源已暂停，不会自动采集。启用后可重新创建任务。",
    "robots_denied": "目标网站限制自动抓取。系统不会绕过该限制，可改用RSS、公开API、手工录入或获得授权的数据源。",
    "network_error": "访问目标网站失败，可能是网络、证书或目标站点不可用。",
    "parse_error": "页面已访问，但内容结构无法解析，需要调整采集规则或改为手工来源。",
    "duplicate": "采集内容已存在，系统未重复入库。",
    "duplicate_running_job": "同一数据源已有待执行或运行中的任务，本次没有重复创建。",
    "playwright_unavailable": "当前本地环境未启用浏览器采集，可改用HTTP、RSS、API或手工来源。",
    "FETCH_FAILED": "无法访问来源地址，请检查网络、证书或目标站点状态。",
    "PARSE_FAILED": "来源已访问，但Feed或返回内容无法解析。",
    "EXTRACTION_EMPTY": "页面已访问，但没有提取到可用正文。",
    "DUPLICATE": "采集内容已存在，系统未重复入库。",
    "SUCCESS": "采集成功。",
    "pending": "任务已创建并进入队列，尚未开始抓取。",
    "queued": "任务已进入队列，等待执行器处理。",
    "running": "任务正在执行。",
    "unchanged": "采集完成，但内容与历史记录一致，没有新增入库。",
    "cancelled": "任务已取消。",
}


def collection_status_label(value: Any) -> str:
    return COLLECTION_STATUS_LABELS.get(str(value or "").strip(), str(value or ""))


def collection_explanation(*values: Any) -> str:
    for value in values:
        key = str(value or "").strip()
        if key in COLLECTION_EXPLANATIONS:
            return COLLECTION_EXPLANATIONS[key]
    return "暂无额外说明。"

def _decorate_source(row: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    latest = conn.execute(
        """
        SELECT id, run_no, status, error_type, error_message, finished_at, created_at,
               new_content_count, changed_content_count, duplicate_content_count,
               failed_content_count, skipped_content_count, queued_item_count
        FROM v04g_monitoring_runs
        WHERE monitoring_source_id=? AND COALESCE(job_type,'collection')='collection'
        ORDER BY id DESC LIMIT 1
        """,
        (row["id"],),
    ).fetchone()
    item_count = int(conn.execute("SELECT COUNT(*) FROM v05f_collection_items WHERE monitoring_source_id=?", (row["id"],)).fetchone()[0] or 0)
    row["collected_item_count"] = item_count
    row["source_status_label"] = "已暂停" if row.get("auto_paused") else ("已启用" if row.get("is_enabled") else "已停用")
    row["domain"] = urlparse(str(row.get("url") or "")).netloc
    row["discovery"] = {}
    if row.get("health_status") == "candidate" and row.get("compliance_note"):
        try:
            row["discovery"] = json.loads(str(row["compliance_note"]))
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    if latest:
        data = dict(latest)
        row["latest_job"] = data
        row["latest_job_id"] = data.get("id")
        row["latest_job_no"] = data.get("run_no")
        row["latest_job_status"] = data.get("status")
        row["latest_job_status_label"] = collection_status_label(data.get("status"))
        row["latest_error_type"] = data.get("error_type")
        row["latest_error_label"] = collection_status_label(data.get("error_type")) if data.get("error_type") else ""
        row["latest_error_explanation"] = collection_explanation(data.get("error_type"), data.get("status"))
        row["latest_result_summary"] = f"新增 {data.get('new_content_count') or 0} / 变化 {data.get('changed_content_count') or 0} / 重复 {data.get('duplicate_content_count') or 0} / 排队 {data.get('queued_item_count') or 0} / 失败 {data.get('failed_content_count') or 0}"
    else:
        row["latest_job"] = None
        row["latest_job_status_label"] = "尚未采集"
        row["latest_result_summary"] = "暂无采集任务"
        row["latest_error_explanation"] = "该数据源还没有采集运行记录。"
    return row


def _decorate_job(row: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    row["status_label"] = collection_status_label(row.get("status"))
    row["error_label"] = collection_status_label(row.get("error_type")) if row.get("error_type") else ""
    row["status_explanation"] = collection_explanation(row.get("error_type"), row.get("status"))
    item_count = int(conn.execute("SELECT COUNT(*) FROM v05f_collection_items WHERE monitoring_run_id=?", (row["id"],)).fetchone()[0] or 0)
    first_item = conn.execute("SELECT id FROM v05f_collection_items WHERE monitoring_run_id=? ORDER BY id LIMIT 1", (row["id"],)).fetchone()
    try:
        proc_count = int(conn.execute("SELECT COUNT(*) FROM v05g_processing_jobs WHERE collection_item_id IN (SELECT id FROM v05f_collection_items WHERE monitoring_run_id=?)", (row["id"],)).fetchone()[0] or 0)
    except sqlite3.Error:
        proc_count = 0
    row["created_item_count"] = item_count
    row["first_item_id"] = int(first_item["id"]) if first_item else None
    row["processing_job_count"] = proc_count
    row["next_step_label"] = "查看原始情报" if item_count else ("查看失败原因" if row.get("status") == "failed" else "等待采集结果")
    row["next_step_url"] = f"/collection/items/{row['first_item_id']}" if row.get("first_item_id") else ""
    return row


def _decorate_item(row: dict[str, Any], conn: sqlite3.Connection) -> dict[str, Any]:
    row["dedup_status_label"] = collection_status_label(row.get("dedup_status"))
    row["change_status_label"] = collection_status_label(row.get("change_status"))
    row["processing_status_label"] = collection_status_label(row.get("processing_status"))
    try:
        proc = conn.execute("SELECT id, job_no, status FROM v05g_processing_jobs WHERE collection_item_id=? ORDER BY id DESC LIMIT 1", (row["id"],)).fetchone()
    except sqlite3.Error:
        proc = None
    try:
        pub = conn.execute("SELECT id FROM v06_intelligence_items WHERE source_name='v05f_collection_items' AND source_url=? ORDER BY id DESC LIMIT 1", (row.get("normalized_url") or "",)).fetchone()
    except sqlite3.Error:
        pub = None
    try:
        candidate = conn.execute(
            "SELECT id,is_pilot,pilot_batch_id FROM v05g_extraction_candidates WHERE collection_item_id=? ORDER BY id LIMIT 1",
            (row["id"],),
        ).fetchone()
        cand_count = int(conn.execute("SELECT COUNT(*) FROM v05g_extraction_candidates WHERE collection_item_id=?", (row["id"],)).fetchone()[0] or 0)
    except sqlite3.Error:
        candidate = None
        cand_count = 0
    row["processing_job_id"] = int(proc["id"]) if proc else None
    row["processing_job_no"] = proc["job_no"] if proc else ""
    row["candidate_count"] = cand_count
    row["first_candidate_id"] = int(candidate["id"]) if candidate else None
    row["is_pilot"] = bool(row.get("is_pilot") or (candidate and candidate["is_pilot"]))
    row["pilot_batch_id"] = row.get("pilot_batch_id") or (candidate["pilot_batch_id"] if candidate else None)
    row["published_intelligence_id"] = int(pub["id"]) if pub else None
    row["flow_hint"] = "已发布到前台情报" if row.get("published_intelligence_id") else ("已有候选，等待审核或发布" if cand_count else ("已进入处理任务" if proc else "尚未进入处理任务"))
    return row


@dataclass
class ExtractedPage:
    url: str
    normalized_url: str
    canonical_url: str
    title: str
    published_at: str
    author: str
    description: str
    raw_html: str
    cleaned_html: str
    text: str
    summary: str
    content_hash: str
    structure_hash: str
    page_structure: str
    language: str
    warnings: list[str]
    http_status: int = 200
    content_type: str = "text/html"
    guid: str = ""
    extractor: str = "trafilatura"


def now() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def ensure_schema(db_path: str | Path | None = None, *, allow_migration: bool = False) -> Path:
    path = Path(db_path) if db_path else default_db_path()
    if not allow_migration:
        return path
    migrate_v05f(path, backup=False)
    return path


def _next_no(conn: sqlite3.Connection, prefix: str) -> str:
    stamp = datetime.now().strftime("%Y%m%d")
    row = conn.execute(
        """
        INSERT INTO v05f_sequence_counters(seq_key, seq_date, seq_value, updated_at)
        VALUES (?, ?, 1, ?)
        ON CONFLICT(seq_key) DO UPDATE SET
            seq_value = CASE WHEN seq_date=excluded.seq_date THEN seq_value+1 ELSE 1 END,
            seq_date = excluded.seq_date,
            updated_at = excluded.updated_at
        RETURNING seq_value
        """,
        (prefix, stamp, now()),
    ).fetchone()
    return f"{prefix}-{stamp}-{int(row['seq_value']):05d}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, default=str)


def _hash_text(value: str) -> str:
    normalized = re.sub(r"\s+", "\n", (value or "").strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_url(url: str, base_url: str = "", canonical_url: str = "") -> str:
    target = (canonical_url or url or "").strip()
    if base_url:
        target = urljoin(base_url, target)
    parsed = urlparse(target)
    scheme = (parsed.scheme or "http").lower()
    netloc = parsed.netloc.lower()
    if scheme == "http" and netloc.endswith(":80"):
        netloc = netloc[:-3]
    if scheme == "https" and netloc.endswith(":443"):
        netloc = netloc[:-4]
    path = re.sub(r"/{2,}", "/", parsed.path or "/")
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    query_pairs = []
    seen: set[tuple[str, str]] = set()
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        if key.lower().startswith("utm_") or key.lower() in TRACKING_PARAMS:
            continue
        pair = (key, value)
        if pair not in seen:
            query_pairs.append(pair)
            seen.add(pair)
    query = urlencode(sorted(query_pairs), doseq=True)
    return urlunparse((scheme, netloc, path, "", query, ""))


def _meta(soup: BeautifulSoup, *keys: str) -> str:
    for key in keys:
        node = soup.find("meta", attrs={"property": key}) or soup.find("meta", attrs={"name": key})
        if node and node.get("content"):
            return str(node["content"]).strip()
    return ""


def _date_candidate(soup: BeautifulSoup, text: str) -> str:
    value = _meta(soup, "article:published_time", "date", "pubdate", "publishdate", "timestamp")
    haystack = f"{value}\n{text[:3000]}"
    match = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", haystack)
    if match:
        y, m, d = map(int, match.groups())
        return f"{y:04d}-{m:02d}-{d:02d}"
    return value[:50] if value else ""


def _structure_type(url: str, title: str, text: str) -> str:
    sample = f"{url}\n{title}\n{text[:2000]}".lower()
    if any(k in sample for k in ["rss", "<feed", "<channel"]):
        return "feed"
    if any(k in sample for k in ["team", "leadership", "management", "管理团队", "团队"]):
        return "team"
    if any(k in sample for k in ["pipeline", "product", "管线", "产品"]):
        return "product_pipeline"
    if any(k in sample for k in ["career", "jobs", "recruit", "招聘"]):
        return "recruitment"
    if any(k in sample for k in ["policy", "政府", "园区", "协会", "公告"]):
        return "policy"
    if len(re.findall(r"\n.{4,80}\n", text[:4000])) > 12:
        return "list"
    if len(text) >= 300:
        return "article"
    return "unknown"


def extract_html(raw_html: str, url: str) -> ExtractedPage:
    soup = BeautifulSoup(raw_html or "", "html.parser")
    title = _meta(soup, "og:title", "twitter:title") or (soup.title.get_text(" ", strip=True) if soup.title else "")
    canonical_node = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical = str(canonical_node.get("href", "")).strip() if canonical_node else ""
    description = _meta(soup, "description", "og:description")
    author = _meta(soup, "author", "article:author")
    lang = (soup.html.get("lang") if soup.html else "") or ""
    text, extractor = extract_main_text(raw_html)
    warnings = []
    if len(text) < 50:
        warnings.extend(["empty_content", "EXTRACTION_EMPTY"])
    truncated = False
    if len(raw_html) > 1_000_000:
        raw_html = raw_html[:1_000_000]
        truncated = True
    if len(text) > 80_000:
        text = text[:80_000]
        truncated = True
    if truncated:
        warnings.append("content_truncated")
    cleaned_html = f"<article>{html.escape(text)}</article>"[:200_000]
    normalized = normalize_url(url, canonical_url=canonical)
    published = _date_candidate(soup, text)
    content_hash = _hash_text(text)
    structure_hash = _hash_text("\n".join(line[:80] for line in text.splitlines()[:40]))
    return ExtractedPage(
        url=url,
        normalized_url=normalized,
        canonical_url=normalize_url(canonical, base_url=url) if canonical else "",
        title=html.unescape(title)[:300],
        published_at=published,
        author=author[:200],
        description=description[:500],
        raw_html=raw_html,
        cleaned_html=cleaned_html,
        text=text,
        summary=text[:500],
        content_hash=content_hash,
        structure_hash=structure_hash,
        page_structure=_structure_type(url, title, text),
        language=lang[:40],
        warnings=warnings,
        extractor=extractor,
    )


def discover_links(raw_html: str, base_url: str, allowed_domains: list[str] | None = None, max_links: int = 20) -> list[dict[str, str]]:
    soup = BeautifulSoup(raw_html or "", "html.parser")
    base_host = urlparse(base_url).hostname or ""
    allowed = {base_host.lower(), *(d.lower().strip() for d in (allowed_domains or []) if d.strip())}
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    blocked_words = ("login", "register", "privacy", "terms", "share", "javascript:", "mailto:", "tel:")
    for node in soup.find_all("a", href=True):
        href = str(node["href"]).strip()
        if not href or any(word in href.lower() for word in blocked_words):
            continue
        absolute = urljoin(base_url, href)
        parsed = urlparse(absolute)
        if parsed.scheme not in {"http", "https"}:
            continue
        if (parsed.hostname or "").lower() not in allowed:
            continue
        normalized = normalize_url(absolute)
        if normalized in seen:
            continue
        seen.add(normalized)
        text = node.get_text(" ", strip=True)[:300]
        if len(text) < 2 and not re.search(r"\d{4}", normalized):
            continue
        rows.append({"url": absolute, "normalized_url": normalized, "link_text": text, "title_candidate": text})
        if len(rows) >= max_links:
            break
    return rows


def _inline_payload(url: str) -> str | None:
    if url.startswith("inline:"):
        return url.split(":", 1)[1]
    return None


def _http_get(
    url: str,
    timeout: int = 15,
    conditional_headers: dict[str, str] | None = None,
    retries: int = 2,
) -> tuple[str, int, str, dict[str, str]]:
    payload = _inline_payload(url)
    if payload is not None:
        return payload, 200, "text/html; charset=utf-8", {}
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/rss+xml,application/xml,application/json;q=0.9,*/*;q=0.5",
        **(conditional_headers or {}),
    }
    with httpx.Client(
        follow_redirects=True,
        timeout=httpx.Timeout(float(timeout), connect=min(float(timeout), 8.0)),
        headers=headers,
    ) as client:
        for attempt in range(max(0, min(retries, 2)) + 1):
            try:
                response = client.get(url)
                if response.status_code == 304:
                    return "", 304, response.headers.get("content-type", ""), dict(response.headers)
                response.raise_for_status()
                return response.text, response.status_code, response.headers.get("content-type", ""), dict(response.headers)
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                retryable = not isinstance(exc, httpx.HTTPStatusError) or exc.response.status_code in {408, 429, 500, 502, 503, 504}
                if attempt >= min(retries, 2) or not retryable:
                    raise RuntimeError("FETCH_FAILED") from exc
                time.sleep(min(4.0, 0.5 * (2 ** attempt)))
    raise RuntimeError("FETCH_FAILED")


def check_robots(url: str, user_agent: str = USER_AGENT, timeout: int = 8) -> dict[str, Any]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return {"allowed": True, "status": "not_applicable", "summary": "non-http or inline source"}
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        with httpx.Client(timeout=timeout, headers={"User-Agent": user_agent}) as client:
            response = client.get(robots_url)
        if response.status_code >= 400:
            return {"allowed": True, "status": "unavailable", "robots_url": robots_url, "summary": f"robots returned {response.status_code}"}
        parser.parse(response.text.splitlines())
        allowed = parser.can_fetch(user_agent, url)
        return {"allowed": allowed, "status": "allowed" if allowed else "denied", "robots_url": robots_url, "summary": "robots parsed"}
    except Exception as exc:
        return {"allowed": True, "status": "unavailable", "robots_url": robots_url, "summary": exc.__class__.__name__}


def create_collection_source(
    *,
    name: str,
    source_type: str,
    url: str,
    collection_mode: str = "auto",
    allowed_domains: str = "",
    subject_type: str = "",
    subject_id: str = "",
    owner: str = "",
    compliance_note: str = "",
    max_links: int = 20,
    crawl_detail_pages: bool = False,
    check_frequency: str = "manual",
    is_enabled: bool = True,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    ensure_schema(db_path)
    source_type = source_type if source_type in SOURCE_TYPES else "webpage"
    collection_mode = collection_mode if collection_mode in COLLECTION_MODES else "auto"
    fetch_mode = "manual" if source_type == "manual_url_list" else "web"
    check_frequency = check_frequency if check_frequency in {"manual", "daily", "weekly", "monthly"} else "manual"
    url = normalize_url(url) if url.startswith(("http://", "https://")) else url.strip()
    ts = now()
    with db_connection(db_path) as conn:
        existing = next((row for row in conn.execute(
            "SELECT * FROM v04g_monitoring_sources WHERE deactivated_at IS NULL"
        ) if _source_identity(row["url"]) == _source_identity(url)), None)
        if existing:
            row_id = existing["id"]
        else:
            cur = conn.execute(
                """
                INSERT INTO v04g_monitoring_sources(
                    source_no, name, source_type, url, subject_type, subject_id, check_frequency,
                    is_enabled, owner, fetch_mode, note, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (_next_no(conn, "MON"), name[:200], source_type, url[:2000], subject_type or None, subject_id or None,
                 check_frequency, int(bool(is_enabled)), owner[:100] or None, fetch_mode, compliance_note[:2000] or None, ts, ts),
            )
            row_id = cur.lastrowid
        conn.execute(
            """
            UPDATE v04g_monitoring_sources
            SET collection_source_type=?, collection_mode=?, allowed_domains=?, content_kind=?,
                max_links=?, crawl_detail_pages=?, compliance_note=?, updated_at=?
            WHERE id=?
            """,
            (source_type, collection_mode, allowed_domains[:1000] or None, source_type, int(max_links or 20), int(bool(crawl_detail_pages)), compliance_note[:2000] or None, ts, row_id),
        )
        return dict(conn.execute("SELECT * FROM v04g_monitoring_sources WHERE id=?", (row_id,)).fetchone())


def list_sources(db_path: str | Path | None = None, page: int = 1, page_size: int = 20, status: str = "", q: str = "") -> tuple[list[dict[str, Any]], int]:
    ensure_schema(db_path)
    clauses = ["deactivated_at IS NULL", "COALESCE(health_status,'')<>'candidate'"] if not status else ["deactivated_at IS NULL"]
    params: list[Any] = []
    if status == "enabled":
        clauses.append("is_enabled=1")
    elif status == "failed":
        clauses.append("consecutive_failures>0")
    elif status == "paused":
        clauses.append("auto_paused=1")
    elif status == "candidate":
        clauses.append("is_enabled=0 AND health_status='candidate'")
    elif status == "disabled":
        clauses.append("is_enabled=0 AND COALESCE(health_status,'')<>'candidate'")
    if q:
        clauses.append("(name LIKE ? OR url LIKE ? OR source_no LIKE ?)")
        params.extend([f"%{q}%", f"%{q}%", f"%{q}%"])
    where = " AND ".join(clauses)
    offset = (max(1, page) - 1) * page_size
    with db_connection(db_path) as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM v04g_monitoring_sources WHERE {where}", params).fetchone()[0])
        rows = [dict(r) for r in conn.execute(
            f"""
            SELECT id, source_no, name, source_type, url, subject_type, subject_id, is_enabled,
                   owner, collection_source_type, collection_mode, robots_status, auto_paused,
                   health_status, check_frequency, last_checked_at, last_success_at, last_error_at,
                   last_pause_reason, consecutive_failures, compliance_note, note
            FROM v04g_monitoring_sources WHERE {where}
            ORDER BY id DESC LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()]
        rows = [_decorate_source(row, conn) for row in rows]
    return rows, total


def source_detail(source_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v04g_monitoring_sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise ValueError("source_not_found")
        data = _decorate_source(dict(row), conn)
        data["intelligence_count"] = int(conn.execute("""
            SELECT COUNT(*) FROM v06_intelligence_items x
            WHERE x.source_record_type='collection_item' AND EXISTS (
              SELECT 1 FROM v05f_collection_items i
              WHERE i.id=CAST(x.source_record_id AS INTEGER) AND i.monitoring_source_id=?
            )
        """, (source_id,)).fetchone()[0] or 0)
        return data


def update_collection_source(source_id: int, fields: dict[str, Any], db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    name, url = str(fields.get("name") or "").strip(), str(fields.get("url") or "").strip()
    if not name or not url:
        raise ValueError("name_and_url_required")
    url = normalize_url(url) if url.startswith(("http://", "https://")) else url
    source_type = str(fields.get("source_type") or "webpage")
    mode = str(fields.get("collection_mode") or "auto")
    frequency = str(fields.get("check_frequency") or "manual")
    if source_type not in SOURCE_TYPES or mode not in COLLECTION_MODES or frequency not in {"manual", "daily", "weekly", "monthly"}:
        raise ValueError("invalid_source_settings")
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT id FROM v04g_monitoring_sources WHERE id=? AND deactivated_at IS NULL", (source_id,)).fetchone()
        if not row:
            raise ValueError("source_not_found")
        if conn.execute("SELECT 1 FROM v04g_monitoring_sources WHERE url=? AND deactivated_at IS NULL AND id<>?", (url, source_id)).fetchone():
            raise ValueError("source_url_exists")
        conn.execute("""
            UPDATE v04g_monitoring_sources SET name=?,url=?,source_type=?,collection_source_type=?,content_kind=?,
              collection_mode=?,check_frequency=?,subject_type=?,subject_id=?,updated_at=? WHERE id=?
        """, (name[:200], url[:2000], source_type, source_type, source_type, mode, frequency,
              fields.get("subject_type") or None, fields.get("subject_id") or None, now(), source_id))
    return source_detail(source_id, db_path)


def set_source_enabled(source_id: int, enabled: bool, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        if not conn.execute("SELECT 1 FROM v04g_monitoring_sources WHERE id=? AND deactivated_at IS NULL", (source_id,)).fetchone():
            raise ValueError("source_not_found")
        conn.execute("""
            UPDATE v04g_monitoring_sources SET is_enabled=?,auto_paused=0,last_pause_reason=NULL,
              health_status=CASE WHEN ?=1 THEN 'healthy' ELSE 'disabled' END,updated_at=? WHERE id=?
        """, (int(enabled), int(enabled), now(), source_id))
    return source_detail(source_id, db_path)


def delete_or_retire_source(source_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    detail = source_detail(source_id, db_path)
    with db_connection(db_path) as conn:
        if detail["collected_item_count"] or detail["intelligence_count"]:
            ts = now()
            conn.execute("""
                UPDATE v04g_monitoring_sources SET is_enabled=0,auto_paused=1,health_status='retired',
                  deactivated_at=?,last_pause_reason='管理员退役，历史保留',updated_at=? WHERE id=?
            """, (ts, ts, source_id))
            return {"action": "retired", "history_preserved": True, **detail}
        conn.execute("DELETE FROM v04g_monitoring_sources WHERE id=?", (source_id,))
        return {"action": "deleted", "history_preserved": False, **detail}


def test_source_url(url: str) -> dict[str, Any]:
    url = str(url or "").strip()
    if not url.startswith(("http://", "https://", "inline:")):
        return {"ok": False, "status": "INVALID_URL", "url": url}
    try:
        body, status, content_type, headers = _http_get(url, timeout=8, retries=0)
    except RuntimeError:
        return {"ok": False, "status": "FETCH_FAILED", "url": url}
    feed = feedparser.parse(body) if ("xml" in content_type or "rss" in content_type or "atom" in content_type) else None
    soup = BeautifulSoup(body, "html.parser")
    feed_link = soup.find("link", rel=lambda value: value and "alternate" in value,
                          attrs={"type": re.compile(r"rss|atom", re.I)})
    text_value, extractor = extract_main_text(body)
    canonical_link = soup.find("link", rel=lambda value: value and "canonical" in value,
                               href=True)
    recent_items = [
        {
            "title": str(entry.get("title") or "").strip(),
            "published": str(entry.get("published") or entry.get("updated") or "").strip(),
        }
        for entry in (feed.entries[:3] if feed else []) if entry.get("title")
    ]
    recent = [item["title"] for item in recent_items]
    if not recent:
        recent = [node.get_text(" ", strip=True) for node in soup.select("h1,h2,h3")[:3]]
        recent_items = [{"title": title, "published": ""} for title in recent]
    return {
        "ok": True, "status": "READY", "url": normalize_url(url) if not url.startswith("inline:") else url,
        "http_status": status, "is_rss": bool(feed and feed.entries),
        "rss_url": urljoin(url, feed_link.get("href")) if feed_link else "",
        "is_html": bool(soup.find()), "needs_playwright": len(text_value) < 120 and len(soup.find_all("script")) >= 5,
        "extractable": len(text_value) >= 80, "extractor": extractor,
        "recent_titles": recent, "recent_items": recent_items,
        "content_type": content_type, "canonical_url": urljoin(url, canonical_link.get("href"))
        if canonical_link else headers.get("content-location", ""),
    }


def _source_identity(url: str) -> str:
    value = normalize_url(url)
    parsed = urlparse(value)
    host = parsed.netloc.lower().removeprefix("www.")
    return f"{host}{parsed.path.rstrip('/') or '/'}?{parsed.query}".rstrip("?")


def preview_source_import(text_value: str, db_path: str | Path | None = None) -> list[dict[str, Any]]:
    raw = str(text_value or "").strip()
    if not raw:
        return []
    if "," in raw.splitlines()[0]:
        parsed = list(csv.DictReader(io.StringIO(raw)))
        rows = [(str(item.get("name") or "").strip(), str(item.get("url") or "").strip()) for item in parsed]
    else:
        rows = [(urlparse(line.strip()).netloc or line.strip(), line.strip()) for line in raw.splitlines() if line.strip()]
    with db_connection(db_path) as conn:
        existing = {_source_identity(row[0]) for row in conn.execute(
            "SELECT url FROM v04g_monitoring_sources WHERE deactivated_at IS NULL"
        )}
    seen: set[str] = set()
    preview = []
    for name, url in rows[:100]:
        if not url.startswith(("http://", "https://", "inline:")):
            preview.append({"name": name, "url": url, "kind": "NEW", "status": "INVALID_URL"})
            continue
        identity = _source_identity(url) if not url.startswith("inline:") else url
        if identity in seen:
            preview.append({"name": name, "url": url, "kind": "NEW", "status": "DUPLICATE_IN_FILE"})
            continue
        seen.add(identity)
        if identity in existing:
            preview.append({"name": name, "url": url, "kind": "EXISTS", "status": "EXISTS"})
            continue
        tested = test_source_url(url)
        preview.append({"name": name or urlparse(url).netloc, "url": tested.get("url", url),
                        "kind": "NEW", "status": tested["status"]})
    return preview


def save_source_import(rows: list[dict[str, Any]], owner: str, db_path: str | Path | None = None) -> dict[str, int]:
    counts = {"created": 0, "exists": 0, "invalid": 0, "failed": 0}
    for row in rows:
        status = row.get("status")
        if status == "READY":
            created = create_collection_source(
                name=str(row.get("name") or "导入来源"), source_type="webpage",
                url=str(row["url"]), owner=owner, is_enabled=False, db_path=db_path,
            )
            with db_connection(db_path) as conn:
                conn.execute("UPDATE v04g_monitoring_sources SET health_status='candidate',note='R7.1 BATCH IMPORT' WHERE id=?", (created["id"],))
            counts["created"] += 1
        elif status == "EXISTS":
            counts["exists"] += 1
        elif status == "INVALID_URL":
            counts["invalid"] += 1
        elif status == "FETCH_FAILED":
            counts["failed"] += 1
    return counts


DISCOVERY_KEYWORDS = re.compile(
    r"news|newsroom|media|press|press-release|investor|updates|blog|announcement|insights|新闻|动态|公告|媒体", re.I
)

THIRD_PARTY_DOMAINS = {
    "wikipedia.org", "wikidata.org", "linkedin.com", "facebook.com", "x.com",
    "twitter.com", "weibo.com", "qcc.com", "tianyancha.com", "crunchbase.com",
    "36kr.com", "baidu.com", "zhihu.com", "liepin.com", "zhipin.com",
}


def _domain_root(url: str) -> str:
    parsed = urlparse(str(url or "").strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return f"{parsed.scheme}://{parsed.netloc}/"


def _is_third_party_domain(url: str) -> bool:
    host = (urlparse(url).hostname or "").lower().removeprefix("www.")
    return any(host == domain or host.endswith(f".{domain}") for domain in THIRD_PARTY_DOMAINS)


def _brand_key(value: str) -> str:
    value = re.sub(r"[\s\W_]+", "", str(value or "").casefold())
    return re.sub(r"(?:有限责任公司|股份有限公司|有限公司|集团|公司)$", "", value)


def validate_official_domain_candidate(url: str, organization_name: str) -> dict[str, Any]:
    """Validate a possible official domain without promoting it to canonical truth."""
    root = _domain_root(url)
    if not root:
        return {"ok": False, "status": "INVALID_URL", "candidate_url": str(url or "")}
    if _is_third_party_domain(root):
        return {"ok": False, "status": "THIRD_PARTY_DOMAIN", "candidate_url": root}
    try:
        body, status, _, _ = _http_get(root, timeout=8, retries=0)
    except RuntimeError:
        return {"ok": False, "status": "FETCH_FAILED", "candidate_url": root}
    soup = BeautifulSoup(body, "html.parser")
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    brand_nodes = [
        soup.find("meta", attrs={"property": "og:site_name"}),
        soup.find("meta", attrs={"name": "application-name"}),
    ]
    brand_text = " ".join(str(node.get("content") or "") for node in brand_nodes if node)
    schema_names: list[str] = []
    for node in soup.find_all("script", attrs={"type": "application/ld+json"})[:10]:
        try:
            payload = json.loads(node.get_text(" ", strip=True) or "{}")
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
        queue = payload if isinstance(payload, list) else [payload]
        for item in queue:
            if isinstance(item, dict) and str(item.get("@type") or "").lower() in {"organization", "corporation"}:
                schema_names.append(str(item.get("name") or ""))
    headings = " ".join(node.get_text(" ", strip=True) for node in soup.select("h1")[:3])
    needle = _brand_key(organization_name)
    title_key, brand_key = _brand_key(title), _brand_key(brand_text)
    schema_keys = [_brand_key(name) for name in schema_names]
    combined = _brand_key(" ".join([title, brand_text, headings, *schema_names]))
    matched = bool(needle and len(needle) >= 3 and needle in combined)
    evidence = []
    if needle and needle in title_key:
        evidence.append("页面标题与主体匹配")
    if needle and needle in brand_key:
        evidence.append("站点品牌标识与主体匹配")
    if any(needle and needle in value for value in schema_keys):
        evidence.append("Schema.org Organization与主体匹配")
    if matched and not evidence:
        evidence.append("首页明显品牌文字与主体匹配")
    return {
        "ok": matched, "status": "CANDIDATE_VERIFIED" if matched else "SUBJECT_MISMATCH",
        "candidate_url": root, "http_status": status, "page_title": title,
        "validation_basis": evidence, "third_party": False,
    }


def propose_official_domain_candidate(
    organization_id: str, organization_name: str, url: str, discovery_basis: str,
    actor: str, db_path: str | Path | None = None,
) -> dict[str, Any]:
    validation = validate_official_domain_candidate(url, organization_name)
    if not validation["ok"]:
        return {"created": False, "validation": validation}
    root = str(validation["candidate_url"])
    normalized = (urlparse(root).hostname or "").lower().removeprefix("www.")
    with db_connection(db_path) as conn:
        existing = conn.execute(
            """SELECT * FROM p3_entity_external_identifiers
               WHERE entity_type='organization' AND entity_id=? AND identifier_type='official_domain'
                 AND normalized_value=? AND review_status IN ('pending','approved') ORDER BY id DESC LIMIT 1""",
            (organization_id, normalized),
        ).fetchone()
        if existing:
            return {"created": False, "candidate": dict(existing), "validation": validation}
        stamp = now()
        cur = conn.execute(
            """INSERT INTO p3_entity_external_identifiers(
               entity_type,entity_id,identifier_type,identifier_value,normalized_value,authority,
               source,source_url,review_status,is_sensitive,is_pilot,created_by,created_at,updated_at
               ) VALUES ('organization',?,'official_domain',?,?,?,?,?,'pending',0,0,?,?,?)""",
            (organization_id, root, normalized, "; ".join(validation["validation_basis"]),
             discovery_basis, root, actor, stamp, stamp),
        )
        candidate = dict(conn.execute(
            "SELECT * FROM p3_entity_external_identifiers WHERE id=?", (cur.lastrowid,)
        ).fetchone())
    return {"created": True, "candidate": candidate, "validation": validation}


def review_official_domain_candidate(
    candidate_id: int, organization_id: str, decision: str, actor: str,
    db_path: str | Path | None = None,
) -> dict[str, Any]:
    if decision not in {"approved", "rejected"}:
        raise ValueError("invalid_domain_decision")
    with db_connection(db_path) as conn:
        row = conn.execute(
            """SELECT * FROM p3_entity_external_identifiers
               WHERE id=? AND entity_type='organization' AND entity_id=? AND identifier_type='official_domain'
                 AND review_status='pending'""", (candidate_id, organization_id),
        ).fetchone()
        if not row:
            raise ValueError("domain_candidate_not_found")
        stamp = now()
        conn.execute(
            "UPDATE p3_entity_external_identifiers SET review_status=?,reviewed_by=?,reviewed_at=?,updated_at=? WHERE id=?",
            (decision, actor, stamp, stamp, candidate_id),
        )
        return dict(conn.execute(
            "SELECT * FROM p3_entity_external_identifiers WHERE id=?", (candidate_id,)
        ).fetchone())


def organization_monitoring_context(
    organization_id: str, db_path: str | Path | None = None,
) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        organization = conn.execute(
            "SELECT id,external_id,COALESCE(NULLIF(name,''),standard_name) AS name,source_url FROM organizations WHERE external_id=?",
            (organization_id,),
        ).fetchone()
        if not organization:
            raise ValueError("organization_not_found")
        internal_id = str(organization["id"])
        sources = [dict(row) for row in conn.execute(
            """SELECT * FROM v04g_monitoring_sources
               WHERE deactivated_at IS NULL AND subject_type='organization' AND subject_id IN (?,?)
               ORDER BY is_enabled DESC,id DESC""", (organization_id, internal_id),
        )]
        sources = [_decorate_source(row, conn) for row in sources]
        domains = [dict(row) for row in conn.execute(
            """SELECT * FROM p3_entity_external_identifiers
               WHERE entity_type='organization' AND entity_id=? AND identifier_type='official_domain'
               ORDER BY CASE review_status WHEN 'approved' THEN 0 WHEN 'pending' THEN 1 ELSE 2 END,id DESC""",
            (organization_id,),
        )]
        latest_intelligence = conn.execute(
            """SELECT i.id,i.title FROM core_intelligence_subject_links l
               JOIN v06_intelligence_items i ON i.id=l.intelligence_item_id
               WHERE l.subject_type='organization' AND l.subject_id=? ORDER BY i.id DESC LIMIT 1""",
            (int(organization["id"]),),
        ).fetchone()
        evidence_urls = [str(organization["source_url"])] if organization["source_url"] else []
        evidence_urls.extend(str(row[0]) for row in conn.execute(
            """SELECT DISTINCT i.source_url FROM core_intelligence_subject_links l
               JOIN v06_intelligence_items i ON i.id=l.intelligence_item_id
               WHERE l.subject_type='organization' AND l.subject_id=? AND i.source_url IS NOT NULL""",
            (int(organization["id"]),),
        ))
    active = [source for source in sources if source.get("is_enabled")]
    candidates = [source for source in sources if source.get("health_status") == "candidate"]
    approved_domain = next((row for row in domains if row["review_status"] == "approved"), None)
    pending_domain = next((row for row in domains if row["review_status"] == "pending"), None)
    status = "COVERED_ACTIVE" if active else ("COVERED_CANDIDATE" if candidates else "MANUAL_DOMAIN_REQUIRED")
    return {
        "organization": dict(organization), "sources": sources, "active_sources": active,
        "candidate_sources": candidates, "official_domain": approved_domain,
        "domain_candidate": pending_domain, "evidence_urls": list(dict.fromkeys(evidence_urls)),
        "monitoring_status": status,
        "last_collection": max((str(source.get("last_success_at") or "") for source in sources), default=""),
        "latest_intelligence": dict(latest_intelligence) if latest_intelligence else None,
    }


def _discovery_priority(item: tuple[str, str, str, str]) -> tuple[int, str]:
    text = f"{item[0]} {item[1]} {item[3]}".lower()
    if re.search(r"newsroom|press|media|news-release|rss|atom|新闻", text):
        return 1, text
    if re.search(r"investor|announcement|投资者|公告", text):
        return 2, text
    if re.search(r"product|r&d|research|updates|研发|产品|动态", text):
        return 3, text
    if re.search(r"blog|insight", text):
        return 4, text
    return 5, text


def discover_source_candidates(
    homepage_url: str, organization_id: int | str | None = None, organization_name: str = "",
    owner: str = "", db_path: str | Path | None = None,
) -> dict[str, Any]:
    tested = test_source_url(homepage_url)
    result = {
        "domain": urlparse(homepage_url).netloc, "homepage_ok": tested["ok"], "rss": 0,
        "sitemap": 0, "newsroom": 0, "created": 0, "duplicates": 0, "invalid": 0,
        "candidates": [],
    }
    if not tested["ok"]:
        result["invalid"] = 1
        return result
    body, _, _, _ = _http_get(homepage_url, timeout=8, retries=0)
    soup = BeautifulSoup(body, "html.parser")
    found: list[tuple[str, str, str, str]] = []
    for node in soup.find_all("link", href=True):
        if "alternate" in (node.get("rel") or []) and re.search(r"rss|atom", str(node.get("type") or ""), re.I):
            found.append((str(node.get("title") or organization_name or "RSS"), urljoin(homepage_url, node["href"]), "rss", "官网RSS/Atom声明"))
    for node in soup.find_all("a", href=True):
        label = node.get_text(" ", strip=True)
        if DISCOVERY_KEYWORDS.search(f"{label} {node['href']}"):
            found.append((label or organization_name or "Newsroom", urljoin(homepage_url, node["href"]), "list_page", "官网导航发现"))
    parsed = urlparse(homepage_url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for suffix in ("/feed", "/rss", "/rss.xml", "/feed.xml", "/atom.xml"):
        found.append((f"{organization_name or parsed.netloc} Feed", base + suffix, "rss", "常见Feed地址验证"))
    sitemap_urls = [base + "/sitemap.xml"]
    try:
        robots, _, _, _ = _http_get(base + "/robots.txt", timeout=5, retries=0)
        sitemap_urls = [line.split(":", 1)[1].strip() for line in robots.splitlines()
                        if line.lower().startswith("sitemap:")] or sitemap_urls
    except RuntimeError:
        pass
    for sitemap_url in sitemap_urls[:2]:
        try:
            sitemap, _, _, _ = _http_get(sitemap_url, timeout=6, retries=0)
            for loc in re.findall(r"<loc>(.*?)</loc>", sitemap, re.I | re.S):
                if DISCOVERY_KEYWORDS.search(loc):
                    found.append((organization_name or "Newsroom", html.unescape(loc.strip()), "list_page", "Sitemap发现"))
        except RuntimeError:
            continue
    existing_rows, _ = list_sources(db_path=db_path, page_size=500, status="all")
    existing = {_source_identity(row["url"]) for row in existing_rows}
    seen: set[str] = set()
    for name, url, source_type, method in sorted(found, key=_discovery_priority):
        if not url.startswith(("http://", "https://")):
            result["invalid"] += 1
            continue
        identity = _source_identity(url)
        if identity in seen or identity in existing:
            result["duplicates"] += 1
            continue
        check = test_source_url(url)
        if not check["ok"]:
            result["invalid"] += 1
            continue
        canonical_url = check.get("canonical_url") or check["url"]
        canonical_identity = _source_identity(canonical_url)
        if canonical_identity in seen or canonical_identity in existing:
            result["duplicates"] += 1
            continue
        seen.update({identity, canonical_identity})
        persisted_test = {
            "status": check.get("status"), "url": check.get("url"),
            "http_status": check.get("http_status"), "is_rss": bool(check.get("is_rss")),
            "needs_playwright": bool(check.get("needs_playwright")),
            "extractable": bool(check.get("extractable")), "extractor": check.get("extractor"),
            "recent_items": [
                {"title": str(item.get("title") or "")[:240], "published": str(item.get("published") or "")[:100]}
                for item in (check.get("recent_items") or [])[:3]
            ],
        }
        created = create_collection_source(
            name=name[:200] or result["domain"], source_type="rss" if check.get("is_rss") else source_type,
            url=canonical_url, collection_mode="rss" if check.get("is_rss") else "http",
            subject_type="organization" if organization_id else "", subject_id=str(organization_id or ""),
            owner=owner, compliance_note=json.dumps(
                {"organization": organization_name, "method": method, "test": persisted_test}, ensure_ascii=False
            ), is_enabled=False, db_path=db_path,
        )
        with db_connection(db_path) as conn:
            conn.execute(
                "UPDATE v04g_monitoring_sources SET health_status='candidate',note=? WHERE id=?",
                (f"R7.1 DISCOVERED|{method}|{result['domain']}", created["id"]),
            )
        result["rss"] += int(check.get("is_rss", False))
        result["sitemap"] += int(method == "Sitemap发现")
        result["newsroom"] += int(method == "官网导航发现")
        result["created"] += 1
        result["candidates"].append({**created, "discovery_method": method, "test": check})
        if result["created"] >= 8:
            break
    return result


def create_job(source_id: int, trigger_type: str = "manual", operator: str = "", db_path: str | Path | None = None, *, force: bool = False) -> dict[str, Any]:
    ensure_schema(db_path)
    ts = now()
    with db_connection(db_path) as conn:
        source = conn.execute("SELECT * FROM v04g_monitoring_sources WHERE id=?", (source_id,)).fetchone()
        if not source:
            raise ValueError("source_not_found")
        running = conn.execute(
            "SELECT * FROM v04g_monitoring_runs WHERE monitoring_source_id=? AND status IN ('pending','running') ORDER BY id DESC LIMIT 1",
            (source_id,),
        ).fetchone()
        if running and not force:
            raise RuntimeError("duplicate_running_job")
        cur = conn.execute(
            """
            INSERT INTO v04g_monitoring_runs(
                run_no, monitoring_source_id, status, started_at, created_at, job_type,
                trigger_type, priority, scheduled_at, max_retries, operator_username
            ) VALUES (?, ?, 'pending', ?, ?, 'collection', ?, 'medium', ?, ?, ?)
            """,
            (_next_no(conn, "JOB"), source_id, ts, ts, trigger_type, ts, int(source["max_retries"] or 2), operator or None),
        )
        return dict(conn.execute("SELECT * FROM v04g_monitoring_runs WHERE id=?", (cur.lastrowid,)).fetchone())


def retry_job(job_id: int, *, operator: str = "", db_path: str | Path | None = None) -> dict[str, Any]:
    """Create a derived retry job so the original run remains an immutable execution record."""
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        original = conn.execute("SELECT * FROM v04g_monitoring_runs WHERE id=?", (job_id,)).fetchone()
        if not original:
            raise ValueError("job_not_found")
        has_parent_column = "parent_job_id" in {str(item[1]) for item in conn.execute("PRAGMA table_info(v04g_monitoring_runs)")}
    derived = create_job(int(original["monitoring_source_id"]), trigger_type="retry", operator=operator, db_path=db_path, force=True)
    if has_parent_column:
        with db_connection(db_path) as conn:
            conn.execute("UPDATE v04g_monitoring_runs SET parent_job_id=?,attempt_count=? WHERE id=?", (job_id, int(original["attempt_count"] or 0) + 1, derived["id"]))
            derived = dict(conn.execute("SELECT * FROM v04g_monitoring_runs WHERE id=?", (derived["id"],)).fetchone())
    return derived


def _acquire_lock(conn: sqlite3.Connection, source_id: int, run_id: int) -> str | None:
    token = secrets.token_hex(12)
    ts = now()
    expires = (datetime.now() + timedelta(minutes=30)).replace(microsecond=0).isoformat()
    existing = conn.execute(
        "SELECT * FROM v05f_collection_job_locks WHERE monitoring_source_id=? AND status='locked' AND expires_at>?",
        (source_id, ts),
    ).fetchone()
    if existing:
        return None
    conn.execute("DELETE FROM v05f_collection_job_locks WHERE monitoring_source_id=? AND expires_at<=?", (source_id, ts))
    conn.execute(
        """
        INSERT OR REPLACE INTO v05f_collection_job_locks(
            monitoring_source_id, monitoring_run_id, lock_token, status, acquired_at, expires_at
        ) VALUES (?, ?, ?, 'locked', ?, ?)
        """,
        (source_id, run_id, token, ts, expires),
    )
    return token


def _release_lock(conn: sqlite3.Connection, source_id: int, token: str) -> None:
    conn.execute(
        "UPDATE v05f_collection_job_locks SET status='released', released_at=? WHERE monitoring_source_id=? AND lock_token=?",
        (now(), source_id, token),
    )


def _parse_rss(xml_text: str, source_url: str, max_links: int = 50) -> list[ExtractedPage]:
    parsed = feedparser.parse(xml_text)
    if not parsed.entries:
        raise RuntimeError("PARSE_FAILED") from getattr(parsed, "bozo_exception", None)
    entries: list[ExtractedPage] = []
    for entry in parsed.entries[:max_links]:
        title = str(entry.get("title") or "untitled")
        guid = str(entry.get("id") or entry.get("guid") or "")
        link = str(entry.get("link") or guid or source_url)
        content = entry.get("content") or []
        content_value = content[0].get("value", "") if content and isinstance(content[0], dict) else ""
        summary = str(entry.get("summary") or entry.get("description") or content_value or title)
        html_text = f"<html><head><title>{html.escape(title)}</title></head><body><article>{summary or title}</article></body></html>"
        page = extract_html(html_text, link)
        parsed_time = entry.get("published_parsed") or entry.get("updated_parsed")
        if parsed_time:
            page.published_at = datetime(*parsed_time[:6], tzinfo=timezone.utc).isoformat()
        else:
            page.published_at = str(entry.get("published") or entry.get("updated") or "")[:80]
        page.author = str(entry.get("author") or "")[:200]
        page.description = BeautifulSoup(summary, "html.parser").get_text(" ", strip=True)[:500]
        page.guid = guid[:500]
        entries.append(page)
    return entries


def _record_link(conn: sqlite3.Connection, source_id: int, run_id: int, link: dict[str, str], parent_snapshot_id: int | None = None) -> int:
    ts = now()
    existing = conn.execute(
        "SELECT id FROM v05f_discovered_links WHERE monitoring_source_id=? AND normalized_url=?",
        (source_id, link["normalized_url"]),
    ).fetchone()
    if existing:
        return int(existing["id"])
    cur = conn.execute(
        """
        INSERT INTO v05f_discovered_links(
            link_no, monitoring_source_id, monitoring_run_id, parent_snapshot_id, source_url,
            normalized_url, canonical_url, link_text, title_candidate, published_at_candidate,
            status, depth, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'new', 1, ?, ?)
        """,
        (_next_no(conn, "LNK"), source_id, run_id, parent_snapshot_id, link["url"], link["normalized_url"], link.get("canonical_url", ""), link.get("link_text", ""), link.get("title_candidate", ""), link.get("published_at_candidate", ""), ts, ts),
    )
    return int(cur.lastrowid)


def _store_page(conn: sqlite3.Connection, source: sqlite3.Row, run_id: int, page: ExtractedPage, discovered_link_id: int | None = None) -> dict[str, Any]:
    ts = now()
    previous = conn.execute(
        "SELECT * FROM v05f_collection_items WHERE monitoring_source_id=? AND normalized_url=? ORDER BY id DESC LIMIT 1",
        (source["id"], page.normalized_url),
    ).fetchone()
    same_hash = conn.execute(
        "SELECT * FROM v05f_collection_items WHERE content_hash=? ORDER BY id ASC LIMIT 1",
        (page.content_hash,),
    ).fetchone()
    dedup_status = "new"
    change_status = "new"
    processing_status = "queued"
    duplicate_of = None
    if previous and previous["content_hash"] == page.content_hash:
        dedup_status = "unchanged"
        change_status = "unchanged"
        processing_status = "ignored"
        duplicate_of = previous["id"]
    elif same_hash:
        dedup_status = "duplicate"
        change_status = "unchanged"
        processing_status = "ignored"
        duplicate_of = same_hash["id"]
    elif previous:
        dedup_status = "changed"
        change_status = "changed"
        processing_status = "queued"

    quality = assess_content_quality(
        title=page.title,
        text=page.text,
        source_url=page.url,
        published_at=page.published_at,
        language=page.language,
        duplicate_score=0.99 if dedup_status in {"duplicate", "unchanged"} else 0.0,
        http_status=page.http_status,
    )
    if not quality.accepted_for_analysis and processing_status == "queued":
        processing_status = "ignored"

    old_snapshot = conn.execute(
        "SELECT * FROM v04g_source_snapshots WHERE monitoring_source_id=? AND normalized_url=? ORDER BY id DESC LIMIT 1",
        (source["id"], page.normalized_url),
    ).fetchone()
    same_content_snapshot = conn.execute(
        "SELECT * FROM v04g_source_snapshots WHERE monitoring_source_id=? AND content_hash=? ORDER BY id DESC LIMIT 1",
        (source["id"], page.content_hash),
    ).fetchone()
    snapshot_id = old_snapshot["id"] if old_snapshot and old_snapshot["content_hash"] == page.content_hash else (same_content_snapshot["id"] if same_content_snapshot else None)
    if not snapshot_id:
        cur = conn.execute(
            """
            INSERT INTO v04g_source_snapshots(
                snapshot_no, monitoring_source_id, monitoring_run_id, page_title, url, captured_at,
                raw_content, cleaned_text, content_hash, metadata_json, created_at,
                original_url, normalized_url, canonical_url, published_at, http_status,
                response_headers_json, raw_html, cleaned_html, structure_hash, encoding,
                content_type, content_length, is_truncated, is_changed, previous_snapshot_id, diff_summary
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                _next_no(conn, "SNP"), source["id"], run_id, page.title, page.url, ts,
                page.text[:12000], page.text[:80000], page.content_hash,
                _json({"description": page.description, "author": page.author, "warnings": page.warnings, "page_structure": page.page_structure, "guid": page.guid, "extractor": page.extractor, "source": source["name"]}),
                ts, page.url, page.normalized_url, page.canonical_url, page.published_at, page.http_status,
                "{}", page.raw_html if int(source["save_raw_html"] or 0) else "", page.cleaned_html,
                page.structure_hash, "utf-8", page.content_type, len(page.text), int("content_truncated" in page.warnings),
                int(change_status == "changed"), old_snapshot["id"] if old_snapshot else None,
                "content changed" if change_status == "changed" else "",
            ),
        )
        snapshot_id = int(cur.lastrowid)

    snapshot_columns = {row[1] for row in conn.execute("PRAGMA table_info(v04g_source_snapshots)")}
    if "quality_status" in snapshot_columns:
        conn.execute(
            "UPDATE v04g_source_snapshots SET quality_status=?,quality_json=? WHERE id=?",
            (quality.status, _json(quality.to_dict()), snapshot_id),
        )

    quality_result = check_content_quality(page.title or "", page.text or "", page.url)
    cur = conn.execute(
        """
        INSERT INTO v05f_collection_items(
            item_no, monitoring_source_id, monitoring_run_id, snapshot_id, discovered_link_id,
            title, original_url, normalized_url, canonical_url, published_at, captured_at,
            content_type, page_structure, language, dedup_status, change_status,
            processing_status, priority, subject_type_candidate, subject_id_candidate,
            content_hash, structure_hash, duplicate_of_item_id, warning_json, metadata_json,
            quality_status, quality_reason, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'medium', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            _next_no(conn, "COL"), source["id"], run_id, snapshot_id, discovered_link_id,
            page.title, page.url, page.normalized_url, page.canonical_url, page.published_at, ts,
            page.content_type, page.page_structure, page.language, dedup_status, change_status,
            processing_status, source["subject_type"], source["subject_id"], page.content_hash, page.structure_hash,
            duplicate_of, _json(page.warnings), _json({"summary": page.summary, "description": page.description, "author": page.author, "guid": page.guid, "extractor": page.extractor, "source": source["name"]}),
            quality_result["quality_status"], quality_result["quality_reason"], ts, ts,
        ),
    )
    item_id = int(cur.lastrowid)
    if duplicate_of:
        conn.execute(
            """
            INSERT OR IGNORE INTO v05f_content_duplicate_links(
                primary_item_id, duplicate_item_id, relation_type, similarity_score, reason, created_at
            ) VALUES (?, ?, ?, 100, ?, ?)
            """,
            (int(duplicate_of), item_id, "same_url" if previous else "duplicate", dedup_status, ts),
        )
    return {"item_id": item_id, "snapshot_id": snapshot_id, "dedup_status": dedup_status, "change_status": change_status, "processing_status": processing_status, "quality_status": quality_result["quality_status"], "quality_reason": quality_result["quality_reason"]}


def _source_allowed_domains(source: sqlite3.Row) -> list[str]:
    domains = [d.strip() for d in str(source["allowed_domains"] or "").split(",") if d.strip()]
    host = urlparse(source["url"]).hostname
    if host:
        domains.append(host)
    return domains


def process_job(run_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    started = time.perf_counter()
    parser_name = "unknown"
    extractor_names: set[str] = set()
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        run = conn.execute("SELECT * FROM v04g_monitoring_runs WHERE id=?", (run_id,)).fetchone()
        if not run:
            raise ValueError("job_not_found")
        source = conn.execute("SELECT * FROM v04g_monitoring_sources WHERE id=?", (run["monitoring_source_id"],)).fetchone()
        if not source or not source["is_enabled"] or source["auto_paused"]:
            conn.execute("UPDATE v04g_monitoring_runs SET status='skipped', finished_at=?, error_type='source_disabled' WHERE id=?", (now(), run_id))
            return {"run_id": run_id, "status": "skipped"}
        token = _acquire_lock(conn, source["id"], run_id)
        if not token:
            conn.execute("UPDATE v04g_monitoring_runs SET status='skipped', finished_at=?, error_type='duplicate_running_job' WHERE id=?", (now(), run_id))
            return {"run_id": run_id, "status": "skipped", "error_type": "duplicate_running_job"}
        try:
            conn.execute("UPDATE v04g_monitoring_runs SET status='running', started_at=?, attempt_count=attempt_count+1 WHERE id=?", (now(), run_id))
            source_type = source["collection_source_type"] or source["source_type"] or "webpage"
            mode = source["collection_mode"] or "auto"
            if mode == "auto":
                mode = "rss" if source_type == "rss" else "api" if source_type == "api" else "http"

            robots = check_robots(source["url"])
            conn.execute(
                "UPDATE v04g_monitoring_sources SET robots_status=?, robots_checked_at=?, robots_summary=? WHERE id=?",
                (robots.get("status"), now(), robots.get("summary"), source["id"]),
            )
            if not robots.get("allowed", True):
                raise PermissionError("robots_denied")

            pages: list[tuple[ExtractedPage, int | None]] = []
            discovered_count = 0
            source_columns = set(source.keys())
            conditional: dict[str, str] = {}
            if "last_etag" in source_columns and source["last_etag"]:
                conditional["If-None-Match"] = str(source["last_etag"])
            if "last_modified_header" in source_columns and source["last_modified_header"]:
                conditional["If-Modified-Since"] = str(source["last_modified_header"])
            if mode == "playwright":
                adapter = PlaywrightAdapter()
                try:
                    dynamic_result = adapter.fetch(
                        source["url"],
                        dynamic=True,
                        timeout_ms=int(source["request_timeout_seconds"] or 15) * 1000,
                        wait_selector=str(source["wait_selector"] or "") if "wait_selector" in source_columns else "",
                    )
                except PlaywrightUnavailable as exc:
                    raise RuntimeError("parser_or_collector_unavailable") from exc
                except PlaywrightCollectionError as exc:
                    raise RuntimeError(exc.code) from exc
                raw, http_status, content_type, headers = dynamic_result.html, 200, "text/html; charset=utf-8", {}
            else:
                raw, http_status, content_type, headers = _http_get(
                    source["url"],
                    int(source["request_timeout_seconds"] or 15),
                    conditional_headers=conditional,
                    retries=2,
                )
            if http_status == 304:
                conn.execute(
                    "UPDATE v04g_monitoring_runs SET status='unchanged',finished_at=? WHERE id=?",
                    (now(), run_id),
                )
                conn.execute(
                    "UPDATE v04g_monitoring_sources SET last_checked_at=?,updated_at=? WHERE id=?",
                    (now(), now(), source["id"]),
                )
                _release_lock(conn, source["id"], token)
                return {"run_id": run_id, "status": "unchanged", "not_modified": True, "result_code": "SUCCESS"}
            if "last_etag" in source_columns:
                conn.execute(
                    "UPDATE v04g_monitoring_sources SET last_etag=?,last_modified_header=? WHERE id=?",
                    (headers.get("etag"), headers.get("last-modified"), source["id"]),
                )
            if source_type == "rss" or "xml" in content_type or "<rss" in raw[:200].lower() or "<feed" in raw[:200].lower():
                parser_name = "feedparser"
                for feed_page in _parse_rss(raw, source["url"], int(source["max_links"] or 20)):
                    link = {
                        "url": feed_page.url,
                        "normalized_url": feed_page.normalized_url,
                        "link_text": feed_page.title,
                        "title_candidate": feed_page.title,
                        "published_at_candidate": feed_page.published_at,
                    }
                    link_id = _record_link(conn, source["id"], run_id, link)
                    discovered_count += 1
                    if source["crawl_detail_pages"] and feed_page.url != source["url"]:
                        try:
                            interval = float(source["request_interval_seconds"] or 1.0) if "request_interval_seconds" in source_columns else float(source["min_interval_seconds"] or 0)
                            time.sleep(max(0.0, min(interval, 10.0)))
                            detail_raw, detail_status, detail_type, _ = _http_get(
                                feed_page.url, int(source["request_timeout_seconds"] or 15), retries=2
                            )
                            feed_page = extract_html(detail_raw, feed_page.url)
                            feed_page.http_status = detail_status
                            feed_page.content_type = detail_type
                        except Exception:
                            conn.execute(
                                "UPDATE v05f_discovered_links SET status='failed',reason=?,updated_at=? WHERE id=?",
                                ("detail_fetch_failed", now(), link_id),
                            )
                    pages.append((feed_page, link_id))
            elif source_type == "api" or "json" in content_type:
                parser_name = "json"
                payload = json.loads(raw)
                records = payload if isinstance(payload, list) else payload.get("data") or payload.get("items") or payload.get("results") or []
                for record in records[: int(source["max_links"] or 20)]:
                    if not isinstance(record, dict):
                        continue
                    title = str(record.get("title") or record.get("name") or record.get("headline") or "api item")
                    link = str(record.get("url") or record.get("link") or source["url"])
                    text = str(record.get("summary") or record.get("description") or record.get("content") or title)
                    pages.append((extract_html(f"<html><head><title>{html.escape(title)}</title></head><body><article>{html.escape(text)}</article></body></html>", link), None))
            elif source_type == "manual_url_list":
                parser_name = "manual_url_list"
                for line in raw.splitlines()[: int(source["max_links"] or 20)]:
                    line = line.strip()
                    if not line:
                        continue
                    link = {"url": line, "normalized_url": normalize_url(line), "link_text": line, "title_candidate": line}
                    _record_link(conn, source["id"], run_id, link)
                    discovered_count += 1
            else:
                parser_name = "html"
                page = extract_html(raw, source["url"])
                page.http_status = http_status
                page.content_type = content_type
                pages.append((page, None))
                if source_type == "list_page":
                    links = discover_links(raw, source["url"], _source_allowed_domains(source), int(source["max_links"] or 20))
                    for link in links:
                        link_id = _record_link(conn, source["id"], run_id, link)
                        discovered_count += 1
                        if source["crawl_detail_pages"]:
                            try:
                                time.sleep(min(1, int(source["min_interval_seconds"] or 0)))
                                detail_raw, detail_status, detail_type, _ = _http_get(link["url"], int(source["request_timeout_seconds"] or 15))
                                detail = extract_html(detail_raw, link["url"])
                                detail.http_status = detail_status
                                detail.content_type = detail_type
                                pages.append((detail, link_id))
                            except Exception:
                                conn.execute("UPDATE v05f_discovered_links SET status='failed', reason=?, updated_at=? WHERE id=?", ("fetch_failed", now(), link_id))

            counts = {"new": 0, "duplicate": 0, "changed": 0, "failed": 0, "skipped": 0, "queued": 0, "snapshots": 0}
            for page, link_id in pages:
                extractor_names.add(page.extractor)
                stored = _store_page(conn, source, run_id, page, link_id)
                counts["snapshots"] += 1
                if stored["dedup_status"] in {"duplicate", "unchanged"}:
                    counts["duplicate"] += 1
                elif stored["dedup_status"] == "changed":
                    counts["changed"] += 1
                else:
                    counts["new"] += 1
                if stored["processing_status"] == "queued":
                    counts["queued"] += 1
                if link_id:
                    conn.execute("UPDATE v05f_discovered_links SET status='fetched', updated_at=? WHERE id=?", (now(), link_id))

            status = "unchanged" if counts["new"] == 0 and counts["changed"] == 0 and counts["duplicate"] > 0 else "success"
            if counts["failed"] and (counts["new"] or counts["changed"]):
                status = "partial"
            conn.execute(
                """
                UPDATE v04g_monitoring_runs
                SET status=?, finished_at=?, changed=?, discovered_link_count=?, fetched_success_count=?,
                    new_content_count=?, duplicate_content_count=?, changed_content_count=?,
                    failed_content_count=?, skipped_content_count=?, snapshot_count=?, queued_item_count=?,
                    created_snapshot_id=(SELECT snapshot_id FROM v05f_collection_items WHERE monitoring_run_id=? ORDER BY id DESC LIMIT 1),
                    created_proposal_count=0
                WHERE id=?
                """,
                (status, now(), int(counts["new"] > 0 or counts["changed"] > 0), discovered_count, len(pages), counts["new"], counts["duplicate"], counts["changed"], counts["failed"], counts["skipped"], counts["snapshots"], counts["queued"], run_id, run_id),
            )
            conn.execute(
                """
                UPDATE v04g_monitoring_sources
                SET last_checked_at=?, last_success_at=?, last_changed_at=CASE WHEN ? THEN ? ELSE last_changed_at END,
                    consecutive_failures=0, updated_at=?
                WHERE id=?
                """,
                (now(), now(), int(counts["new"] > 0 or counts["changed"] > 0), now(), now(), source["id"]),
            )
            if "health_status" in source.keys():
                conn.execute("UPDATE v04g_monitoring_sources SET health_status='healthy' WHERE id=?", (source["id"],))
            _release_lock(conn, source["id"], token)
            empty_count = sum("EXTRACTION_EMPTY" in page.warnings for page, _ in pages)
            result_code = (
                "EXTRACTION_EMPTY"
                if pages and empty_count == len(pages)
                else "DUPLICATE"
                if counts["duplicate"] and not counts["new"] and not counts["changed"]
                else "SUCCESS"
            )
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            _logger.info(
                "collection url=%s parser=%s extractor=%s result=%s elapsed_ms=%s",
                source["url"],
                parser_name,
                ",".join(sorted(extractor_names)) or "none",
                result_code,
                elapsed_ms,
            )
            return {
                "run_id": run_id,
                "status": status,
                "result_code": result_code,
                **counts,
                "discovered": discovered_count,
            }
        except Exception as exc:
            raw_error = getattr(exc, "args", [exc.__class__.__name__])[0] or exc.__class__.__name__
            if isinstance(exc, (httpx.HTTPError, httpx.TimeoutException)) or str(raw_error) == "FETCH_FAILED":
                error_type = "FETCH_FAILED"
            elif isinstance(exc, json.JSONDecodeError) or str(raw_error) == "PARSE_FAILED":
                error_type = "PARSE_FAILED"
            else:
                error_type = str(raw_error)
            failures = int(source["consecutive_failures"] or 0) + 1
            auto_paused = failures >= 3
            conn.execute(
                """
                UPDATE v04g_monitoring_runs
                SET status='failed', finished_at=?, error_type=?, error_message=?
                WHERE id=?
                """,
                (now(), str(error_type)[:80], str(exc)[:800], run_id),
            )
            conn.execute(
                """
                UPDATE v04g_monitoring_sources
                SET last_checked_at=?, last_error_at=?, consecutive_failures=?,
                    auto_paused=?, last_pause_reason=CASE WHEN ? THEN ? ELSE last_pause_reason END,
                    updated_at=?
                WHERE id=?
                """,
                (now(), now(), failures, int(auto_paused), int(auto_paused), str(error_type)[:200], now(), source["id"]),
            )
            if "health_status" in source.keys():
                conn.execute("UPDATE v04g_monitoring_sources SET health_status=? WHERE id=?", ("paused" if auto_paused else "degraded", source["id"] ))
            _release_lock(conn, source["id"], token)
            elapsed_ms = round((time.perf_counter() - started) * 1000)
            _logger.error(
                "collection url=%s parser=%s extractor=%s result=%s elapsed_ms=%s error_type=%s",
                source["url"],
                parser_name,
                ",".join(sorted(extractor_names)) or "none",
                error_type,
                elapsed_ms,
                error_type,
            )
            return {
                "run_id": run_id,
                "status": "failed",
                "result_code": str(error_type),
                "error_type": str(error_type),
                "error": str(exc)[:800],
            }


def run_worker(*, once: bool = True, job_id: int | None = None, source_id: int | None = None, due_only: bool = False, limit: int = 20, db_path: str | Path | None = None, operator: str = "worker") -> dict[str, Any]:
    ensure_schema(db_path)
    processed: list[dict[str, Any]] = []
    with db_connection(db_path) as conn:
        if job_id:
            jobs = [conn.execute("SELECT id FROM v04g_monitoring_runs WHERE id=?", (job_id,)).fetchone()]
        elif source_id:
            jobs = [create_job(source_id, trigger_type="command", operator=operator, db_path=db_path)]
        else:
            where = "status='pending' AND job_type='collection'"
            if due_only:
                where += " AND (scheduled_at IS NULL OR scheduled_at<=?)"
                params: list[Any] = [now(), limit]
            else:
                params = [limit]
            jobs = [dict(r) for r in conn.execute(f"SELECT id FROM v04g_monitoring_runs WHERE {where} ORDER BY scheduled_at, id LIMIT ?", params).fetchall()]
    for job in jobs:
        if not job:
            continue
        processed.append(process_job(int(job["id"]), db_path=db_path))
        if once:
            break
    return {"processed": len(processed), "results": processed}


def list_jobs(db_path: str | Path | None = None, page: int = 1, page_size: int = 20, status: str = "") -> tuple[list[dict[str, Any]], int]:
    ensure_schema(db_path)
    clauses = ["COALESCE(job_type,'collection')='collection'"]
    params: list[Any] = []
    if status:
        clauses.append("r.status=?")
        params.append(status)
    where = " AND ".join(clauses)
    offset = (max(1, page) - 1) * page_size
    with db_connection(db_path) as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM v04g_monitoring_runs r WHERE {where}", params).fetchone()[0])
        rows = [dict(r) for r in conn.execute(
            f"""
            SELECT r.*, s.name AS source_name, s.source_no
            FROM v04g_monitoring_runs r JOIN v04g_monitoring_sources s ON s.id=r.monitoring_source_id
            WHERE {where} ORDER BY r.id DESC LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()]
        rows = [_decorate_job(row, conn) for row in rows]
    return rows, total


def list_items(db_path: str | Path | None = None, page: int = 1, page_size: int = 20, processing_status: str = "", dedup_status: str = "") -> tuple[list[dict[str, Any]], int]:
    ensure_schema(db_path)
    clauses = ["1=1"]
    params: list[Any] = []
    if processing_status:
        clauses.append("i.processing_status=?")
        params.append(processing_status)
    if dedup_status:
        clauses.append("i.dedup_status=?")
        params.append(dedup_status)
    where = " AND ".join(clauses)
    offset = (max(1, page) - 1) * page_size
    with db_connection(db_path) as conn:
        total = int(conn.execute(f"SELECT COUNT(*) FROM v05f_collection_items i WHERE {where}", params).fetchone()[0])
        rows = [dict(r) for r in conn.execute(
            f"""
            SELECT i.id, i.item_no, i.title, i.normalized_url, i.published_at, i.captured_at,
                   i.page_structure, i.dedup_status, i.change_status, i.processing_status,
                   i.priority, i.snapshot_id, i.content_hash, s.name AS source_name, s.source_no,
                   COALESCE(sn.is_pilot,0) AS is_pilot, sn.pilot_batch_id
            FROM v05f_collection_items i JOIN v04g_monitoring_sources s ON s.id=i.monitoring_source_id
            LEFT JOIN v04g_source_snapshots sn ON sn.id=i.snapshot_id
            WHERE {where} ORDER BY i.id DESC LIMIT ? OFFSET ?
            """,
            [*params, page_size, offset],
        ).fetchall()]
        rows = [_decorate_item(row, conn) for row in rows]
    return rows, total


def queue_item(item_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v05f_collection_items WHERE id=?", (item_id,)).fetchone()
        if not row:
            raise ValueError("item_not_found")
        if row["dedup_status"] in {"duplicate", "unchanged"}:
            conn.execute("UPDATE v05f_collection_items SET processing_status='ignored', updated_at=? WHERE id=?", (now(), item_id))
        else:
            conn.execute("UPDATE v05f_collection_items SET processing_status='queued', updated_at=? WHERE id=?", (now(), item_id))
        return dict(conn.execute("SELECT * FROM v05f_collection_items WHERE id=?", (item_id,)).fetchone())


def cancel_job(job_id: int, db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM v04g_monitoring_runs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise ValueError("job_not_found")
        if row["status"] == "running":
            raise RuntimeError("running_job_cannot_be_cancelled")
        if row["status"] not in JOB_STATUSES:
            raise ValueError("invalid_job_status")
        conn.execute(
            "UPDATE v04g_monitoring_runs SET status='skipped', finished_at=?, error_type='cancelled' WHERE id=?",
            (now(), job_id),
        )
        return dict(conn.execute("SELECT * FROM v04g_monitoring_runs WHERE id=?", (job_id,)).fetchone())


def dashboard(db_path: str | Path | None = None) -> dict[str, Any]:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        counts = {
            "enabled_sources": conn.execute("SELECT COUNT(*) FROM v04g_monitoring_sources WHERE is_enabled=1 AND deactivated_at IS NULL").fetchone()[0],
            "due_sources": conn.execute("SELECT COUNT(*) FROM v04g_monitoring_sources WHERE is_enabled=1 AND deactivated_at IS NULL AND COALESCE(auto_paused,0)=0").fetchone()[0],
            "jobs_today": conn.execute("SELECT COUNT(*) FROM v04g_monitoring_runs WHERE date(created_at)=date('now','localtime') AND COALESCE(job_type,'collection')='collection'").fetchone()[0],
            "failed_jobs": conn.execute("SELECT COUNT(*) FROM v04g_monitoring_runs WHERE status='failed' AND COALESCE(job_type,'collection')='collection'").fetchone()[0],
            "new_items": conn.execute("SELECT COUNT(*) FROM v05f_collection_items WHERE dedup_status IN ('new','changed')").fetchone()[0],
            "queued_items": conn.execute("SELECT COUNT(*) FROM v05f_collection_items WHERE processing_status='queued'").fetchone()[0],
            "paused_sources": conn.execute("SELECT COUNT(*) FROM v04g_monitoring_sources WHERE COALESCE(auto_paused,0)=1").fetchone()[0],
        }
        latest_items = [dict(r) for r in conn.execute(
            """
            SELECT i.item_no, i.title, i.dedup_status, i.processing_status, i.captured_at, s.name AS source_name
            FROM v05f_collection_items i JOIN v04g_monitoring_sources s ON s.id=i.monitoring_source_id
            ORDER BY i.id DESC LIMIT 8
            """
        ).fetchall()]
        latest_jobs = [dict(r) for r in conn.execute(
            """
            SELECT r.run_no, r.status, r.new_content_count, r.changed_content_count, r.duplicate_content_count, r.created_at, s.name AS source_name
            FROM v04g_monitoring_runs r JOIN v04g_monitoring_sources s ON s.id=r.monitoring_source_id
            WHERE COALESCE(r.job_type,'collection')='collection'
            ORDER BY r.id DESC LIMIT 8
            """
        ).fetchall()]
    return {"counts": counts, "latest_items": latest_items, "latest_jobs": latest_jobs}


def snapshot_detail(snapshot_id: int, include_raw: bool = False, db_path: str | Path | None = None) -> dict[str, Any] | None:
    ensure_schema(db_path)
    with db_connection(db_path) as conn:
        row = conn.execute(
            """
            SELECT sn.*, s.name AS source_name
            FROM v04g_source_snapshots sn JOIN v04g_monitoring_sources s ON s.id=sn.monitoring_source_id
            WHERE sn.id=?
            """,
            (snapshot_id,),
        ).fetchone()
    if not row:
        return None
    data = dict(row)
    if not include_raw:
        data.pop("raw_html", None)
        data.pop("raw_content", None)
    return data
