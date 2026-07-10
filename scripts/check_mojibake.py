from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TARGETS = [ROOT / "app", ROOT / "scripts", ROOT / "docs"]
SUFFIXES = {".py", ".html", ".js", ".css", ".md", ".bat"}
SKIP_PARTS = {".venv", "venv", "__pycache__", ".git", "data", "logs", "runtime", "patches"}

COMMON_CHINESE_TERMS = [
    "??????????", "????", "????", "????", "????",
    "????", "????", "????", "????", "????", "??",
    "??", "??", "??", "??", "??", "????", "????",
    "???", "????", "????", "??????", "????",
]


def mojibake_variants(term: str) -> set[str]:
    variants: set[str] = set()
    for codec in ("gbk", "cp936"):
        try:
            broken = term.encode("utf-8").decode(codec, errors="ignore")
        except UnicodeError:
            continue
        if broken and broken != term:
            variants.add(broken)
            if len(broken) > 4:
                variants.add(broken[:4])
    return variants


RARE_MOJIBAKE_CHARS = "".join(chr(int(code, 16)) for code in [
    "95BA", "95B9", "95BB", "95C2", "95C1", "95BF", "9225", "922B",
    "951B", "9286", "6B7F", "9422", "93C3", "93C9", "93C4", "93C6",
    "93B5", "95AB",
])
PATTERNS = sorted(
    {"\ufffd", "psection", "ptable", "pdiv", "ph1>", "p/section", "p/table", "p/div"}
    | {ch for ch in RARE_MOJIBAKE_CHARS}
    | {v for term in COMMON_CHINESE_TERMS for v in mojibake_variants(term) if len(v) >= 2}
)
ALLOW_LINE_RE = re.compile(
    r"model_version|external_id|source_text|source_url|source_title|local-rule-v0\.|v0\.4|v0\.5|charset|Content-Disposition|unicode_escape"
)


def iter_files() -> list[Path]:
    roots = [p for p in TARGETS if p.exists()]
    files: list[Path] = []
    for root in roots:
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in SUFFIXES:
                continue
            if any(part in SKIP_PARTS for part in path.parts):
                continue
            if path.name == "check_mojibake.py":
                continue
            files.append(path)
    for path in ROOT.glob("*.bat"):
        files.append(path)
    return sorted(set(files))


def main() -> int:
    findings = []
    whitelist = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            findings.append((path.relative_to(ROOT), 0, "high", "???? UTF-8 ?????????"))
            continue
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if not any(token in line for token in PATTERNS):
                continue
            rel = path.relative_to(ROOT)
            snippet = line.strip()[:180]
            if ALLOW_LINE_RE.search(line):
                whitelist.append((rel, lineno, snippet))
            else:
                findings.append((rel, lineno, "high", snippet))
    print(f"files_scanned={len(iter_files())}")
    print(f"mojibake_findings={len(findings)}")
    print(f"mojibake_whitelist={len(whitelist)}")
    for rel, lineno, level, snippet in findings[:300]:
        safe_snippet = snippet.encode("ascii", errors="backslashreplace").decode("ascii")
        print(f"[MOJIBAKE] {rel}:{lineno}: {level}: {safe_snippet}")
    if len(findings) > 300:
        print(f"[MOJIBAKE] ... {len(findings) - 300} more")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
