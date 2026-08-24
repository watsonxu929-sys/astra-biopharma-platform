from __future__ import annotations

import argparse
import json
import signal
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.collection_scheduler import (  # noqa: E402
    run_scheduler_once,
    start_scheduler,
    stop_scheduler,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 APScheduler 采集调度器")
    parser.add_argument("--once", action="store_true", help="执行同一采集周期函数后退出")
    args = parser.parse_args()
    if args.once:
        print(json.dumps(run_scheduler_once(), ensure_ascii=False))
        return 0

    stopped = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    if not start_scheduler(force=True):
        return 1
    print("APScheduler 采集调度器已启动")
    try:
        stopped.wait()
    finally:
        stop_scheduler()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
