from __future__ import annotations

from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
main_path = ROOT / "app" / "main.py"
base_path = ROOT / "app" / "templates" / "base.html"
source_dir = ROOT / "_v03b_patch_files"

if not main_path.exists():
    raise SystemExit("ERROR: app/main.py not found. Run this file inside the project.")

# Copy new files from staging directory.
copy_map = {
    source_dir / "app" / "analyzer.py": ROOT / "app" / "analyzer.py",
    source_dir / "app" / "paste_router.py": ROOT / "app" / "paste_router.py",
    source_dir / "app" / "templates" / "paste_analyze.html": ROOT / "app" / "templates" / "paste_analyze.html",
    source_dir / "app" / "templates" / "paste_preview.html": ROOT / "app" / "templates" / "paste_preview.html",
    source_dir / "app" / "static" / "v03b_additions.css": ROOT / "app" / "static" / "v03b_additions.css",
    source_dir / "scripts" / "test_paste_analyzer.py": ROOT / "scripts" / "test_paste_analyzer.py",
}
for src, dst in copy_map.items():
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)

# Patch main.py idempotently.
main_text = main_path.read_text(encoding="utf-8")
import_line = "from .paste_router import router as paste_analysis_router"
include_line = "app.include_router(paste_analysis_router)"

if import_line not in main_text:
    marker = "from .models import"
    pos = main_text.find(marker)
    if pos == -1:
        main_text = import_line + "\n" + main_text
    else:
        main_text = main_text[:pos] + import_line + "\n" + main_text[pos:]

if include_line not in main_text:
    marker_candidates = [
        'app.mount("/static"',
        "app.mount('/static'",
    ]
    inserted = False
    for marker in marker_candidates:
        pos = main_text.find(marker)
        if pos != -1:
            line_end = main_text.find("\n", pos)
            main_text = main_text[:line_end+1] + include_line + "\n" + main_text[line_end+1:]
            inserted = True
            break
    if not inserted:
        app_pos = main_text.find("app = FastAPI")
        line_end = main_text.find("\n", app_pos)
        main_text = main_text[:line_end+1] + include_line + "\n" + main_text[line_end+1:]

main_path.write_text(main_text, encoding="utf-8")

# Patch base.html idempotently.
base_text = base_path.read_text(encoding="utf-8")
css_line = '  <link rel="stylesheet" href="{{ url_for(\'static\', path=\'/v03b_additions.css\') }}">'
if "v03b_additions.css" not in base_text:
    base_text = base_text.replace("</head>", css_line + "\n</head>")

if "/analyze/paste" not in base_text:
    nav_candidates = [
        '<a href="/intelligence">情报</a>',
        '<a href="/intelligence">情报库</a>',
    ]
    inserted = False
    for marker in nav_candidates:
        if marker in base_text:
            base_text = base_text.replace(
                marker,
                marker + '<a href="/analyze/paste">智能粘贴</a>',
                1,
            )
            inserted = True
            break
    if not inserted:
        base_text = base_text.replace(
            "</nav>",
            '<a href="/analyze/paste">智能粘贴</a></nav>',
            1,
        )

base_path.write_text(base_text, encoding="utf-8")

print("v0.3B patch applied successfully.")
print("Added route: /analyze/paste")
