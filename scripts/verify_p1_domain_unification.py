from __future__ import annotations

import os
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0,str(ROOT))
from scripts.test_db_utils import temporary_database

PYTHON=sys.executable
LIVE_DB=ROOT/"data"/"app.db"
MIGRATION=ROOT/"scripts"/"migrations"/"001_core_domain_unification.py"

def run(args,env=None):
    result=subprocess.run(args,cwd=ROOT,env=env,text=True,capture_output=True)
    if result.stdout: print(result.stdout.rstrip())
    if result.stderr: print(result.stderr.rstrip())
    if result.returncode: raise AssertionError(f"exit={result.returncode}: {' '.join(args)}")

def main():
    results=[]
    def check(name,fn):
        try: fn(); print("PASS",name); results.append(True)
        except Exception as exc: print("FAIL",name,exc); results.append(False)
    with temporary_database("p1_domain_clone_") as clone:
        shutil.copy2(LIVE_DB,clone)
        initial_fk=foreign_key_count(clone)
        env=os.environ.copy(); env["APP_DB_PATH"]=str(clone); env["DATABASE_URL"]=f"sqlite:///{clone.as_posix()}"
        check("migration_dry_run",lambda:run([PYTHON,str(MIGRATION),"--db-path",str(clone),"--dry-run"],env))
        check("migration_apply",lambda:run([PYTHON,str(MIGRATION),"--db-path",str(clone),"--apply"],env))
        first=snapshot(clone)
        check("migration_idempotent",lambda:run([PYTHON,str(MIGRATION),"--db-path",str(clone),"--apply"],env))
        second=snapshot(clone)
        check("mapping_counts_stable",lambda:equal(first,second))
        check("required_schema",lambda:required_schema(clone))
        check("unified_service_rules",lambda:service_rules(env))
        check("foreign_keys_not_increased",lambda:foreign_keys_not_increased(clone,initial_fk))
    print(f"verify_p1_domain_unification passed={sum(results)} failed={len(results)-sum(results)}")
    return 0 if all(results) else 1

def snapshot(path):
    with sqlite3.connect(path) as c: return tuple(c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in ("platform_entity_mappings","platform_migration_conflicts"))
def equal(a,b): assert a==b,(a,b)
def required_schema(path):
    required={"v06_market_resources":{"category","owner_person_id","visibility","legacy_source_type","legacy_source_id"},"v06_opportunities":{"priority","estimated_amount","next_action","next_follow_at","human_confirmed_by","human_confirmed_at"},"v06_intelligence_items":{"source_record_type","source_record_id","evidence_hash"}}
    with sqlite3.connect(path) as c:
        for table,want in required.items():
            got={row[1] for row in c.execute(f"PRAGMA table_info({table})")}; assert not(want-got),(table,want-got)
def service_rules(env):
    code=r'''
from fastapi import HTTPException
from sqlalchemy import text
from app.database import SessionLocal
from app.services.unified_resource_service import UnifiedResourceService
from app.services.unified_opportunity_service import UnifiedOpportunityService
s=SessionLocal()
try:
    uid=s.execute(text("SELECT id FROM v05a_users ORDER BY id LIMIT 1")).scalar(); assert uid is not None
    resources=UnifiedResourceService(s)
    demand=resources.create(actor_user_id=int(uid),fields={"title":"P1副本验证需求","direction":"demand","category":"verification","visibility":"private"})
    supply=resources.create(actor_user_id=int(uid),fields={"title":"P1副本验证供给","direction":"supply","category":"verification","visibility":"private"})
    assert demand.direction=="demand" and supply.direction=="supply"
    assert resources.find_duplicates({"title":"P1副本验证需求","direction":"demand"})
    opportunities=UnifiedOpportunityService(s)
    try:
        opportunities.create(actor_user_id=int(uid),fields={"title":"不得自动转正式商机"})
        raise AssertionError("unconfirmed opportunity accepted")
    except HTTPException as exc: assert exc.status_code==409
    opp=opportunities.create(actor_user_id=int(uid),fields={"title":"P1副本人工确认商机","human_confirmed":True,"priority":"P1","next_action":"人工跟进","visibility":"private"})
    follow=opportunities.create_follow_up(opp_id=opp.id,actor_user_id=int(uid),fields={"content":"副本验证跟进","follow_type":"note"})
    task=opportunities.create_task(opp_id=opp.id,actor_user_id=int(uid),owner_id=int(uid),fields={"title":"副本验证任务"})
    assert follow.opportunity_id==opp.id and task.opportunity_id==opp.id
    assert not opportunities.can_access(opp,int(uid)+999999)
finally: s.close()
'''
    run([PYTHON,"-c",code],env)
def foreign_key_count(path):
    with sqlite3.connect(path) as c: return len(c.execute("PRAGMA foreign_key_check").fetchall())
def foreign_keys_not_increased(path,initial):
    final=foreign_key_count(path); assert final<=initial,(initial,final)
if __name__=="__main__": raise SystemExit(main())
