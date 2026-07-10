import importlib
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

for module in ["httpx", "bs4"]:
    try:
        importlib.import_module(module)
        check(f"Import {module}", True)
    except Exception as exc:
        check(f"Import {module}", False, repr(exc))

try:
    from app.main import app
    paths = {
        getattr(route, "path", None)
        for route in app.routes
        if getattr(route, "path", None)
    }

    for route in [
        "/manage/fetch-webpage",
        "/manage/{entity_key}/analyze",
        "/manage/{entity_key}/new",
    ]:
        check(f"Web route {route}", route in paths)
except Exception as exc:
    check("Import app.main", False, repr(exc))

if failed:
    print(f"SELF CHECK FAILED: {failed}")
    raise SystemExit(1)

print("ALL V0.4A CHECKS PASSED")
