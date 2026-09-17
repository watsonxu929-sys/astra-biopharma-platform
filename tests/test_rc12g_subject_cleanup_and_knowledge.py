import re
import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session

from app.database import get_db
from app.main import app
from app.models import Organization, Person
from app.models_platform import IntelligenceItem
from app.services.canonical_relationship_service import CanonicalRelationshipService
from app.services.data_quality import delete_subject, person_reference_details, reference_fingerprint
from app.services.knowledge_service import KnowledgeService
from scripts.migrate_db import run_upgrade


@pytest.fixture
def environment(temp_database, monkeypatch):
    assert temp_database.resolve() != (Path(__file__).resolve().parents[1] / "data/app.db").resolve()
    # temp_database applies the current schema before binding runtime environment variables.
    engine = create_engine(f"sqlite:///{temp_database.as_posix()}", connect_args={"check_same_thread": False})
    @event.listens_for(engine, "connect")
    def enable_fk(conn, _):
        conn.execute("PRAGMA foreign_keys=ON")
    with engine.connect() as conn:
        uid = conn.execute(text("SELECT id FROM v05a_users ORDER BY id LIMIT 1")).scalar_one()
    user = {"id": uid, "username": "isolated_rc12g", "display_name": "隔离检查", "role": "admin", "status": "active", "must_change_password": 0}
    monkeypatch.setenv("APP_AUTH_DISABLED", "0")
    monkeypatch.setattr("app.security.verify_session_token", lambda _: user)
    def override():
        with Session(engine) as db:
            yield db
    app.dependency_overrides[get_db] = override
    from app.security import SESSION_COOKIE
    try:
        with TestClient(app) as client:
            client.cookies.set(SESSION_COOKIE, "isolated-only")
            yield engine, client, user, temp_database
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def subjects(db, suffix):
    p = Person(external_id="G-P-"+suffix, name="隔离人物"+suffix, is_active=True)
    o = Organization(external_id="G-O-"+suffix, standard_name="隔离机构"+suffix, is_active=True)
    db.add_all([p,o]); db.commit()
    return p,o


def profile(db, pid):
    db.execute(text("INSERT INTO v06_person_profiles(person_id) VALUES (:id)"), {"id":pid})
    db.commit()


def relationship(path, p, o):
    service = CanonicalRelationshipService(path)
    candidate = service.create_candidate(subject_type="person", subject_id=p.external_id,
        relationship_type="employed_by", object_type="organization", object_id=o.external_id, actor="isolated")
    return service.review_candidate(candidate["id"], "approved", actor="isolated", permissions={"review_data"})["relationship"]["id"]


def test_metadata_membership_cleanup_and_atomic_rollback(environment):
    engine, client, user, path = environment
    with Session(engine) as db:
        p,o = subjects(db,"metadata"); pid, oid = p.id,o.id
        profile(db,pid)
        db.execute(text("INSERT INTO v06_favorites(user_id,target_type,target_id) VALUES (:u,'person',:p)"), {"u":user["id"],"p":pid})
        db.execute(text("INSERT INTO v04f_club_memberships(member_no,person_id,status,joined_at,created_at,updated_at) VALUES ('G-MEMBER',:p,'active',datetime('now'),datetime('now'),datetime('now'))"), {"p":pid})
        db.commit()
    response = client.post(f"/admin/people/{pid}/delete", data={"confirm":"1"}, follow_redirects=False)
    assert response.status_code == 303 and "error=" not in response.headers["location"]
    with Session(engine) as db:
        assert db.get(Person,pid) is None and db.get(Organization,oid) is not None
        assert db.execute(text("SELECT COUNT(*) FROM v06_person_profiles WHERE person_id=:id"), {"id":pid}).scalar() == 0
        member = db.execute(text("SELECT person_id,status FROM v04f_club_memberships WHERE member_no='G-MEMBER'")).one()
        assert member == (None,"exited")
        assert db.execute(text("SELECT COUNT(*) FROM p4_membership_history WHERE reason LIKE '%错误主体%' ")).scalar() == 1
        p,o = subjects(db,"rollback"); pid=p.id
        profile(db,pid)
        # A future/unknown FK must roll back all metadata cleanup, never bypass protection.
        db.execute(text("CREATE TABLE isolated_guard(person_id INTEGER REFERENCES people(id))"))
        db.execute(text("INSERT INTO isolated_guard VALUES (:p)"), {"p":pid}); db.commit()
    response = client.post(f"/admin/people/{pid}/delete",data={"confirm":"1"},follow_redirects=False)
    assert "error=" in response.headers["location"]
    with Session(engine) as db:
        assert db.get(Person,pid) is not None
        assert db.execute(text("SELECT COUNT(*) FROM v06_person_profiles WHERE person_id=:p"),{"p":pid}).scalar() == 1


