from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.config import _bool, get_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Print sanitized runtime configuration")
    parser.add_argument("role", choices=("Web", "Scheduler", "Worker"))
    args = parser.parse_args()
    settings = get_settings()
    errors = settings.validate()
    if errors:
        for error in errors:
            print(f"[{args.role}] configuration_error={error}")
        return 1
    database_label = str(settings.sqlite_path) if settings.db_backend == "sqlite" else settings.db_backend
    print(f"[{args.role}] environment={settings.app_env}")
    print(f"[{args.role}] database_backend={settings.db_backend} database={database_label}")
    if args.role == "Web":
        print(f"[Web] authentication={'disabled-development-bypass' if _bool('APP_AUTH_DISABLED') else 'enabled'}")
        print(f"[Web] embedded_scheduler={settings.scheduler_enabled}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
