from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.settings import resolved_db_path

MIGRATION_ID = "006_entity_relationship_network"
REQUIRED_TABLES = {
    "people", "organizations", "projects", "relations", "v04e_entity_aliases",
    "v04e_duplicate_candidates", "v04g_source_snapshots", "raw_intelligence",
    "v05g_extraction_candidates",
}
P3_TABLES = {
    "p3_product_assets", "p3_entity_aliases", "p3_entity_external_identifiers",
    "p3_entity_resolution_candidates", "p3_entity_redirects", "p3_entity_merge_records",
    "p3_relationship_type_registry", "p3_canonical_relationships",
    "p3_relationship_evidence", "p3_relationship_candidates", "p3_relationship_audit",
    "p3_connection_candidates",
}

TABLE_SQL = r"""
CREATE TABLE IF NOT EXISTS p3_product_assets (
 id INTEGER PRIMARY KEY AUTOINCREMENT, external_id TEXT NOT NULL UNIQUE,
 canonical_name TEXT NOT NULL, asset_type TEXT NOT NULL, development_code TEXT,
 brand_name TEXT, target_text TEXT, modality TEXT, owner_organization_id TEXT,
 status TEXT NOT NULL DEFAULT 'active', completeness INTEGER NOT NULL DEFAULT 0,
 review_status TEXT NOT NULL DEFAULT 'pending_review', visibility TEXT NOT NULL DEFAULT 'internal',
 source TEXT, is_pilot INTEGER NOT NULL DEFAULT 0, pilot_batch_id TEXT,
 created_by TEXT, reviewed_by TEXT, reviewed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(asset_type IN ('drug','medical_device','technology_platform','pipeline','combination_therapy','other')),
 CHECK(status IN ('active','inactive','merged','redirected','archived')),
 CHECK(review_status IN ('pending_review','approved','rejected','needs_revision')),
 CHECK(visibility IN ('public','internal','restricted','private')),
 CHECK(completeness BETWEEN 0 AND 100), CHECK(is_pilot IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_p3_product_asset_name ON p3_product_assets(canonical_name,status);

CREATE TABLE IF NOT EXISTS p3_entity_aliases (
 id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
 alias TEXT NOT NULL, alias_type TEXT NOT NULL, language TEXT, normalized_alias TEXT NOT NULL,
 source TEXT, source_url TEXT, evidence_snapshot_id INTEGER, valid_from TEXT, valid_to TEXT,
 review_status TEXT NOT NULL DEFAULT 'pending', legacy_alias_id INTEGER,
 is_pilot INTEGER NOT NULL DEFAULT 0, pilot_batch_id TEXT, created_by TEXT,
 reviewed_by TEXT, reviewed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(evidence_snapshot_id) REFERENCES v04g_source_snapshots(id) ON DELETE RESTRICT,
 CHECK(entity_type IN ('person','organization','product','project')),
 CHECK(alias_type IN ('official_name','short_name','english_name','former_name','brand_name','product_code','abbreviation','transliteration')),
 CHECK(review_status IN ('pending','approved','rejected','inactive')), CHECK(is_pilot IN (0,1)),
 UNIQUE(entity_type,entity_id,normalized_alias,alias_type)
);
CREATE INDEX IF NOT EXISTS ix_p3_alias_lookup ON p3_entity_aliases(entity_type,normalized_alias,review_status);

CREATE TABLE IF NOT EXISTS p3_entity_external_identifiers (
 id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL, entity_id TEXT NOT NULL,
 identifier_type TEXT NOT NULL, identifier_value TEXT NOT NULL, normalized_value TEXT NOT NULL,
 market TEXT, authority TEXT, source TEXT, source_url TEXT, evidence_snapshot_id INTEGER,
 review_status TEXT NOT NULL DEFAULT 'pending', is_sensitive INTEGER NOT NULL DEFAULT 0,
 is_pilot INTEGER NOT NULL DEFAULT 0, pilot_batch_id TEXT, created_by TEXT,
 reviewed_by TEXT, reviewed_at TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(evidence_snapshot_id) REFERENCES v04g_source_snapshots(id) ON DELETE RESTRICT,
 CHECK(entity_type IN ('person','organization','product','project')),
 CHECK(identifier_type IN ('unified_social_credit_code','stock_code','official_domain','nmpa_number','clinicaltrials_gov','development_code','orcid','doi','legacy_id','other_public')),
 CHECK(review_status IN ('pending','approved','rejected','inactive')), CHECK(is_sensitive=0), CHECK(is_pilot IN (0,1))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_p3_external_identifier
 ON p3_entity_external_identifiers(identifier_type,normalized_value,COALESCE(market,''))
 WHERE review_status<>'rejected';
CREATE INDEX IF NOT EXISTS ix_p3_identifier_entity ON p3_entity_external_identifiers(entity_type,entity_id);

CREATE TABLE IF NOT EXISTS p3_entity_resolution_candidates (
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_no TEXT NOT NULL UNIQUE,
 candidate_type TEXT NOT NULL, raw_name TEXT NOT NULL, normalized_name TEXT NOT NULL,
 possible_entity_id TEXT, possible_entity_label TEXT, matching_features_json TEXT NOT NULL DEFAULT '{}',
 score REAL NOT NULL DEFAULT 0, match_strength TEXT NOT NULL DEFAULT 'weak', generated_by TEXT NOT NULL,
 source_record_type TEXT, source_record_id TEXT, evidence_ids_json TEXT NOT NULL DEFAULT '[]',
 resolution_status TEXT NOT NULL DEFAULT 'pending', review_note TEXT,
 is_pilot INTEGER NOT NULL DEFAULT 0, pilot_batch_id TEXT, reviewer TEXT, reviewed_at TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(candidate_type IN ('person','organization','product','project')),
 CHECK(match_strength IN ('strong','medium','weak')), CHECK(score BETWEEN 0 AND 1),
 CHECK(resolution_status IN ('pending','matched','create_new','rejected','ambiguous','needs_more_evidence')),
 CHECK(is_pilot IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_p3_resolution_queue ON p3_entity_resolution_candidates(resolution_status,score DESC,id DESC);

CREATE TABLE IF NOT EXISTS p3_entity_redirects (
 id INTEGER PRIMARY KEY AUTOINCREMENT, entity_type TEXT NOT NULL, source_entity_id TEXT NOT NULL,
 target_entity_id TEXT NOT NULL, merge_record_id INTEGER, status TEXT NOT NULL DEFAULT 'active',
 created_at TEXT NOT NULL, rolled_back_at TEXT,
 CHECK(entity_type IN ('person','organization','product','project')),
 CHECK(status IN ('active','rolled_back'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_p3_active_redirect ON p3_entity_redirects(entity_type,source_entity_id) WHERE status='active';

CREATE TABLE IF NOT EXISTS p3_entity_merge_records (
 id INTEGER PRIMARY KEY AUTOINCREMENT, merge_no TEXT NOT NULL UNIQUE,
 source_entity_id TEXT NOT NULL, target_entity_id TEXT NOT NULL, entity_type TEXT NOT NULL,
 merge_reason TEXT NOT NULL, merge_evidence_json TEXT NOT NULL DEFAULT '[]', preview_json TEXT NOT NULL,
 initiated_by TEXT NOT NULL, approved_by TEXT, merged_at TEXT,
 affected_relations_json TEXT NOT NULL DEFAULT '[]', affected_aliases_json TEXT NOT NULL DEFAULT '[]',
 rollback_payload_json TEXT NOT NULL DEFAULT '{}', merge_status TEXT NOT NULL DEFAULT 'preview',
 rollback_by TEXT, rollback_reason TEXT, rolled_back_at TEXT,
 is_pilot INTEGER NOT NULL DEFAULT 0, pilot_batch_id TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(entity_type IN ('person','organization','product','project')), CHECK(source_entity_id<>target_entity_id),
 CHECK(merge_status IN ('preview','pending_approval','merged','rejected','rolled_back','failed')),
 CHECK(is_pilot IN (0,1))
);

CREATE TABLE IF NOT EXISTS p3_relationship_type_registry (
 relationship_type TEXT PRIMARY KEY, display_name TEXT NOT NULL, reverse_display_name TEXT NOT NULL,
 category TEXT NOT NULL, subject_types_json TEXT NOT NULL, object_types_json TEXT NOT NULL,
 is_symmetric INTEGER NOT NULL DEFAULT 0, risk_level TEXT NOT NULL DEFAULT 'medium',
 active INTEGER NOT NULL DEFAULT 1, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(category IN ('person_organization','organization_organization','organization_product','person_asset_project','project_organization')),
 CHECK(risk_level IN ('low','medium','high')), CHECK(is_symmetric IN (0,1)), CHECK(active IN (0,1))
);

CREATE TABLE IF NOT EXISTS p3_canonical_relationships (
 id INTEGER PRIMARY KEY AUTOINCREMENT, relationship_no TEXT NOT NULL UNIQUE,
 subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, relationship_type TEXT NOT NULL,
 object_type TEXT NOT NULL, object_id TEXT NOT NULL, direction TEXT NOT NULL DEFAULT 'directed',
 valid_from TEXT, valid_to TEXT, is_current INTEGER NOT NULL DEFAULT 1,
 confidence INTEGER NOT NULL DEFAULT 50, review_status TEXT NOT NULL DEFAULT 'pending_review',
 evidence_status TEXT NOT NULL DEFAULT 'manual_unverified', source_count INTEGER NOT NULL DEFAULT 0,
 visibility TEXT NOT NULL DEFAULT 'internal', legacy_relation_id INTEGER,
 is_pilot INTEGER NOT NULL DEFAULT 0, pilot_batch_id TEXT, created_by TEXT NOT NULL,
 reviewed_by TEXT, reviewed_at TEXT, review_note TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(relationship_type) REFERENCES p3_relationship_type_registry(relationship_type) ON DELETE RESTRICT,
 CHECK(subject_type IN ('person','organization','product','project')),
 CHECK(object_type IN ('person','organization','product','project')),
 CHECK(subject_type<>object_type OR subject_id<>object_id), CHECK(direction IN ('directed','symmetric')),
 CHECK(is_current IN (0,1)), CHECK(confidence BETWEEN 0 AND 100),
 CHECK(review_status IN ('pending_review','approved','rejected','needs_revision','archived')),
 CHECK(evidence_status IN ('evidence_backed','manual_unverified')),
 CHECK(visibility IN ('public','internal','restricted','private')), CHECK(is_pilot IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_p3_relationship_subject ON p3_canonical_relationships(subject_type,subject_id,review_status,is_current);
CREATE INDEX IF NOT EXISTS ix_p3_relationship_object ON p3_canonical_relationships(object_type,object_id,review_status,is_current);
CREATE INDEX IF NOT EXISTS ix_p3_relationship_time ON p3_canonical_relationships(valid_from,valid_to,is_current);

CREATE TABLE IF NOT EXISTS p3_relationship_evidence (
 id INTEGER PRIMARY KEY AUTOINCREMENT, relationship_id INTEGER NOT NULL,
 evidence_snapshot_id INTEGER, raw_intelligence_id INTEGER, fact_candidate_id INTEGER,
 fact_assertion_id INTEGER, industry_event_id INTEGER, evidence_text TEXT NOT NULL,
 page_number INTEGER, locator_json TEXT NOT NULL DEFAULT '{}', source_url TEXT, source_date TEXT,
 evidence_strength TEXT NOT NULL DEFAULT 'supporting', evidence_hash TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(relationship_id) REFERENCES p3_canonical_relationships(id) ON DELETE RESTRICT,
 FOREIGN KEY(evidence_snapshot_id) REFERENCES v04g_source_snapshots(id) ON DELETE RESTRICT,
 FOREIGN KEY(raw_intelligence_id) REFERENCES raw_intelligence(id) ON DELETE RESTRICT,
 FOREIGN KEY(fact_candidate_id) REFERENCES v05g_extraction_candidates(id) ON DELETE RESTRICT,
 CHECK(evidence_strength IN ('authoritative','strong','supporting','weak','contradicting'))
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_p3_relationship_evidence
 ON p3_relationship_evidence(relationship_id,evidence_hash,COALESCE(evidence_snapshot_id,-1));

CREATE TABLE IF NOT EXISTS p3_relationship_candidates (
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_no TEXT NOT NULL UNIQUE,
 subject_type TEXT NOT NULL, subject_id TEXT NOT NULL, relationship_type TEXT NOT NULL,
 object_type TEXT NOT NULL, object_id TEXT NOT NULL, valid_from TEXT, valid_to TEXT,
 confidence INTEGER NOT NULL DEFAULT 50, source_record_type TEXT, source_record_id TEXT,
 evidence_json TEXT NOT NULL DEFAULT '[]', similar_relationship_ids_json TEXT NOT NULL DEFAULT '[]',
 conflict_relationship_ids_json TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL DEFAULT 'pending',
 visibility TEXT NOT NULL DEFAULT 'internal',
 revision_json TEXT NOT NULL DEFAULT '{}', is_pilot INTEGER NOT NULL DEFAULT 0, pilot_batch_id TEXT,
 created_by TEXT NOT NULL, reviewed_by TEXT, reviewed_at TEXT, review_note TEXT,
 created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 FOREIGN KEY(relationship_type) REFERENCES p3_relationship_type_registry(relationship_type) ON DELETE RESTRICT,
 CHECK(status IN ('pending','approved','rejected','merged','conflict','needs_more_evidence')),
 CHECK(visibility IN ('public','internal','restricted','private')),
 CHECK(confidence BETWEEN 0 AND 100), CHECK(is_pilot IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_p3_relationship_candidate_queue ON p3_relationship_candidates(status,confidence DESC,id DESC);

CREATE TABLE IF NOT EXISTS p3_relationship_audit (
 id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT NOT NULL, relationship_id INTEGER,
 relationship_candidate_id INTEGER, merge_record_id INTEGER, actor TEXT NOT NULL,
 before_json TEXT, after_json TEXT, reason TEXT, created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS p3_connection_candidates (
 id INTEGER PRIMARY KEY AUTOINCREMENT, candidate_no TEXT NOT NULL UNIQUE,
 source_person_id TEXT NOT NULL, recommended_person_id TEXT, recommended_organization_id TEXT,
 target_track TEXT, target_organization_id TEXT, need_text TEXT, reason_json TEXT NOT NULL DEFAULT '{}',
 path_json TEXT NOT NULL DEFAULT '{}', common_contacts_json TEXT NOT NULL DEFAULT '[]',
 evidence_json TEXT NOT NULL DEFAULT '[]', confidence INTEGER NOT NULL DEFAULT 0, risk_note TEXT,
 status TEXT NOT NULL DEFAULT 'candidate', is_pilot INTEGER NOT NULL DEFAULT 0, pilot_batch_id TEXT,
 created_by TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
 CHECK(confidence BETWEEN 0 AND 100), CHECK(status IN ('candidate','dismissed','accepted_for_review')),
 CHECK(is_pilot IN (0,1))
);
CREATE INDEX IF NOT EXISTS ix_p3_connection_source ON p3_connection_candidates(source_person_id,status,confidence DESC);
"""

