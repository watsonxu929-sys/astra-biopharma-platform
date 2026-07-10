import csv
import sys
from pathlib import Path
from sqlalchemy import select
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from app.database import SessionLocal
from app.models import ActionItem, HistoricalEvent, Organization, Person, ProjectPool, Relation, Resource
EXPORTS = [("organizations", Organization),("people", Person),("projects", ProjectPool),("resources", Resource),("events", HistoricalEvent),("relations", Relation),("actions", ActionItem)]
out_dir = ROOT / "data" / "exports"
out_dir.mkdir(parents=True, exist_ok=True)
db = SessionLocal()
try:
    for name, model in EXPORTS:
        rows = db.scalars(select(model)).all()
        columns = [c.name for c in model.__table__.columns]
        path = out_dir / f"{name}.csv"
        with path.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            for row in rows:
                writer.writerow({col: getattr(row, col) for col in columns})
        print(f"EXPORTED: {path} ({len(rows)} rows)")
finally:
    db.close()
