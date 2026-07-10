from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.v04c_review import (  # noqa: E402
    create_pending_relation,
    create_review_item,
    register_claim,
)


def main() -> int:
    conflict = create_review_item(
        item_type="conflict",
        subject_type="org",
        subject_id="ORG-DEMO-0001",
        subject_label="示例生物科技有限公司",
        field_name="融资金额",
        current_value="1亿元",
        proposed_value="1.2亿元",
        fact_level="unknown",
        created_by="demo",
        evidence=[
            {
                "source_title": "企业新闻稿",
                "source_grade": "C",
                "source_value": "1亿元",
                "source_excerpt": "宣布完成亿元级融资。",
                "source_url": "https://example.com/company",
            },
            {
                "source_title": "投资机构公告",
                "source_grade": "A",
                "source_value": "1.2亿元",
                "source_excerpt": "本轮总额为人民币1.2亿元。",
                "source_url": "https://example.com/investor",
                "is_primary": True,
            },
        ],
    )
    relation = create_pending_relation(
        left_type="person",
        left_id="PER-DEMO-0001",
        left_label="张某",
        relation_type="创始人",
        right_type="org",
        right_id="ORG-DEMO-0001",
        right_label="示例生物科技有限公司",
        confidence=0.78,
        basis="两篇采访均称张某负责公司创立，但未找到工商或官网高管页确认。",
        source_url="https://example.com/interview",
    )
    claim = register_claim(
        subject_type="project",
        subject_id="PRJ-DEMO-0001",
        subject_label="示例候选药物A",
        predicate="临床阶段",
        object_value="II期",
        claim_type="inference",
        confidence=0.62,
        source_grade="C",
        source_url="https://example.com/pipeline",
        basis="管线图位置推测为II期，页面未给出明确文字。",
        created_by="demo",
    )
    print("[OK] 已写入演示数据：")
    print(" -", conflict["review_no"])
    print(" -", relation["relation_no"])
    print(" -", claim["claim_no"])
    print("打开：http://127.0.0.1:8000/review")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
