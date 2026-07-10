from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.test_db_utils import foreign_key_check, run_migration_suite, temporary_database


def check(results: list[bool], name: str, func) -> None:
    try:
        func()
        print(f"PASS {name}")
        results.append(True)
    except Exception as exc:
        print(f"FAIL {name}: {exc}")
        results.append(False)


def run_script(*args: str) -> None:
    result = subprocess.run([sys.executable, *args], cwd=ROOT, text=True, capture_output=True)
    if result.returncode != 0:
        raise AssertionError(result.stdout + result.stderr)


def main() -> int:
    results: list[bool] = []
    with temporary_database("domain_verify_") as db_path:
        run_migration_suite(db_path)
        check(results, "domain_migration_dry_run", lambda: run_script("scripts/migrate_domain_consolidation_v1.py", "--dry-run"))
        check(results, "domain_migration_apply", lambda: run_script("scripts/migrate_domain_consolidation_v1.py", "--apply"))
        check(results, "domain_migration_idempotent", lambda: run_script("scripts/migrate_domain_consolidation_v1.py", "--apply"))
        check(results, "foreign_key_check_zero", lambda: _zero(foreign_key_check(db_path)))
        check(results, "unified_services_import", lambda: _imports())
    print(f"verify_domain_consolidation_v1 passed={sum(results)} failed={len(results)-sum(results)}")
    return 0 if all(results) else 1


def _zero(value: int) -> None:
    assert value == 0, value


def _imports() -> None:
    from app.services.unified_intelligence_service import UnifiedIntelligenceService
    from app.services.unified_resource_service import UnifiedResourceService
    from app.services.unified_opportunity_service import UnifiedOpportunityService
    from app.services.unified_search_service import UnifiedSearchService
    assert UnifiedIntelligenceService and UnifiedResourceService and UnifiedOpportunityService and UnifiedSearchService


if __name__ == "__main__":
    raise SystemExit(main())
