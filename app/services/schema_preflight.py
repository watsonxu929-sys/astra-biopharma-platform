from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.settings import Settings, get_settings


CAPABILITY_TABLES: dict[str, tuple[str, ...]] = {
    "authentication": ("v05a_users",),
    "people": ("people",),
    "organizations": ("organizations",),
    "intelligence": ("raw_intelligence",),
    "resources": ("resources",),
    "opportunities": ("v06_opportunities",),
    "research_fusion": (
        "p2_3_industry_events", "p2_3_event_subjects", "p2_3_event_candidates",
        "p2_3_event_evidence", "p2_3_fact_assertions", "p2_3_assertion_evidence",
        "p2_3_fact_conflicts", "p2_3_research_questions", "p2_3_topic_events",
        "p2_3_research_findings", "p2_3_finding_assertions", "p2_3_report_sections",
        "p2_3_report_citations", "p2_3_report_versions", "p2_3_research_agent_runs",
        "research_topics", "v05h_generated_reports",
    ),
    "industry_relationships": (
        "p3_product_assets", "p3_entity_aliases", "p3_entity_external_identifiers", "p3_entity_resolution_candidates",
        "p3_entity_redirects", "p3_entity_merge_records", "p3_relationship_type_registry",
        "p3_canonical_relationships", "p3_relationship_evidence", "p3_relationship_candidates",
        "p3_relationship_audit", "p3_connection_candidates",
    ),
    "club_core": (
        "v04f_club_applications", "v04f_club_memberships", "v05c_club_event_profiles",
        "v05c_club_event_registrations", "v05c_club_event_participation",
    ),
    "club_operations": (
        "events", "actions", "v04f_club_applications", "v04f_club_memberships",
        "v05c_club_event_profiles", "v05c_club_event_registrations",
        "v05c_club_event_participation", "v06_market_resources",
        "p4_membership_history", "p4_event_feedback", "p4_checkin_tokens", "p4_checkin_audit",
        "p4_event_relationship_candidates", "p4_resource_match_candidates", "p4_club_lead_candidates",
        "p4_domain_events", "p4_operation_audit",
    ),
    "resource_matching": ("v04f_club_needs", "v04f_club_offerings", "v04f_club_matches"),
    "business_collaboration": (
        "v04f_lead_records", "v06_opportunities", "v06_follow_ups", "v06_collab_tasks",
        "p5_opportunity_participants", "p5_opportunity_stage_history", "p5_opportunity_sources",
        "p5_opportunity_meetings", "p5_opportunity_artifacts", "p5_opportunity_risks",
        "p5_domain_events", "p5_operation_audit",
    ),
}

CAPABILITY_COLUMNS: dict[str, dict[str, tuple[str, ...]]] = {
    "research_fusion": {
        "research_topics": ("keywords", "research_scope", "responsible_user", "subject_scope_json", "pilot_batch_id"),
        "v05h_generated_reports": ("topic_id", "research_status", "research_report_type", "citation_completeness", "current_version_no", "pilot_batch_id"),
    },
    "industry_relationships": {"p3_relationship_candidates": ("visibility",)},
    "club_operations": {
        "events": ("name", "event_date"),
        "v04f_club_applications": ("status", "submitted_at", "user_id", "member_type", "application_reason", "pilot_batch_id"),
        "v04f_club_memberships": ("status", "expired_at", "user_id", "pilot_batch_id"),
        "v05c_club_event_profiles": (
            "event_id", "status", "registration_status", "registration_deadline",
            "lifecycle_status", "topic", "agenda", "review_mode", "pilot_batch_id",
        ),
        "v05c_club_event_registrations": (
            "status", "registered_at", "checked_in_at", "lifecycle_status",
            "person_id", "organization_id", "is_guest", "pilot_batch_id",
        ),
        "v05c_club_event_participation": ("attendance_status", "check_in_time", "canonical_membership_id", "pilot_batch_id"),
        "v06_market_resources": ("status", "source_event_id", "target_audience", "pilot_batch_id"),
        "p4_event_feedback": ("status", "created_at", "updated_at"),
        "p4_resource_match_candidates": ("status",),
        "p4_club_lead_candidates": ("status",),
    },
    "business_collaboration": {
        "v04f_lead_records": ("title", "source_type", "source_record_id", "owner_user_id", "priority", "lifecycle_status", "converted_opportunity_id", "pilot_batch_id"),
        "v06_opportunities": ("opportunity_no", "currency", "success_probability", "target_complete_at", "risk_summary", "last_stage_changed_at", "pilot_batch_id"),
        "v06_follow_ups": ("participants_json", "result", "next_action", "shared_summary", "internal_note", "artifact_ids_json", "pilot_batch_id"),
        "v06_collab_tasks": ("task_type", "completion_criteria", "related_follow_up_id", "related_meeting_id", "visibility", "blocked_reason", "completed_at", "pilot_batch_id"),
        "v06_timeline_entries": ("pilot_batch_id",),
        "p5_opportunity_artifacts": ("uploaded_at",),
    },
}

CAPABILITY_INDEXES: dict[str, tuple[str, ...]] = {
    "research_fusion": ("ix_p23_event_status_time", "ix_p23_assertion_subject", "ix_p23_report_citations"),
    "industry_relationships": ("ix_p3_relationship_subject", "ix_p3_relationship_object", "ix_p3_connection_source"),
    "club_operations": ("ix_p4_membership_history_member", "ix_p4_domain_events_queue"),
    "business_collaboration": ("idx_v04f_lifecycle_status", "idx_p5_participants_opp", "idx_p5_risks_opp"),
}

