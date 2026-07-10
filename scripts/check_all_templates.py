from __future__ import annotations

import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, TemplateSyntaxError, TemplateNotFound

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = ROOT / "app" / "templates"


def main() -> int:
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)), autoescape=True)
    files = sorted(TEMPLATE_DIR.rglob("*.html"))
    failures: list[tuple[str, int, str, str]] = []
    for path in files:
        rel = path.relative_to(TEMPLATE_DIR).as_posix()
        try:
            env.get_template(rel)
        except TemplateSyntaxError as exc:
            failures.append((rel, exc.lineno or 0, exc.__class__.__name__, exc.message))
        except TemplateNotFound as exc:
            failures.append((rel, 0, exc.__class__.__name__, str(exc)))
        except Exception as exc:
            failures.append((rel, 0, exc.__class__.__name__, str(exc)))
    print(f"templates_total={len(files)}")
    print(f"templates_passed={len(files) - len(failures)}")
    print(f"templates_failed={len(failures)}")
    for rel, line, kind, message in failures:
        print(f"[FAIL] {rel}:{line}: {kind}: {message}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