def test_bulk_history_and_explicit_atomic_relationship_archive(environment):
    engine,client,user,path = environment
    with Session(engine) as db:
        p,o = subjects(db,"history"); pid,oid=p.id,o.id
        profile(db,pid)
        rid = relationship(path,p,o)
        safe,_ = subjects(db,"safe"); safe_id=safe.id; profile(db,safe_id)
    response=client.post("/admin/people/bulk-delete",data={"person_ids":[str(safe_id),str(pid)]},follow_redirects=False)
    assert response.status_code==303
    with Session(engine) as db:
        assert db.get(Person,safe_id) is None and db.get(Person,pid) is not None
        assert db.execute(text("SELECT COUNT(*) FROM v06_person_profiles WHERE person_id=:p"),{"p":pid}).scalar()==1
    page=client.get(f"/admin/people/{pid}")
    assert page.status_code==200 and "彻底清理" in page.text and "附属资料" in page.text
    token=re.search(r'name="preview_token" value="([a-f0-9]+)"',page.text).group(1)
    form={"confirm":"1","confirm_name":"隔离人物history","reason":"明确错误的隔离数据","relationship_ids":str(rid),"preview_token":token}
    user["role"]="operator"
    assert client.post(f"/admin/people/{pid}/cleanup",data=form).status_code==403
    user["role"]="admin"
    bad=client.post(f"/admin/people/{pid}/cleanup",data={**form,"preview_token":"stale"},follow_redirects=False)
    assert "error=" in bad.headers["location"]
    with Session(engine) as db:
        db.execute(text("CREATE TABLE isolated_history_guard(person_id INTEGER REFERENCES people(id))"))
        db.execute(text("INSERT INTO isolated_history_guard VALUES (:p)"), {"p":pid}); db.commit()
    blocked=client.post(f"/admin/people/{pid}/cleanup",data=form,follow_redirects=False)
    assert "error=" in blocked.headers["location"]
    with Session(engine) as db:
        assert db.execute(text("SELECT review_status FROM p3_canonical_relationships WHERE id=:r"),{"r":rid}).scalar()=="approved"
        assert db.execute(text("SELECT COUNT(*) FROM v06_person_profiles WHERE person_id=:p"),{"p":pid}).scalar()==1
        db.execute(text("DELETE FROM isolated_history_guard")); db.commit()
    response=client.post(f"/admin/people/{pid}/cleanup",data=form,follow_redirects=False)
    assert "error=" not in response.headers["location"]
    with Session(engine) as db:
        assert db.get(Person,pid) is None and db.get(Organization,oid) is not None
        assert db.execute(text("SELECT review_status FROM p3_canonical_relationships WHERE id=:r"),{"r":rid}).scalar()=="archived"


def test_organization_detaches_people_and_draft_resource_only(environment):
    engine,client,user,path=environment
    with Session(engine) as db:
        p,o=subjects(db,"organization"); pid,oid=p.id,o.id
        p.organization_network=o.standard_name
        db.execute(text("INSERT INTO v06_market_resources(title,direction,resource_type,publisher_id,organization_id,status) VALUES ('隔离草稿','demand','其他',:u,:o,'draft')"),{"u":user["id"],"o":oid})
        db.commit()
    response=client.post(f"/admin/organizations/{oid}/delete",data={"confirm":"1"},follow_redirects=False)
    assert "error=" not in response.headers["location"]
    with Session(engine) as db:
        assert db.get(Organization,oid) is None
        assert db.get(Person,pid).organization_network is None
        assert db.execute(text("SELECT organization_id,category,status FROM v06_market_resources WHERE title='隔离草稿'")).one()==(None,None,"draft")


