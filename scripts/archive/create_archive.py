from __future__ import annotations

import csv
import hashlib
import os
import shutil
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent.parent
ARCHIVE_DIR = BASE_DIR.parent / "biopharma-intelligence-archive" / "p1-2"

TARGET_PATTERNS = [
    "backups/code_before_v06*",
    "backup_before_v05m_recovery*",
    "patches/v05*",
]

def compute_sha256(filepath: Path) -> str:
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()

def count_files_and_size(root: Path) -> tuple[int, int]:
    count = 0
    size = 0
    for path in root.rglob("*"):
        if path.is_file():
            count += 1
            size += path.stat().st_size
    return count, size

def main():
    ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
    
    manifest = []
    archived_count = 0
    blocked_count = 0
    total_size = 0
    
    timestamp = datetime.now().isoformat()
    
    for pattern in TARGET_PATTERNS:
        for target in BASE_DIR.glob(pattern):
            if not target.exists():
                continue
            
            if target.is_file():
                continue
            
            count, size = count_files_and_size(target)
            
            archive_rel_path = target.relative_to(BASE_DIR)
            archive_path = ARCHIVE_DIR / archive_rel_path
            
            if archive_path.exists():
                timestamp_suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
                archive_path = ARCHIVE_DIR / f"{archive_rel_path}_{timestamp_suffix}"
            
            original_sha256 = ""
            if count > 0:
                first_file = next(target.rglob("*"))
                while not first_file.is_file() and list(target.rglob("*")):
                    first_file = next(target.rglob("*"))
                if first_file.is_file():
                    original_sha256 = compute_sha256(first_file)
            
            shutil.move(str(target), str(archive_path))
            
            restore_cmd = f"mv \"{archive_path}\" \"{BASE_DIR / archive_rel_path}\""
            
            manifest.append({
                "original_path": str(archive_rel_path),
                "archive_path": str(archive_path),
                "file_count": count,
                "size": size,
                "sha256": original_sha256,
                "category": "backup" if pattern.startswith("backups") else "patch",
                "reason": "Historical backup/patch covered by Git",
                "archived_at": timestamp,
                "restore_command": restore_cmd
            })
            
            archived_count += 1
            total_size += size
            print(f"Archived: {target} -> {archive_path}")
    
    with open(BASE_DIR / "docs" / "audit" / "P1_2_ARCHIVE_MANIFEST.csv", "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=manifest[0].keys())
        writer.writeheader()
        writer.writerows(manifest)
    
    print(f"\n=== Archive Complete ===")
    print(f"Archived directories: {archived_count}")
    print(f"Total size: {total_size / 1024 / 1024:.1f} MB")
    print(f"Blocked directories: {blocked_count}")
    print(f"Manifest saved to: docs/audit/P1_2_ARCHIVE_MANIFEST.csv")

if __name__ == "__main__":
    main()