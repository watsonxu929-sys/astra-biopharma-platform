from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.services.golden_loop_service import GoldenLoopService
from app.services.processing.subject_matching_service import match_subject


ROOT = Path(__file__).resolve().parents[1]


def _session(database: Path) -> Session:
    engine = create_engine(
        f"sqlite:///{database.as_posix()}", connect_args={"check_same_thread": False}
    )
    return Session(engine)


def _published_item(
    database: Path,
    *,
    title: str,
    event_type: str,
    summary: str = "公开产业事实",
    organization_id: int | None = None,
) -> int:
    stamp = datetime.now().replace(microsecond=0).isoformat()
    with sqlite3.connect(database) as conn:
        item_id = conn.execute(
            """INSERT INTO v06_intelligence_items(
                title,summary,intel_type,event_type,importance,source_name,source_url,
                visibility,status,is_demo,created_at,updated_at)
                VALUES (?,?,?, ?,4,'R7.2 official','https://example.invalid/r72',
                        'organization','published',0,?,?)""",
            (title, summary, event_type, event_type, stamp, stamp),
        ).lastrowid
        if organization_id:
            conn.execute(
                """INSERT INTO core_intelligence_subject_links(
                    intelligence_item_id,subject_type,subject_id,created_by_user_id,created_at)
                    VALUES (?,'organization',?,1,?)""",
                (item_id, organization_id, stamp),
            )
        conn.commit()
    return int(item_id)


def _seed_priority_context(database: Path) -> dict[str, int]:
    stamp = datetime.now().replace(microsecond=0).isoformat()
    with sqlite3.connect(database) as conn:
        priority_org_id = int(conn.execute(
            """INSERT INTO organizations(external_id,standard_name,name,visibility,verification_status,is_active,created_at)
               VALUES ('ORG-R72-PRIORITY','R7.2优先企业','R7.2优先企业','内部','已核验',1,?)""", (stamp,),
        ).lastrowid)
        member_org_id = int(conn.execute(
            """INSERT INTO organizations(external_id,standard_name,name,visibility,verification_status,is_active,created_at)
               VALUES ('ORG-R72-MEMBER','R7.2会员企业','R7.2会员企业','内部','已核验',1,?)""", (stamp,),
        ).lastrowid)
        other_org_id = int(conn.execute(
            """INSERT INTO organizations(external_id,standard_name,name,visibility,verification_status,is_active,created_at)
               VALUES ('ORG-R72-OTHER','R7.2普通企业','R7.2普通企业','内部','已核验',1,?)""", (stamp,),
        ).lastrowid)
        person_id = int(conn.execute(
            """INSERT INTO people(external_id,name,visibility,verification_status,is_active,created_at)
               VALUES ('PER-R72-CONTACT','R72 Contact','internal','verified',1,?)""", (stamp,),
        ).lastrowid)
        conn.execute(
            """INSERT INTO v04f_club_memberships(
                member_no,organization_id,member_role,member_level,status,joined_at,created_at,updated_at)
               VALUES ('R72-MEMBER',?,'member','standard','active',?,?,?)""",
            (member_org_id, stamp[:10], stamp, stamp),
        )
        relationship_id = int(conn.execute(
            """INSERT INTO p3_canonical_relationships(
                relationship_no,subject_type,subject_id,relationship_type,object_type,object_id,
                direction,is_current,confidence,review_status,evidence_status,source_count,
                visibility,created_by,reviewed_by,reviewed_at,created_at,updated_at)
               VALUES ('REL-R72','organization','ORG-R72-PRIORITY','contact','person','PER-R72-CONTACT',
                       'directed',1,0.95,'approved','evidence_backed',1,
                       'internal',1,1,?,?,?)""",
            (stamp, stamp, stamp),
        ).lastrowid)
        conn.execute(
            """INSERT INTO p3_relationship_evidence(
                relationship_id,evidence_text,source_url,evidence_strength,evidence_hash,created_at)
               VALUES (?,'R72 isolated evidence','https://example.invalid/r72-evidence',
                       'strong','r72-evidence-hash',?)""",
            (relationship_id, stamp),
        )
        conn.commit()
        item_id = _published_item(
            database, title="R7.2优先企业发布服务能力", event_type="corporate",
            summary="该企业公开提供产业服务能力。", organization_id=priority_org_id,
        )
        conn.execute(
            """INSERT INTO v06_market_resources(
                title,description,direction,resource_type,status,publisher_id,source_intelligence_id,
                organization_id,is_demo,created_at,updated_at,region,visibility)
               VALUES ('R72 existing service','Confirmed isolated service','supply','service','published',
                       1,?,?,0,?,?,'Shanghai','internal')""",
            (item_id, priority_org_id, stamp, stamp),
        )
        conn.commit()
    return {"priority_org": priority_org_id, "member_org": member_org_id,
            "other_org": other_org_id, "person": person_id, "item": item_id}


