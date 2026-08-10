"""Recovered additive migration for intelligence-to-opportunity lineage."""

MIGRATION_ID = "010_intelligence_opportunity_loop"
REQUIRED_TABLES = {
    "p4_club_lead_candidates",
    "p4_resource_match_candidates",
    "v06_follow_ups",
    "v06_market_resources",
    "v06_opportunities",
}

ADDITIVE_COLUMNS = {
    "p4_club_lead_candidates": {"opportunity_id": "INTEGER"},
    "p4_resource_match_candidates": {
        "unmet_conditions_json": "TEXT",
        "conflicts_json": "TEXT",
        "explanation": "TEXT",
        "created_by_user_id": "INTEGER",
        "opportunity_id": "INTEGER",
    },
    "v06_follow_ups": {
        "next_action": "TEXT",
        "contact_result": "TEXT",
        "risk_note": "TEXT",
        "stage_after": "TEXT",
        "attachment_note": "TEXT",
    },
    "v06_market_resources": {
        "source_intelligence_id": "INTEGER",
        "project_id": "INTEGER",
        "source_collection_item_id": "INTEGER",
        "source_snapshot_id": "INTEGER",
        "source_intelligence_title": "TEXT",
        "source_content_hash": "TEXT",
        "opportunity_type": "TEXT",
        "project_stage": "TEXT",
        "cooperation_terms": "TEXT",
        "confidentiality_level": "TEXT NOT NULL DEFAULT 'internal'",
        "duplicate_of_id": "INTEGER",
        "closed_reason": "TEXT",
        "converted_at": "TEXT",
    },
    "v06_opportunities": {
        "source_intelligence_id": "INTEGER",
        "source_demand_resource_id": "INTEGER",
        "source_supply_resource_id": "INTEGER",
        "source_match_id": "INTEGER",
        "club_lead_candidate_id": "INTEGER",
        "risk_note": "TEXT",
        "final_result": "TEXT",
        "closed_reason": "TEXT",
    },
}

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS ix_p4_match_opportunity
ON p4_resource_match_candidates(opportunity_id, status);
CREATE UNIQUE INDEX IF NOT EXISTS ux_p4_match_single_opportunity
ON p4_resource_match_candidates(opportunity_id) WHERE opportunity_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_v06_opportunity_source_intelligence
ON v06_opportunities(source_intelligence_id, status, stage);
CREATE UNIQUE INDEX IF NOT EXISTS ux_v06_opportunity_source_match
ON v06_opportunities(source_match_id) WHERE source_match_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS ix_v06_resource_owner_status
ON v06_market_resources(publisher_id, status, updated_at);
CREATE INDEX IF NOT EXISTS ix_v06_resource_source_intelligence
ON v06_market_resources(source_intelligence_id, status, direction);
"""
