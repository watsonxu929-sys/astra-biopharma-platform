import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DATABASE_URL"] = "sqlite:///data/rehearsal/v06j_app_migrated.db"
os.environ["APP_ENV"] = "testing"
os.environ["ENABLE_SCHEDULER_IN_WEB"] = "false"
os.environ["APP_AUTH_DISABLED"] = "false"

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

all_routes = collect_routes(app)

filtered_prefixes = ['/network', '/club', '/collaboration', '/admin']
filtered_routes = [(path, methods) for path, methods in all_routes if any(path.startswith(p) for p in filtered_prefixes)]

print(f"Total routes with prefixes {filtered_prefixes}: {len(filtered_routes)}")
print("-" * 80)
for path, methods in sorted(filtered_routes):
    print(f"{path:50s} {', '.join(methods)}")