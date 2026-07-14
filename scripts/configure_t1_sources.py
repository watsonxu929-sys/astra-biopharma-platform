from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.collection_service import create_collection_source, list_sources


def configure_t1_sources():
    sources = [
        {
            "name": "EMA News RSS",
            "source_type": "rss",
            "url": "https://www.ema.europa.eu/en/news.xml",
            "collection_mode": "rss",
            "allowed_domains": "ema.europa.eu",
            "max_links": 5,
            "crawl_detail_pages": True,
            "compliance_note": "P2.2已验证成功来源，EMA官方RSS Feed",
        },
        {
            "name": "FDA Press Announcements",
            "source_type": "list_page",
            "url": "https://www.fda.gov/news-events/fda-newsroom/press-announcements",
            "collection_mode": "http",
            "allowed_domains": "fda.gov",
            "max_links": 5,
            "crawl_detail_pages": True,
            "compliance_note": "P2.2已验证成功来源，FDA官方新闻发布页面",
        },
        {
            "name": "ClinicalTrials.gov Search",
            "source_type": "dynamic_page",
            "url": "https://clinicaltrials.gov/search?cond=biopharma",
            "collection_mode": "playwright",
            "allowed_domains": "clinicaltrials.gov",
            "max_links": 5,
            "crawl_detail_pages": False,
            "compliance_note": "P2.2已验证成功来源，需要Playwright动态渲染",
        },
    ]

    for source_config in sources:
        try:
            result = create_collection_source(**source_config)
            print(f"Created/Updated source: {result['source_no']} - {result['name']} (id={result['id']})")
        except Exception as e:
            print(f"Failed to create source {source_config['name']}: {e}")

    print("\n--- All sources ---")
    rows, total = list_sources(page=1, page_size=20)
    for row in rows:
        print(f"  {row['id']:2d} | {row['source_no']} | {row['name']:30s} | type={row['source_type']:12s} | enabled={row['is_enabled']} | freq={row['check_frequency']:6s}")


if __name__ == "__main__":
    configure_t1_sources()
