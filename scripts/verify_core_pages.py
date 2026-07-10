from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
DB_PATH = ROOT / "data" / "app.db"

os.environ["APP_AUTH_DISABLED"] = "1"

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402


def first_external_id(table: str) -> str | None:
    if not DB_PATH.exists():
        return None
    conn = sqlite3.connect(DB_PATH)
    try:
        row = conn.execute(f"SELECT external_id FROM {table} WHERE COALESCE(external_id,'')<>'' LIMIT 1").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None
    finally:
        conn.close()


def main() -> int:
    person_id = first_external_id("people")
    org_id = first_external_id("organizations")
    paths = [
        "/", "/subjects", "/organizations", "/people", "/projects", "/events", "/resources",
        "/intelligence", "/search", "/imports", "/reviews", "/collection/sources", "/collection/jobs",
        "/processing/jobs", "/processing/review", "/pipeline", "/signals", "/reports", "/club", "/club/members",
    ]
    if person_id:
        paths.append(f"/subjects/person/{person_id}")
    else:
        paths.append("/subjects/person/__missing__")
    if org_id:
        paths.append(f"/subjects/organization/{org_id}")
    else:
        paths.append("/subjects/organization/__missing__")
    client = TestClient(app)
    failures = []
    for path in paths:
        try:
            response = client.get(path, follow_redirects=False)
            body = response.text[:1000]
            print(f"{path} {response.status_code}")
            if response.status_code >= 500 or "Internal Server Error" in body:
                failures.append((path, response.status_code, "server error"))
            if response.status_code == 200 and "<html" not in body.lower() and "<!doctype html" not in body.lower():
                failures.append((path, response.status_code, "html not rendered"))
        except Exception as exc:
            print(f"{path} EXC {type(exc).__name__}: {exc}")
            failures.append((path, "EXC", f"{type(exc).__name__}: {exc}"))
    print(f"core_pages_total={len(paths)}")
    print(f"core_pages_failed={len(failures)}")
    for item in failures:
        print(f"[FAIL] {item[0]} {item[1]} {item[2]}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

