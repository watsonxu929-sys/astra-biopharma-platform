from datetime import datetime
from pathlib import Path
import shutil
ROOT = Path(__file__).resolve().parents[1]
source = ROOT / "data" / "app.db"
backup_dir = ROOT / "data" / "backups"
backup_dir.mkdir(parents=True, exist_ok=True)
if not source.exists():
    raise SystemExit("ERROR: data/app.db does not exist.")
target = backup_dir / f"app_{datetime.now():%Y%m%d_%H%M%S}.db"
shutil.copy2(source, target)
print(f"BACKUP CREATED: {target}")
