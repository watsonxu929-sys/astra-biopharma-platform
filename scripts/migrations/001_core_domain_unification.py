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

MIGRATION_ID = "001_core_domain_unification"
COLUMN_PLAN = {
    "v06_intelligence_items": {"source_record_type": "TEXT", "source_record_id": "INTEGER", "evidence_hash": "TEXT"},
    "v06_market_resources": {"category": "TEXT", "owner_person_id": "INTEGER", "visibility": "TEXT NOT NULL DEFAULT 'organization'", "legacy_source_type": "TEXT", "legacy_source_id": "TEXT"},
    "v06_opportunities": {"demand_organization_id": "INTEGER", "supply_organization_id": "INTEGER", "priority": "TEXT NOT NULL DEFAULT 'P2'", "estimated_amount": "TEXT", "next_action": "TEXT", "next_follow_at": "TEXT", "human_confirmed_by": "INTEGER", "human_confirmed_at": "TEXT"},
}

def table_exists(conn, table):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)).fetchone() is not None

def columns(conn, table):
    return {str(row[1]) for row in conn.execute(f'PRAGMA table_info("{table}")')} if table_exists(conn, table) else set()

def backup_database(conn, db_path):
    backup_dir=db_path.parent/"backups"; backup_dir.mkdir(parents=True,exist_ok=True)
    backup_path=backup_dir/f"{db_path.stem}_before_{MIGRATION_ID}_{datetime.now():%Y%m%d_%H%M%S_%f}.db"
    with sqlite3.connect(backup_path) as target: conn.backup(target)
    digest=hashlib.sha256(backup_path.read_bytes()).hexdigest()
    with sqlite3.connect(f"file:{backup_path.as_posix()}?mode=ro",uri=True) as check: integrity=check.execute("PRAGMA integrity_check").fetchone()[0]
    if integrity!="ok": backup_path.unlink(missing_ok=True); raise RuntimeError(f"backup integrity check failed: {integrity}")
    return backup_path,digest

