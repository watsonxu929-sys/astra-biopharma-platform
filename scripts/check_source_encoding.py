from __future__ import annotations

import argparse
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ROOTS = (ROOT / "app", ROOT / "scripts")
INVISIBLE = {"\ufeff", "\u200b", "\u200c", "\u200d", "\u2060", "\u00a0"}


def scan_file(path: Path) -> list[str]:
    findings: list[str] = []
    data = path.read_bytes()
    bom_count = 0
    while data[bom_count * 3 : bom_count * 3 + 3] == b"\xef\xbb\xbf":
        bom_count += 1
    if bom_count:
        findings.append(f"leading UTF-8 BOM x{bom_count}")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        return [f"invalid UTF-8: {exc}"]
    for line_no, line in enumerate(text.splitlines(), 1):
        for column, char in enumerate(line, 1):
            if char in INVISIBLE or unicodedata.category(char) == "Cf":
                findings.append(f"line {line_no}, column {column}: U+{ord(char):04X} {unicodedata.name(char, 'UNKNOWN')}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Report Python source encoding and invisible-character problems without modifying files.")
    parser.add_argument("paths", nargs="*", type=Path)
    args = parser.parse_args()
    roots = args.paths or list(DEFAULT_ROOTS)
    files = sorted({p for root in roots for p in ([root] if root.is_file() else root.rglob("*.py"))})
    failed = 0
    for path in files:
        findings = scan_file(path)
        for finding in findings:
            failed += 1
            print(f"FAIL {path.relative_to(ROOT)}: {finding}")
    print(f"source_encoding files={len(files)} findings={failed}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
