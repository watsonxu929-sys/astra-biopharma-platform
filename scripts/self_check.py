import importlib
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
failed = 0


def check(name, ok, detail=""):
    global failed
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        failed += 1
        if detail:
            print("   ", detail)


check("Python >= 3.11", sys.version_info >= (3, 11), sys.version)

for module in [
    "fastapi",
    "uvicorn",
    "sqlalchemy",
    "jinja2",
    "multipart",
    "openpyxl",
]:
    try:
        importlib.import_module(module)
        check(f"Import {module}", True)
    except Exception as exc:
        check(f"Import {module}", False, repr(exc))

try:
    from app.main import app
    check("Import app.main", True)

    route_paths = {
        getattr(route, "path", None)
        for route in app.routes
        if getattr(route, "path", None)
    }

    required_routes = [
        "/",
        "/intelligence",
        "/organizations",
        "/people",
        "/projects",
        "/resources",
        "/events",
        "/relations",
        "/actions",
        "/imports",
        "/analyze/paste",
        "/analyze/paste/preview",
        "/analyze/paste/confirm",
        "/manage/{entity_key}/new",
        "/manage/{entity_key}/{item_id}/edit",
    ]

    for route in required_routes:
        check(f"Web route {route}", route in route_paths)

except Exception as exc:
    check("Import app.main", False, repr(exc))

db_path = ROOT / "data" / "app.db"
check("Database file exists", db_path.exists(), str(db_path))

expected_tables = [
    "raw_intelligence",
    "organizations",
    "people",
    "resources",
    "events",
    "projects",
    "relations",
    "actions",
    "import_logs",
]

if db_path.exists():
    try:
        connection = sqlite3.connect(db_path)
        existing = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        connection.close()

        for table in expected_tables:
            check(f"Database table {table}", table in existing)

    except Exception as exc:
        check("Database readable", False, repr(exc))

print("-" * 60)

if failed:
    print(f"SELF CHECK FAILED: {failed} issue(s)")
    raise SystemExit(1)

print("ALL CHECKS PASSED")
