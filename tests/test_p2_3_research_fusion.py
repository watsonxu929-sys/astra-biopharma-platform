from __future__ import annotations

import hashlib
import importlib.util
import sqlite3
from pathlib import Path

import pytest

from app.services.research import add_topic_subject, create_topic
from app.services.research.fusion_service import (
    add_event_evidence,
    add_event_subject,
    classify_event_relation,
    create_assertion,
    create_industry_event,
    event_timeline,
    link_assertion_evidence,
    link_topic_event,
    register_conflict,
    resolve_conflict,
    review_assertion,
    review_event,
    submit_event,
)
from app.services.research.research_engine_service import (
    ResearchAgentService,
    check_report_citations,
    create_finding,
    create_research_report,
    delete_research_report,
    get_research_report,
    review_finding,
    save_report_version,
    submit_finding,
    submit_research_report,
    topic_workspace,
)
from app.settings import resolved_db_path
from app.v04c_review import db_connection


@pytest.fixture
def p23_db(temp_database: Path) -> Path:
    migration_path = Path(__file__).parents[1] / "scripts" / "migrations" / "005_research_fusion_engine.py"
    spec = importlib.util.spec_from_file_location("migration005", migration_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    with sqlite3.connect(temp_database) as conn:
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("BEGIN IMMEDIATE")
        module.apply_schema(conn)
        conn.commit()
        assert not module.analyze(conn)["missing_p2_3_tables"]
    return temp_database


def _topic_and_orgs(db_path: Path):
    topic = create_topic(name="ADC受控研究试点", topic_type="technology", db_path=db_path)
    with db_connection(db_path) as conn:
        orgs = [dict(row) for row in conn.execute(
            "SELECT external_id,standard_name FROM organizations ORDER BY id LIMIT 3"
        )]
    assert len(orgs) >= 3
    for org in orgs:
        add_topic_subject(topic["id"], "organization", org["external_id"], db_path=db_path)
    return topic, orgs


def _approved_fact(db_path: Path, topic_id: int, org: dict, *, title: str = "FDA approves ADC A"):
    with db_connection(db_path) as conn:
        snapshots = [dict(row) for row in conn.execute(
            "SELECT id,page_title,url,captured_at FROM v04g_source_snapshots ORDER BY id LIMIT 2"
        )]
    assert snapshots
    event = create_industry_event(
        title=title, event_type="regulatory_approval", occurred_at="2025-01-30",
        confidence=90, created_by="analyst", db_path=db_path,
    )
    add_event_subject(
        event["id"], subject_type="organization", subject_id=org["external_id"],
        subject_label=org["standard_name"], db_path=db_path,
    )
    evidence = add_event_evidence(
        event["id"], snapshot_id=snapshots[0]["id"], source_organization="FDA",
        source_title=snapshots[0]["page_title"] or "FDA source",
        source_url=snapshots[0]["url"] or "https://www.fda.gov/",
        captured_at=snapshots[0]["captured_at"] or "2025-01-30",
        evidence_excerpt="The FDA approved ADC A on January 30, 2025.", db_path=db_path,
    )
    if len(snapshots) > 1:
        add_event_evidence(
            event["id"], snapshot_id=snapshots[1]["id"], source_organization="EMA",
            source_title=snapshots[1]["page_title"] or "EMA source",
            source_url=snapshots[1]["url"] or "https://www.ema.europa.eu/",
            captured_at=snapshots[1]["captured_at"] or "2025-01-31",
            evidence_excerpt="A second authority reported the approval of ADC A.", db_path=db_path,
        )
    submit_event(event["id"], actor="analyst", db_path=db_path)
    review_event(event["id"], decision="approved", actor="human-reviewer", db_path=db_path)
    link_topic_event(topic_id, event["id"], actor="human-reviewer", db_path=db_path)
    assertion = create_assertion(
        event_id=event["id"], topic_id=topic_id, subject_type="organization",
        subject_id=org["external_id"], subject_label=org["standard_name"],
        predicate="received_regulatory_approval", object_value="ADC A",
        confidence=90, created_by="analyst", db_path=db_path,
    )
    link_assertion_evidence(assertion["id"], evidence["id"], db_path=db_path)
    assertion = review_assertion(
        assertion["id"], decision="approved", actor="human-reviewer", db_path=db_path
    )
    return event, assertion, evidence


def test_event_relation_rules_separate_same_related_and_conflict():
    base = {
        "title": "Company A announces financing",
        "event_type": "financing",
        "subjects": ["Company A"],
        "occurred_at": "2025-01-10",
        "amount_value": 100,
    }
    same = {**base, "title": "Company A financing announced", "occurred_at": "2025-01-11"}
    related = {**base, "title": "Company A closes a later round", "occurred_at": "2025-03-10"}
    conflict = {**base, "title": base["title"], "amount_value": 200}
    assert classify_event_relation(base, same)["relation_type"] == "same_event"
    assert classify_event_relation(base, related)["relation_type"] == "related_event"
    conflict_result = classify_event_relation(base, conflict)
    assert conflict_result["relation_type"] == "conflict"
    assert "amount_value" in conflict_result["conflict_fields"]


def test_multi_source_evidence_and_formal_timeline_require_review(p23_db: Path):
    topic, orgs = _topic_and_orgs(p23_db)
    draft = create_industry_event(
        title="Unreviewed event", event_type="clinical_progress", created_by="analyst", db_path=p23_db
    )
    assert all(row["id"] != draft["id"] for row in event_timeline(topic_id=topic["id"], db_path=p23_db))
    event, _, _ = _approved_fact(p23_db, topic["id"], orgs[0])
    timeline = event_timeline(topic_id=topic["id"], db_path=p23_db)
    assert [row["id"] for row in timeline] == [event["id"]]
    assert timeline[0]["source_count"] >= 1


def test_unresolved_conflict_blocks_event_approval_and_is_not_overwritten(p23_db: Path):
    topic, orgs = _topic_and_orgs(p23_db)
    with db_connection(p23_db) as conn:
        snapshot = dict(conn.execute("SELECT id,url,page_title,captured_at FROM v04g_source_snapshots LIMIT 1").fetchone())
    event = create_industry_event(title="Financing event", event_type="financing", db_path=p23_db)
    add_event_evidence(
        event["id"], snapshot_id=snapshot["id"], source_title=snapshot["page_title"] or "source",
        source_url=snapshot["url"] or "https://example.test", captured_at=snapshot["captured_at"] or "",
        evidence_excerpt="Source A says financing was USD 100 million.", db_path=p23_db,
    )
    conflict = register_conflict(
        topic_id=topic["id"], event_id=event["id"], subject_type="organization",
        subject_id=orgs[0]["external_id"], field_name="amount_value", value_a="100",
        value_b="120", evidence_a=[{"excerpt": "USD 100 million"}],
        evidence_b=[{"excerpt": "USD 120 million"}], db_path=p23_db,
    )
    submit_event(event["id"], actor="analyst", db_path=p23_db)
    with pytest.raises(ValueError, match="event_has_unresolved_conflict"):
        review_event(event["id"], decision="approved", actor="human-reviewer", db_path=p23_db)
    resolved = resolve_conflict(
        conflict["id"], adopted_value="100", reason="audited filing", actor="human-reviewer", db_path=p23_db
    )
    assert resolved["value_b"] == "120"
    assert resolved["adopted_value"] == "100"
    assert review_event(event["id"], decision="approved", actor="human-reviewer", db_path=p23_db)["status"] == "approved"


def test_finding_types_and_report_citations_are_traceable(p23_db: Path):
    topic, orgs = _topic_and_orgs(p23_db)
    _, assertion, _ = _approved_fact(p23_db, topic["id"], orgs[0])
    finding = create_finding(
        topic["id"], finding_type="verified_fact", title="ADC A获批",
        content="ADC A已获得监管批准。", assertion_ids=[assertion["id"]], db_path=p23_db,
    )
    submit_finding(finding["id"], actor="analyst", db_path=p23_db)
    review_finding(finding["id"], decision="approved", actor="human-reviewer", db_path=p23_db)
    report = create_research_report(topic["id"], created_by="analyst", db_path=p23_db)
    check = check_report_citations(report["id"], db_path=p23_db)
    assert check["complete"] is True
    assert check["rate"] == 1.0
    report = get_research_report(report["id"], db_path=p23_db)
    fact_sections = [row for row in report["sections"] if row["section_type"] == "fact"]
    assert fact_sections and fact_sections[0]["citation_complete"] == 1
    assert report["citations"][0]["snapshot_id"] is not None
    assert report["citations"][0]["evidence_excerpt"]


def test_unreviewed_finding_does_not_enter_report_and_submit_requires_citations(p23_db: Path):
    topic, orgs = _topic_and_orgs(p23_db)
    _, assertion, _ = _approved_fact(p23_db, topic["id"], orgs[0])
    draft = create_finding(
        topic["id"], finding_type="inference", title="未审核推断",
        content="该产品可能加快商业化。", assertion_ids=[assertion["id"]], db_path=p23_db,
    )
    report = create_research_report(topic["id"], created_by="analyst", db_path=p23_db)
    assert all(section["finding_id"] != draft["id"] for section in report["sections"])
    assert submit_research_report(report["id"], actor="analyst", db_path=p23_db)["research_status"] == "pending_review"


def test_report_versions_and_delete_preserve_evidence(p23_db: Path):
    topic, orgs = _topic_and_orgs(p23_db)
    _, assertion, _ = _approved_fact(p23_db, topic["id"], orgs[0])
    finding = create_finding(
        topic["id"], finding_type="verified_fact", title="获批", content="已获批。",
        assertion_ids=[assertion["id"]], db_path=p23_db,
    )
    submit_finding(finding["id"], actor="analyst", db_path=p23_db)
    review_finding(finding["id"], decision="approved", actor="human-reviewer", db_path=p23_db)
    report = create_research_report(topic["id"], created_by="analyst", db_path=p23_db)
    version = save_report_version(report["id"], change_note="manual edit", actor="analyst", db_path=p23_db)
    assert version["version_no"] == 2
    with db_connection(p23_db) as conn:
        evidence_before = conn.execute("SELECT COUNT(*) FROM p2_3_event_evidence").fetchone()[0]
    assert delete_research_report(report["id"], db_path=p23_db) == {"deleted": True, "evidence_preserved": True}
    with db_connection(p23_db) as conn:
        assert conn.execute("SELECT COUNT(*) FROM p2_3_event_evidence").fetchone()[0] == evidence_before


def test_research_agent_only_creates_reviewable_draft(p23_db: Path):
    topic, orgs = _topic_and_orgs(p23_db)
    _approved_fact(p23_db, topic["id"], orgs[0])
    result = ResearchAgentService(p23_db).generate_draft(topic["id"], provider_name="rule", actor="agent")
    assert result["status"] == "success"
    assert result["review_status"] == "draft"
    workspace = topic_workspace(topic["id"], db_path=p23_db)
    agent_finding = next(row for row in workspace["findings"] if row["id"] == result["finding_id"])
    assert agent_finding["status"] == "draft"
    assert workspace["reports"] == []


def test_routes_exist_and_formal_database_is_not_modified():
    before = hashlib.sha256(resolved_db_path().read_bytes()).hexdigest()
    from app.main import app
    paths = set(app.openapi()["paths"])
    assert "/research/topics/{topic_id}/workspace" in paths
    assert "/research/events" in paths
    assert "/research/conflicts" in paths
    assert "/api/v1/research-fusion/topics/{topic_id}/workspace" in paths
    assert hashlib.sha256(resolved_db_path().read_bytes()).hexdigest() == before


def test_research_entry_links_and_review_permissions():
    template = (Path(__file__).parents[1] / "app" / "templates" / "v05j_research.html").read_text(encoding="utf-8")
    assert '/research/topics/{{ t.id }}/workspace' in template
    from app.security import required_permission
    assert required_permission("/research/conflicts/1/resolve", "POST") == "review_data"
    assert required_permission("/research/findings/1/review", "POST") == "review_data"
    assert required_permission("/research/reports/1/review", "POST") == "review_data"
    assert required_permission("/research/reports/1/publish", "POST") == "review_data"
