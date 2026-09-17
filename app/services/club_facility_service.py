"""Small room/time transaction domain; canonical users and memberships remain authoritative."""
from datetime import datetime, timedelta, time
import re
from fastapi import HTTPException
from sqlalchemy import text
from app.services.membership_access_service import service_member_identity

BOOKING_STATUSES={"PENDING":"待确认","CONFIRMED":"已确认","REJECTED":"已拒绝","CANCELLED":"已取消","COMPLETED":"已完成"}


class ClubFacilityService:
    def __init__(self,db): self.db=db

    def rows(self,sql,**params):
        return [dict(r) for r in self.db.execute(text(sql),params).mappings()]

    def lock(self):
        conn=self.db.connection().connection.driver_connection
        if not conn.in_transaction: conn.execute("BEGIN IMMEDIATE")

    def admin(self,user_id):
        if not self.rows("SELECT id FROM v05a_users WHERE id=:u AND role='admin' AND status='active'",u=user_id):
            raise HTTPException(403,"需要管理员权限")

    def get(self,facility_id):
        rooms=self.rows("SELECT * FROM club_facilities WHERE id=:id",id=facility_id)
        if not rooms: raise HTTPException(404,"会议室不存在")
        return rooms[0]

    def save(self,fields,user_id,facility_id=None):
        self.admin(user_id); self.lock()
        if facility_id: self.get(facility_id)
        values={k:str(fields.get(k,"")).strip() for k in ("name","location","facilities","instructions","open_start","open_end")}
        try:
            values.update({k:int(fields.get(k,0)) for k in ("capacity","min_minutes","max_minutes","advance_days")})
            start=time.fromisoformat(values["open_start"]); end=time.fromisoformat(values["open_end"])
        except ValueError: raise HTTPException(422,"请填写有效的开放时间、人数、时长和提前天数")
        if not values["name"] or not values["location"] or not 1<=values["capacity"]<=10000 or start>=end or not 1<=values["min_minutes"]<=values["max_minutes"]<=1440 or not 0<=values["advance_days"]<=365 or start.tzinfo or end.tzinfo:
            raise HTTPException(422,"会议室规则无效（仅支持当天开放时段）")
        for k in ("is_open","allow_members","tenant_auto_confirm","non_tenant_review"): values[k]=int(str(fields.get(k,0)) in {"1","on","true"})
        values["updated_at"]=datetime.now().isoformat()
        if facility_id:
            self.db.execute(text("UPDATE club_facilities SET "+",".join(f"{k}=:{k}" for k in values)+" WHERE id=:id"),{**values,"id":facility_id})
        else:
            values["created_at"]=values["updated_at"]
            facility_id=self.db.execute(text("INSERT INTO club_facilities("+",".join(values)+") VALUES ("+",".join(f":{k}" for k in values)+")"),values).lastrowid
        return facility_id

    def conflict(self,facility_id,start,end,exclude=0):
        return bool(self.rows("SELECT id FROM club_facility_bookings WHERE facility_id=:f AND id<>:id AND status IN ('PENDING','CONFIRMED') AND start_at<:e AND end_at>:s LIMIT 1",f=facility_id,id=exclude,s=start,e=end))

    def book(self,facility_id,user_id,fields):
        self.lock()
        room=self.get(facility_id)
        identity=service_member_identity(self.db,user_id)
        member=identity["member"]
        if not member: raise HTTPException(403,"会议室服务面向Q-BAY有效会员开放，请先申请加入俱乐部")
        if not room["is_open"] or not room["allow_members"]: raise HTTPException(409,"会议室当前不接受会员预约")
        try:
            start=datetime.fromisoformat(str(fields.get("start_at",""))); end=datetime.fromisoformat(str(fields.get("end_at","")))
            attendees=int(fields.get("attendee_count",0))
        except ValueError: raise HTTPException(422,"请输入有效的起止时间和人数")
        now=datetime.now()
        if start.tzinfo or end.tzinfo or start.second or end.second or start.microsecond or end.microsecond or start<=now or end<=start or start.date()!=end.date(): raise HTTPException(422,"预约须为将来同一天内的有效时间，精确到分钟（北京时间）")
        minutes=(end-start).total_seconds()/60
        if start.date()>now.date()+timedelta(days=room["advance_days"]) or not room["min_minutes"]<=minutes<=room["max_minutes"] or start.time()<time.fromisoformat(room["open_start"]) or end.time()>time.fromisoformat(room["open_end"]): raise HTTPException(422,"时间不符合开放时段、预约时长或提前天数规则")
        if not 1<=attendees<=room["capacity"]: raise HTTPException(422,"预计人数超过会议室容量或无效")
        values={k:str(fields.get(k,"")).strip() for k in ("purpose","contact_name","contact_method","remark","request_token")}
        if not all(values[k] for k in ("purpose","contact_name","contact_method")) or any(len(values[k])>2000 for k in values) or not re.fullmatch(r"[a-f0-9]{32}",values["request_token"]): raise HTTPException(422,"请填写用途、联系人和联系方式；请从会议室页面提交预约")
        s,e=start.isoformat(),end.isoformat()
        prior=self.rows("SELECT * FROM club_facility_bookings WHERE request_token=:t",t=values["request_token"])
        if prior:
            if prior[0]["user_id"]!=user_id or prior[0]["facility_id"]!=facility_id or prior[0]["start_at"]!=s or prior[0]["end_at"]!=e: raise HTTPException(409,"提交标识已使用，请刷新页面")
            return prior[0]["id"]
        if self.conflict(facility_id,s,e): raise HTTPException(409,"该时段已有待确认或已确认预约，请选择其他时间")
        tenant=identity["tenant_member"]
        status="CONFIRMED" if (tenant is True and room["tenant_auto_confirm"]) or (tenant is False and not room["non_tenant_review"]) else "PENDING"
        values.update({"facility_id":facility_id,"user_id":user_id,"person_id":member.get("person_id"),"organization_id":member.get("organization_id"),"membership_id":member["id"],"member_type":"TENANT_MEMBER" if tenant is True else "MEMBER_REVIEW","start_at":s,"end_at":e,"attendee_count":attendees,"status":status,"created_at":now.isoformat(),"updated_at":now.isoformat()})
        return self.db.execute(text("INSERT INTO club_facility_bookings("+",".join(values)+") VALUES ("+",".join(f":{k}" for k in values)+")"),values).lastrowid

    def booking(self,booking_id,user_id,admin=False):
        if admin: self.admin(user_id)
        rows=self.rows("SELECT b.*,f.name AS facility_name,u.display_name,o.standard_name AS organization_name FROM club_facility_bookings b JOIN club_facilities f ON f.id=b.facility_id JOIN v05a_users u ON u.id=b.user_id LEFT JOIN organizations o ON o.id=b.organization_id WHERE b.id=:id",id=booking_id)
        if not rows or (not admin and rows[0]["user_id"]!=user_id): raise HTTPException(403,"无权查看该预约")
        return rows[0]

    def transition(self,booking_id,user_id,action,note="",admin=False):
        self.lock(); booking=self.booking(booking_id,user_id,admin)
        targets={"confirm":"CONFIRMED","reject":"REJECTED","cancel":"CANCELLED","complete":"COMPLETED"}
        if action not in targets or (not admin and action!="cancel"): raise HTTPException(403,"无权执行该预约操作")
        now=datetime.now().isoformat()
        if not admin and booking["start_at"]<=now: raise HTTPException(409,"预约已开始，不能自行取消，请联系管理员")
        if booking["status"]==targets[action]: return
        allowed={"confirm":{"PENDING"},"reject":{"PENDING"},"cancel":{"PENDING","CONFIRMED"},"complete":{"CONFIRMED"}}
        if booking["status"] not in allowed[action]: raise HTTPException(409,"预约状态已变化，不允许该操作")
        if action=="confirm":
            if booking["start_at"]<=now or not self.get(booking["facility_id"])["is_open"]: raise HTTPException(409,"预约已开始或会议室停用，不能确认")
            if self.conflict(booking["facility_id"],booking["start_at"],booking["end_at"],booking_id): raise HTTPException(409,"时段冲突，管理员也不能重复确认")
        if action=="complete" and booking["end_at"]>now: raise HTTPException(409,"会议尚未结束")
        self.db.execute(text("UPDATE club_facility_bookings SET status=:s,review_note=CASE WHEN :admin THEN :n ELSE review_note END,reviewed_by=CASE WHEN :admin THEN :u ELSE reviewed_by END,reviewed_at=CASE WHEN :admin THEN :at ELSE reviewed_at END,updated_at=:at WHERE id=:id"),{"s":targets[action],"n":note[:2000],"u":user_id,"admin":int(admin),"at":now,"id":booking_id})
