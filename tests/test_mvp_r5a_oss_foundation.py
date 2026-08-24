from __future__ import annotations

from difflib import SequenceMatcher
from pathlib import Path

import pytest

from app.core.content_extraction import extract_main_text
from app.core.similarity import similarity_ratio
from app.services import collection_scheduler
from app.services.collection_service import _parse_rss, collection_status_label, extract_html
from app.v04e_entity_resolution import compact_name, normalize_name


RSS_FIXTURE = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0"><channel><title>EMA News</title>
<item><title>Medicine update</title><link>https://example.test/news/1</link>
<guid>ema-news-1</guid><pubDate>Tue, 18 Aug 2026 09:30:00 +0200</pubDate>
<author>press@example.test</author>
<description><![CDATA[<p>European medicine safety update with sufficient article detail.</p>]]></description>
</item></channel></rss>"""

ATOM_FIXTURE = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Policy feed</title>
<entry><title>监管政策更新</title><id>tag:example.test,2026:2</id>
<link href="https://example.test/policy/2"/><updated>2026-08-18T10:30:00+08:00</updated>
<author><name>政策办公室</name></author>
<summary type="html">&lt;p&gt;监管政策正文摘要，包含足够的业务内容用于采集验证。&lt;/p&gt;</summary>
</entry></feed>"""


@pytest.mark.parametrize(
    ("kind", "body"),
    [
        ("新闻文章", "创新药临床研究取得进展，企业公布了完整的阶段数据和下一步计划。"),
        ("企业新闻", "公司宣布完成新一轮融资，将用于生物药研发平台和生产能力建设。"),
        ("政府网站", "主管部门发布产业扶持政策，明确申报条件、办理流程和材料要求。"),
        ("普通资讯站", "产业资讯梳理了本周项目合作、投融资与技术转移的主要动态。"),
        ("复杂页面", "复杂网页中的核心文章包含研发、注册、生产和商业合作等连续信息。"),
        ("大量导航", "正文应被准确识别，顶部导航和底部版权不应成为主要抽取内容。"),
        ("中文页面", "中文正文需要保持字符完整，不出现乱码、替换字符或异常空白。"),
        ("人物访谈", "访谈介绍了创始人的研发经历、团队建设和企业未来发展方向。"),
        ("项目公告", "项目公告列出合作范围、申报时间、联系人和后续评审安排。"),
        ("园区动态", "园区动态记录了企业落地、公共平台建设和产业服务活动情况。"),
    ],
)
def test_trafilatura_extracts_ten_representative_html_samples(kind: str, body: str) -> None:
    article = (body + "这是用于验证正文连续性的补充句子。") * 4
    html = f"""<html lang="zh-CN"><head><title>{kind}</title></head><body>
    <nav>JUNK_NAV_TOKEN 首页 产品 联系我们</nav>
    <main><article><h1>{kind}</h1><p>{article}</p></article></main>
    <footer>JUNK_FOOTER_TOKEN 版权所有</footer></body></html>"""
    text, method = extract_main_text(html)
    page = extract_html(html, f"https://example.test/{kind}")
    assert method == "trafilatura"
    assert body in text
    assert len(page.text) >= 100
    assert "JUNK_NAV_TOKEN" not in text
    assert "JUNK_FOOTER_TOKEN" not in text
    assert "\ufffd" not in text
    assert "EXTRACTION_EMPTY" not in page.warnings


@pytest.mark.parametrize("code", ["FETCH_FAILED", "PARSE_FAILED", "EXTRACTION_EMPTY", "DUPLICATE", "SUCCESS"])
def test_collection_result_codes_have_business_labels(code: str) -> None:
    assert collection_status_label(code) != code


def test_feedparser_preserves_rss_business_fields() -> None:
    page = _parse_rss(RSS_FIXTURE, "https://example.test/news.xml")[0]
    assert page.title == "Medicine update"
    assert page.url == "https://example.test/news/1"
    assert page.guid == "ema-news-1"
    assert page.author == "press@example.test"
    assert page.description.startswith("European medicine")
    assert page.published_at == "2026-08-18T07:30:00+00:00"
    assert page.normalized_url == "https://example.test/news/1"


def test_feedparser_supports_atom_and_malformed_feed_result() -> None:
    page = _parse_rss(ATOM_FIXTURE, "https://example.test/atom.xml")[0]
    assert page.title == "监管政策更新"
    assert page.url == "https://example.test/policy/2"
    assert page.guid == "tag:example.test,2026:2"
    assert page.author == "政策办公室"
    assert "监管政策正文摘要" in page.description
    with pytest.raises(RuntimeError, match="PARSE_FAILED"):
        _parse_rss("<not-a-feed>", "https://example.test/broken.xml")
    with pytest.raises(RuntimeError, match="PARSE_FAILED"):
        _parse_rss("<rss><channel></channel></rss>", "https://example.test/empty.xml")


