from __future__ import annotations

import tempfile
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from app.v04c_review import (  # noqa: E402
    add_evidence,
    batch_resolve,
    create_pending_relation,
    create_review_item,
    dashboard_data,
    decide_pending_relation,
    ensure_v04c_schema,
    register_claim,
    review_detail,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v04c_verify_", ignore_cleanup_errors=True) as temp_dir:
        db_path = Path(temp_dir) / "test.db"
        ensure_v04c_schema(db_path, allow_migration=True)
        check(db_path.exists(), "可以独立创建 v0.4C 数据表")

        item = create_review_item(
            item_type="conflict",
            subject_type="org",
            subject_id="ORG-T-001",
            subject_label="测试企业",
            field_name="融资金额",
            current_value="1000万元",
            proposed_value="1200万元",
            fact_level="unknown",
            evidence=[{"source_title": "来源A", "source_grade": "A", "source_value": "1200万元"}],
            db_path=db_path,
        )
        check(item["priority"] == "high", "高风险字段会自动提升优先级")

        duplicate = create_review_item(
            item_type="conflict",
            subject_type="org",
            subject_id="ORG-T-001",
            subject_label="测试企业",
            field_name="融资金额",
            current_value="1000万元",
            proposed_value="1200万元",
            fact_level="unknown",
            db_path=db_path,
        )
        check(duplicate["id"] == item["id"], "相同未结审核项不会重复入队")

        add_evidence(item["id"], {"source_title": "来源B", "source_grade": "B", "source_value": "1000万元"}, db_path=db_path)
        detail = review_detail(item["id"], db_path)
        check(len(detail["evidence"]) == 2, "冲突来源会并存，不覆盖旧证据")

        relation = create_pending_relation(
            left_type="person",
            left_id="PER-T-001",
            left_label="测试人物",
            relation_type="创始人",
            right_type="org",
            right_id="ORG-T-001",
            right_label="测试企业",
            confidence=0.7,
            basis="测试依据",
            db_path=db_path,
        )
        check(relation["fact_level"] == "inference", "待确认关联默认标记为推测")
        relation_done = decide_pending_relation(
            relation["id"], decision="approved", reviewer="tester", note="已核对官网", db_path=db_path
        )
        check(relation_done["fact_level"] == "fact", "关联审核通过后才可定为事实")

        claim = register_claim(
            subject_type="project",
            subject_id="PRJ-T-001",
            subject_label="测试项目",
            predicate="临床阶段",
            object_value="II期",
            claim_type="inference",
            confidence=0.6,
            basis="仅根据图片位置判断",
            db_path=db_path,
        )
        check(claim["claim_type"] == "inference" and claim["status"] == "pending", "推测不会自动变为事实")

        other = create_review_item(
            item_type="fact_check",
            subject_type="org",
            subject_id="ORG-T-002",
            field_name="成立时间",
            proposed_value="2020-01-01",
            fact_level="fact",
            db_path=db_path,
        )
        result = batch_resolve(
            [item["id"], other["id"]], decision="approved", actor="tester", note="批量核对原始文件", db_path=db_path
        )
        check(len(result["succeeded"]) == 2 and not result["failed"], "批量审核可逐条记录结果")

        data = dashboard_data(db_path=db_path)
        check("items" in data and "relations" in data and "claims" in data, "审核页面数据可以完整读取")

    print("\n[SUCCESS] v0.4C 自检全部通过。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
