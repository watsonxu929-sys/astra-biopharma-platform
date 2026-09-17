"""RC1.2H focused checks: all writes use the existing isolated database fixture."""
from datetime import datetime, timedelta
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session

from test_rc12g_subject_cleanup_and_knowledge import environment
from app.services.knowledge_service import KnowledgeService
from app.services.club_facility_service import ClubFacilityService


def knowledge(db):
    return KnowledgeService(db).save(dict(title="隔离知识H",category="EHS/安全基础",
        difficulty="入门",body="隔离正文",summary="规则",status="PUBLISHED"))


def training(db, uid):
    s=KnowledgeService(db); k=knowledge(db)
    p=s.save(dict(title="隔离培训H",description="规则",status="PUBLISHED",
        learning_type="REQUIRED_TRAINING",version="2026.1",audience="ALL_USERS",requires_exam="1"),path=True)
    s.set_path_items(p,[k])
    qs=[s.save_question(dict(title=kind,question_type=kind,options="选项一\n选项二\n选项三",
        correct=answer,knowledge_id=k,explanation="评分秘密解析H"))
        for kind,answer in [("SINGLE_CHOICE","1"),("MULTIPLE_CHOICE","1,3"),("TRUE_FALSE","2")]]
    e=s.save_exam(dict(title="隔离考试H",path_id=p,status="PUBLISHED",pass_score=60,max_attempts=2),qs)
    s.progress(k,uid,"MASTERED",""); db.commit()
    return k,p,qs,e


def test_annotations_private_ownership_and_reply_depth(environment):
    engine,client,user,_=environment
    with Session(engine) as db:
        s=KnowledgeService(db); k=knowledge(db); db.commit()
        s.annotate(k,user["id"],dict(type="NOTE",visibility="INTERNAL",content="私有H")); db.commit()
        note=s.annotations(k,user["id"])[0]
        assert note["visibility"]=="PRIVATE"
        assert not s.annotations(k,-1)
        with pytest.raises(HTTPException) as denied:
            s.delete_annotation(k,note["id"],-1,True)
        assert denied.value.status_code==403
        s.annotate(k,user["id"],dict(type="NOTE",content="修订H"),note["id"]); db.commit()
        s.annotate(k,user["id"],dict(type="COMMENT",content="根评论")); db.commit()
        root=s.rows("SELECT max(id) AS id FROM knowledge_annotations")[0]["id"]
        s.annotate(k,user["id"],dict(type="COMMENT",content="回复",parent_id=root)); db.commit()
        reply=s.rows("SELECT max(id) AS id FROM knowledge_annotations")[0]["id"]
        with pytest.raises(HTTPException):
            s.annotate(k,user["id"],dict(type="COMMENT",content="二级回复",parent_id=reply))
        db.rollback()
        assert len(s.annotations(k,-1))==2
        s.delete_annotation(k,root,-1,True); db.commit()
        assert len(s.annotations(k,user["id"]))==3
    assert client.get(f"/knowledge/{k}").status_code==200


def test_exam_score_snapshot_versions_and_page_permissions(environment):
    engine,client,user,_=environment
    with Session(engine) as db:
        k,p,qs,e=training(db,user["id"]); s=KnowledgeService(db)
        a=s.start_exam(e,user["id"]); db.commit()
        assert s.start_exam(e,user["id"])==a; db.commit()
    page=client.get(f"/knowledge/attempts/{a}")
    assert page.status_code==200 and "评分秘密解析H" not in page.text
    response=client.post(f"/knowledge/attempts/{a}/submit",data={f"q_{qs[0]}":"1",f"q_{qs[1]}":["1","3"],f"q_{qs[2]}":"1","score":"100"})
    assert response.status_code==200 and "重新学习" in response.text
    with Session(engine) as db:
        s=KnowledgeService(db); arow=s.attempt(a,user["id"])
        assert arow["score"]==66.67 and arow["passed"]==1
        s.submit_exam(a,user["id"],{}); db.commit()
        assert s.attempt(a,user["id"])["score"]==66.67
        with pytest.raises(HTTPException): s.attempt(a,-1)
        with pytest.raises(HTTPException): s.delete_question(qs[0])
        db.rollback()
        old=s.get(p,manager=True,path=True)
        s.save({**old,"version":"2027.1"},p,path=True); db.commit()
        assert not s.training_summary(s.get(p,path=True),user["id"])["learned_all"]
        records=s.training_records(user["id"])
        assert any(r["version"]=="2026.1" and r["completed"] for r in records)
        with pytest.raises(HTTPException): s.save(old,p,path=True)
        db.rollback()
        assert s.attempt(a,user["id"])["path_version"]=="2026.1"
    for url in ["/admin/knowledge/questions","/admin/knowledge/exams","/admin/knowledge/training-records",
                "/knowledge/my-training",f"/knowledge/paths/{p}"]:
        assert client.get(url).status_code==200, url
    user["role"]="viewer"
    denied=client.get("/admin/knowledge/questions",follow_redirects=False)
    assert denied.status_code==303 and "/account/forbidden" in denied.headers["location"]
    assert client.post("/admin/knowledge/exams/save",data={}).status_code==403


