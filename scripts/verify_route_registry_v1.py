from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.main import app


def path_segments(path: str) -> list[str]:
    return [seg for seg in path.strip("/").split("/") if seg]


def dynamic(seg: str) -> bool:
    return seg.startswith("{") and seg.endswith("}")


def int_param(seg: str, convertors: dict) -> bool:
    if not dynamic(seg):
        return False
    name = seg.strip("{}").split(":", 1)[0]
    if ":int}" in seg:
        return True
    convertor = convertors.get(name)
    return convertor is not None and "integer" in convertor.__class__.__name__.lower()


def main() -> int:
    seen = defaultdict(list)
    names = defaultdict(list)
    routes = []

    def add_route(path: str, methods, name: str, convertors: dict | None = None) -> None:
        if not path:
            return
        convertors = convertors or {}
        for method in sorted(methods or []):
            if method in {"HEAD", "OPTIONS"}:
                continue
            key = (method, path)
            seen[key].append(name)
            names[name].append((method, path))
            routes.append((method, path, name, convertors))

    for route in app.routes:
        contexts = getattr(route, "effective_route_contexts", None)
        if callable(contexts):
            for ctx in contexts():
                add_route(
                    getattr(ctx, "path", ""),
                    getattr(ctx, "methods", set()),
                    getattr(ctx, "name", ""),
                    getattr(ctx, "param_convertors", {}),
                )
            continue
        add_route(
            getattr(route, "path", ""),
            getattr(route, "methods", []) or [],
            getattr(route, "name", ""),
            getattr(route, "param_convertors", {}),
        )

    errors = []
    explained_duplicates = {("GET", "/review"), ("GET", "/review/")}
    for key, handlers in seen.items():
        if len(handlers) > 1 and key not in explained_duplicates:
            errors.append(f"duplicate method/path {key}: {handlers}")

    for method, path, name, convertors in routes:
        segs = path_segments(path)
        for other_method, other_path, other_name, _ in routes:
            if method != other_method or path == other_path:
                continue
            other = path_segments(other_path)
            if len(segs) != len(other):
                continue
            for i, seg in enumerate(segs):
                if (
                    dynamic(seg)
                    and not dynamic(other[i])
                    and not int_param(seg, convertors)
                    and segs[:i] == other[:i]
                    and segs[i + 1 :] == other[i + 1 :]
                ):
                    errors.append(f"static path may be shadowed: {other_path} by {path}")

    for required in ["/intelligence/subscriptions", "/resources/new"]:
        if not any(path == required for _, path, _, _ in routes):
            errors.append(f"missing required static route {required}")

    print(f"route_count={len(routes)}")
    print(f"duplicate_count={sum(1 for v in seen.values() if len(v)>1)}")
    if errors:
        print("route_registry_errors:")
        for error in sorted(set(errors)):
            print(error)
        return 1
    print("route_registry=ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
