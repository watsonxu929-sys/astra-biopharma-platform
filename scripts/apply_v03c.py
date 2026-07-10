from pathlib import Path
import shutil
ROOT=Path(__file__).resolve().parents[1]; STAGE=ROOT/'_v03c_patch_files'
for rel in ['app/entity_analyzer.py','app/templates/generic_form.html','app/static/entity_smart_paste.js','app/static/v03c_additions.css']:
    src=STAGE/rel; dst=ROOT/rel; dst.parent.mkdir(parents=True,exist_ok=True); shutil.copy2(src,dst)
m=ROOT/'app/main.py'; text=m.read_text(encoding='utf-8')
if 'from .entity_analyzer import analyze_entity' not in text:
    marker='from .crud_config import ENTITY_CONFIGS'
    text=text.replace(marker,marker+'\nfrom .entity_analyzer import analyze_entity',1) if marker in text else 'from .entity_analyzer import analyze_entity\n'+text
route='''
# === V03C ENTITY SMART PASTE API ===
from pydantic import BaseModel as _SmartPasteBaseModel
class _EntityPasteRequest(_SmartPasteBaseModel):
    text: str
@app.post("/manage/{entity_key}/analyze")
def analyze_entity_paste(entity_key: str, payload: _EntityPasteRequest):
    if entity_key not in ENTITY_CONFIGS:
        raise HTTPException(status_code=404, detail="未知数据类型")
    value=payload.text.strip()
    if len(value)<10:
        raise HTTPException(status_code=400, detail="请至少粘贴10个字符")
    return {"entity":entity_key,"fields":analyze_entity(entity_key,value),"manual_review_required":True}
'''
if '# === V03C ENTITY SMART PASTE API ===' not in text:
    text=text.rstrip()+'\n'+route
m.write_text(text,encoding='utf-8')
b=ROOT/'app/templates/base.html'; bt=b.read_text(encoding='utf-8')
if 'v03c_additions.css' not in bt:
    css='  <link rel="stylesheet" href="{{ url_for(\'static\', path=\'/v03c_additions.css\') }}">'
    bt=bt.replace('</head>',css+'\n</head>',1)
bt=bt.replace('<a href="/analyze/paste">智能粘贴</a>','').replace('<a href="/analyze/paste">智能粘贴分析</a>','')
b.write_text(bt,encoding='utf-8')
print('V0.3C APPLIED')
