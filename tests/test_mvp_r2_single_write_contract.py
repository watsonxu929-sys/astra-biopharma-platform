from __future__ import annotations

import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app"
FORMAL_DATABASE = (ROOT / "data" / "app.db").resolve()

CANONICAL_OWNERS = {
    "v06_intelligence_items": "app/services/intelligence_product_service.py",
    "v06_market_resources": "app/services/unified_resource_service.py",
    "p4_resource_match_candidates": "app/services/golden_loop_service.py",
    "v06_opportunities": "app/services/unified_opportunity_service.py",
    "v06_follow_ups": "app/services/unified_opportunity_service.py",
    "v06_collab_tasks": "app/services/unified_opportunity_service.py",
    "p3_canonical_relationships": "app/services/canonical_relationship_service.py",
    "p3_relationship_evidence": "app/services/canonical_relationship_service.py",
}

ORM_OWNERS = {
    "IntelligenceItem": "app/services/intelligence_product_service.py",
    "MarketResource": "app/services/unified_resource_service.py",
    "CooperationOpportunity": "app/services/unified_opportunity_service.py",
    "FollowUp": "app/services/unified_opportunity_service.py",
    "CollabTask": "app/services/unified_opportunity_service.py",
}

LEGACY_PLATFORM_EQUIVALENTS = (
    "resources", "v04f_club_needs", "v04f_club_offerings", "v04f_club_matches", "relations", "actions",
)


def _sources() -> dict[str, str]:
    return {
        path.relative_to(ROOT).as_posix(): path.read_text(encoding="utf-8-sig")
        for path in APP.rglob("*.py")
    }


def test_canonical_owner_manifest_and_static_write_guard() -> None:
    sources = _sources()
    write_verb = r"(?:insert\s+(?:or\s+ignore\s+)?into|update|delete\s+from)"
    for table, owner in CANONICAL_OWNERS.items():
        hits = [name for name, source in sources.items() if re.search(
            rf"{write_verb}\s+{re.escape(table)}\b", source, re.IGNORECASE)]
        assert hits, f"owner write not found for {table}"
        assert set(hits) == {owner}, f"non-owner canonical writer for {table}: {hits}"

    route_hits = []
    canonical_names = "|".join(map(re.escape, CANONICAL_OWNERS))
    for name, source in sources.items():
        if "/services/" not in name and re.search(
            rf"{write_verb}\s+(?:{canonical_names})\b", source, re.IGNORECASE):
            route_hits.append(name)
    assert route_hits == []


def test_canonical_orm_construction_is_owner_only() -> None:
    sources = _sources()
    for model, owner in ORM_OWNERS.items():
        hits = [name for name, source in sources.items()
                if name != "app/models_platform.py" and re.search(rf"\b{model}\s*\(", source)]
        if model == "IntelligenceItem":
            assert hits == []  # Intelligence owner intentionally uses its audited sqlite transaction.
        else:
            assert set(hits) == {owner}, f"non-owner ORM writer for {model}: {hits}"


def test_legacy_platform_equivalent_writers_are_frozen() -> None:
    sources = _sources()
    write_verb = r"(?:insert\s+(?:or\s+ignore\s+)?into|update|delete\s+from)"
    tables = "|".join(map(re.escape, LEGACY_PLATFORM_EQUIVALENTS))
    hits = [(name, match.group(0)) for name, source in sources.items()
            for match in re.finditer(rf"{write_verb}\s+(?:{tables})\b", source, re.IGNORECASE)]
    assert hits == []


def test_golden_loop_uses_temp_database_and_creates_no_legacy_copies(temp_database: Path) -> None:
    target = temp_database.resolve()
    assert target != FORMAL_DATABASE
    assert "test" in target.name.lower()
    legacy_tables = ("resources", "v04f_club_needs", "v04f_club_offerings", "v04f_club_matches", "relations", "actions")
    with sqlite3.connect(target) as conn:
        before = {table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in legacy_tables}

    result = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "verify_mvp_rc1_golden_loop.py"), "--database", str(target)],
        cwd=ROOT, check=False, capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 0, result.stderr or result.stdout
    report = json.loads(result.stdout)
    assert report["trace_counts"] == {
        "subjects": 2, "resources": 6, "matches": 3, "opportunities": 3, "follow_ups": 3, "relationships": 1,
    }
    assert report["case_a"]["relationship_id"]
    assert report["case_b"]["relationship_id"] is None
    assert report["case_c"]["relationship_id"] is None
    assert report["cleanup"] == "complete"
    assert report["marker_residue"] == 0
    assert report["viewer_write_status"] == 403
    assert report["integrity"] == "ok"

    with sqlite3.connect(target) as conn:
        after = {table: conn.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in legacy_tables}
    assert after == before
