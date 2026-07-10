from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
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


def _backup_row(backup_id: str, db_path: str | Path | None = None) -> dict[str, Any] | None:
    with db_connection(db_path) as conn:
        row = conn.execute("SELECT * FROM backup_records WHERE backup_id=?", (backup_id,)).fetchone()
        return dict(row) if row else None


def validate_backup(backup_id: str, *, db_path: str | Path | None = None) -> dict[str, Any]:
    row = _backup_row(backup_id, db_path=db_path)
    if not row:
        return {"ok": False, "message": "备份记录不存在"}
    path = Path(row["backup_path"])
    if not path.exists():
        return {"ok": False, "message": "备份文件不存在"}
    digest_ok = _sha256(path) == row.get("sha256")
    zip_ok = zipfile.is_zipfile(path)
    manifest_ok = False
    if zip_ok:
        with zipfile.ZipFile(path) as zf:
            manifest_ok = "manifest.json" in zf.namelist()
    return {"ok": bool(digest_ok and zip_ok and manifest_ok), "digest_ok": digest_ok, "zip_ok": zip_ok, "manifest_ok": manifest_ok, "backup_path": str(path)}


def restore_backup(backup_id: str, *, dry_run: bool = True, confirm: bool = False, target_path: str | Path | None = None, db_path: str | Path | None = None, created_by: str = "manual") -> dict[str, Any]:
    validation = validate_backup(backup_id, db_path=db_path)
    status = "validated" if validation["ok"] and dry_run else "failed"
    restore_id = ""
    settings = get_settings()
    target = Path(target_path) if target_path else settings.sqlite_path
    if validation["ok"] and confirm and not dry_run:
        current_backup = target.with_suffix(target.suffix + f".before_restore_{now().replace(':', '').replace('-', '')}.bak")
        if target.exists():
            shutil.copy2(target, current_backup)
        row = _backup_row(backup_id, db_path=db_path)
        assert row is not None
        with zipfile.ZipFile(row["backup_path"]) as zf:
            zf.extract("database/app.db", target.parent)
        extracted = target.parent / "database" / "app.db"
        shutil.move(str(extracted), target)
        try:
            (target.parent / "database").rmdir()
        except OSError:
            pass
        status = "restored"
    with db_connection(db_path) as conn:
        restore_id = next_uid(conn, "RST")
        conn.execute(
            "INSERT INTO restore_records(restore_id,backup_id,status,dry_run,target_path,validation_json,created_by,created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (restore_id, backup_id, status, int(dry_run), str(target), json.dumps(validation, ensure_ascii=False), created_by, now()),
        )
    return {"restore_id": restore_id, "status": status, "dry_run": dry_run, "validation": validation, "target_path": str(target)}


def list_restore_records(*, db_path: str | Path | None = None) -> dict[str, Any]:
    with db_connection(db_path) as conn:
        rows = [dict(r) for r in conn.execute("SELECT * FROM restore_records ORDER BY id DESC LIMIT 50").fetchall()]
    return {"data": rows}
