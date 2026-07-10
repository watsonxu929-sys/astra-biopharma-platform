from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.services.operations import list_backups, restore_backup, validate_backup


def main() -> int:
    parser = argparse.ArgumentParser(description="备份恢复工具，默认只演练")
    parser.add_argument("--list", action="store_true", help="列出备份")
    parser.add_argument("--backup-id", default="", help="备份编号")
    parser.add_argument("--dry-run", action="store_true", help="恢复演练")
    parser.add_argument("--validate", action="store_true", help="只校验备份")
    parser.add_argument("--confirm", action="store_true", help="确认正式恢复")
    parser.add_argument("--target-path", default="", help="恢复目标路径；为空时恢复到配置数据库")
    args = parser.parse_args()
    if args.list:
        for row in list_backups()["data"]:
            print(f"{row['backup_id']} {row['status']} {row['backup_path']}")
        return 0
    if not args.backup_id:
        parser.error("--backup-id required unless --list")
    if args.validate:
        print(validate_backup(args.backup_id))
        return 0
    dry_run = args.dry_run or not args.confirm
    print(restore_backup(args.backup_id, dry_run=dry_run, confirm=args.confirm, target_path=args.target_path or None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