def ensure_support_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS platform_entity_mappings(id INTEGER PRIMARY KEY AUTOINCREMENT,domain TEXT NOT NULL,source_system TEXT NOT NULL,source_entity_type TEXT NOT NULL,source_entity_id TEXT NOT NULL,canonical_entity_type TEXT NOT NULL,canonical_entity_id TEXT NOT NULL,metadata_json TEXT,created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),UNIQUE(domain,source_system,source_entity_type,source_entity_id));
    CREATE INDEX IF NOT EXISTS ix_platform_entity_mappings_canonical ON platform_entity_mappings(domain,canonical_entity_type,canonical_entity_id);
    CREATE TABLE IF NOT EXISTS platform_migration_conflicts(id INTEGER PRIMARY KEY AUTOINCREMENT,migration_id TEXT NOT NULL,domain TEXT NOT NULL,source_entity_type TEXT NOT NULL,source_entity_id TEXT NOT NULL,reason TEXT NOT NULL,details_json TEXT,status TEXT NOT NULL DEFAULT 'pending',created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')),UNIQUE(migration_id,domain,source_entity_type,source_entity_id,reason));
    CREATE TABLE IF NOT EXISTS platform_migration_runs(id INTEGER PRIMARY KEY AUTOINCREMENT,migration_id TEXT NOT NULL,mode TEXT NOT NULL,stats_json TEXT NOT NULL,backup_path TEXT,backup_sha256 TEXT,created_at TEXT NOT NULL DEFAULT (datetime('now','localtime')));
    """)

def plan_columns(conn):
    return [(table,column,ddl) for table,defs in COLUMN_PLAN.items() if table_exists(conn,table) for column,ddl in defs.items() if column not in columns(conn,table)]

def collect_mappings(conn):
    mappings=[]; conflicts=[]
    if table_exists(conn,"v04f_club_memberships"):
        available=columns(conn,"v04f_club_memberships"); selected=[n for n in ("id","user_id","person_id","organization_id") if n in available]
        if "id" in selected:
            for row in conn.execute(f"SELECT {','.join(selected)} FROM v04f_club_memberships"):
                data=dict(row); mid=str(data["id"]); mappings.append(("identity","legacy","membership",mid,"membership",mid,"{}"))
                for key,target in (("user_id","user"),("person_id","person"),("organization_id","organization")):
                    if data.get(key) is not None: mappings.append(("identity","legacy",f"membership_{target}",mid,target,str(data[key]),"{}"))
    if table_exists(conn,"v06_intelligence_items") and table_exists(conn,"raw_intelligence"):
        has_source_id="source_record_id" in columns(conn,"v06_intelligence_items")
        for row in conn.execute("SELECT id,source_url"+(",source_record_id" if has_source_id else "")+" FROM v06_intelligence_items"):
            raw=None
            if has_source_id and row["source_record_id"]: raw=conn.execute("SELECT id FROM raw_intelligence WHERE id=?",(row["source_record_id"],)).fetchone()
            if raw is None and row["source_url"]:
                matches=conn.execute("SELECT id FROM raw_intelligence WHERE source_url=?",(row["source_url"],)).fetchall()
                if len(matches)==1: raw=matches[0]
                elif len(matches)>1: conflicts.append((MIGRATION_ID,"intelligence","raw_intelligence",str(row["id"]),"ambiguous_source_url",json.dumps({"source_url":row["source_url"]},ensure_ascii=False)))
            if raw: mappings.append(("intelligence","legacy","raw_intelligence",str(raw["id"]),"intelligence_product",str(row["id"]),"{}"))
    if table_exists(conn,"v06_market_resources"):
        for table,direction in (("resources","supply"),("v04f_club_needs","demand"),("v04f_club_offerings","supply")):
            if not table_exists(conn,table) or "title" not in columns(conn,table): continue
            for row in conn.execute(f'SELECT id,title FROM "{table}"'):
                matches=conn.execute("SELECT id FROM v06_market_resources WHERE direction=? AND trim(title)=trim(?)",(direction,row["title"] or "")).fetchall()
                if len(matches)==1: mappings.append(("marketplace","legacy",table,str(row["id"]),"market_resource",str(matches[0]["id"]),json.dumps({"direction":direction})))
                else: conflicts.append((MIGRATION_ID,"marketplace",table,str(row["id"]),"unmatched" if not matches else "ambiguous_title",json.dumps({"title":row["title"],"direction":direction},ensure_ascii=False)))
    if table_exists(conn,"v06_opportunities"):
        for row in conn.execute("SELECT id,source_type,source_id FROM v06_opportunities WHERE source_type IS NOT NULL AND source_id IS NOT NULL"):
            mappings.append(("opportunity","legacy",str(row["source_type"]),str(row["source_id"]),"opportunity",str(row["id"]),"{}"))
    return mappings,conflicts

def build_stats(conn,mappings,conflicts,pending):
    tables=("v05a_users","people","organizations","v04f_club_memberships","raw_intelligence","v06_intelligence_items","resources","v04f_club_needs","v04f_club_offerings","v06_market_resources","v06_opportunities","v06_follow_ups","v06_collab_tasks")
    records={t:(int(conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0]) if table_exists(conn,t) else None) for t in tables}
    return {"migration_id":MIGRATION_ID,"records":records,"pending_columns":len(pending),"planned_mappings":len(mappings),"conflicts":len(conflicts),"unmigrated":sum(1 for r in conflicts if r[4]=="unmatched")}

def main():
    parser=argparse.ArgumentParser(description="Additive core-domain compatibility migration"); mode=parser.add_mutually_exclusive_group(); mode.add_argument("--apply",action="store_true"); mode.add_argument("--dry-run",action="store_true"); parser.add_argument("--db-path",type=Path); args=parser.parse_args()
    db_path=(args.db_path or resolved_db_path()).resolve()
    if not db_path.exists(): print(f"ERROR database not found: {db_path}"); return 2
    apply=bool(args.apply); uri=str(db_path) if apply else f"file:{db_path.as_posix()}?mode=ro"
    with sqlite3.connect(uri,uri=not apply) as conn:
        conn.row_factory=sqlite3.Row; conn.execute("PRAGMA foreign_keys=ON")
        pending=plan_columns(conn); mappings,conflicts=collect_mappings(conn); summary=build_stats(conn,mappings,conflicts,pending); print(json.dumps({"mode":"apply" if apply else "dry-run",**summary},ensure_ascii=False,sort_keys=True))
        if not apply: return 0
        backup_path,backup_sha=backup_database(conn,db_path)
        try:
            conn.execute("BEGIN IMMEDIATE"); ensure_support_tables(conn)
            for table,column,ddl in pending: conn.execute(f'ALTER TABLE "{table}" ADD COLUMN "{column}" {ddl}')
            mappings,conflicts=collect_mappings(conn)
            conn.executemany("INSERT OR IGNORE INTO platform_entity_mappings(domain,source_system,source_entity_type,source_entity_id,canonical_entity_type,canonical_entity_id,metadata_json) VALUES (?,?,?,?,?,?,?)",mappings)
            conn.executemany("INSERT OR IGNORE INTO platform_migration_conflicts(migration_id,domain,source_entity_type,source_entity_id,reason,details_json) VALUES (?,?,?,?,?,?)",conflicts)
            final=build_stats(conn,mappings,conflicts,[]); conn.execute("INSERT INTO platform_migration_runs(migration_id,mode,stats_json,backup_path,backup_sha256) VALUES (?,?,?,?,?)",(MIGRATION_ID,"apply",json.dumps(final,ensure_ascii=False,sort_keys=True),str(backup_path),backup_sha)); conn.commit()
        except Exception: conn.rollback(); raise
    print(json.dumps({"backup":str(backup_path),"backup_sha256":backup_sha,"result":final},ensure_ascii=False,sort_keys=True)); return 0

if __name__=="__main__": raise SystemExit(main())
