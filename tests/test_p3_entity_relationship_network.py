from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.security import required_permission
from app.services.canonical_relationship_service import (
    CanonicalRelationshipService,
    ConnectionRecommendationService,
    RelationshipNetworkService,
    list_relationship_types,
)
from app.services.entity_governance_service import (
    EntityMergeService,
    EntityRegistryService,
    EntityResolutionService,
)


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def p3_db(temp_database: Path) -> Path:
    subprocess.run(
        [sys.executable, str(ROOT / "scripts/migrations/006_entity_relationship_network.py"), "--apply", "--db", str(temp_database)],
        cwd=ROOT, check=True, capture_output=True, text=True,
    )
    return temp_database


@pytest.fixture
def subjects(p3_db: Path) -> dict[str, list[str]]:
    with sqlite3.connect(p3_db) as conn:
        return {
            "people": [str(row[0]) for row in conn.execute("SELECT external_id FROM people WHERE external_id IS NOT NULL ORDER BY id LIMIT 5")],
            "organizations": [str(row[0]) for row in conn.execute("SELECT external_id FROM organizations WHERE external_id IS NOT NULL ORDER BY id LIMIT 5")],
            "projects": [str(row[0]) for row in conn.execute("SELECT external_id FROM projects WHERE external_id IS NOT NULL ORDER BY id LIMIT 2")],
        }


def make_product(db: Path, owner: str, name: str = "P3 test asset") -> dict:
    return EntityRegistryService(db).create_product(
        name, asset_type="drug", actor="tester", permissions={"edit_data"},
        owner_organization_id=owner, is_pilot=True, pilot_batch_id="P3-PYTEST",
    )


def evidence(label: str = "verified source") -> list[dict]:
    return [{"evidence_text": label, "source_url": "https://example.invalid/p3", "evidence_strength": "supporting"}]


def approved_relation(db: Path, *, subject_type: str, subject_id: str, relation_type: str, object_type: str, object_id: str, with_evidence: bool = True, valid_to: str | None = None) -> dict:
    service = CanonicalRelationshipService(db)
    candidate = service.create_candidate(
        subject_type=subject_type, subject_id=subject_id, relationship_type=relation_type,
        object_type=object_type, object_id=object_id, actor="tester", confidence=80,
        evidence=evidence() if with_evidence else [], valid_from="2018-01-01" if valid_to else "2023-01-01", valid_to=valid_to,
        is_pilot=True, pilot_batch_id="P3-PYTEST",
    )
    return service.review_candidate(candidate["id"], "approved", actor="reviewer", permissions={"review_data"})["relationship"]


def test_migration_is_idempotent(p3_db: Path):
    subprocess.run([sys.executable, str(ROOT / "scripts/migrations/006_entity_relationship_network.py"), "--apply", "--db", str(p3_db)], cwd=ROOT, check=True, capture_output=True, text=True)
    with sqlite3.connect(p3_db) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert conn.execute("SELECT COUNT(*) FROM p3_relationship_type_registry").fetchone()[0] == 43


