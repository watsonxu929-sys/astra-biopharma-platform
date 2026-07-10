from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
STAGE = ROOT / "_v04a_patch_files"

copy_map = {
    STAGE / "app" / "web_extractor.py": ROOT / "app" / "web_extractor.py",
    STAGE / "app" / "templates" / "generic_form.html": ROOT / "app" / "templates" / "generic_form.html",
    STAGE / "app" / "static" / "entity_smart_paste.js": ROOT / "app" / "static" / "entity_smart_paste.js",
    STAGE / "app" / "static" / "v04a_additions.css": ROOT / "app" / "static" / "v04a_additions.css",
}

for source, target in copy_map.items():
    if not source.exists():
        raise SystemExit(f"ERROR: missing patch file: {source}")
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)

main_path = ROOT / "app" / "main.py"
main_text = main_path.read_text(encoding="utf-8")

import_line = "from .web_extractor import fetch_and_extract"
if import_line not in main_text:
    marker = "from .entity_analyzer import analyze_entity"
    if marker in main_text:
        main_text = main_text.replace(marker, marker + "\n" + import_line, 1)
    else:
        main_text = import_line + "\n" + main_text

route_marker = "# === V04A WEB PAGE FETCH API ==="
route_code = """
# === V04A WEB PAGE FETCH API ===
from pydantic import BaseModel as _WebFetchBaseModel


class _WebFetchRequest(_WebFetchBaseModel):
    url: str


@app.post("/manage/fetch-webpage")
def fetch_webpage_for_smart_paste(payload: _WebFetchRequest):
    try:
        result = fetch_and_extract(payload.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "result": result.to_dict(),
        "manual_review_required": True,
    }
"""

if route_marker not in main_text:
    main_text = main_text.rstrip() + "\n\n" + route_code.strip() + "\n"

main_path.write_text(main_text, encoding="utf-8")

base_path = ROOT / "app" / "templates" / "base.html"
base_text = base_path.read_text(encoding="utf-8")

if "v04a_additions.css" not in base_text:
    css_line = (
        '  <link rel="stylesheet" '
        'href="{{ url_for(\'static\', path=\'/v04a_additions.css\') }}">'
    )
    base_text = base_text.replace("</head>", css_line + "\n</head>", 1)

base_path.write_text(base_text, encoding="utf-8")

print("V0.4A WEB FETCH PATCH APPLIED")