RELATIONSHIP_TYPES = [
 ("employed_by","任职","任职人员","person_organization",["person"],["organization"],0,"medium"),
 ("formerly_employed_by","历史任职","历史任职人员","person_organization",["person"],["organization"],0,"medium"),
 ("founder_of","创始人","由其创立","person_organization",["person"],["organization"],0,"high"),
 ("cofounder_of","联合创始人","由其联合创立","person_organization",["person"],["organization"],0,"high"),
 ("legal_representative_of","法定代表人","法定代表人为","person_organization",["person"],["organization"],0,"high"),
 ("director_of","董事","董事包括","person_organization",["person"],["organization"],0,"high"),
 ("executive_of","高管","高管包括","person_organization",["person"],["organization"],0,"high"),
 ("advisor_to","顾问","顾问包括","person_organization",["person"],["organization"],0,"medium"),
 ("scientific_advisor_to","科学顾问","科学顾问包括","person_organization",["person"],["organization"],0,"medium"),
 ("investor_in","投资人","投资人包括","person_organization",["person"],["organization"],0,"high"),
 ("contact_for","联系人","联系人为","person_organization",["person"],["organization"],0,"high"),
 ("member_of","会员所属","会员包括","person_organization",["person"],["organization"],0,"medium"),
 ("invests_in","投资","获得投资","organization_organization",["organization"],["organization"],0,"high"),
 ("controls","控股","被控股","organization_organization",["organization"],["organization"],0,"high"),
 ("subsidiary_of","子公司","母公司","organization_organization",["organization"],["organization"],0,"high"),
 ("parent_of","母公司","子公司","organization_organization",["organization"],["organization"],0,"high"),
 ("strategic_partner_of","战略合作","战略合作","organization_organization",["organization"],["organization"],1,"medium"),
 ("research_partner_of","研发合作","研发合作","organization_organization",["organization"],["organization"],1,"medium"),
 ("licenses_to","许可授权","被许可","organization_organization",["organization"],["organization"],0,"high"),
 ("licensed_from","被许可","许可授权","organization_organization",["organization"],["organization"],0,"high"),
 ("acquired","并购","被并购","organization_organization",["organization"],["organization"],0,"high"),
 ("supplies_services_to","供应服务","接受服务","organization_organization",["organization"],["organization"],0,"medium"),
 ("jointly_established","联合成立","联合成立","organization_organization",["organization"],["organization"],1,"medium"),
 ("located_in_park","园区入驻","入驻企业","organization_organization",["organization"],["organization"],0,"medium"),
 ("member_organization_of","会员机构关系","会员机构","organization_organization",["organization"],["organization"],0,"medium"),
 ("develops","研发","由其研发","organization_product",["organization"],["product"],0,"high"),
 ("owns","持有","由其持有","organization_product",["organization"],["product"],0,"high"),
 ("licenses_product","授权","被其授权","organization_product",["organization"],["product"],0,"high"),
 ("commercializes","商业化","由其商业化","organization_product",["organization"],["product"],0,"high"),
 ("manufactures","生产","由其生产","organization_product",["organization"],["product"],0,"high"),
 ("sponsors_clinical_trial","临床申办","申办机构","organization_product",["organization"],["product"],0,"high"),
 ("supports_product","服务支持","获得服务支持","organization_product",["organization"],["product"],0,"medium"),
 ("inventor_of","发明人","发明人为","person_asset_project",["person"],["product","project"],0,"high"),
 ("leads","负责人","负责人为","person_asset_project",["person"],["product","project"],0,"high"),
 ("researcher_for","研究者","研究者包括","person_asset_project",["person"],["product","project"],0,"medium"),
 ("advisor_for","顾问","顾问包括","person_asset_project",["person"],["product","project"],0,"medium"),
 ("participates_in","项目参与者","参与者包括","person_asset_project",["person"],["project"],0,"medium"),
 ("initiated_by","发起","发起项目","project_organization",["project"],["organization"],0,"medium"),
 ("participated_by","参与","参与项目","project_organization",["project"],["organization"],0,"medium"),
 ("funded_by","投资","投资项目","project_organization",["project"],["organization"],0,"high"),
 ("serviced_by","服务","服务项目","project_organization",["project"],["organization"],0,"medium"),
 ("undertaken_by","承担","承担项目","project_organization",["project"],["organization"],0,"medium"),
 ("cooperated_by","合作","合作项目","project_organization",["project"],["organization"],1,"medium"),
]

