import os
import hashlib
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

official_db = PROJECT_ROOT / "data" / "app.db"
print(f"正式数据库路径: {official_db}")

sha256_hash = hashlib.sha256(official_db.read_bytes()).hexdigest()
print(f"正式数据库SHA256: {sha256_hash}")

acceptance_dir = PROJECT_ROOT / "data" / "acceptance"
acceptance_dir.mkdir(parents=True, exist_ok=True)

acceptance_db = acceptance_dir / "t5_1_mvp.db"

shutil.copy2(official_db, acceptance_db)
print(f"验收数据库已创建: {acceptance_db}")

acceptance_sha256 = hashlib.sha256(acceptance_db.read_bytes()).hexdigest()
print(f"验收数据库SHA256: {acceptance_sha256}")
print(f"复制验证: {'成功' if sha256_hash == acceptance_sha256 else '失败'}")
