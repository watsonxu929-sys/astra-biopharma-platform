from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]


def _load_env_file() -> dict[str, str]:
    values: dict[str, str] = {}
    path = ROOT / ".env"
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


_ENV_FILE = _load_env_file()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, _ENV_FILE.get(name, default))


def _bool(name: str, default: bool = False) -> bool:
    value = _env(name, "true" if default else "false").strip().lower()
    return value in {"1", "true", "yes", "on", "y"}


def _int(name: str, default: int) -> int:
    try:
        return int(_env(name, str(default)))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    app_env: str = "development"
    app_host: str = "127.0.0.1"
    app_port: int = 8000
    app_reload: bool = True
    app_open_browser: bool = True
    database_url: str = "sqlite:///data/app.db"
    secret_key: str = ""
    session_secret: str = ""
    log_level: str = "INFO"
    worker_enabled: bool = True
    worker_concurrency: int = 1
    scheduler_enabled: bool = True
    backup_enabled: bool = True
    backup_retention_days: int = 30
    playwright_enabled: bool = False
    external_ai_enabled: bool = False

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def db_backend(self) -> str:
        parsed = urlparse(self.database_url)
        if parsed.scheme.startswith("postgres"):
            return "postgresql"
        return "sqlite"

    @property
    def sqlite_path(self) -> Path:
        if self.db_backend != "sqlite":
            return ROOT / "data" / "app.db"
        raw = self.database_url.removeprefix("sqlite:///")
        path = Path(raw)
        return path if path.is_absolute() else ROOT / path

    def sanitized_database_url(self) -> str:
        parsed = urlparse(self.database_url)
        if not parsed.password:
            return self.database_url
        safe_netloc = parsed.netloc.replace(parsed.password, "***")
        return parsed._replace(netloc=safe_netloc).geturl()

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.app_env not in {"development", "testing", "production"}:
            errors.append("APP_ENV 只能是 development、testing 或 production")
        if self.is_production:
            if not self.secret_key:
                errors.append("生产环境必须设置 SECRET_KEY")
            if not self.session_secret:
                errors.append("生产环境必须设置 SESSION_SECRET")
            if self.app_host in {"0.0.0.0", "::"} and not self.secret_key:
                errors.append("生产环境开放监听地址前必须完成密钥配置")
        if self.worker_concurrency < 1:
            errors.append("WORKER_CONCURRENCY 必须大于等于 1")
        if self.db_backend == "sqlite" and self.app_env == "testing" and self.sqlite_path == ROOT / "data" / "app.db":
            errors.append("测试环境不得使用正式 data/app.db")
        return errors


def get_settings() -> Settings:
    return Settings(
        app_env=_env("APP_ENV", "development"),
        app_host=_env("APP_HOST", "127.0.0.1"),
        app_port=_int("APP_PORT", 8000),
        app_reload=_bool("APP_RELOAD", True),
        app_open_browser=_bool("APP_OPEN_BROWSER", True),
        database_url=_env("DATABASE_URL", "sqlite:///data/app.db"),
        secret_key=_env("SECRET_KEY", ""),
        session_secret=_env("SESSION_SECRET", ""),
        log_level=_env("LOG_LEVEL", "INFO").upper(),
        worker_enabled=_bool("WORKER_ENABLED", True),
        worker_concurrency=_int("WORKER_CONCURRENCY", 1),
        scheduler_enabled=_bool("SCHEDULER_ENABLED", True),
        backup_enabled=_bool("BACKUP_ENABLED", True),
        backup_retention_days=_int("BACKUP_RETENTION_DAYS", 30),
        playwright_enabled=_bool("PLAYWRIGHT_ENABLED", False),
        external_ai_enabled=_bool("EXTERNAL_AI_ENABLED", False),
    )
