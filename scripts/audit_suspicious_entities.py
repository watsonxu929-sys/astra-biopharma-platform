from __future__ import annotations

import argparse
import csv
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sqlalchemy import select

from app.database import SessionLocal
from app.models import HistoricalEvent, Organization, Person, ProjectPool, Resource
from app.services.manual_ingestion import validate_entity_submission

ENTITY_SPECS = [
    ("people", Person, "name"),
    ("organizations", Organization, "standard_name"),
    ("projects", ProjectPool, "name"),
    ("events", HistoricalEvent, "name"),
    ("resources", Resource, "description"),
]


def row_values(item) -> dict[str, object]:
    return {
        column.name: getattr(item, column.name, None)
        for column in item.__table__.columns
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="只读扫描疑似错误主体，不修改数据库。")
    parser.add_argument("--output", default="", help="可选：导出CSV路径")
    args = parser.parse_args()

    findings: list[dict[str, str]] = []
    with SessionLocal() as db:
        for entity_key, model, display_field in ENTITY_SPECS:
            items = db.scalars(select(model).order_by(model.id)).all()
            for item in items:
                result = validate_entity_submission(entity_key, row_values(item))
                reasons = [*result["errors"], *result["warnings"]]
                if not reasons:
                    continue
                findings.append(
                    {
                        "类型": entity_key,
                        "数据库ID": str(item.id),
                        "系统编号": str(getattr(item, "external_id", "") or ""),
                        "名称": str(getattr(item, display_field, "") or "")[:120],
                        "级别": "阻止保存" if result["errors"] else "需要复核",
                        "原因": "；".join(dict.fromkeys(reasons)),
                    }
                )

    if not findings:
        print("未发现符合当前规则的疑似记录。")
        return

    print(f"发现 {len(findings)} 条需要复核的记录（脚本只读，未修改数据库）：")
    for row in findings:
        print(
            f"- [{row['级别']}] {row['类型']} #{row['数据库ID']} "
            f"{row['系统编号']} {row['名称']}\n  {row['原因']}"
        )

    if args.output:
        output = Path(args.output)
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(findings[0]))
            writer.writeheader()
            writer.writerows(findings)
        print(f"\n已导出：{output}")


if __name__ == "__main__":
    main()
