import sys
from pathlib import Path
from sqlalchemy import func, select
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from app.database import SessionLocal
from app.models import ActionItem, HistoricalEvent, ImportLog, Organization, Person, ProjectPool, Relation, Resource
models=[('organizations',Organization),('people',Person),('resources',Resource),('events',HistoricalEvent),('projects',ProjectPool),('relations',Relation),('actions',ActionItem),('import_logs',ImportLog)]
db=SessionLocal()
try:
    print('SEED DATA COUNTS'); print('='*50)
    for name,model in models:
        c=db.scalar(select(func.count()).select_from(model)) or 0
        print(f'{name:15} {c}')
finally:
    db.close()