def table_names(conn: sqlite3.Connection) -> set[str]:
    return {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}

def counts(conn: sqlite3.Connection) -> dict[str,int]:
    names=table_names(conn)
    return {name:int(conn.execute(f'SELECT COUNT(*) FROM "{name}"').fetchone()[0]) for name in sorted(P3_TABLES|{"people","organizations","projects","relations"}) if name in names}

def analyze(conn: sqlite3.Connection) -> dict:
    names=table_names(conn)
    return {"missing_required_tables":sorted(REQUIRED_TABLES-names),"missing_p3_tables":sorted(P3_TABLES-names),"relationship_type_count":int(conn.execute("SELECT COUNT(*) FROM p3_relationship_type_registry").fetchone()[0]) if "p3_relationship_type_registry" in names else 0,"counts":counts(conn)}

def backup_database(conn: sqlite3.Connection, db_path: Path) -> tuple[Path,str]:
    backup_dir=db_path.parent/"backups"; backup_dir.mkdir(parents=True,exist_ok=True)
    target=backup_dir/f"{db_path.stem}_before_{MIGRATION_ID}_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    with sqlite3.connect(target) as destination: conn.backup(destination)
    digest=hashlib.sha256(target.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{target.as_posix()}?mode=ro",uri=True) as check:
        if check.execute("PRAGMA integrity_check").fetchone()[0]!="ok": target.unlink(missing_ok=True); raise RuntimeError("backup_integrity_check_failed")
    return target,digest

def apply_schema(conn: sqlite3.Connection) -> None:
    for statement in TABLE_SQL.split(";"):
        if statement.strip(): conn.execute(statement)
    candidate_columns={row[1] for row in conn.execute("PRAGMA table_info(p3_relationship_candidates)")}
    if "visibility" not in candidate_columns:
        conn.execute("ALTER TABLE p3_relationship_candidates ADD COLUMN visibility TEXT NOT NULL DEFAULT 'internal' CHECK(visibility IN ('public','internal','restricted','private'))")
    ts=datetime.now().replace(microsecond=0).isoformat()
    for key,display,reverse,category,subject_types,object_types,symmetric,risk in RELATIONSHIP_TYPES:
        conn.execute("""INSERT INTO p3_relationship_type_registry(relationship_type,display_name,reverse_display_name,category,subject_types_json,object_types_json,is_symmetric,risk_level,active,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,1,?,?) ON CONFLICT(relationship_type) DO UPDATE SET display_name=excluded.display_name,reverse_display_name=excluded.reverse_display_name,category=excluded.category,subject_types_json=excluded.subject_types_json,object_types_json=excluded.object_types_json,is_symmetric=excluded.is_symmetric,risk_level=excluded.risk_level,active=1,updated_at=excluded.updated_at""",(key,display,reverse,category,json.dumps(subject_types),json.dumps(object_types),symmetric,risk,ts,ts))

def write_report(path: Path|None,report: dict) -> None:
    if path: path.parent.mkdir(parents=True,exist_ok=True); path.write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding="utf-8")

