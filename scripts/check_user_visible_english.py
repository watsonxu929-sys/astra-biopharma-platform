from __future__ import annotations

import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [
    ROOT / "app" / "templates",
    ROOT / "app" / "static",
    ROOT / "app" / "navigation.py",
    ROOT / "app" / "api",
    ROOT / "app" / "services",
]
MUST_PATTERNS = [
    r"v0\.(?:4C(?:-1)?|4D|5[FGHIJKLM]|5K-L)",
    r"Collection Center",
    r"Processing Center",
    r"Pipeline Center",
    r"Signal Center",
    r"Report Center",
    r"Weekly Industry Report",
    r"Executive Summary",
    r"Core Signals",
    r"Create Job",
    r"Run once",
    r"No jobs",
    r"No data",
    r"source_success_rate",
    r"collection_new_item_rate",
    r"duplicate_rate",
    r"empty_content_rate",
    r"processing_success_rate",
    r"structure_confidence_average",
    r"candidate_per_item",
    r"subject_match_rate",
    r"ambiguous_match_rate",
]
CHECK_WORDS = {
    "Dashboard", "Collection", "Processing", "Pipeline", "Report", "Worker", "Job", "Status", "Counts",
    "Action", "Limit", "optional", "queued", "generated", "draft", "Events", "Risks", "Review",
    "Create", "Run", "Summary", "Signals", "Executive",
}
WHITELIST_WORDS = {
    "Q-BAY", "API", "RSS", "JSON", "CSV", "PDF", "Word", "Excel", "CMC", "BD", "URL",
    "HTTP", "HTTPS", "Atom", "Markdown", "FastAPI", "SQLAlchemy", "Jinja2", "SQLite",
}
ALLOWED_PATH_PARTS = {
    "migrate_", "verify_v04", "verify_v05", "run_", "check_user_visible_english.py", "report_generation_service.py", "pipeline_metrics_service.py", "source_quality_service.py", "research_service.py", "api/v1/router.py",
}
CODE_HINTS = ("def ", "class ", "import ", "from ", "return ", "=", "{", "}", "[", "]", "href=", "action=", "name=", "value=", "id=", "class=", "data-")


def iter_files() -> list[Path]:
    files: list[Path] = []
    for target in TARGETS:
        if not target.exists():
            continue
        if target.is_file():
            files.append(target)
        else:
            files.extend(path for path in target.rglob("*") if path.suffix.lower() in {".html", ".js", ".py"})
    return sorted(set(files))


def classify_line(path: Path, line: str) -> str | None:
    rel = str(path.relative_to(ROOT)).replace("\\", "/")
    if any(part in rel for part in ALLOWED_PATH_PARTS):
        return None
    stripped = line.strip()
    if not stripped or "{%" in stripped or "{{" in stripped or stripped.startswith(("#", "//", "/*", "*")):
        return None
    if any(word in stripped for word in WHITELIST_WORDS):
        return "white"
    for pattern in MUST_PATTERNS:
        if re.search(pattern, stripped, re.I):
            if any(hint in stripped for hint in CODE_HINTS) and path.suffix == ".py":
                return "check"
            return "must"
    if path.suffix in {".html", ".js"} and not any(hint in stripped for hint in CODE_HINTS):
        if any(re.search(rf"\b{re.escape(word)}\b", stripped) for word in CHECK_WORDS):
            return "check"
    return None


def main() -> int:
    must_fix: list[str] = []
    need_check: list[str] = []
    whitelist: list[str] = []
    for path in iter_files():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for lineno, line in enumerate(text.splitlines(), 1):
            kind = classify_line(path, line)
            if not kind:
                continue
            item = f"{path.relative_to(ROOT)}:{lineno}:{line.strip()[:160]}"
            if kind == "must":
                must_fix.append(item)
            elif kind == "check":
                need_check.append(item)
            else:
                whitelist.append(item)
    print(f"必须修复: {len(must_fix)}")
    print(f"需要人工确认: {len(need_check)}")
    print(f"合法白名单: {len(whitelist)}")
    for item in must_fix[:120]:
        print(f"[必须修复] {item}")
    for item in need_check[:80]:
        print(f"[人工确认] {item}")
    for item in whitelist[:40]:
        print(f"[白名单] {item}")
    return 1 if must_fix else 0


if __name__ == "__main__":
    sys.exit(main())