def test_attempt_limit_exact_multiple_choice_and_tenant_training(environment):
    engine,_,user,_=environment
    with Session(engine) as db:
        k,p,qs,e=training(db,user["id"]); s=KnowledgeService(db)
        for _ in range(2):
            a=s.start_exam(e,user["id"]); db.commit()
            s.submit_exam(a,user["id"],{str(qs[1]):["1"]}); db.commit()
            assert s.attempt(a,user["id"])["score"]==0
        with pytest.raises(HTTPException) as limit: s.start_exam(e,user["id"])
        assert limit.value.status_code==409; db.rollback()
        path=s.get(p,path=True)
        assert not s.audience_allowed({**path,"audience":"TENANT_MEMBERS"},user["id"])


def room_and_member(db,uid):
    db.execute(text("UPDATE v05a_users SET role='admin',status='active' WHERE id=:u"),{"u":uid})
    db.execute(text("""INSERT INTO v04f_club_memberships(member_no,user_id,status,joined_at,created_at,updated_at)
        VALUES (:n,:u,'active',datetime('now'),datetime('now'),datetime('now'))"""),{"u":uid,"n":"H-"+uuid4().hex})
    service=ClubFacilityService(db)
    room=service.save(dict(name="隔离会议室",location="隔离楼层",capacity=8,open_start="08:00",open_end="20:00",
        min_minutes=30,max_minutes=180,advance_days=7,is_open=1,allow_members=1,tenant_auto_confirm=1,non_tenant_review=0),uid)
    db.commit()
    return room


def booking_fields(hour=10,minute=0):
    day=(datetime.now()+timedelta(days=1)).replace(hour=hour,minute=minute,second=0,microsecond=0)
    return dict(start_at=day.isoformat(),end_at=(day+timedelta(hours=1)).isoformat(),attendee_count=2,
        purpose="隔离测试",contact_name="本人",contact_method="isolated.invalid",
        request_token=uuid4().hex,remark="")


def test_booking_conflict_cancellation_permissions_and_pages(environment):
    engine,client,user,_=environment; uid=user["id"]
    with Session(engine) as db:
        room=room_and_member(db,uid); s=ClubFacilityService(db); fields=booking_fields()
        b=s.book(room,uid,fields); db.commit()
        assert s.book(room,uid,fields)==b; db.commit()
        assert s.booking(b,uid)["status"]=="PENDING"
        with pytest.raises(HTTPException): s.book(room,uid,booking_fields(10,30))
        db.rollback()
        with pytest.raises(HTTPException) as forbidden: s.book(room,-1,booking_fields(12))
        assert forbidden.value.status_code==403; db.rollback()
        with pytest.raises(HTTPException): s.booking(b,-1)
        s.transition(b,uid,"confirm",admin=True); db.commit()
        s.transition(b,uid,"cancel"); db.commit()
        second=s.book(room,uid,booking_fields()); db.commit()
        assert second!=b
        adjacent=s.book(room,uid,booking_fields(11)); db.commit()
        assert adjacent
        with pytest.raises(HTTPException): s.book(room,uid,{**booking_fields(15),"attendee_count":9})
        db.rollback()
    for url in ["/club/services",f"/club/services/rooms/{room}","/club/services/my-bookings",
                f"/club/services/bookings/{second}","/admin/club-facilities",
                "/admin/club-facilities/bookings",f"/admin/club-facilities/bookings/{second}"]:
        assert client.get(url).status_code==200, url
    user["role"]="viewer"
    denied=client.get("/admin/club-facilities",follow_redirects=False)
    assert denied.status_code==303 and "/account/forbidden" in denied.headers["location"]
    assert client.post("/admin/club-facilities/save",data={}).status_code==403


def test_booking_concurrent_writes_and_admin_recheck(environment):
    engine,_,user,_=environment; uid=user["id"]
    with Session(engine) as db: room=room_and_member(db,uid)
    barrier=Barrier(2)
    def book():
        with Session(engine) as db:
            barrier.wait()
            try:
                bid=ClubFacilityService(db).book(room,uid,booking_fields()); db.commit()
                return bid
            except HTTPException as exc:
                db.rollback(); assert exc.status_code==409
                return None
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:book(),range(2)))
    assert sum(x is not None for x in results)==1
    with Session(engine) as db:
        s=ClubFacilityService(db)
        b=s.book(room,uid,booking_fields(12)); db.commit()
        first=next(x for x in results if x)
        # Deliberately simulate historical bad data in this isolated DB only.
        db.execute(text("UPDATE club_facility_bookings SET start_at=:s,end_at=:e WHERE id=:id"),
            {"s":booking_fields()["start_at"],"e":booking_fields()["end_at"],"id":b}); db.commit()
        with pytest.raises(HTTPException) as conflict: s.transition(b,uid,"confirm",admin=True)
        assert conflict.value.status_code==409; db.rollback()
        assert s.booking(first,uid)["status"]=="PENDING"
        db.execute(text("UPDATE v04f_club_memberships SET status='exited' WHERE user_id=:u"),{"u":uid}); db.commit()
        with pytest.raises(HTTPException) as denied: s.book(room,uid,booking_fields(16))
        assert denied.value.status_code==403
