import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app

def collect_routes(router, prefix=""):
    routes = []
    for route in router.routes:
        if hasattr(route, 'path'):
            path = prefix + route.path
            methods = sorted(route.methods) if hasattr(route, 'methods') else []
            routes.append((path, methods))
        elif hasattr(route, 'routes'):
            new_prefix = prefix + (route.prefix if hasattr(route, 'prefix') else '')
            routes.extend(collect_routes(route, new_prefix))
    return routes

print("=== FastAPI Registered Routes ===")
print()

routes = collect_routes(app)
routes.sort(key=lambda x: x[0])

filtered = [r for r in routes if r[0].startswith('/network') or r[0].startswith('/club') or r[0].startswith('/collaboration') or r[0].startswith('/admin')]

for path, methods in filtered:
    methods_str = ', '.join(methods)
    print(f"{path} [{methods_str}]")