@pytest.mark.parametrize(
    ("left", "right"),
    [
        ("XX生物医药有限公司", "XX生物"),
        ("上海XX生物医药有限公司", "上海XX生物"),
        ("张三", "张 三"),
        ("Q-BAY Pharma", "q bay pharma"),
        ("创新药（上海）", "创新药-上海"),
    ],
)
def test_rapidfuzz_keeps_normalized_similarity_semantics(left: str, right: str) -> None:
    normalized_left = normalize_name(left)
    normalized_right = normalize_name(right)
    old_score = SequenceMatcher(None, normalized_left, normalized_right).ratio()
    new_score = similarity_ratio(normalized_left, normalized_right)
    assert 0.0 <= new_score <= 1.0
    assert abs(new_score - old_score) <= 0.15


def test_rapidfuzz_remains_a_score_helper_not_an_auto_merger() -> None:
    assert compact_name("上海XX生物医药有限公司", "organization") == "上海xx"
    similar = similarity_ratio(
        compact_name("上海XX生物医药有限公司", "organization"),
        compact_name("上海XX生物科技有限公司", "organization"),
    )
    different = similarity_ratio(
        compact_name("上海XX生物医药有限公司", "organization"),
        compact_name("北京YY医疗器械有限公司", "organization"),
    )
    assert similar > different
    assert isinstance(similar, float)


def test_scheduler_manual_and_timed_paths_use_one_callable(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    calls: list[tuple[str, str]] = []

    def fake_schedule(**kwargs):
        calls.append(("schedule", kwargs["operator"]))
        return {"created": 1, "skipped": 0, "jobs": []}

    def fake_worker(**kwargs):
        calls.append(("worker", kwargs["operator"]))
        return {"processed": 1, "processing_jobs_created": 0, "results": []}

    monkeypatch.setattr(collection_scheduler, "schedule_due_collection_jobs", fake_schedule)
    monkeypatch.setattr(collection_scheduler, "run_collection_worker_with_cascade", fake_worker)
    test_db = tmp_path / "scheduler.db"
    result = collection_scheduler.run_collection_cycle(
        limit=2,
        operator="acceptance",
        db_path=test_db,
    )
    assert result["scheduled"]["created"] == 1
    assert result["worker"]["processed"] == 1
    assert calls == [("schedule", "acceptance"), ("worker", "acceptance")]

    monkeypatch.setattr(
        collection_scheduler,
        "run_collection_cycle",
        lambda **kwargs: {"same_callable": True, "operator": kwargs["operator"]},
    )
    assert collection_scheduler.run_scheduler_once(test_db) == {
        "same_callable": True,
        "operator": "manual-run",
    }


def test_scheduler_refuses_implicit_database_under_pytest() -> None:
    assert collection_scheduler.start_scheduler(force=True) is False
    assert collection_scheduler.is_scheduler_running() is False


def test_scheduler_refuses_formal_database_under_pytest() -> None:
    formal_db = Path(__file__).resolve().parents[1] / "data" / "app.db"
    assert collection_scheduler.start_scheduler(force=True, db_path=formal_db) is False
    assert collection_scheduler.is_scheduler_running() is False
    with pytest.raises(RuntimeError, match="explicit_non_formal_database"):
        collection_scheduler.run_collection_cycle(db_path=formal_db)


def test_apscheduler_registers_only_collection_cycle(tmp_path: Path) -> None:
    try:
        assert collection_scheduler.start_scheduler(force=True, db_path=tmp_path / "scheduler.db") is True
        info = collection_scheduler.get_scheduler_info()
        assert [job["id"] for job in info["jobs"]] == ["collection_cycle"]
    finally:
        collection_scheduler.stop_scheduler()


def test_removed_custom_foundations_do_not_return() -> None:
    root = Path(__file__).resolve().parents[1]
    production = "\n".join(
        (root / relative).read_text(encoding="utf-8")
        for relative in (
            "app/services/collection_service.py",
            "app/web_extractor.py",
            "app/services/fact_deduplication_service.py",
            "app/services/research/fusion_service.py",
            "app/v04e_entity_resolution.py",
        )
    )
    assert "xml.etree" not in production
    assert "SequenceMatcher" not in production
    assert "_best_content_node" not in production
    assert "_clean_html" not in production
    task_registry = (root / "app/services/tasks/task_registry.py").read_text(encoding="utf-8")
    assert "run_collection_cycle" in task_registry
    assert "schedule_due_collection_jobs" not in task_registry