def test_product_asset_is_separate_from_project(p3_db: Path, subjects: dict):
    product = make_product(p3_db, subjects["organizations"][0])
    with sqlite3.connect(p3_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM p3_product_assets WHERE external_id=?", (product["external_id"],)).fetchone()[0] == 1
        assert conn.execute("SELECT COUNT(*) FROM projects WHERE external_id=?", (product["external_id"],)).fetchone()[0] == 0


def test_alias_and_public_identifier(p3_db: Path, subjects: dict):
    service = EntityRegistryService(p3_db)
    org = subjects["organizations"][0]
    alias = service.add_alias("organization", org, "P3 测试简称", alias_type="short_name", actor="reviewer", permissions={"review_data"})
    identifier = service.add_external_identifier("organization", org, "official_domain", "https://www.example.org/about", actor="reviewer", permissions={"review_data"})
    assert alias["review_status"] == "approved"
    assert identifier["normalized_value"] == "example.org"
    assert identifier["is_sensitive"] == 0


def test_same_name_person_is_weak_without_context(p3_db: Path, subjects: dict):
    registry = EntityRegistryService(p3_db)
    person = registry.get("person", subjects["people"][0])
    candidate = EntityResolutionService(p3_db).propose("person", person["canonical_label"], actor="test")[0]
    assert candidate["match_strength"] == "weak"
    assert candidate["resolution_status"] == "ambiguous"


def test_exact_public_identifier_is_strong(p3_db: Path, subjects: dict):
    org = subjects["organizations"][0]
    EntityRegistryService(p3_db).add_external_identifier("organization", org, "official_domain", "strong.example", actor="reviewer", permissions={"review_data"})
    candidate = EntityResolutionService(p3_db).propose("organization", "unrelated spelling", external_identifiers={"official_domain": "https://strong.example"})[0]
    assert candidate["possible_entity_id"] == org
    assert candidate["match_strength"] == "strong"


def test_alias_match_is_medium(p3_db: Path, subjects: dict):
    org = subjects["organizations"][0]
    EntityRegistryService(p3_db).add_alias("organization", org, "Medium Alias", alias_type="english_name", actor="reviewer", permissions={"review_data"})
    assert EntityResolutionService(p3_db).propose("organization", "Medium Alias")[0]["match_strength"] == "medium"


def test_resolution_review_requires_permission(p3_db: Path, subjects: dict):
    person = EntityRegistryService(p3_db).get("person", subjects["people"][0])
    candidate = EntityResolutionService(p3_db).propose("person", person["canonical_label"])[0]
    with pytest.raises(PermissionError, match="review_data_required"):
        EntityResolutionService(p3_db).review(candidate["id"], "matched", actor="viewer", permissions=set())


def test_relationship_type_registry_covers_five_groups(p3_db: Path):
    rows = list_relationship_types(p3_db)
    assert len(rows) == 43
    assert {row["category"] for row in rows} == {"person_organization", "organization_organization", "organization_product", "person_asset_project", "project_organization"}


def test_relationship_endpoint_type_is_validated(p3_db: Path, subjects: dict):
    with pytest.raises(ValueError, match="endpoint_type_mismatch"):
        CanonicalRelationshipService(p3_db).create_candidate(subject_type="person", subject_id=subjects["people"][0], relationship_type="develops", object_type="organization", object_id=subjects["organizations"][0], actor="test")


def test_high_risk_relationship_needs_evidence(p3_db: Path, subjects: dict):
    product = make_product(p3_db, subjects["organizations"][0])
    service = CanonicalRelationshipService(p3_db)
    candidate = service.create_candidate(subject_type="organization", subject_id=subjects["organizations"][0], relationship_type="develops", object_type="product", object_id=product["external_id"], actor="test")
    with pytest.raises(ValueError, match="requires_evidence"):
        service.review_candidate(candidate["id"], "approved", actor="reviewer", permissions={"review_data"})


def test_evidence_is_structured_and_retained_on_archive(p3_db: Path, subjects: dict):
    product = make_product(p3_db, subjects["organizations"][0])
    relationship = approved_relation(p3_db, subject_type="organization", subject_id=subjects["organizations"][0], relation_type="develops", object_type="product", object_id=product["external_id"])
    service = CanonicalRelationshipService(p3_db)
    detail = service.detail(relationship["id"])
    assert detail["evidence_status"] == "evidence_backed" and len(detail["evidence"]) == 1
    service.archive(relationship["id"], actor="reviewer", permissions={"review_data"}, reason="superseded")
    assert len(service.detail(relationship["id"])["evidence"]) == 1


def test_manual_unverified_relationship_can_be_low_risk(p3_db: Path, subjects: dict):
    relation = approved_relation(p3_db, subject_type="person", subject_id=subjects["people"][0], relation_type="employed_by", object_type="organization", object_id=subjects["organizations"][0], with_evidence=False)
    assert relation["evidence_status"] == "manual_unverified"


def test_temporal_overlap_creates_conflict_candidate(p3_db: Path, subjects: dict):
    approved_relation(p3_db, subject_type="person", subject_id=subjects["people"][0], relation_type="employed_by", object_type="organization", object_id=subjects["organizations"][0])
    candidate = CanonicalRelationshipService(p3_db).create_candidate(subject_type="person", subject_id=subjects["people"][0], relationship_type="employed_by", object_type="organization", object_id=subjects["organizations"][0], actor="test", valid_from="2024-01-01")
    assert candidate["status"] == "conflict"
    assert json.loads(candidate["conflict_relationship_ids_json"])


def test_history_filter(p3_db: Path, subjects: dict):
    approved_relation(p3_db, subject_type="person", subject_id=subjects["people"][0], relation_type="formerly_employed_by", object_type="organization", object_id=subjects["organizations"][0], valid_to="2020-12-31")
    service = CanonicalRelationshipService(p3_db)
    assert service.entity_relationships("person", subjects["people"][0], history=False) == []
    assert len(service.entity_relationships("person", subjects["people"][0], history=True)) == 1


def test_merge_preview_does_not_mutate_source(p3_db: Path, subjects: dict):
    source, target = subjects["organizations"][:2]
    record = EntityMergeService(p3_db).preview("organization", source, target, reason="preview test", actor="tester")
    assert record["merge_status"] == "preview"
    assert EntityRegistryService(p3_db).get("organization", source)["redirected"] is False


def test_merge_execute_redirect_and_rollback(p3_db: Path, subjects: dict):
    source, target = subjects["organizations"][:2]
    service = EntityMergeService(p3_db)
    record = service.preview("organization", source, target, reason="verified duplicate", actor="tester", evidence=[{"proof": "test"}])
    service.submit(record["id"], actor="tester", permissions={"edit_data"})
    service.execute(record["id"], actor="reviewer", permissions={"review_data"})
    assert EntityRegistryService(p3_db).resolve_redirect("organization", source) == target
    rolled = service.rollback(record["id"], actor="reviewer", permissions={"review_data"}, reason="acceptance rollback")
    assert rolled["merge_status"] == "rolled_back"
    assert EntityRegistryService(p3_db).resolve_redirect("organization", source) == source


def test_path_engine_returns_two_hops(p3_db: Path, subjects: dict):
    product = make_product(p3_db, subjects["organizations"][0])
    approved_relation(p3_db, subject_type="person", subject_id=subjects["people"][0], relation_type="employed_by", object_type="organization", object_id=subjects["organizations"][0])
    approved_relation(p3_db, subject_type="organization", subject_id=subjects["organizations"][0], relation_type="develops", object_type="product", object_id=product["external_id"])
    result = RelationshipNetworkService(p3_db).find_paths("person", subjects["people"][0], "product", product["external_id"])
    assert result["paths"][0]["hops"] == 2
    assert result["limits"]["max_depth"] == 3


def test_path_engine_caps_depth_at_three(p3_db: Path, subjects: dict):
    result = RelationshipNetworkService(p3_db).find_paths("person", subjects["people"][0], "organization", subjects["organizations"][0], max_depth=99)
    assert result["limits"]["max_depth"] == 3


def test_connection_candidates_require_evidence(p3_db: Path, subjects: dict):
    org = subjects["organizations"][0]
    approved_relation(p3_db, subject_type="person", subject_id=subjects["people"][0], relation_type="employed_by", object_type="organization", object_id=org, with_evidence=False)
    approved_relation(p3_db, subject_type="person", subject_id=subjects["people"][1], relation_type="employed_by", object_type="organization", object_id=org, with_evidence=False)
    assert ConnectionRecommendationService(p3_db).recommend(subjects["people"][0]) == []


def test_connection_candidate_is_explainable_and_not_an_action(p3_db: Path, subjects: dict):
    org = subjects["organizations"][0]
    for person in subjects["people"][:2]:
        approved_relation(p3_db, subject_type="person", subject_id=person, relation_type="employed_by", object_type="organization", object_id=org)
    rows = ConnectionRecommendationService(p3_db).recommend(subjects["people"][0], persist=True)
    assert rows[0]["reason"]["hops"] == 2
    assert "不代表联系授权" in rows[0]["risk_note"]


def test_p3_permission_mapping():
    assert required_permission("/network/merges/1/approve", "POST") == "review_data"
    assert required_permission("/network/merges/preview", "POST") == "edit_data"
    assert required_permission("/api/v1/entity-network/relationship-candidates/1/review", "POST") == "review_data"
    assert required_permission("/api/v1/entity-network/paths", "GET") == "view_internal"


def test_web_entry_and_empty_queues_are_discoverable(p3_db: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("APP_AUTH_DISABLED", "1")
    from app.main import app
    with TestClient(app) as client:
        network = client.get("/network")
        governance = client.get("/network/governance")
        relationships = client.get("/network/relationship-candidates")
        admin = client.get("/admin/platform")
    assert network.status_code == governance.status_code == relationships.status_code == 200
    assert admin.status_code == 200
    assert "/network/governance" not in network.text
    assert "/network/governance" in admin.text
    assert "暂无消歧候选" in governance.text
    assert "暂无关系候选" in relationships.text
