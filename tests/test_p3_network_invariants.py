from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from app.services.canonical_relationship_service import CanonicalRelationshipService, ConnectionRecommendationService, RelationshipNetworkService
from app.services.entity_governance_service import EntityMergeService

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def network_db(temp_database: Path) -> tuple[Path, list[str], list[str]]:
    subprocess.run([sys.executable, str(ROOT / "scripts/migrations/006_entity_relationship_network.py"), "--apply", "--db", str(temp_database)], cwd=ROOT, check=True, capture_output=True, text=True)
    with sqlite3.connect(temp_database) as conn:
        people = [str(row[0]) for row in conn.execute("SELECT external_id FROM people WHERE external_id IS NOT NULL ORDER BY id LIMIT 4")]
        orgs = [str(row[0]) for row in conn.execute("SELECT external_id FROM organizations WHERE external_id IS NOT NULL ORDER BY id LIMIT 4")]
    return temp_database, people, orgs


def create(service: CanonicalRelationshipService, subject_type: str, subject_id: str, rel_type: str, object_type: str, object_id: str, *, visibility: str = "internal", approve: bool = True, source_count: int = 1):
    evidence = [{"evidence_text": f"source-{index}", "source_url": f"https://example.invalid/{index}"} for index in range(source_count)]
    candidate = service.create_candidate(subject_type=subject_type, subject_id=subject_id, relationship_type=rel_type, object_type=object_type, object_id=object_id, actor="test", evidence=evidence, visibility=visibility)
    if not approve:
        return candidate
    return service.review_candidate(candidate["id"], "approved", actor="reviewer", permissions={"review_data"})["relationship"]


def test_unapproved_candidate_is_not_in_network(network_db):
    db, people, orgs = network_db
    create(CanonicalRelationshipService(db), "person", people[0], "employed_by", "organization", orgs[0], approve=False)
    assert RelationshipNetworkService(db).find_paths("person", people[0], "organization", orgs[0])["paths"] == []


def test_merge_cannot_execute_before_approval(network_db):
    db, _, orgs = network_db
    record = EntityMergeService(db).preview("organization", orgs[0], orgs[1], reason="preview only", actor="test")
    with pytest.raises(ValueError, match="not_pending_approval"):
        EntityMergeService(db).execute(record["id"], actor="reviewer", permissions={"review_data"})


def test_invalid_period_is_rejected(network_db):
    db, people, orgs = network_db
    with pytest.raises(ValueError, match="invalid_relationship_period"):
        CanonicalRelationshipService(db).create_candidate(subject_type="person", subject_id=people[0], relationship_type="employed_by", object_type="organization", object_id=orgs[0], actor="test", valid_from="2025-01-01", valid_to="2020-01-01")


def test_multiple_sources_are_counted_and_linked(network_db):
    db, people, orgs = network_db
    row = create(CanonicalRelationshipService(db), "person", people[0], "employed_by", "organization", orgs[0], source_count=2)
    detail = CanonicalRelationshipService(db).detail(row["id"])
    assert detail["source_count"] == 2
    assert len(detail["evidence"]) == 2


def test_one_hop_and_no_path_results(network_db):
    db, people, orgs = network_db
    create(CanonicalRelationshipService(db), "person", people[0], "employed_by", "organization", orgs[0])
    network = RelationshipNetworkService(db)
    assert network.find_paths("person", people[0], "organization", orgs[0])["paths"][0]["hops"] == 1
    assert network.find_paths("person", people[1], "organization", orgs[1])["paths"] == []


def test_cycles_do_not_repeat_nodes(network_db):
    db, _, orgs = network_db
    service = CanonicalRelationshipService(db)
    for left, right in ((orgs[0], orgs[1]), (orgs[1], orgs[2]), (orgs[2], orgs[0])):
        create(service, "organization", left, "strategic_partner_of", "organization", right)
    result = RelationshipNetworkService(db).find_paths("organization", orgs[0], "organization", orgs[2], max_depth=3)
    assert result["paths"]
    for path in result["paths"]:
        keys = [(node["type"], node["id"]) for node in path["nodes"]]
        assert len(keys) == len(set(keys))


def test_restricted_relationship_is_filtered_by_default(network_db):
    db, people, orgs = network_db
    create(CanonicalRelationshipService(db), "person", people[0], "employed_by", "organization", orgs[0], visibility="restricted")
    network = RelationshipNetworkService(db)
    assert network.find_paths("person", people[0], "organization", orgs[0])["paths"] == []
    assert network.find_paths("person", people[0], "organization", orgs[0], include_private=True)["paths"][0]["hops"] == 1


def test_directly_connected_person_is_not_recommended(network_db):
    db, people, orgs = network_db
    with sqlite3.connect(db) as conn:
        ts = "2026-01-01T00:00:00"
        conn.execute("INSERT INTO p3_relationship_type_registry(relationship_type,display_name,reverse_display_name,category,subject_types_json,object_types_json,is_symmetric,risk_level,active,created_at,updated_at) VALUES ('knows_for_test','认识','认识','person_organization','[\"person\"]','[\"person\"]',1,'low',1,?,?)", (ts, ts))
    service = CanonicalRelationshipService(db)
    create(service, "person", people[0], "knows_for_test", "person", people[1])
    create(service, "person", people[0], "employed_by", "organization", orgs[0])
    create(service, "person", people[1], "employed_by", "organization", orgs[0])
    assert all(item["recommended_person_id"] != people[1] for item in ConnectionRecommendationService(db).recommend(people[0]))
