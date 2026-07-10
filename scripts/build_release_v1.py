from __future__ import annotations

import argparse
import fnmatch
import shutil
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DENY_PATTERNS = [
    ".env", ".venv/*", "venv/*", "logs/*", "data/*.db", "data/*.sqlite*", "data/*.backup*",
    "data/backups/*", "data/.session_secret", "data/*-wal", "data/*-shm", "__pycache__/*", "*.pyc",
    ".pytest_cache/*", "data/uploads/*", ".git/*",
]
ALLOW_EXACT = {".env.example", "logs/.gitkeep"}


def denied(rel: str) -> str | None:
    norm = rel.replace("\\", "/")
    if norm in ALLOW_EXACT:
        return None
    for pattern in DENY_PATTERNS:
        if fnmatch.fnmatch(norm, pattern) or fnmatch.fnmatch(Path(norm).name, pattern):
            return pattern
    return None


def iter_files() -> list[Path]:
    return [path for path in ROOT.rglob("*") if path.is_file() and not path.relative_to(ROOT).as_posix().startswith(".git/")]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="dist/release_v1")
    parser.add_argument("--zip", action="store_true")
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    violations = []
    included = []
    for path in iter_files():
        rel = path.relative_to(ROOT).as_posix()
        reason = denied(rel)
        if reason:
            if rel == ".env" or rel.startswith("data/") or rel.startswith(".venv/") or rel.startswith("logs/"):
                violations.append((rel, reason))
            continue
        included.append(path)
    if violations:
        print("release_refused_sensitive_files:")
        for rel, reason in violations:
            print(f"  {rel} ({reason})")
        return 1
    print(f"release_file_count={len(included)}")
    if args.check_only:
        print("release_check=ok")
        return 0
    out = (ROOT / args.output).resolve()
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True, exist_ok=True)
    manifest = []
    for path in included:
        rel = path.relative_to(ROOT)
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        manifest.append(rel.as_posix())
    (out / "RELEASE_MANIFEST.txt").write_text("\n".join(sorted(manifest)) + "\n", encoding="utf-8")
    if args.zip:
        zip_path = out.with_suffix(".zip")
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in out.rglob("*"):
                if file.is_file():
                    zf.write(file, file.relative_to(out.parent))
        print(f"release_zip={zip_path}")
    print(f"release_dir={out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
