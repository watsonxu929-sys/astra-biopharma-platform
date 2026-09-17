from urllib.parse import urlencode

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.routes_platform import get_current_user_id, render
from app.services.knowledge_service import KnowledgeService, CATEGORIES, CATEGORY_VALUES, STATUSES, PROGRESS, KNOWLEDGE_TYPES, LEARNING_TYPES, AUDIENCES, QUESTION_TYPES
import json

router = APIRouter()


def manager(request):
    sec = request.scope.get("security_context", {})
    return bool(sec.get("can_edit") or "edit_data" in sec.get("permissions", []))


def require_manager(request):
    if not manager(request):
        raise HTTPException(403, "需要知识管理权限")


def page(request, mode, **context):
    return render(request, "platform/knowledge.html", mode=mode, manager=manager(request),
                  categories=CATEGORIES, category_values=CATEGORY_VALUES, statuses=STATUSES, progress_labels=PROGRESS,
                  knowledge_types=KNOWLEDGE_TYPES,learning_types=LEARNING_TYPES,audiences=AUDIENCES,question_types=QUESTION_TYPES, **context)


def redirect(url, message="已保存", error=False):
    return RedirectResponse(url + "?" + urlencode({"error" if error else "message": message}), 303)


@router.get("/knowledge")
@router.get("/admin/knowledge")
def knowledge_list(request: Request, q: str = "", category: str = "", status: str = "", progress: str = "", db: Session = Depends(get_db)):
    admin = request.url.path.startswith("/admin/")
    if admin:
        require_manager(request)
    service, uid = KnowledgeService(db), get_current_user_id(request)
    items = service.listing(q=q, category=category, status=status, manager=admin, user_id=uid, progress=progress)
    paths = service.rows("SELECT * FROM learning_paths" + ("" if admin else " WHERE status='PUBLISHED'") + " ORDER BY updated_at DESC")
    counts = service.rows("SELECT p.status,COUNT(*) AS n FROM user_knowledge_progress p JOIN knowledge_items k ON k.id=p.knowledge_id WHERE p.user_id=:u AND k.status='PUBLISHED' GROUP BY p.status", u=uid)
    return page(request, "list", items=items, paths=paths, counts={r["status"]: r["n"] for r in counts}, admin=admin, q=q, category=category, status=status, progress=progress)


@router.get("/knowledge/{item_id:int}")
def knowledge_detail(item_id: int, request: Request, db: Session = Depends(get_db)):
    service, uid = KnowledgeService(db), get_current_user_id(request)
    item = service.get(item_id, manager=manager(request))
    progress = service.rows("SELECT * FROM user_knowledge_progress WHERE user_id=:u AND knowledge_id=:k", u=uid, k=item_id)
    return page(request, "detail", item=item, links=service.links(item_id, manager=manager(request)), user_progress=progress[0] if progress else {}, uid=uid,
                annotations=service.annotations(item_id,uid))


@router.post("/knowledge/{item_id:int}/progress")
def knowledge_progress(item_id: int, request: Request, status: str = Form(...), note: str = Form(""), db: Session = Depends(get_db)):
    KnowledgeService(db).progress(item_id, get_current_user_id(request), status, note.strip())
    db.commit()
    return redirect(f"/knowledge/{item_id}", "学习状态已保存")


@router.get("/admin/knowledge/new")
@router.get("/admin/knowledge/{item_id:int}/edit")
def knowledge_editor(request: Request, item_id: int | None = None, target_type: str = "intelligence", target_q: str = "", db: Session = Depends(get_db)):
    require_manager(request)
    service = KnowledgeService(db)
    item = service.get(item_id, manager=True) if item_id else {"status": "DRAFT", "difficulty": "入门"}
    return page(request, "edit", item=item, links=service.links(item_id, manager=True) if item_id else [],
                target_type=target_type, target_q=target_q, targets=service.target_options(target_type, target_q))


@router.post("/admin/knowledge/save")
@router.post("/admin/knowledge/{item_id:int}/save")
async def knowledge_save(request: Request, item_id: int | None = None, db: Session = Depends(get_db)):
    require_manager(request)
    fields = await request.form()
    try:
        item_id = KnowledgeService(db).save(fields, item_id)
        db.commit()
    except HTTPException as exc:
        db.rollback()
        return page(request, "edit", item={**fields, "id": item_id}, links=[], target_type="intelligence", target_q="", targets=[], error=exc.detail)
    return redirect(f"/admin/knowledge/{item_id}/edit")


@router.post("/admin/knowledge/{item_id:int}/links")
def knowledge_link(item_id: int, request: Request, target_type: str = Form(...), target_id: int = Form(...), db: Session = Depends(get_db)):
    require_manager(request)
    KnowledgeService(db).add_link(item_id, target_type, target_id)
    db.commit()
    return redirect(f"/admin/knowledge/{item_id}/edit", "业务关联已保存")