CAPABILITY_LABELS = {
    "authentication": "\u767b\u5f55\u4e0e\u7528\u6237",
    "people": "\u4eba\u7269\u57fa\u7840\u6863\u6848",
    "organizations": "\u673a\u6784\u57fa\u7840\u6863\u6848",
    "intelligence": "\u57fa\u7840\u60c5\u62a5",
    "resources": "\u57fa\u7840\u8d44\u6e90",
    "opportunities": "\u57fa\u7840\u673a\u4f1a",
    "research_fusion": "\u4e3b\u4f53\u7814\u7a76\u878d\u5408",
    "industry_relationships": "\u4ea7\u4e1a\u5173\u7cfb\u4e0e\u4eba\u8109\u63a8\u8350",
    "club_core": "Q-BAY \u4ff1\u4e50\u90e8\u57fa\u7840\u80fd\u529b",
    "club_operations": "Q-BAY \u4ff1\u4e50\u90e8\u8fd0\u8425\u589e\u5f3a",
    "resource_matching": "\u8d44\u6e90\u5339\u914d",
    "business_collaboration": "\u4e1a\u52a1\u534f\u540c",
}


@dataclass(frozen=True)
class CapabilityStatus:
    name: str
    label: str
    enabled: bool
    required_tables: tuple[str, ...]
    missing_tables: tuple[str, ...]
    reason: str
    missing_columns: tuple[str, ...] = ()
    missing_indexes: tuple[str, ...] = ()

    def public_dict(self, *, include_tables: bool = True) -> dict[str, object]:
        data: dict[str, object] = {"name": self.name, "label": self.label, "enabled": self.enabled, "reason": self.reason}
        if include_tables:
            data["required_tables"] = list(self.required_tables)
            data["missing_tables"] = list(self.missing_tables)
            data["missing_columns"] = list(self.missing_columns)
            data["missing_indexes"] = list(self.missing_indexes)
        return data


@dataclass(frozen=True)
class SchemaPreflight:
    backend: str
    connected: bool
    database_exists: bool
    capabilities: tuple[CapabilityStatus, ...]
    error: str = ""

    def capability(self, name: str) -> CapabilityStatus:
        for item in self.capabilities:
            if item.name == name:
                return item
        raise KeyError(name)

    def public_dict(self, *, include_tables: bool = True) -> dict[str, object]:
        return {
            "backend": self.backend,
            "connected": self.connected,
            "database_exists": self.database_exists,
            "error": self.error,
            "capabilities": [item.public_dict(include_tables=include_tables) for item in self.capabilities],
        }


def _statuses(
    table_names: Iterable[str],
    *,
    connected: bool,
    columns: dict[str, set[str]] | None = None,
    indexes: Iterable[str] = (),
) -> tuple[CapabilityStatus, ...]:
    existing = set(table_names)
    actual_columns = columns or {}
    actual_indexes = set(indexes)
    result: list[CapabilityStatus] = []
    for name, required in CAPABILITY_TABLES.items():
        missing = tuple(table for table in required if table not in existing)
        missing_columns = tuple(
            f"{table}.{column}"
            for table, expected in CAPABILITY_COLUMNS.get(name, {}).items()
            for column in expected
            if column not in actual_columns.get(table, set())
        )
        missing_indexes = tuple(index for index in CAPABILITY_INDEXES.get(name, ()) if index not in actual_indexes)
        enabled = connected and not missing and not missing_columns and not missing_indexes
        reason = "\u6240\u9700\u8868\u3001\u5b57\u6bb5\u4e0e\u7d22\u5f15\u7ed3\u6784\u5b8c\u6574" if enabled else ("\u6570\u636e\u5e93\u5c1a\u672a\u5177\u5907\u8be5\u6a21\u5757\u6240\u9700\u7ed3\u6784" if connected else "\u6570\u636e\u5e93\u7ed3\u6784\u5f53\u524d\u4e0d\u53ef\u8bfb\u53d6")
        result.append(CapabilityStatus(
            name, CAPABILITY_LABELS[name], enabled, required, missing, reason,
            missing_columns=missing_columns, missing_indexes=missing_indexes,
        ))
    return tuple(result)


def run_schema_preflight(settings: Settings | None = None) -> SchemaPreflight:
    settings = settings or get_settings()
    if settings.db_backend != "sqlite":
        return SchemaPreflight(settings.db_backend, False, True, _statuses((), connected=False), "backend_not_checked")
    path = settings.sqlite_path
    if path != Path(":memory:") and not path.exists():
        return SchemaPreflight("sqlite", False, False, _statuses((), connected=False), "database_file_missing")
    try:
        if path == Path(":memory:"):
            conn = sqlite3.connect(":memory:")
        else:
            conn = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True, timeout=5)
        try:
            table_names = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
            columns = {
                table: {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')}
                for table in table_names
            }
            indexes = {str(row[0]) for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
            statuses = _statuses(table_names, connected=True, columns=columns, indexes=indexes)
        finally:
            conn.close()
        return SchemaPreflight("sqlite", True, True, statuses)
    except sqlite3.Error:
        return SchemaPreflight("sqlite", False, path.exists(), _statuses((), connected=False), "database_unavailable")


_CACHE: dict[str, SchemaPreflight] = {}


def get_schema_preflight(*, refresh: bool = False) -> SchemaPreflight:
    settings = get_settings()
    key = settings.database_url
    if refresh or key not in _CACHE:
        _CACHE[key] = run_schema_preflight(settings)
    return _CACHE[key]
