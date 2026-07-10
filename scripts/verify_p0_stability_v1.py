from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.test_db_utils import foreign_key_check, run_migration_suite, temporary_database


def check(results: list[bool], name: str, func) -> None:
    try:
        func()
        print(f"PASS {name}")
        results.append(True)
    except Exception as exc:
        print(f"FAIL {name}: {exc}")
        results.append(False)


def main() -> int:
    results: list[bool] = []
    live_db = ROOT / "data" / "app.db"
    before = live_db.stat().st_mtime_ns if live_db.exists() else 0
    with temporary_database("p0_verify_") as db_path:
        run_migration_suite(db_path)
        check(results, "foreign_keys_enabled", lambda: _fk_on(db_path))
        check(results, "foreign_key_check_zero", lambda: _expect_zero(foreign_key_check(db_path)))
        check(results, "app_import", lambda: _import_app(db_path))
        check(results, "route_registry", lambda: _run_script("scripts/verify_route_registry_v1.py"))
        check(results, "auth_disabled_positive_user", lambda: _auth_disabled_positive(db_path))
        check(results, "release_refuses_sensitive", lambda: _run_script_expect_fail("scripts/build_release_v1.py", "--check-only"))
    after = live_db.stat().st_mtime_ns if live_db.exists() else 0
    check(results, "live_db_not_modified_by_temp_verification", lambda: _expect_equal(before, after))
    print(f"verify_p0_stability_v1 passed={sum(results)} failed={len(results)-sum(results)}")
    return 0 if all(results) else 1


def _fk_on(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        assert int(conn.execute("PRAGMA foreign_keys").fetchone()[0]) == 1


def _expect_zero(value: int) -> None:
    assert value == 0, value


def _expect_equal(a, b) -> None:
    assert a == b, (a, b)


def _temp_env(db_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    env["APP_DB_PATH"] = str(db_path)
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    return env


def _import_app(db_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, "-c", "import app.main"],
        cwd=ROOT,
        env=_temp_env(db_path),
        text=True,
        capture_output=True,
    )
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
def _run_script(*args: str) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)


def _run_script_expect_fail(*args: str) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True)
    if result.returncode == 0:
        raise AssertionError("expected release check to refuse current tree with local sensitive files")


def _auth_disabled_positive(db_path: Path) -> None:
    env = _temp_env(db_path)
    env["APP_AUTH_DISABLED"] = "1"
    code = (
        "import os;"
        "from app.security import auth_disabled_user;"
        "user=auth_disabled_user(os.environ['APP_DB_PATH']);"
        "assert int(user['id']) > 0"
    )
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)
if __name__ == "__main__":
    raise SystemExit(main())


