from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "app.db"


def _load_dotenv_once() -> None:
    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key and key not in os.environ:
            os.environ[key] = value.strip().strip('"').strip("'")


def sqlite_url_from_path(path: str | Path) -> str:
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = (PROJECT_ROOT / resolved).resolve()
    return f"sqlite:///{resolved.as_posix()}"


def sqlite_path_from_url(database_url: str) -> Path:
    parsed = urlparse(database_url)
    if parsed.scheme not in {"sqlite", "sqlite+pysqlite"}:
        raise ValueError("Only sqlite database URLs can be resolved to a local path")
    if database_url in {"sqlite://", "sqlite:///:memory:", "sqlite+pysqlite:///:memory:"}:
        return Path(":memory:")
    raw_path = unquote(parsed.path or "")
    if os.name == "nt" and raw_path.startswith("/") and len(raw_path) > 2 and raw_path[2] == ":":
        raw_path = raw_path[1:]
    path = Path(raw_path).expanduser()
    if os.name == "nt" and raw_path.startswith("/") and not (len(raw_path) > 2 and raw_path[2] == ":"):
        path = Path(raw_path.lstrip("/"))
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path.resolve()


@dataclass(frozen=True)
class Settings:
    database_url: str
    app_db_path: Path
    app_env: str = "development"


def get_settings() -> Settings:
    _load_dotenv_once()
    app_env = os.getenv("APP_ENV", "development").strip() or "development"
    database_url = os.getenv("DATABASE_URL", "").strip()
    app_db_path = os.getenv("APP_DB_PATH", "").strip()
    if database_url:
        if database_url.startswith("sqlite"):
            db_path = sqlite_path_from_url(database_url)
        else:
            db_path = Path(app_db_path).expanduser().resolve() if app_db_path else DEFAULT_DB_PATH.resolve()
    else:
        db_path = Path(app_db_path).expanduser() if app_db_path else DEFAULT_DB_PATH
        if not db_path.is_absolute():
            db_path = (PROJECT_ROOT / db_path).resolve()
        database_url = sqlite_url_from_path(db_path)
    return Settings(database_url=database_url, app_db_path=db_path, app_env=app_env)


def resolved_database_url() -> str:
    return get_settings().database_url


def resolved_db_path() -> Path:
    return get_settings().app_db_path

