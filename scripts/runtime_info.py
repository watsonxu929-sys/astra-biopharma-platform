from __future__ import annotations

import argparse

from app.settings import validate_runtime_settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Print sanitized runtime configuration")
    parser.add_argument("role", choices=("Web", "Scheduler", "Worker"))
    args = parser.parse_args()
    settings = validate_runtime_settings()
    database_label = str(settings.sqlite_path) if settings.db_backend == "sqlite" else settings.db_backend
    print(f"[{args.role}] environment={settings.app_env}")
    print(f"[{args.role}] database_backend={settings.db_backend} database={database_label}")
    if args.role == "Web":
        print(f"[Web] authentication={'disabled-development-bypass' if settings.auth_disabled else 'enabled'}")
        print(f"[Web] embedded_scheduler={settings.enable_scheduler_in_web}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