def main() -> int:
    parser=argparse.ArgumentParser(description="P3 canonical entity and relationship network migration")
    mode=parser.add_mutually_exclusive_group(); mode.add_argument("--dry-run",action="store_true"); mode.add_argument("--apply",action="store_true")
    parser.add_argument("--db",type=Path); parser.add_argument("--report",type=Path); args=parser.parse_args()
    db_path=(args.db or resolved_db_path()).resolve()
    if not db_path.exists(): print(json.dumps({"error":"database_not_found"},ensure_ascii=False)); return 2
    applying=bool(args.apply); uri=str(db_path) if applying else f"file:{db_path.as_posix()}?mode=ro"
    with sqlite3.connect(uri,uri=not applying) as conn:
        conn.execute("PRAGMA foreign_keys=ON"); before=analyze(conn)
        report={"migration_id":MIGRATION_ID,"mode":"apply" if applying else "dry-run","database_name":db_path.name,"timestamp":datetime.now().isoformat(),"before":before}
        if before["missing_required_tables"]: report["error"]="missing_required_tables"; write_report(args.report,report); print(json.dumps(report,ensure_ascii=False,indent=2)); return 3
        if not applying: write_report(args.report,report); print(json.dumps(report,ensure_ascii=False,indent=2)); return 0
        backup_path,backup_sha=backup_database(conn,db_path)
        try:
            conn.execute("BEGIN IMMEDIATE"); apply_schema(conn); after=analyze(conn)
            if after["missing_p3_tables"] or after["relationship_type_count"]!=len(RELATIONSHIP_TYPES): raise RuntimeError("schema_verification_failed")
            conn.commit()
        except Exception: conn.rollback(); raise
        report.update({"backup_name":backup_path.name,"backup_sha256":backup_sha,"after":after,"applied":True}); write_report(args.report,report); print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__": raise SystemExit(main())
