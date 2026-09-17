from datetime import datetime,timedelta,date
from uuid import uuid4
from fastapi import APIRouter,Depends,Request,HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.routes_platform import render,get_current_user_id
from app.routes_knowledge import redirect
from app.services.club_facility_service import ClubFacilityService,BOOKING_STATUSES
from app.services.membership_access_service import service_member_identity

router=APIRouter()


def page(request,mode,**context):
    return render(request,"platform/club_facilities.html",mode=mode,statuses=BOOKING_STATUSES,**context)


@router.get("/club/services")
@router.get("/admin/club-facilities")
def rooms(request:Request,edit:int=0,db:Session=Depends(get_db)):
    service=ClubFacilityService(db); admin=request.url.path.startswith("/admin/")
    if admin: service.admin(get_current_user_id(request))
    items=service.rows("SELECT f.*,(SELECT MIN(start_at) FROM club_facility_bookings b WHERE b.facility_id=f.id AND b.status IN ('PENDING','CONFIRMED') AND b.end_at>:now) AS next_booking FROM club_facilities f ORDER BY f.is_open DESC,f.id",now=datetime.now().isoformat())
    return page(request,"rooms",items=items,admin=admin,item=service.get(edit) if edit and admin else {})


@router.post("/admin/club-facilities/save")
async def room_save(request:Request,db:Session=Depends(get_db)):
    form=await request.form()
    try:
        ClubFacilityService(db).save(form,get_current_user_id(request),int(form.get("id") or 0) or None); db.commit()
    except (ValueError,HTTPException) as exc:
        db.rollback()
        if isinstance(exc,HTTPException) and exc.status_code==403: raise
        return redirect("/admin/club-facilities",str(exc.detail) if isinstance(exc,HTTPException) else "会议室编号无效",True)
    return redirect("/admin/club-facilities","会议室已保存，历史预约保留")


@router.get("/club/services/rooms/{room_id:int}")
def room_detail(room_id:int,request:Request,day:str="",db:Session=Depends(get_db)):
    service=ClubFacilityService(db); room=service.get(room_id)
    try: chosen=date.fromisoformat(day) if day else datetime.now().date()
    except ValueError: raise HTTPException(422,"请选择有效日期")
    slots=service.rows("SELECT start_at,end_at,status FROM club_facility_bookings WHERE facility_id=:f AND start_at<:e AND end_at>:s AND status IN ('PENDING','CONFIRMED','COMPLETED') ORDER BY start_at",f=room_id,s=chosen.isoformat()+"T00:00:00",e=(chosen+timedelta(days=1)).isoformat()+"T00:00:00")
    return page(request,"room",item=room,slots=slots,day=chosen.isoformat(),identity=service_member_identity(db,get_current_user_id(request)),token=uuid4().hex)


@router.post("/club/services/rooms/{room_id:int}/book")
async def book(room_id:int,request:Request,db:Session=Depends(get_db)):
    form=dict(await request.form())
    form["start_at"]=str(form.get("day",""))+"T"+str(form.get("start_time",""))
    form["end_at"]=str(form.get("day",""))+"T"+str(form.get("end_time",""))
    try:
        identifier=ClubFacilityService(db).book(room_id,get_current_user_id(request),form); db.commit()
    except HTTPException as exc:
        db.rollback()
        if exc.status_code==403: raise
        return redirect(f"/club/services/rooms/{room_id}",str(exc.detail),True)
    return redirect(f"/club/services/bookings/{identifier}","预约已提交，请查看确认状态")


@router.get("/club/services/my-bookings")
@router.get("/admin/club-facilities/bookings")
def bookings(request:Request,scope:str="future",filter:str="pending",db:Session=Depends(get_db)):
    service=ClubFacilityService(db); admin=request.url.path.startswith("/admin/"); uid=get_current_user_id(request)
    clauses=[]; params={"u":uid,"now":datetime.now().isoformat()}
    if admin:
        service.admin(uid)
        today=datetime.now().date()
        if filter=="pending": clauses.append("b.status='PENDING'")
        elif filter in {"today","week"}:
            start=today if filter=="today" else today-timedelta(days=today.weekday())
            end=start+timedelta(days=1 if filter=="today" else 7)
            clauses.append("b.start_at<:end AND b.end_at>:start"); params.update(start=start.isoformat(),end=end.isoformat())
    else:
        clauses.append("b.user_id=:u")
        clauses.append("b.end_at<=:now" if scope=="history" else "b.end_at>:now")
    items=service.rows("SELECT b.*,f.name AS facility_name,u.display_name,o.standard_name AS organization_name FROM club_facility_bookings b JOIN club_facilities f ON f.id=b.facility_id JOIN v05a_users u ON u.id=b.user_id LEFT JOIN organizations o ON o.id=b.organization_id WHERE "+(" AND ".join(clauses) or "1=1")+" ORDER BY b.start_at DESC LIMIT 300",**params)
    return page(request,"bookings",items=items,admin=admin,scope=scope,filter=filter)


@router.get("/club/services/bookings/{booking_id:int}")
@router.get("/admin/club-facilities/bookings/{booking_id:int}")
def booking_detail(booking_id:int,request:Request,db:Session=Depends(get_db)):
    admin=request.url.path.startswith("/admin/")
    return page(request,"booking",item=ClubFacilityService(db).booking(booking_id,get_current_user_id(request),admin),admin=admin,now=datetime.now().isoformat())


@router.post("/club/services/bookings/{booking_id:int}/action")
@router.post("/admin/club-facilities/bookings/{booking_id:int}/action")
async def booking_action(booking_id:int,request:Request,db:Session=Depends(get_db)):
    admin=request.url.path.startswith("/admin/"); form=await request.form()
    target=f"/admin/club-facilities/bookings/{booking_id}" if admin else f"/club/services/bookings/{booking_id}"
    try:
        ClubFacilityService(db).transition(booking_id,get_current_user_id(request),str(form.get("action","")),str(form.get("review_note","")),admin); db.commit()
    except HTTPException as exc:
        db.rollback()
        if exc.status_code==403: raise
        return redirect(target,str(exc.detail),True)
    return redirect(target,"预约状态已更新")
