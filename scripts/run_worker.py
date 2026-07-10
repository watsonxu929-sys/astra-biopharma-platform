from __future__ import annotations

import argparse
import signal
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import get_settings
from app.services.tasks import heartbeat, recover_stale_tasks, run_once

STOP = False


def _stop(signum, frame) -> None:  # type: ignore[no-untyped-def]
    global STOP
    STOP = True


def main() -> int:
    parser = argparse.ArgumentParser(description="运行统一后台 Worker")
    parser.add_argument("--once", action="store_true", help="只执行一个任务")
    parser.add_argument("--task-type", default="", help="限定任务类型")
    parser.add_argument("--concurrency", type=int, default=None, help="并发数；SQLite 默认 1")
    parser.add_argument("--queue", default="default", help="队列名称")
    parser.add_argument("--sleep", type=float, default=3.0, help="空队列等待秒数")
    parser.add_argument("--recover-stale", action="store_true", help="启动时恢复卡死任务")
    args = parser.parse_args()

    settings = get_settings()
    concurrency = args.concurrency or settings.worker_concurrency
    if settings.db_backend == "sqlite" and concurrency > 1:
        print("SQLite 模式自动限制并发为 1")
        concurrency = 1
    if concurrency != 1:
        print("首版统一 Worker 仅在单进程内串行执行；请启动多个进程前确认数据库后端和锁策略")
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)
    if args.recover_stale:
        recovered = recover_stale_tasks(worker_id=worker_id)
        print(f"已恢复卡死任务 {recovered} 个")
    print(f"Worker 已启动：{worker_id} queue={args.queue} task_type={args.task_type or '全部'}")
    while not STOP:
        heartbeat(worker_id, queue_name=args.queue, task_type=args.task_type)
        result = run_once(worker_id=worker_id, queue_name=args.queue, task_type=args.task_type)
        print(result)
        if args.once:
            break
        if not result.get("processed"):
            time.sleep(args.sleep)
    heartbeat(worker_id, queue_name=args.queue, task_type=args.task_type, status="stopped")
    print("Worker 已停止")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
