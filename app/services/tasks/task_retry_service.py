from __future__ import annotations

from datetime import datetime, timedelta


def next_retry_at(attempts: int) -> str:
    seconds = min(3600, 2 ** max(0, attempts - 1) * 30)
    return (datetime.now() + timedelta(seconds=seconds)).replace(microsecond=0).isoformat()