def test_r7_2_priority_universe_and_context_use_existing_canonical_data(
    temp_database: Path,
) -> None:
    seeded = _seed_priority_context(temp_database)
    with _session(temp_database) as db:
        service = GoldenLoopService(db)
        member = service.subject_priority("organization", seeded["member_org"])
        resource_org = service.subject_priority("organization", seeded["priority_org"])
        unrelated = service.subject_priority("organization", seeded["other_org"])
        trace = service.trace(seeded["item"])
        context = service.opportunity_discovery(seeded["item"], trace=trace)

    assert member["priority"] == "P1"
    assert resource_org["priority"] == "P2"
    assert unrelated["is_priority"] is False
    assert context["priority"]["priority"] == "P2"
    assert context["value_level"] == "LEVEL_2_ACTIONABLE_SIGNAL"
    assert context["resource_signal"] == "POSSIBLE_SUPPLY"
    assert context["qualification"]["eligible"] is False
    assert context["qualification"]["unresolved_need"] is False


def test_r7_2_relationship_context_uses_external_id_and_evidence(
    temp_database: Path,
) -> None:
    seeded = _seed_priority_context(temp_database)
    with _session(temp_database) as db:
        related = GoldenLoopService(db).related_context(seeded["item"])

    assert related["relationships"]
    relationship = related["relationships"][0]
    assert "R72 Contact" in relationship["label"]
    assert relationship["detail"]


def test_r7_2_industry_events_do_not_create_our_opportunity(
    temp_database: Path,
) -> None:
    seeded = _seed_priority_context(temp_database)
    event_types = ("financing", "cooperation", "expansion", "merger", "approval")
    item_ids = [
        _published_item(
            temp_database,
            title=f"R7.2 completed {event_type} event",
            event_type=event_type,
            organization_id=seeded["priority_org"],
        )
        for event_type in event_types
    ]
    with _session(temp_database) as db:
        service = GoldenLoopService(db)
        results = [service.opportunity_discovery(item_id) for item_id in item_ids]

    assert all(result["value_level"] != "LEVEL_3_OUR_OPPORTUNITY" for result in results)
    assert all(result["qualification"]["eligible"] is False for result in results)
    assert all(result["qualification"]["unresolved_need"] is False for result in results)


def test_r7_2_opportunity_requires_all_five_conditions_without_auto_write(
    temp_database: Path,
) -> None:
    seeded = _seed_priority_context(temp_database)
    item_id = _published_item(
        temp_database,
        title="Q-BAY公开征集产业合作伙伴",
        event_type="corporate",
        summary="面向生态企业寻求合作伙伴，需求仍待确认。",
        organization_id=seeded["priority_org"],
    )
    with _session(temp_database) as db:
        service = GoldenLoopService(db)
        before = db.execute(text("SELECT COUNT(*) FROM v06_opportunities")).scalar()
        result = service.opportunity_discovery(item_id)
        after = db.execute(text("SELECT COUNT(*) FROM v06_opportunities")).scalar()

    assert result["qualification"] == {
        "subject_confirmed": True,
        "unresolved_need": True,
        "unresolved_need_evidence": "寻求",
        "capability_context": True,
        "next_action_specific": True,
        "time_valid": True,
        "eligible": True,
    }
    assert before == after


def test_r7_2_organization_normalization_is_exact_or_ambiguous(
    temp_database: Path,
) -> None:
    stamp = datetime.now().replace(microsecond=0).isoformat()
    with sqlite3.connect(temp_database) as conn:
        conn.row_factory = sqlite3.Row
        exact = match_subject(conn, "organization", "星源生物科技")
        conn.execute(
            """INSERT INTO organizations(
                external_id,standard_name,name,visibility,verification_status,is_active,created_at)
                VALUES ('ORG-R72-AMBIGUOUS','星源生物科技集团','星源生物科技集团',
                        '内部','待核验',1,?)""",
            (stamp,),
        )
        ambiguous = match_subject(conn, "organization", "星源生物科技")

    assert exact["status"] == "confirmed"
    assert exact["method"] == "normalized_alias"
    assert ambiguous["status"] == "ambiguous"
    assert ambiguous["ambiguity_count"] == 2


def test_r7_2_workbench_priority_sort_and_product_copy() -> None:
    template = (ROOT / "app/templates/platform/intelligence_detail.html").read_text(
        encoding="utf-8"
    )
    source = (ROOT / "app/services/golden_loop_service.py").read_text(encoding="utf-8")
    assert "为什么值得关注" in template
    assert "与我们的关系" in template
    assert "相关资源" in template
    assert "建立跟进" in template
    assert "def priority_feed" in source
    assert "LEVEL_1_INDUSTRY_INFORMATION" in source
    assert "LEVEL_2_ACTIONABLE_SIGNAL" in source
    assert "LEVEL_3_OUR_OPPORTUNITY" in source
