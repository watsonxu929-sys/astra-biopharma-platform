from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.v04c1_ingestion import ingest_payload  # noqa: E402


def main() -> int:
    payload = {
        "batch": {
            "source_name": "v0.4C-1演示来源",
            "source_type": "demo-json",
            "note": "用于验证新增、冲突、推测、重复来源与待确认关联",
        },
        "records": [
            {
                "external_key": "C1-DEMO-001",
                "title": "华辰生物完成B轮融资",
                "source_url": "https://example.com/demo/001",
                "source_grade": "B",
                "published_at": "2026-06-20",
                "subjects": [
                    {
                        "subject_type": "org",
                        "subject_id": "ORG-C1-001",
                        "subject_label": "华辰生物",
                        "fields": [
                            {"name": "融资轮次", "value": "B轮", "fact_level": "fact", "confidence": 0.95, "excerpt": "公司宣布完成B轮融资。"},
                            {"name": "融资金额", "value": "2亿元", "fact_level": "fact", "confidence": 0.85, "excerpt": "本轮融资金额约2亿元。"},
                            {"name": "员工人数", "value": "约120人", "fact_level": "inference", "confidence": 0.55, "excerpt": "根据公开招聘与团队页面估算。"},
                        ],
                    }
                ],
                "relations": [
                    {
                        "left_type": "person",
                        "left_id": "PER-C1-001",
                        "left_label": "李明",
                        "relation_type": "创始人",
                        "right_type": "org",
                        "right_id": "ORG-C1-001",
                        "right_label": "华辰生物",
                        "confidence": 0.82,
                        "basis": "报道将李明描述为华辰生物创始人。",
                    }
                ],
            },
            {
                "external_key": "C1-DEMO-002",
                "title": "行业媒体称华辰生物融资规模为1.8亿元",
                "source_url": "https://example.com/demo/002",
                "source_grade": "C",
                "published_at": "2026-06-21",
                "subject_type": "org",
                "subject_id": "ORG-C1-001",
                "subject_label": "华辰生物",
                "fields": [
                    {"name": "融资金额", "value": "1.8亿元", "fact_level": "fact", "confidence": 0.7, "excerpt": "行业媒体援引知情人士称融资规模为1.8亿元。"},
                    {"name": "融资轮次", "value": "B轮", "fact_level": "fact", "confidence": 0.8, "excerpt": "报道同样称其为B轮融资。"},
                ],
            },
            {
                "external_key": "C1-DEMO-003",
                "title": "未结构化原始线索",
                "source_url": "https://example.com/demo/003",
                "source_grade": "D",
                "excerpt": "只有原始文字，没有 fields 或 relations，应进入待结构化状态。",
            },
        ],
    }
    result = ingest_payload(payload, created_by="demo-seed")
    batch = result["batch"]
    print(f"[OK] 演示批次：{batch['batch_no']}")
    print(f"[INFO] 处理 {batch['processed_records']}，重复 {batch['duplicate_records']}，失败 {batch['failed_records']}")
    print("[NEXT] 打开 http://127.0.0.1:8000/review/intake")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
