"""Recovered additive migration for match feedback and outcome lineage."""

MIGRATION_ID = "011_feedback_outcome_loop"
REQUIRED_TABLES = {
    "p3_canonical_relationships",
    "p4_resource_match_candidates",
    "v06_opportunities",
}

ADDITIVE_COLUMNS = {
    "p3_canonical_relationships": {
        "source_opportunity_id": "INTEGER",
        "source_match_id": "INTEGER",
        "source_intelligence_id": "INTEGER",
        "confidence_level": "TEXT NOT NULL DEFAULT 'pending_verification'",
    },
    "p4_resource_match_candidates": {
        "intention_status": "TEXT",
        "intention_reason_code": "TEXT",
        "intention_note": "TEXT",
        "intention_by_user_id": "INTEGER",
        "intention_at": "TEXT",
    },
    "v06_opportunities": {
        "outcome_status": "TEXT",
        "closed_by_user_id": "INTEGER",
        "closed_at": "TEXT",
        "final_result_note": "TEXT",
        "final_cooperation_scale": "TEXT",
        "result_relationship_id": "INTEGER",
    },
}

INDEX_SQL = """
CREATE INDEX IF NOT EXISTS ix_p3_relationship_source_intelligence
ON p3_canonical_relationships(source_intelligence_id);
CREATE INDEX IF NOT EXISTS ix_p3_relationship_source_match
ON p3_canonical_relationships(source_match_id);
CREATE INDEX IF NOT EXISTS ix_p3_relationship_source_opportunity
ON p3_canonical_relationships(source_opportunity_id);
CREATE INDEX IF NOT EXISTS ix_p4_match_intention
ON p4_resource_match_candidates(intention_status, intention_reason_code, intention_at);
CREATE INDEX IF NOT EXISTS ix_v06_opportunity_closed
ON v06_opportunities(status, outcome_status, closed_at);
"""
