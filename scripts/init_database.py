from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.database import Base, engine
from app import models  # noqa: F401
from scripts.apply_v04b import apply_v04b
Path("data").mkdir(exist_ok=True)
Base.metadata.create_all(bind=engine)
apply_v04b()
print("数据库初始化成功：data/app.db")
