from __future__ import annotations

import os
import gc
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import contextmanager
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def assert_not_live_db(db_path: Path) -> None:
    real = (ROOT / "data" / "app.db").resolve()
    try:
        if db_path.resolve() == real:
            raise RuntimeError(f"refusing to use live database for verification: {db_path}")
    except FileNotFoundError:
        pass
    if str(db_path.resolve()).startswith(str((ROOT / "data").resolve())):
        raise RuntimeError(f"verification database must be outside data/: {db_path}")


@contextmanager
def temporary_database(prefix: str = "bio_verify_"):
    tmp = Path(tempfile.mkdtemp(prefix=prefix))
    db_path = tmp / "app_test.db"
    assert_not_live_db(db_path)
    old_app = os.environ.get("APP_DB_PATH")
    old_url = os.environ.get("DATABASE_URL")
    os.environ["APP_DB_PATH"] = str(db_path)
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    try:
        yield db_path
    finally:
        try:
            if old_app is None:
                os.environ.pop("APP_DB_PATH", None)
            else:
                os.environ["APP_DB_PATH"] = old_app
            if old_url is None:
                os.environ.pop("DATABASE_URL", None)
            else:
                os.environ["DATABASE_URL"] = old_url
        finally:
            database_module = sys.modules.get("app.database")
            engine = getattr(database_module, "engine", None) if database_module else None
            if engine is not None:
                try:
                    engine.dispose()
                except Exception:
                    pass
            for _ in range(60):
                try:
                    shutil.rmtree(tmp)
                    break
                except PermissionError:
                    gc.collect()
                    time.sleep(0.5)
            else:
                shutil.rmtree(tmp)


def run_migration_suite(db_path: Path) -> None:
    assert_not_live_db(db_path)
    env = os.environ.copy()
    env["APP_DB_PATH"] = str(db_path)
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    result = subprocess.run([sys.executable, str(ROOT / "scripts" / "migrate_all.py")], cwd=ROOT, env=env, text=True, capture_output=True)
    if result.returncode != 0:
        raise RuntimeError(result.stdout + result.stderr)
    platform = subprocess.run([sys.executable, str(ROOT / "scripts" / "migrate_platform_mvp_v1.py")], cwd=ROOT, env=env, text=True, capture_output=True)
    if platform.returncode != 0:
        raise RuntimeError(platform.stdout + platform.stderr)


def foreign_key_check(db_path: Path) -> int:
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA foreign_keys=ON")
        return len(conn.execute("PRAGMA foreign_key_check").fetchall())
    finally:
        conn.close()



