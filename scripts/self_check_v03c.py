import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from app.main import app
paths={getattr(r,'path',None) for r in app.routes if getattr(r,'path',None)}
for p in ['/manage/{entity_key}/analyze','/manage/{entity_key}/new','/manage/{entity_key}/{item_id}/edit']:
    ok=p in paths; print(f"[{'PASS' if ok else 'FAIL'}] Web route {p}")
    if not ok: raise SystemExit(1)
print('ALL CHECKS PASSED')