@router.post("/admin/knowledge/{item_id:int}/links/{link_id:int}/remove")
def knowledge_unlink(item_id: int, link_id: int, request: Request, db: Session = Depends(get_db)):
    require_manager(request)
    db.execute(text("DELETE FROM knowledge_links WHERE id=:id AND knowledge_id=:k"), {"id": link_id, "k": item_id})
    db.commit()
    return redirect(f"/admin/knowledge/{item_id}/edit", "业务关联已解除")


@router.post("/admin/knowledge/{item_id:int}/delete")
def knowledge_delete(item_id: int, request: Request, db: Session = Depends(get_db)):
    require_manager(request)
    try:
        KnowledgeService(db).delete(item_id)
        db.commit()
    except HTTPException as exc:
        db.rollback()
        return redirect(f"/admin/knowledge/{item_id}/edit", str(exc.detail), True)
    return redirect("/admin/knowledge", "草稿已删除")


@router.get("/knowledge/paths/{path_id:int}")
def learning_path(path_id: int, request: Request, db: Session = Depends(get_db)):
    service = KnowledgeService(db)
    item=service.get(path_id, manager=manager(request), path=True)
    return page(request,"path",item=item,training=service.training_summary(item,get_current_user_id(request)))


@router.get("/admin/knowledge/paths/new")
@router.get("/admin/knowledge/paths/{path_id:int}/edit")
def path_editor(request: Request, path_id: int | None = None, db: Session = Depends(get_db)):
    require_manager(request)
    service = KnowledgeService(db)
    return page(request, "path_edit", item=service.get(path_id, manager=True, path=True) if path_id else {"status": "DRAFT"},
                items=service.path_items(path_id, manager=True) if path_id else [], options=service.listing(manager=True))


@router.post("/admin/knowledge/paths/save")
@router.post("/admin/knowledge/paths/{path_id:int}/save")
async def path_save(request: Request, path_id: int | None = None, db: Session = Depends(get_db)):
    require_manager(request)
    form, service = await request.form(), KnowledgeService(db)
    original_id = path_id
    item_ids = [int(v) for v in form.getlist("knowledge_ids") if str(v).isdigit()]
    try:
        path_id = service.save(form, path_id, path=True)
        service.set_path_items(path_id, item_ids)
        db.commit()
    except HTTPException as exc:
        db.rollback()
        return redirect(f"/admin/knowledge/paths/{original_id}/edit" if original_id else "/admin/knowledge/paths/new", str(exc.detail), True)
    return redirect(f"/admin/knowledge/paths/{path_id}/edit")


@router.post("/knowledge/{item_id:int}/annotations")
async def annotation_save(item_id:int,request:Request,db:Session=Depends(get_db)):
    form=await request.form()
    try:
        annotation_id=int(form.get("annotation_id") or 0) or None
        KnowledgeService(db).annotate(item_id,get_current_user_id(request),form,annotation_id)
        db.commit()
    except (ValueError,HTTPException) as exc:
        db.rollback()
        if isinstance(exc,HTTPException) and exc.status_code==403: raise
        return redirect(f"/knowledge/{item_id}",str(exc.detail) if isinstance(exc,HTTPException) else "回复或内容编号无效",True)
    return redirect(f"/knowledge/{item_id}","内容已保存")


@router.post("/knowledge/{item_id:int}/annotations/{annotation_id:int}/delete")
def annotation_delete(item_id:int,annotation_id:int,request:Request,db:Session=Depends(get_db)):
    KnowledgeService(db).delete_annotation(item_id,annotation_id,get_current_user_id(request),request.scope.get("security_context",{}).get("user",{}).get("role")=="admin")
    db.commit(); return redirect(f"/knowledge/{item_id}","内容已删除，已有回复保留")


def training_page(request,mode,**context):
    return render(request,"platform/knowledge_training.html",mode=mode,question_types=QUESTION_TYPES,statuses=STATUSES,**context)


@router.get("/admin/knowledge/questions")
def questions(request:Request,q:str="",knowledge_id:int=0,edit:int=0,db:Session=Depends(get_db)):
    require_manager(request); service=KnowledgeService(db)
    items=service.rows("SELECT q.*,k.title AS knowledge_title FROM knowledge_questions q JOIN knowledge_items k ON k.id=q.knowledge_id WHERE q.title LIKE :q AND (:k=0 OR q.knowledge_id=:k) ORDER BY q.id DESC",q=f"%{q}%",k=knowledge_id)
    rows=service.rows("SELECT * FROM knowledge_questions WHERE id=:id",id=edit) if edit else []
    item=rows[0] if rows else {}
    if item: item={**item,"options":"\n".join(json.loads(item["options_json"])),"correct":",".join(map(str,json.loads(item["correct_json"])))}
    return training_page(request,"questions",items=items,item=item,knowledge=service.listing(manager=True),q=q,knowledge_id=knowledge_id)


