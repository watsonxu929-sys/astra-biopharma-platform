from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.tasks import create_task, list_tasks, task_metrics
from scripts.migrate_v05kl import migrate


def main() -> int:
    parser = argparse.ArgumentParser(description="Create safe v0.5K-L operational pilot tasks without real crawling")
    parser.add_argument("--days", type=int, default=3)
    parser.add_argument("--source-group", default="pilot")
    parser.add_argument("--confirm", action="store_true", help="Create tasks. Without this flag the script only previews.")
    args = parser.parse_args()
    migrate(backup=False)
    days = max(1, min(args.days, 14))
    planned = [
        ("source_health_check", {"source_group": args.source_group, "pilot_day": day})
        for day in range(1, days + 1)
    ]
    planned.extend(
        [
            ("backup", {"backup_type": "pilot"}),
            ("quality_sample", {"report": "pilot_quality", "source_group": args.source_group}),
        ]
    )
    if not args.confirm:
        print("DRY-RUN operational pilot tasks:")
        for task_type, payload in planned:
            print(f"- {task_type}: {payload}")
        return 0
    created = []
    for task_type, payload in planned:
        task = create_task(
            task_type,
            payload=payload,
            created_by="operational_pilot",
            idempotency_key=f"pilot:{task_type}:{payload}",
        )
        created.append(task["task_uid"])
    print(f"已创建 {len(created)} 个运营试运行任务。")
    print(task_metrics())
    print(list_tasks(page_size=10))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
