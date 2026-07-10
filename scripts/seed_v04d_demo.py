from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.v04c1_ingestion import ingest_payload  # noqa: E402
from app.v04d_structuring import create_task_item, get_or_create_task  # noqa: E402
from app.v04c_review import db_connection  # noqa: E402


def main() -> int:
    result = ingest_payload(
        {
            "batch": {
                "source_name": "v04d-demo",
                "source_type": "demo",
                "note": "v0.4D 结构化工作台演示数据",
            },
            "records": [
                {
                    "external_key": "v04d-demo-001",
                    "source_name": "v04d-demo",
                    "source_type": "演示新闻",
                    "source_grade": "B",
                    "source_url": "https://example.test/v04d-demo",
                    "title": "澄明生物完成A轮融资并推进创新药项目",
                    "published_at": "2026-06-28",
                    "content": (
                        "澄明生物近日宣布完成A轮融资，融资金额约1.2亿元，"
                        "由远景资本领投。公司创始人李明表示，核心项目CM-101"
                        "计划于2027年进入II期临床。"
                    ),
                    "excerpt": (
                        "澄明生物近日宣布完成A轮融资，融资金额约1.2亿元，"
                        "由远景资本领投。公司创始人李明表示，核心项目CM-101"
                        "计划于2027年进入II期临床。"
                    ),
                }
            ],
        },
        created_by="v04d-demo",
    )
    first = result["results"][0]
    source = first["record"]
    task = get_or_create_task(int(source["id"]), created_by="v04d-demo")

    with db_connection() as conn:
        existing_count = conn.execute(
            "SELECT COUNT(*) AS c FROM v04d_structure_items WHERE task_id=?",
            (task["id"],),
        ).fetchone()["c"]
    if existing_count == 0:
        create_task_item(
            int(task["id"]),
            actor="v04d-demo",
            item_type="field",
            subject_type="organization",
            subject_label="澄明生物",
            field_name="融资金额",
            candidate_value="约1.2亿元",
            fact_level="fact",
            confidence="0.88",
            evidence_excerpt="澄明生物近日宣布完成A轮融资，融资金额约1.2亿元。",
            source_url="https://example.test/v04d-demo",
        )
        create_task_item(
            int(task["id"]),
            actor="v04d-demo",
            item_type="relation",
            left_type="organization",
            left_label="远景资本",
            relation_type="领投",
            right_type="organization",
            right_label="澄明生物",
            fact_level="fact",
            confidence="0.85",
            evidence_excerpt="由远景资本领投。",
            source_url="https://example.test/v04d-demo",
        )
        create_task_item(
            int(task["id"]),
            actor="v04d-demo",
            item_type="event",
            event_name="澄明生物完成A轮融资",
            event_date="2026-06-28",
            event_type="融资",
            related_entity="澄明生物、远景资本",
            event_summary="澄明生物完成约1.2亿元A轮融资，由远景资本领投。",
            fact_level="fact",
            confidence="0.86",
            evidence_excerpt="澄明生物近日宣布完成A轮融资，融资金额约1.2亿元，由远景资本领投。",
            source_url="https://example.test/v04d-demo",
        )
        print(f"[OK] Demo task created: {task['task_no']}")
    else:
        print(f"[SKIP] Demo task already exists: {task['task_no']}")
    print(f"Open: http://127.0.0.1:8000/review/structure/tasks/{task['id']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
