from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import ROOT, get_settings
from app.services.tasks.task_common import db_connection, next_uid, now


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def create_backup(*, backup_type: str = "manual", created_by: str = "manual", db_path: str | Path | None = None, target_dir: str | Path | None = None) -> dict[str, Any]:
    settings = get_settings()
    backup_root = Path(target_dir) if target_dir else ROOT / "data" / "backups" / "v05kl"
    backup_root.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    backup_id = f"BKP-{stamp}"
    package = backup_root / f"{backup_id}.zip"
    source_db = Path(db_path) if db_path else settings.sqlite_path
    manifest: dict[str, Any] = {
        "backup_id": backup_id,
        "backup_type": backup_type,
        "environment": settings.app_env,
        "database_backend": settings.db_backend,
        "created_at": now(),
        "files": [],
    }
    temp_db = backup_root / f"{backup_id}_app.db"
    if settings.db_backend == "sqlite" and source_db.exists():
        src = sqlite3.connect(source_db)
        dst = sqlite3.connect(temp_db)
        try:
            src.backup(dst)
        finally:
            dst.close()
            src.close()
        manifest["files"].append({"path": "database/app.db", "type": "sqlite"})
    config_files = [ROOT / ".env.example", ROOT / "config" / "pilot_sources.yaml"]
    with zipfile.ZipFile(package, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        if temp_db.exists():
            zf.write(temp_db, "database/app.db")
        for path in config_files:
            if path.exists():
                zf.write(path, f"config/{path.name}")
                manifest["files"].append({"path": f"config/{path.name}", "type": "config_template"})
        zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2))
    if temp_db.exists():
        temp_db.unlink()
    digest = _sha256(package)
    size = package.stat().st_size
    with db_connection(db_path) as conn:
        conn.execute(
            """
            INSERT INTO backup_records(backup_id,backup_type,status,environment,database_backend,backup_path,manifest_json,sha256,size_bytes,created_by,created_at)
            VALUES (?, ?, 'success', ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (backup_id, backup_type, settings.app_env, settings.db_backend, str(package), json.dumps(manifest, ensure_ascii=False), digest, size, created_by, now()),
        )
    return {"backup_id": backup_id, "backup_path": str(package), "sha256": digest, "size_bytes": size, "manifest": manifest}


def list_backups(*, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM backup_records ORDER BY id DESC LIMIT 50").fetchall()]
    return {"data": rows}
