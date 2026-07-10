from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.entity_analyzer import analyze_entity
from app.services.manual_ingestion import (
    extract_person_candidates,
    inspect_entity_text,
    validate_entity_submission,
)

SAMPLE_TEAM_PAGE = """标题：管理团队 | 药明康德
李革 博士
董事长兼首席执行官
科学家、企业家。李革博士于 2000 年创建药明康德，他开创了开放式研发服务平台。
陈民章 博士
联席首席执行官
拥有二十多年新药研发和生产管理经验。加入药明康德前，担任美国福泰制药公司技术运营总监。
杨青 博士
联席首席执行官
在建立医药研发及服务能力方面经验丰富。加入药明康德之前曾任阿斯利康副总裁。
"""


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def main() -> None:
    diagnostics = inspect_entity_text("people", SAMPLE_TEAM_PAGE)
    check(diagnostics["risk_level"] == "high", "团队页被判定为高风险")
    check(diagnostics["page_mode"] == "multiple_subjects", "团队页被判定为多主体")
    check(diagnostics["fill_allowed"] is False, "多主体全文禁止自动填表")

    candidates = extract_person_candidates(SAMPLE_TEAM_PAGE)
    check(len(candidates) == 3, "从示例团队页拆出3个人物候选")
    check([item.label for item in candidates] == ["李革", "陈民章", "杨青"], "候选姓名顺序正确")

    first_fields = analyze_entity("people", candidates[0].text)
    check(first_fields["name"] == "李革", "单条候选正确提取姓名")
    check(first_fields["public_role"] == "董事长兼首席执行官", "单条候选正确提取职位")
    check(first_fields["organization_network"] == "药明康德", "单条候选正确提取当前机构")

    invalid = validate_entity_submission(
        "people",
        {"name": "管理团队", "source_text": SAMPLE_TEAM_PAGE},
    )
    check(bool(invalid["errors"]), "栏目名不能作为人物姓名保存")

    valid_with_source_warning = validate_entity_submission(
        "people",
        {
            "name": "李革",
            "public_role": "董事长兼首席执行官",
            "organization_network": "药明康德",
            "source_text": SAMPLE_TEAM_PAGE,
        },
    )
    check(not valid_with_source_warning["errors"], "单人物字段本身通过硬校验")
    check(valid_with_source_warning["requires_confirmation"], "多主体原始来源要求人工确认")

    event_page = """2026年1月1日 新闻一\n某企业完成融资。\n2026年2月2日 新闻二\n某项目启动。\n2026年3月3日 新闻三\n某产品获批。\n""" + ("补充内容。" * 50)
    event_diagnostics = inspect_entity_text("events", event_page)
    check(event_diagnostics["risk_level"] == "high", "多日期新闻列表被判定为高风险")

    print("\n人工主导录入验证完成：全部通过。")


if __name__ == "__main__":
    main()
