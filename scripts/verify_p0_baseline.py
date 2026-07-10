from __future__ import annotations

import hashlib
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable
LIVE_DB = ROOT / "data" / "app.db"
CORE_TABLES = {"raw_intelligence", "organizations", "people", "projects", "events", "resources", "relations", "actions"}
PAGES = ["/", "/subjects", "/organizations", "/people", "/projects", "/events", "/resources", "/intelligence", "/club", "/reports", "/pipeline"]
APIS = ["/api/v1/system/health", "/api/v1/dashboard", "/api/v1/organizations", "/api/v1/intelligence"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(label: str, args: list[str], env: dict[str, str] | None = None) -> bool:
    result = subprocess.run(args, cwd=ROOT, env=env, text=True, capture_output=True)
    if result.stdout:
        print(result.stdout.rstrip())
    if result.stderr:
        print(result.stderr.rstrip())
    print(("PASS" if result.returncode == 0 else "FAIL"), label)
    return result.returncode == 0


def readonly_database_check() -> bool:
    uri = f"file:{LIVE_DB.as_posix()}?mode=ro"
    with sqlite3.connect(uri, uri=True) as conn:
        tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        integrity = conn.execute("PRAGMA quick_check").fetchone()[0]
    missing = CORE_TABLES - tables
    ok = integrity == "ok" and not missing
    print(f"{'PASS' if ok else 'FAIL'} readonly_database integrity={integrity} missing={sorted(missing)}")
    return ok


def cloned_http_check(clone: Path) -> bool:
    env = os.environ.copy()
    env["APP_DB_PATH"] = str(clone)
    env["DATABASE_URL"] = f"sqlite:///{clone.as_posix()}"
    env["APP_AUTH_DISABLED"] = "1"
    code = """
from fastapi.testclient import TestClient
from app.main import app
client = TestClient(app)
failures = []
for path in %r:
    response = client.get(path, follow_redirects=False)
    print(path, response.status_code)
    if response.status_code >= 500:
        failures.append(path)
raise SystemExit(1 if failures else 0)
""" % (PAGES + APIS,)
    return run("cloned_http_pages_and_api", [PYTHON, "-c", code], env)


def main() -> int:
    checks: list[bool] = []
    if not LIVE_DB.exists():
        print(f"FAIL live database missing: {LIVE_DB}")
        return 1
    live_before = sha256(LIVE_DB)
    checks.append(run("compileall", [PYTHON, "-m", "compileall", "-q", "app", "scripts"]))
    checks.append(run("source_encoding", [PYTHON, "scripts/check_source_encoding.py"]))
    checks.append((ROOT / "app" / "templates").is_dir() and (ROOT / "app" / "static").is_dir())
    print(f"{'PASS' if checks[-1] else 'FAIL'} template_and_static_directories")
    checks.append(readonly_database_check())
    with tempfile.TemporaryDirectory(prefix="p0_clone_") as temp_dir:
        clone = Path(temp_dir) / "app.db"
        shutil.copy2(LIVE_DB, clone)
        checks.append(cloned_http_check(clone))
    live_after = sha256(LIVE_DB)
    checks.append(live_before == live_after)
    print(f"{'PASS' if checks[-1] else 'FAIL'} live_database_unchanged")
    print(f"verify_p0_baseline passed={sum(checks)} failed={len(checks)-sum(checks)}")
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