def test_knowledge_ui_persistence_links_paths_and_permissions(environment):
    engine,client,user,path=environment
    fields={"title":"隔离知识条目","category":"生物医药/产业基础","summary":"隔离摘要","body":"<script>alert(1)</script>","difficulty":"入门","status":"PUBLISHED","tags":"隔离标签","source_name":"隔离验证","source_url":"https://example.invalid/reference"}
    response=client.post("/admin/knowledge/save",data=fields,follow_redirects=False)
    assert response.status_code==303
    kid=int(re.search(r'/knowledge/(\d+)/edit',response.headers["location"]).group(1))
    for url in ["/knowledge","/knowledge?q=隔离标签",f"/knowledge/{kid}",f"/admin/knowledge/{kid}/edit"]:
        result=client.get(url); assert result.status_code==200
    assert "&lt;script&gt;" in client.get(f"/knowledge/{kid}").text
    assert client.post(f"/knowledge/{kid}/progress",data={"status":"LEARNING","note":"自己的备注"},follow_redirects=False).status_code==303
    with Session(engine) as db:
        p,o=subjects(db,"links"); oid=o.id
        p_id=p.id
        intel=IntelligenceItem(title="隔离知识关联情报", summary="隔离的页面关联检查", intel_type="brief", visibility="public", status="published")
        db.add(intel); db.commit(); intel_id=intel.id
    for kind,identifier in [("organization",oid),("person",p_id),("intelligence",intel_id)]:
        for _ in range(2):
            assert client.post(f"/admin/knowledge/{kid}/links",data={"target_type":kind,"target_id":identifier},follow_redirects=False).status_code==303
    with Session(engine) as db:
        assert KnowledgeService(db).related("organization",oid)[0]["id"]==kid
        assert db.execute(text("SELECT COUNT(*) FROM knowledge_links WHERE knowledge_id=:k AND target_type='organization'"),{"k":kid}).scalar()==1
    for url in [f"/network/entities/organization/G-O-links", f"/network/people/{p_id}", f"/intelligence/{intel_id}"]:
        response=client.get(url)
        assert response.status_code==200 and f'/knowledge/{kid}' in response.text
    response=client.post("/admin/knowledge/paths/save",data={"title":"隔离学习路径","description":"顺序学习","status":"PUBLISHED","knowledge_ids":str(kid)},follow_redirects=False)
    path_id=int(re.search(r'/paths/(\d+)/edit',response.headers["location"]).group(1))
    assert client.get(f"/knowledge/paths/{path_id}").status_code==200
    with Session(engine) as db:
        assert KnowledgeService(db).path_items(path_id,user_id=user["id"])[0]["progress_status"]=="LEARNING"
    user["role"]="viewer"
    for url in ["/admin/knowledge/save",f"/admin/knowledge/{kid}/links",f"/admin/knowledge/{kid}/delete","/admin/knowledge/paths/save"]:
        assert client.post(url,data=fields).status_code==403
    assert client.post(f"/knowledge/{kid}/progress",data={"status":"MASTERED","note":"自己的备注"},follow_redirects=False).status_code==303
    assert "已掌握" in client.get(f"/knowledge/{kid}").text
    original_uid=user["id"]
    with Session(engine) as db:
        other=db.execute(text("INSERT INTO v05a_users(username,display_name,password_hash,role,status,created_at,updated_at) VALUES ('isolated_rc12g_second','隔离第二用户','!not-a-login-password','viewer','active',datetime('now'),datetime('now'))")).lastrowid
        db.commit()
    user["id"]=other
    assert "自己的备注" not in client.get(f"/knowledge/{kid}").text
    assert client.post(f"/knowledge/{kid}/progress",data={"status":"REVIEW_LATER","note":"另一用户独立记录"},follow_redirects=False).status_code==303
    user["id"]=original_uid
    user["role"]="admin"
    assert "error=" in client.post(f"/admin/knowledge/{kid}/delete",follow_redirects=False).headers["location"]
    assert client.post(f"/admin/knowledge/{kid}/save",data={**fields,"status":"ARCHIVED"},follow_redirects=False).status_code==303
    user["role"]="viewer"
    assert client.get(f"/knowledge/{kid}").status_code==404
    with Session(engine) as db:
        assert db.execute(text("SELECT status FROM user_knowledge_progress WHERE user_id=:u AND knowledge_id=:k"),{"u":user["id"],"k":kid}).scalar()=="MASTERED"
    from app.services.intelligence_product_service import IntelligenceProductService
    assert IntelligenceProductService(path).delete(intel_id,actor="isolated",permissions={"edit_data"})["deleted"]
    with Session(engine) as db:
        assert KnowledgeService(db).get(kid,manager=True)["status"]=="ARCHIVED"
        assert db.execute(text("SELECT COUNT(*) FROM knowledge_links WHERE target_type='intelligence' AND target_id=:i"),{"i":intel_id}).scalar()==0
