import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.web_extractor import validate_public_url

checks = [
    ("https accepted", validate_public_url("https://example.com") == "https://example.com"),
]

blocked = False
try:
    validate_public_url("http://127.0.0.1:8000")
except ValueError:
    blocked = True

checks.append(("local address blocked", blocked))

failed = 0
for name, ok in checks:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}")
    if not ok:
        failed += 1

if failed:
    raise SystemExit(1)

print("ALL WEB EXTRACTOR CHECKS PASSED")
