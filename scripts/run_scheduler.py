from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.tasks.task_common import db_connection, now
from app.services.tasks.task_dispatcher import create_task
from scripts.migrate_v05kl import migrate


def main() -> int:
    parser = argparse.ArgumentParser(description="运行轻量调度器，只创建到期任务，不执行重业务")
    parser.add_argument("--once", action="store_true", help="执行一轮调度后退出")
    parser.add_argument("--include-disabled", action="store_true", help="调试时也显示停用计划")
    args = parser.parse_args()
    migrate(backup=False)
    scheduled = 0
    with db_connection() as conn:
        rows = conn.execute("SELECT * FROM scheduler_jobs WHERE enabled=1 OR ?=1 ORDER BY id", (int(args.include_disabled),)).fetchall()
    for row in rows:
        if not row["enabled"]:
            print(f"跳过停用计划：{row['schedule_key']}")
            continue
        due = not row["next_run_at"] or row["next_run_at"] <= now()
        if not due:
            continue
        payload = json.loads(row["payload_json"] or "{}")
        task = create_task(row["task_type"], payload=payload, queue_name=row["queue_name"], idempotency_key=f"{row['schedule_key']}:{datetime.now():%Y%m%d%H}", created_by="scheduler")
        next_run = (datetime.now() + timedelta(seconds=int(row["interval_seconds"]))).replace(microsecond=0).isoformat()
        with db_connection() as conn:
            conn.execute("UPDATE scheduler_jobs SET last_scheduled_at=?, next_run_at=?, updated_at=? WHERE id=?", (now(), next_run, now(), row["id"]))
            conn.execute("INSERT INTO scheduler_runs(schedule_key,task_id,status,scheduled_at,created_at,note) VALUES (?, ?, 'scheduled', ?, ?, ?)", (row["schedule_key"], task["id"], now(), now(), "已创建任务"))
        scheduled += 1
        print(f"已调度：{row['schedule_key']} -> {task['task_uid']}")
    print(f"本轮调度任务数：{scheduled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
