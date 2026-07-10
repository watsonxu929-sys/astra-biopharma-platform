import hashlib
import os
import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LIVE_DB_PATH = ROOT / "data" / "app.db"


def compute_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture(scope="session")
def live_db_sha256():
    return compute_sha256(LIVE_DB_PATH)


@pytest.fixture(scope="session")
def live_db_path():
    return LIVE_DB_PATH


@pytest.fixture
def temp_database(live_db_path):
    tmpdir = tempfile.mkdtemp()
    temp_db = Path(tmpdir) / "test_app.db"
    shutil.copy2(live_db_path, temp_db)
    yield temp_db
    time.sleep(0.5)
    try:
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass


@pytest.fixture
def temp_db_conn(temp_database):
    conn = sqlite3.connect(temp_database)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    yield conn
    conn.close()


@pytest.fixture(autouse=True)
def protect_real_database(live_db_path, live_db_sha256):
    original_sha = live_db_sha256
    yield
    final_sha = compute_sha256(live_db_path)
    assert original_sha == final_sha, f"Real database was modified! SHA256 changed from {original_sha} to {final_sha}"


@pytest.fixture(scope="session")
def app_env():
    env = os.environ.copy()
    return env
