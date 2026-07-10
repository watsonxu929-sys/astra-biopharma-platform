from __future__ import annotations

import hashlib
import json
import sqlite3
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
HANDOFF = ROOT / "handoff"
WORK = HANDOFF / f"v04d_context_{STAMP}"
ZIP_PATH = HANDOFF / f"v04d_context_bundle_{STAMP}.zip"

EXCLUDED_PARTS = {
    ".git", ".venv", "venv", "node_modules", "__pycache__",
    "logs", "backups", ".pytest_cache", ".mypy_cache",
}
EXCLUDED_SUFFIXES = {
    ".db", ".sqlite", ".sqlite3", ".pyc", ".pyo", ".log",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf",
    ".zip", ".rar", ".7z",
}
ROOT_FILES = {
    "requirements.txt", "pyproject.toml", "setup.cfg", "alembic.ini",
    ".gitignore", "README.md", "README.txt",
}
ALLOWED_SUFFIXES = {
    ".py", ".html", ".htm", ".css", ".js", ".ts", ".tsx",
    ".json", ".md", ".txt", ".yml", ".yaml", ".toml",
    ".ini", ".cfg", ".cmd", ".bat", ".ps1",
}
INCLUDED_TOP_DIRS = {
    "app", "scripts", "docs", "examples", "migrations", "alembic",
    "tests", "test",
}


def is_allowed(path: Path) -> bool:
    try:
        rel = path.relative_to(ROOT)
    except ValueError:
        return False

    if any(part in EXCLUDED_PARTS for part in rel.parts):
        return False
    if path.suffix.lower() in EXCLUDED_SUFFIXES:
        return False
    if rel.name in ROOT_FILES:
        return True
    if len(rel.parts) == 1 and path.suffix.lower() in {".cmd", ".bat", ".ps1", ".md", ".txt"}:
        return True
    if rel.parts and rel.parts[0] in INCLUDED_TOP_DIRS:
        return path.suffix.lower() in ALLOWED_SUFFIXES
    return False


def iter_source_files() -> Iterable[Path]:
    for path in ROOT.rglob("*"):
        if path.is_file() and is_allowed(path):
            yield path


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def copy_file(src: Path) -> None:
    rel = src.relative_to(ROOT)
    dest = WORK / "project_files" / rel
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(src.read_bytes())


def find_database() -> Path | None:
    candidates = [
        ROOT / "data" / "app.db",
        ROOT / "app.db",
        ROOT / "data" / "database.db",
    ]
    for path in candidates:
        if path.exists() and path.is_file():
            return path
    return None


def quote_ident(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def build_schema_report(db_path: Path | None) -> str:
    lines = [
        "v0.4D context database schema report",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "This report contains schema and row counts only. No row content is exported.",
        "",
    ]
    if db_path is None:
        lines.append("Database not found. Expected data/app.db or app.db.")
        return "\n".join(lines)

    lines.append(f"Database path: {db_path.relative_to(ROOT)}")
    lines.append(f"Database size: {db_path.stat().st_size} bytes")
    lines.append("")

    uri = f"file:{db_path.as_posix()}?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True, timeout=10)
        conn.row_factory = sqlite3.Row
    except Exception as exc:
        lines.append(f"Could not open database read-only: {exc}")
        return "\n".join(lines)

    try:
        tables = conn.execute(
            """
            SELECT name, sql
            FROM sqlite_master
            WHERE type = 'table'
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """
        ).fetchall()

        lines.append(f"Table count: {len(tables)}")
        lines.append("")

        for table in tables:
            name = table["name"]
            lines.append("=" * 80)
            lines.append(f"TABLE: {name}")
            try:
                count = conn.execute(
                    f"SELECT COUNT(*) FROM {quote_ident(name)}"
                ).fetchone()[0]
                lines.append(f"ROW COUNT: {count}")
            except Exception as exc:
                lines.append(f"ROW COUNT ERROR: {exc}")

            lines.append("COLUMNS:")
            try:
                columns = conn.execute(
                    f"PRAGMA table_info({quote_ident(name)})"
                ).fetchall()
                for col in columns:
                    lines.append(
                        f"  - {col['name']} | type={col['type']} | "
                        f"notnull={col['notnull']} | default={col['dflt_value']} | pk={col['pk']}"
                    )
            except Exception as exc:
                lines.append(f"  COLUMN ERROR: {exc}")

            lines.append("FOREIGN KEYS:")
            try:
                fks = conn.execute(
                    f"PRAGMA foreign_key_list({quote_ident(name)})"
                ).fetchall()
                if not fks:
                    lines.append("  - none")
                for fk in fks:
                    lines.append(
                        f"  - {fk['from']} -> {fk['table']}.{fk['to']} "
                        f"| on_update={fk['on_update']} | on_delete={fk['on_delete']}"
                    )
            except Exception as exc:
                lines.append(f"  FK ERROR: {exc}")

            lines.append("INDEXES:")
            try:
                indexes = conn.execute(
                    f"PRAGMA index_list({quote_ident(name)})"
                ).fetchall()
                if not indexes:
                    lines.append("  - none")
                for idx in indexes:
                    lines.append(
                        f"  - {idx['name']} | unique={idx['unique']} | origin={idx['origin']}"
                    )
            except Exception as exc:
                lines.append(f"  INDEX ERROR: {exc}")

            lines.append("CREATE SQL:")
            lines.append(table["sql"] or "(none)")
            lines.append("")
    finally:
        conn.close()

    return "\n".join(lines)


def build_tree(files: list[Path]) -> str:
    rels = sorted(str(p.relative_to(ROOT)).replace("\\", "/") for p in files)
    return "\n".join([
        "v0.4D selected project tree",
        f"Generated: {datetime.now().isoformat(timespec='seconds')}",
        "",
        *rels,
        "",
    ])


def main() -> int:
    HANDOFF.mkdir(parents=True, exist_ok=True)
    WORK.mkdir(parents=True, exist_ok=True)

    files = sorted(iter_source_files())
    manifest = []

    for src in files:
        copy_file(src)
        rel = str(src.relative_to(ROOT)).replace("\\", "/")
        manifest.append({
            "path": rel,
            "size_bytes": src.stat().st_size,
            "sha256": sha256(src),
        })

    db_path = find_database()
    (WORK / "DATABASE_SCHEMA_ONLY.txt").write_text(
        build_schema_report(db_path), encoding="utf-8"
    )
    (WORK / "PROJECT_TREE.txt").write_text(
        build_tree(files), encoding="utf-8"
    )
    (WORK / "MANIFEST.json").write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "project_root": str(ROOT),
                "file_count": len(files),
                "database_included": False,
                "files": manifest,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (WORK / "UPLOAD_NOTE.txt").write_text(
        "请将同目录生成的 v04d_context_bundle_*.zip 上传到 ChatGPT。\n"
        "压缩包不包含 app.db、日志、备份、虚拟环境或业务数据行。\n",
        encoding="utf-8",
    )

    with zipfile.ZipFile(ZIP_PATH, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(WORK.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(WORK))

    print("=" * 70)
    print("v0.4D context collection completed")
    print(f"Files collected: {len(files)}")
    print(f"Database included: NO")
    print(f"Output: {ZIP_PATH}")
    print("=" * 70)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[ERROR] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
