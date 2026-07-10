from __future__ import annotations

import sqlite3
import sys
import tempfile
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.database import Base  # noqa: E402
from app.models import ActionItem, HistoricalEvent, Organization, Person, ProjectPool, Relation, Resource  # noqa: E402
from app.services.subject_profile_service import subject_center, subject_profile  # noqa: E402
from app.v04c_review import db_connection  # noqa: E402
from app.v04e_entity_resolution import (  # noqa: E402
    add_alias,
    candidate_detail,
    deactivate_alias,
    decide_candidate,
    ensure_v04e_schema,
    scan_duplicates,
    search_entities,
)


def check(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)
    print(f"[PASS] {message}")


def create_resolution_tables(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(
            """
            CREATE TABLE organizations(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT NOT NULL UNIQUE,
                standard_name TEXT NOT NULL,
                org_type TEXT,
                region TEXT,
                industry_tags TEXT,
                resources TEXT,
                needs TEXT,
                relationship_source TEXT,
                visibility TEXT DEFAULT 'internal',
                verification_status TEXT DEFAULT 'pending',
                source_url TEXT,
                source_type TEXT,
                source_title TEXT,
                source_text TEXT,
                captured_at TEXT,
                analyzed_at TEXT,
                model_version TEXT,
                manually_confirmed INTEGER DEFAULT 0,
                auto_generated_fields TEXT,
                confirmed_fields TEXT,
                is_active INTEGER DEFAULT 1,
                deactivated_at TEXT,
                deactivated_reason TEXT,
                subject_match_method TEXT,
                subject_matched_at TEXT,
                subject_manually_confirmed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE people(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                public_role TEXT,
                organization_network TEXT,
                ability_tags TEXT,
                value_provided TEXT,
                relationship_source TEXT,
                visibility TEXT DEFAULT 'internal',
                verification_status TEXT DEFAULT 'pending',
                source_url TEXT,
                source_type TEXT,
                source_title TEXT,
                source_text TEXT,
                captured_at TEXT,
                analyzed_at TEXT,
                model_version TEXT,
                manually_confirmed INTEGER DEFAULT 0,
                auto_generated_fields TEXT,
                confirmed_fields TEXT,
                is_active INTEGER DEFAULT 1,
                deactivated_at TEXT,
                deactivated_reason TEXT,
                subject_match_method TEXT,
                subject_matched_at TEXT,
                subject_manually_confirmed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE projects(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                external_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL,
                project_type TEXT,
                owner_external_id TEXT,
                stage TEXT,
                tags TEXT,
                needs TEXT,
                visibility TEXT DEFAULT 'internal',
                verification_status TEXT DEFAULT 'pending',
                is_active INTEGER DEFAULT 1,
                source_title TEXT,
                source_url TEXT,
                created_at TEXT
            );
            """
        )
        conn.executemany(
            """
            INSERT INTO organizations(
                external_id, standard_name, org_type, region, visibility,
                verification_status, is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            [
                ("ORG-001", "Huachen Bio Technology Limited", "biotech", "Shanghai", "internal", "confirmed", "2026-06-29"),
                ("ORG-002", "Huachen Bio", "biotech", "Shanghai", "internal", "pending", "2026-06-29"),
                ("ORG-003", "Huajing Bio", "biotech", "Beijing", "internal", "pending", "2026-06-29"),
            ],
        )
        conn.executemany(
            """
            INSERT INTO people(
                external_id, name, public_role, organization_network, visibility,
                verification_status, is_active, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, ?)
            """,
            [
                ("PER-001", "Zhang Wei", "CEO, Huachen Bio", "Huachen Bio", "internal", "pending", "2026-06-29"),
                ("PER-002", "Zhang Wei", "Hospital director", "Some Hospital", "internal", "pending", "2026-06-29"),
            ],
        )
        conn.commit()
    finally:
        conn.close()


def verify_entity_resolution(db_path: Path) -> None:
    create_resolution_tables(db_path)
    ensure_v04e_schema(db_path, allow_migration=True)

    result = scan_duplicates("organization", threshold=0.70, db_path=db_path)
    check(result["created"] >= 1, "similar organizations create duplicate candidates")
    with db_connection(db_path) as conn:
        candidate = conn.execute(
            "SELECT * FROM v04e_duplicate_candidates WHERE left_external_id='ORG-001' AND right_external_id='ORG-002'"
        ).fetchone()
    check(candidate is not None, "legal suffix normalization identifies organization pair")

    detail = candidate_detail(int(candidate["id"]), db_path)
    check(detail["left"] and detail["right"] and detail["comparisons"], "candidate comparison details available")

    decided = decide_candidate(
        int(candidate["id"]),
        "same_entity",
        reviewer="verify",
        note="short name and region match; record decision only, no merge",
        db_path=db_path,
    )
    check(decided["status"] == "same_entity", "manual same-entity decision stored")

    alias = add_alias(
        "organization",
        "ORG-001",
        "HCB Global",
        alias_type="english_name",
        source_note="official English name",
        actor="verify",
        db_path=db_path,
    )
    check(alias["status"] == "active", "entity alias created")
    matches = search_entities("organization", "HCB Global", db_path=db_path)
    check(
        matches and matches[0]["subject_id"] == "ORG-001" and matches[0]["match_type"] == "alias_exact",
        "alias search resolves to canonical entity",
    )

    deactivate_alias(int(alias["id"]), actor="verify", db_path=db_path)
    matches_after = search_entities("organization", "HCB Global", db_path=db_path)
    check(not matches_after, "inactive aliases are excluded from lookup")

    person_result = scan_duplicates("person", threshold=0.70, db_path=db_path)
    check(person_result["created"] >= 1, "same-name people are flagged for cautious review")
    with db_connection(db_path) as conn:
        person_candidate = conn.execute(
            "SELECT * FROM v04e_duplicate_candidates WHERE subject_type='person' LIMIT 1"
        ).fetchone()
        active_before = conn.execute("SELECT COUNT(*) FROM organizations WHERE is_active=1").fetchone()[0]
    check(float(person_candidate["similarity_score"]) <= 0.82, "same-name people without shared evidence receive capped score")
    check(active_before == 3, "scan and decisions do not merge or deactivate entities")


def verify_subject_profiles(db_path: Path) -> None:
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    try:
        with SessionLocal() as db:
            org = Organization(
                external_id="ORG-PROFILE-001",
                standard_name="WuXi AppTec",
                org_type="CRO/CDMO",
                region="Shanghai",
                industry_tags="CXO;drug discovery",
                resources="R&D platform",
                needs="partner leads",
                visibility="internal",
                verification_status="confirmed",
                source_url="https://example.test/org",
                source_title="WuXi public profile",
                source_text="WuXi AppTec provides research and manufacturing services.",
                created_at=datetime(2026, 6, 1),
            )
            person = Person(
                external_id="PER-PROFILE-001",
                name="Li Jing",
                public_role="BD lead",
                organization_network="WuXi AppTec",
                ability_tags="business development;partnering",
                value_provided="industry connection",
                visibility="internal",
                verification_status="confirmed",
                source_url="https://example.test/person",
                source_title="Li Jing profile",
                source_text="Li Jing works with WuXi AppTec.",
                created_at=datetime(2026, 6, 2),
            )
            project = ProjectPool(
                external_id="PRJ-PROFILE-001",
                name="Innovative Drug Partnering",
                project_type="drug project",
                owner_external_id="ORG-PROFILE-001",
                focus_tags="ADC;partnering",
                typical_needs="preclinical cooperation",
                target_actions="contact owner",
                visibility="internal",
                status="active",
                source_url="https://example.test/project",
                source_title="Project profile",
                source_text="The project is initiated by WuXi AppTec.",
                created_at=datetime(2026, 6, 3),
            )
            db.add_all([org, person, project])
            db.flush()
            project.owner_organization_id = org.id
            db.add_all([
                Relation(
                    external_id="REL-PROFILE-001",
                    source_external_id=person.external_id,
                    relation_type="employment",
                    target_external_id=org.external_id,
                    evidence_source="public profile",
                    visibility="internal",
                    verification_status="pending",
                    created_at=datetime(2026, 6, 4),
                ),
                Relation(
                    external_id="REL-PROFILE-002",
                    source_external_id=org.external_id,
                    relation_type="initiates",
                    target_external_id=project.external_id,
                    evidence_source="project profile",
                    visibility="internal",
                    verification_status="pending",
                    created_at=datetime(2026, 6, 5),
                ),
                HistoricalEvent(
                    external_id="EVT-PROFILE-001",
                    event_date="2026-06-06",
                    name="Project kickoff",
                    event_type="partnering",
                    related_entity=org.external_id,
                    related_organization_id=org.id,
                    fact_summary="Project kickoff completed.",
                    visibility="internal",
                    verification_status="pending",
                    created_at=datetime(2026, 6, 6),
                ),
                Resource(
                    external_id="RES-PROFILE-001",
                    owner_external_id=org.external_id,
                    owner_organization_id=org.id,
                    category="R&D resource",
                    description="Preclinical R&D platform",
                    applicable_to="drug partnering",
                    visibility="internal",
                    verification_status="pending",
                    created_at=datetime(2026, 6, 7),
                ),
                ActionItem(
                    external_id="ACT-PROFILE-001",
                    task="Contact Li Jing for project cooperation",
                    target_external_id=org.external_id,
                    target_organization_id=org.id,
                    completion_standard="Initial contact completed and logged",
                    owner="BD operator",
                    priority="P1",
                    status="not_started",
                    suggested_deadline="2026-07-01",
                    created_at=datetime(2026, 6, 8),
                ),
            ])
            db.commit()

            center = subject_center(db, q="WuXi", page=1)
            check(center["total"] >= 1 and center["items"], "subject center searches by name and paginates")
            org_profile = subject_profile(db, "organization", org.external_id)
            person_profile = subject_profile(db, "person", person.external_id)
            project_profile = subject_profile(db, "project", project.external_id)
            check(org_profile["found"], "organization unified profile returns data")
            check(person_profile["found"], "person unified profile returns data")
            check(project_profile["found"], "project unified profile returns data")
            check(org_profile["related"]["people"], "person-organization relation is visible from organization")
            check(person_profile["related"]["organizations"], "person-organization relation is visible from person")
            check(org_profile["related"]["projects"], "organization-project relation is visible from organization")
            check(project_profile["related"]["organizations"], "organization-project relation is visible from project")
            check(org_profile["events"], "events enter subject timeline source set")
            check(org_profile["resources"], "resources enter related resource section")
            check(org_profile["actions"], "actions enter follow-up section")
            check(org_profile["sources"], "source snippets are available without full text dump")
            check(org_profile["review"]["open_count"] == 0, "missing review table is handled safely")
            check(org_profile["completeness"]["percent"] >= person_profile["completeness"]["percent"] - 50, "completeness score is calculable")
            check(org_profile["paths"], "two-level relation paths are generated")
            path_keys = {
                tuple(part.get("node", {}).get("external_id", part.get("relation", "")) for part in path)
                for path in org_profile["paths"]
            }
            check(len(path_keys) == len(org_profile["paths"]), "relation paths are deduplicated")
            missing = subject_profile(db, "organization", "ORG-NOT-FOUND")
            check(missing["found"] is False, "missing subject returns explicit result")
    finally:
        engine.dispose()


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="v04e_verify_") as tmp:
        tmp_path = Path(tmp)
        verify_entity_resolution(tmp_path / "resolution.db")
        verify_subject_profiles(tmp_path / "profile.db")

    print("ALL V0.4E CHECKS PASSED")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[FAIL] {type(exc).__name__}: {exc}")
        raise