@router.post("/admin/knowledge/questions/save")
async def question_save(request:Request,db:Session=Depends(get_db)):
    require_manager(request); form=await request.form()
    try:
        qid=KnowledgeService(db).save_question(form,int(form.get("id") or 0) or None); db.commit()
    except (ValueError,HTTPException) as exc:
        db.rollback(); return redirect("/admin/knowledge/questions",str(exc.detail) if isinstance(exc,HTTPException) else "题目编号无效",True)
    return redirect("/admin/knowledge/questions","题目已保存")


@router.post("/admin/knowledge/questions/{question_id:int}/delete")
def question_delete(question_id:int,request:Request,db:Session=Depends(get_db)):
    require_manager(request)
    try: KnowledgeService(db).delete_question(question_id); db.commit()
    except HTTPException as exc:
        db.rollback(); return redirect("/admin/knowledge/questions",str(exc.detail),True)
    return redirect("/admin/knowledge/questions","无历史题目已删除")


@router.get("/admin/knowledge/exams")
def exams(request:Request,edit:int=0,db:Session=Depends(get_db)):
    require_manager(request); service=KnowledgeService(db)
    rows=service.rows("SELECT * FROM knowledge_exams WHERE id=:id",id=edit) if edit else []
    selected=[r["question_id"] for r in service.rows("SELECT question_id FROM knowledge_exam_questions WHERE exam_id=:id ORDER BY position",id=edit)]
    return training_page(request,"exams",items=service.rows("SELECT e.*,p.title AS path_title,p.version FROM knowledge_exams e JOIN learning_paths p ON p.id=e.path_id ORDER BY e.id DESC"),item=rows[0] if rows else {},paths=service.rows("SELECT * FROM learning_paths ORDER BY id DESC"),questions=service.rows("SELECT q.*,k.title AS knowledge_title FROM knowledge_questions q JOIN knowledge_items k ON k.id=q.knowledge_id WHERE q.status='ACTIVE' ORDER BY q.id"),selected=selected)


@router.post("/admin/knowledge/exams/save")
async def exam_save(request:Request,db:Session=Depends(get_db)):
    require_manager(request); form=await request.form()
    try:
        KnowledgeService(db).save_exam(form,[int(v) for v in form.getlist("question_ids")],int(form.get("id") or 0) or None); db.commit()
    except (ValueError,HTTPException) as exc:
        db.rollback(); return redirect("/admin/knowledge/exams",str(exc.detail) if isinstance(exc,HTTPException) else "考试或题目编号无效",True)
    return redirect("/admin/knowledge/exams","考试已保存")


@router.post("/knowledge/exams/{exam_id:int}/start")
def exam_start(exam_id:int,request:Request,db:Session=Depends(get_db)):
    try: aid=KnowledgeService(db).start_exam(exam_id,get_current_user_id(request)); db.commit()
    except HTTPException as exc:
        db.rollback()
        if exc.status_code==403: raise
        return redirect("/knowledge",str(exc.detail),True)
    return redirect(f"/knowledge/attempts/{aid}","请作答；提交后由系统评分")


@router.get("/knowledge/attempts/{attempt_id:int}")
def attempt_view(attempt_id:int,request:Request,db:Session=Depends(get_db)):
    attempt=KnowledgeService(db).attempt(attempt_id,get_current_user_id(request),manager(request))
    questions=[]
    for q in attempt["snapshot"]["questions"]:
        row={"id":q["id"],"title":q["title"],"question_type":q["question_type"],"knowledge_id":q["knowledge_id"],"options":json.loads(q["options_json"])}
        if attempt["submitted_at"]:
            row.update(correct=json.loads(q["correct_json"]),explanation=q["explanation"],selected=attempt["snapshot"]["answers"].get(str(q["id"]),[]))
        questions.append(row)
    return training_page(request,"attempt",attempt=attempt,questions=questions,own=attempt["user_id"]==get_current_user_id(request))


@router.post("/knowledge/attempts/{attempt_id:int}/submit")
async def exam_submit(attempt_id:int,request:Request,db:Session=Depends(get_db)):
    form=await request.form()
    answers={k[2:]:form.getlist(k) for k in form if k.startswith("q_")}
    KnowledgeService(db).submit_exam(attempt_id,get_current_user_id(request),answers); db.commit()
    return redirect(f"/knowledge/attempts/{attempt_id}","考试已提交，成绩由后端计算")


@router.get("/admin/knowledge/training-records")
@router.get("/knowledge/my-training")
def training_records(request:Request,db:Session=Depends(get_db)):
    admin=request.url.path.startswith("/admin/")
    if admin: require_manager(request)
    return training_page(request,"records",records=KnowledgeService(db).training_records(None if admin else get_current_user_id(request)),admin=admin)
