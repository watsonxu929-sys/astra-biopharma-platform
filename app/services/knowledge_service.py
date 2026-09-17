"""Small knowledge subdomain using the existing session and canonical object IDs."""
from datetime import datetime
import json
import random
import re
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import inspect, text

CATEGORIES = {
    "内部制度": ("管理制度", "入场须知"), "EHS": ("安全基础", "危废管理", "应急管理"),
    "SOP": ("操作流程",), "培训": ("入职培训",),
    "生物医药": ("产业基础", "药物研发", "临床研究", "法规注册", "CMC与生产", "技术平台", "市场准入", "BD与交易", "知识产权", "企业经营"),
    "投资分析": ("商业模式", "Pipeline分析", "临床数据分析", "竞争格局", "财务与现金流", "融资与资本市场", "估值", "催化剂", "风险分析"),
}
CATEGORY_VALUES = tuple(f"{group}/{name}" for group, names in CATEGORIES.items() for name in names)
STATUSES = {"DRAFT": "草稿", "PUBLISHED": "已发布", "ARCHIVED": "已归档"}
PROGRESS = {"NOT_STARTED": "未开始", "LEARNING": "学习中", "MASTERED": "已掌握", "REVIEW_LATER": "稍后复习"}
KNOWLEDGE_TYPES = {"INDUSTRY":"产业知识", "INVESTMENT":"投资分析", "INTERNAL_POLICY":"内部制度", "EHS":"EHS知识", "SOP":"操作SOP", "REGULATION":"法规政策", "TRAINING":"培训知识"}
AUDIENCES = {"ALL_USERS":"全部用户", "CLUB_MEMBERS":"Q-BAY会员", "TENANT_MEMBERS":"入驻企业会员（须可靠核验）", "INTERNAL_STAFF":"内部运营人员"}
LEARNING_TYPES = {"GENERAL_LEARNING":"普通学习", "REQUIRED_TRAINING":"必修培训"}
QUESTION_TYPES = {"SINGLE_CHOICE":"单选题", "MULTIPLE_CHOICE":"多选题", "TRUE_FALSE":"判断题"}
TARGETS = {
    "intelligence": ("v06_intelligence_items", "title", "/intelligence/"),
    "organization": ("organizations", "standard_name", "/admin/organizations/"),
    "person": ("people", "name", "/network/people/"),
}


class KnowledgeService:
    def __init__(self, db):
        self.db = db

    def rows(self, sql, **params):
        return [dict(r) for r in self.db.execute(text(sql), params).mappings()]

    def get(self, item_id, *, manager=False, path=False):
        table = "learning_paths" if path else "knowledge_items"
        rows = self.rows(f"SELECT * FROM {table} WHERE id=:id", id=item_id)
        if not rows or (not manager and rows[0]["status"] != "PUBLISHED"):
            raise HTTPException(404, "内容不存在或尚未发布")
        return rows[0]

    def listing(self, *, q="", category="", status="", manager=False, user_id=None, progress=""):
        clauses, params = [], {"q": f"%{q}%", "category": category, "uid": user_id}
        if not manager:
            clauses.append("k.status='PUBLISHED'")
        elif status in STATUSES:
            clauses.append("k.status=:status")
            params["status"] = status
        if q:
            clauses.append("(k.title LIKE :q OR k.summary LIKE :q OR k.tags LIKE :q)")
        if category:
            clauses.append("(k.category=:category OR k.category LIKE :category || '/%')")
        if progress in PROGRESS:
            clauses.append("COALESCE(p.status,'NOT_STARTED')=:progress")
            params["progress"] = progress
        return self.rows("SELECT k.*,COALESCE(p.status,'NOT_STARTED') AS progress_status FROM knowledge_items k "
                         "LEFT JOIN user_knowledge_progress p ON p.knowledge_id=k.id AND p.user_id=:uid WHERE "
                         + (" AND ".join(clauses) or "1=1") + " ORDER BY k.updated_at DESC,k.id DESC LIMIT 200", **params)

    def save(self, fields, item_id=None, *, path=False):
        self.lock()
        table = "learning_paths" if path else "knowledge_items"
        original = self.get(item_id, manager=True, path=path) if item_id else {}
        keys = ("title", "description", "status") if path else (
            "title", "category", "summary", "body", "key_points", "difficulty", "tags",
            "source_name", "source_url", "region", "effective_version", "status")
        data = {k: str(fields.get(k, "")).strip() for k in keys}
        extra = ("learning_type", "version", "effective_date", "audience") if path else ("knowledge_type", "source_file", "source_version", "source_section", "effective_date", "expiry_date", "applicable_to")
        defaults = {"learning_type":"GENERAL_LEARNING", "version":"1", "audience":"ALL_USERS", "knowledge_type":"INDUSTRY"}
        data.update({k:str(fields.get(k, original.get(k, defaults.get(k,"")))).strip() for k in extra})
        for field in ("effective_date", "expiry_date"):
            if data.get(field):
                try:
                    datetime.strptime(data[field], "%Y-%m-%d")
                except ValueError:
                    raise HTTPException(422, "请填写有效的生效/失效日期")
        if data.get("expiry_date") and data.get("effective_date") and data["expiry_date"] < data["effective_date"]:
            raise HTTPException(422, "失效日期不能早于生效日期")
        if path:
            data["requires_exam"] = int(str(fields.get("requires_exam",original.get("requires_exam",0))) in {"1","true","on"})
            if data["learning_type"] not in LEARNING_TYPES or data["audience"] not in AUDIENCES or not re.fullmatch(r"[A-Za-z0-9._-]{1,50}",data["version"]):
                raise HTTPException(422,"请选择培训类型、适用对象和有效版本（字母、数字、点或连字符）")
            if item_id and data["version"] == original["version"] and self.path_locked(item_id,original["version"]):
                if any(data[k] != original[k] for k in (*extra,"requires_exam","title","description")):
                    raise HTTPException(409,"已有学习/考试历史，请使用新版本修改培训要求")
            if item_id and data["version"] != original["version"] and self.path_locked(item_id,data["version"]):
                raise HTTPException(409,"该版本已有历史记录，请使用尚未使用的新版本")
        elif data["knowledge_type"] not in KNOWLEDGE_TYPES:
            raise HTTPException(422,"内容性质无效")
        if not data["title"] or len(data["title"]) > 300 or data["status"] not in STATUSES:
            raise HTTPException(422, "请填写标题（最多300字）并选择有效状态")
        if not path:
            if data["category"] not in CATEGORY_VALUES or data["difficulty"] not in {"入门", "进阶", "专业"}:
                raise HTTPException(422, "请选择分类和难度")
            try:
                url = urlsplit(data["source_url"])
            except ValueError:
                raise HTTPException(422, "来源URL格式无效")
            if data["source_url"] and (url.scheme not in {"http", "https"} or not url.hostname or url.username):
                raise HTTPException(422, "来源URL必须是有效的HTTP或HTTPS地址")
            if data["status"] == "PUBLISHED" and not data["body"]:
                raise HTTPException(422, "发布前请填写知识正文")
        data["updated_at"] = datetime.now().isoformat()
        if item_id:
            self.db.execute(text(f"UPDATE {table} SET " + ",".join(f"{k}=:{k}" for k in data) + " WHERE id=:id"), {**data, "id": item_id})
        else:
            data["created_at"] = data["updated_at"]
            result = self.db.execute(text(f"INSERT INTO {table} (" + ",".join(data) + ") VALUES (" + ",".join(f":{k}" for k in data) + ")"), data)
            item_id = result.lastrowid
        return item_id

    def target_options(self, kind, q=""):
        if kind not in TARGETS:
            raise HTTPException(422, "不支持的关联对象")
        table, label, _ = TARGETS[kind]
        return self.rows(f"SELECT id,{label} AS label FROM {table} WHERE {label} LIKE :q ORDER BY id DESC LIMIT 100", q=f"%{q}%")

    def add_link(self, item_id, kind, target_id):
        self.get(item_id, manager=True)
        if kind not in TARGETS:
            raise HTTPException(422, "不支持的关联对象")
        table = TARGETS[kind][0]
        if not self.rows(f"SELECT id FROM {table} WHERE id=:id", id=target_id):
            raise HTTPException(422, "关联对象不存在")
        self.db.execute(text("INSERT INTO knowledge_links(knowledge_id,target_type,target_id) VALUES (:k,:t,:i) ON CONFLICT DO NOTHING"), {"k": item_id, "t": kind, "i": target_id})

    def links(self, item_id, *, manager=False):
        result = []
        for kind, (table, label, url) in TARGETS.items():
            visibility = ""
            if not manager:
                visibility = " AND t.status='published'" if kind == "intelligence" else " AND COALESCE(t.visibility,'内部') IN ('内部','公开','internal','public')"
            for row in self.rows(f"SELECT l.id,t.id AS target_id,t.{label} AS label" + (",t.external_id" if kind == "organization" else "") + f" FROM knowledge_links l JOIN {table} t ON t.id=l.target_id WHERE l.knowledge_id=:id AND l.target_type=:kind" + visibility, id=item_id, kind=kind):
                row["url"] = f"/network/entities/organization/{row['external_id']}" if kind == "organization" else url + str(row["target_id"])
                row["kind"] = kind
                result.append(row)
        return result

    def related(self, kind, target_id):
        if not inspect(self.db.get_bind()).has_table("knowledge_items"):
            return []
        return self.rows("SELECT k.id,k.title FROM knowledge_links l JOIN knowledge_items k ON k.id=l.knowledge_id WHERE l.target_type=:kind AND l.target_id=:id AND k.status='PUBLISHED' ORDER BY k.updated_at DESC", kind=kind, id=target_id)

    def progress(self, item_id, user_id, status, note):
        self.lock()
        self.get(item_id)
        if user_id is None or not self.rows("SELECT id FROM v05a_users WHERE id=:id", id=user_id):
            raise HTTPException(403, "请使用正式登录账号保存自己的学习进度")
        if status not in PROGRESS or len(note) > 3000:
            raise HTTPException(422, "学习状态或备注无效")
        self.db.execute(text("INSERT INTO user_knowledge_progress(user_id,knowledge_id,status,note,updated_at) VALUES (:u,:k,:s,:n,:at) ON CONFLICT(user_id,knowledge_id) DO UPDATE SET status=excluded.status,note=excluded.note,updated_at=excluded.updated_at"), {"u": user_id, "k": item_id, "s": status, "n": note, "at": datetime.now().isoformat()})
        if status == "MASTERED":
            history = json.loads(self.rows("SELECT training_history_json FROM user_knowledge_progress WHERE user_id=:u AND knowledge_id=:k",u=user_id,k=item_id)[0]["training_history_json"])
            for path in self.rows("SELECT p.* FROM learning_paths p JOIN learning_path_items i ON i.path_id=p.id WHERE i.knowledge_id=:k AND p.status='PUBLISHED' AND p.learning_type='REQUIRED_TRAINING'",k=item_id):
                if self.audience_allowed(path,user_id):
                    key=f"{path['id']}:{path['version']}"
                    ids=[r["knowledge_id"] for r in self.rows("SELECT knowledge_id FROM learning_path_items WHERE path_id=:p ORDER BY position",p=path["id"])]
                    history.setdefault(key,{"path_id":path["id"],"version":path["version"],"title":path["title"],"ids":ids,"requires_exam":path["requires_exam"],"at":datetime.now().isoformat()})
            self.db.execute(text("UPDATE user_knowledge_progress SET training_history_json=:h WHERE user_id=:u AND knowledge_id=:k"),{"h":json.dumps(history,ensure_ascii=False),"u":user_id,"k":item_id})

    def path_items(self, path_id, *, manager=False, user_id=None):
        return self.rows("SELECT k.*,i.position,COALESCE(p.status,'NOT_STARTED') AS progress_status FROM learning_path_items i JOIN knowledge_items k ON k.id=i.knowledge_id LEFT JOIN user_knowledge_progress p ON p.knowledge_id=k.id AND p.user_id=:u WHERE i.path_id=:id" + ("" if manager else " AND k.status='PUBLISHED'") + " ORDER BY i.position", id=path_id, u=user_id)

    def set_path_items(self, path_id, item_ids):
        path = self.get(path_id, manager=True, path=True)
        previous=[r["knowledge_id"] for r in self.rows("SELECT knowledge_id FROM learning_path_items WHERE path_id=:p ORDER BY position",p=path_id)]
        if previous!=item_ids and self.path_locked(path_id,path["version"]):
            raise HTTPException(409,"该版本已有学习/考试历史，请先设置新版本再调整知识顺序")
        if len(item_ids) > 200 or len(item_ids) != len(set(item_ids)):
            raise HTTPException(422, "学习路径最多200条且不能重复")
        for item_id in item_ids:
            self.get(item_id, manager=True)
        self.db.execute(text("DELETE FROM learning_path_items WHERE path_id=:id"), {"id": path_id})
        for position, item_id in enumerate(item_ids, 1):
            self.db.execute(text("INSERT INTO learning_path_items(path_id,knowledge_id,position) VALUES (:p,:k,:n)"), {"p": path_id, "k": item_id, "n": position})

    def delete(self, item_id):
        item = self.get(item_id, manager=True)
        references = sum(self.rows(f"SELECT COUNT(*) AS n FROM {table} WHERE knowledge_id=:id", id=item_id)[0]["n"] for table in ("knowledge_links", "learning_path_items", "user_knowledge_progress", "knowledge_annotations", "knowledge_questions"))
        if item["status"] != "DRAFT" or references:
            raise HTTPException(409, "只有无关联、无学习记录的草稿可删除；请使用归档")
        self.db.execute(text("DELETE FROM knowledge_items WHERE id=:id"), {"id": item_id})

    def lock(self):
        conn=self.db.connection().connection.driver_connection
        if not conn.in_transaction:
            conn.execute("BEGIN IMMEDIATE")

    def audience_allowed(self,path,user_id):
        from app.services.membership_access_service import service_member_identity
        identity=service_member_identity(self.db,user_id)
        if not identity["user"] or (path["effective_date"] and path["effective_date"]>datetime.now().date().isoformat()):
            return False
        return {"ALL_USERS":True,"CLUB_MEMBERS":bool(identity["member"]),"TENANT_MEMBERS":identity["tenant_member"] is True,"INTERNAL_STAFF":identity["user"].get("role") in {"admin","operator"}}.get(path["audience"],False)

    def path_locked(self,path_id,version):
        key=json.dumps(f"{path_id}:{version}")+":"
        return bool(self.rows("SELECT id FROM knowledge_exam_attempts WHERE exam_id IN (SELECT id FROM knowledge_exams WHERE path_id=:p) AND path_version=:v LIMIT 1",p=path_id,v=version) or self.rows("SELECT id FROM user_knowledge_progress WHERE instr(training_history_json,:key)>0 LIMIT 1",key=key))

    def annotations(self,knowledge_id,user_id):
        return self.rows("SELECT a.*,u.display_name FROM knowledge_annotations a JOIN v05a_users u ON u.id=a.user_id WHERE a.knowledge_id=:k AND (a.user_id=:u OR a.visibility='INTERNAL') ORDER BY a.created_at,a.id",k=knowledge_id,u=user_id)

    def annotate(self,knowledge_id,user_id,fields,annotation_id=None):
        self.get(knowledge_id)
        kind,visibility=str(fields.get("type","NOTE")),str(fields.get("visibility","PRIVATE"))
        content=str(fields.get("content","")).strip()
        if kind not in {"NOTE","VIEWPOINT","COMMENT"} or visibility not in {"PRIVATE","INTERNAL"} or not content or len(content)>10000:
            raise HTTPException(422,"请填写有效的笔记、观点或评论（最多10000字）")
        visibility="PRIVATE" if kind=="NOTE" else "INTERNAL" if kind=="COMMENT" else visibility
        parent_id=int(fields.get("parent_id") or 0) or None
        if parent_id:
            parent=self.rows("SELECT * FROM knowledge_annotations WHERE id=:id AND knowledge_id=:k",id=parent_id,k=knowledge_id)
            if kind!="COMMENT" or not parent or parent[0]["type"]!="COMMENT" or parent[0]["parent_id"] or parent[0]["deleted"]:
                raise HTTPException(422,"仅允许回复本条知识下的一级评论")
        at=datetime.now().isoformat()
        if annotation_id:
            original=self.rows("SELECT * FROM knowledge_annotations WHERE id=:id AND knowledge_id=:k",id=annotation_id,k=knowledge_id)
            if not original or original[0]["user_id"]!=user_id or original[0]["deleted"]:
                raise HTTPException(403,"只能编辑自己的内容")
            if kind!=original[0]["type"] or parent_id!=original[0]["parent_id"]:
                raise HTTPException(422,"不能改变内容类型或回复对象")
            self.db.execute(text("UPDATE knowledge_annotations SET content=:c,visibility=:v,updated_at=:at WHERE id=:id"),{"c":content,"v":visibility,"at":at,"id":annotation_id})
        else:
            self.db.execute(text("INSERT INTO knowledge_annotations(knowledge_id,user_id,type,content,visibility,parent_id,created_at,updated_at) VALUES (:k,:u,:t,:c,:v,:p,:at,:at)"),{"k":knowledge_id,"u":user_id,"t":kind,"c":content,"v":visibility,"p":parent_id,"at":at})

    def delete_annotation(self,knowledge_id,annotation_id,user_id,admin=False):
        row=self.rows("SELECT * FROM knowledge_annotations WHERE id=:id AND knowledge_id=:k",id=annotation_id,k=knowledge_id)
        if not row or (row[0]["user_id"]!=user_id and not (admin and row[0]["type"]=="COMMENT")):
            raise HTTPException(403,"只能删除自己的内容；管理员仅可移除不当评论")
        # Tombstone retains replies without disclosing the deleted text.
        self.db.execute(text("UPDATE knowledge_annotations SET content='',deleted=1,updated_at=:at WHERE id=:id"),{"at":datetime.now().isoformat(),"id":annotation_id})

    def save_question(self,fields,question_id=None):
        self.lock()
        title=str(fields.get("title","")).strip()
        kind=fields.get("question_type")
        options=[s.strip() for s in str(fields.get("options","")).splitlines() if s.strip()]
        if kind=="TRUE_FALSE": options=["正确","错误"]
        try:
            answers=sorted({int(x.strip()) for x in str(fields.get("correct","")).replace("，",",").split(",") if x.strip()})
            knowledge_id=int(fields.get("knowledge_id") or 0)
        except ValueError:
            raise HTTPException(422,"答案请填写选项序号，以逗号分隔")
        self.get(knowledge_id,manager=True)
        if kind not in QUESTION_TYPES or not title or len(title)>2000 or not 2<=len(options)<=10 or not answers or any(a<1 or a>len(options) for a in answers) or (kind!="MULTIPLE_CHOICE" and len(answers)!=1):
            raise HTTPException(422,"请检查题型、题目、2–10个选项及正确答案序号")
        status=fields.get("status","ACTIVE")
        if status not in {"ACTIVE","INACTIVE"}: raise HTTPException(422,"题目状态无效")
        values={"knowledge_id":knowledge_id,"title":title,"question_type":kind,"options_json":json.dumps(options,ensure_ascii=False),"correct_json":json.dumps(answers),"explanation":str(fields.get("explanation","")).strip(),"status":status,"updated_at":datetime.now().isoformat()}
        if question_id:
            if not self.rows("SELECT id FROM knowledge_questions WHERE id=:id",id=question_id): raise HTTPException(404,"题目不存在")
            self.db.execute(text("UPDATE knowledge_questions SET "+",".join(f"{k}=:{k}" for k in values)+" WHERE id=:id"),{**values,"id":question_id})
        else:
            values["created_at"]=values["updated_at"]
            question_id=self.db.execute(text("INSERT INTO knowledge_questions("+",".join(values)+") VALUES ("+",".join(f":{k}" for k in values)+")"),values).lastrowid
        return question_id

    def delete_question(self,question_id):
        self.lock()
        refs=self.rows("SELECT exam_id FROM knowledge_exam_questions WHERE question_id=:id",id=question_id)
        history=self.rows("SELECT a.id FROM knowledge_exam_attempts a,json_each(a.answers_json,'$.questions') j WHERE json_extract(j.value,'$.id')=:id LIMIT 1",id=question_id)
        if refs or history: raise HTTPException(409,"题目已有考试引用或作答历史，请停用而不是删除")
        self.db.execute(text("DELETE FROM knowledge_questions WHERE id=:id"),{"id":question_id})

    def save_exam(self,fields,question_ids,exam_id=None):
        self.lock()
        try:
            path_id=int(fields.get("path_id") or 0); passing=int(fields.get("pass_score",60)); maximum=int(fields.get("max_attempts",3))
        except ValueError: raise HTTPException(422,"请选择路径并填写分数、次数")
        path=self.get(path_id,manager=True,path=True)
        title=str(fields.get("title","")).strip(); status=fields.get("status","DRAFT")
        if not title or not 1<=passing<=100 or not 1<=maximum<=100 or status not in STATUSES or len(question_ids)!=len(set(question_ids)) or len(question_ids)>200:
            raise HTTPException(422,"考试名称、分数、次数或题目选择无效")
        if status=="PUBLISHED" and not question_ids: raise HTTPException(422,"发布考试前请选择题目")
        for qid in question_ids:
            q=self.rows("SELECT q.id FROM knowledge_questions q JOIN learning_path_items i ON i.knowledge_id=q.knowledge_id WHERE q.id=:id AND i.path_id=:p AND q.status='ACTIVE'",id=qid,p=path_id)
            if not q: raise HTTPException(422,"请选择该学习路径知识下的启用题目")
        original=self.rows("SELECT * FROM knowledge_exams WHERE id=:id",id=exam_id) if exam_id else []
        if exam_id and not original: raise HTTPException(404,"考试不存在")
        if self.rows("SELECT id FROM knowledge_exams WHERE path_id=:p AND id<>:id",p=path_id,id=exam_id or 0): raise HTTPException(409,"该学习路径已有考试，请编辑原考试")
        values={"path_id":path_id,"title":title,"description":str(fields.get("description","")).strip(),"pass_score":passing,"max_attempts":maximum,"random_order":int(str(fields.get("random_order",0)) in {"1","on"}),"status":status,"updated_at":datetime.now().isoformat()}
        if original:
            old=original[0]
            if old["path_id"]!=path_id: raise HTTPException(409,"已有考试不能换绑学习路径，请在对应路径另建考试")
            prior=[r["question_id"] for r in self.rows("SELECT question_id FROM knowledge_exam_questions WHERE exam_id=:e ORDER BY position",e=exam_id)]
            if self.path_locked(path_id,path["version"]) and (prior!=question_ids or any(old[k]!=values[k] for k in ("title","description","pass_score","max_attempts","random_order"))):
                raise HTTPException(409,"该培训版本已有历史，请先更新路径版本再调整考试")
            self.db.execute(text("UPDATE knowledge_exams SET "+",".join(f"{k}=:{k}" for k in values)+" WHERE id=:id"),{**values,"id":exam_id})
        else:
            values["created_at"]=values["updated_at"]
            exam_id=self.db.execute(text("INSERT INTO knowledge_exams("+",".join(values)+") VALUES ("+",".join(f":{k}" for k in values)+")"),values).lastrowid
        self.db.execute(text("DELETE FROM knowledge_exam_questions WHERE exam_id=:e"),{"e":exam_id})
        for n,qid in enumerate(question_ids,1):
            self.db.execute(text("INSERT INTO knowledge_exam_questions(exam_id,question_id,position) VALUES (:e,:q,:n)"),{"e":exam_id,"q":qid,"n":n})
        return exam_id

    def training_summary(self,path,user_id):
        items=self.path_items(path["id"],manager=True,user_id=user_id)
        key=f"{path['id']}:{path['version']}"
        mastered=set()
        for row in self.rows("SELECT knowledge_id,training_history_json FROM user_knowledge_progress WHERE user_id=:u",u=user_id):
            if key in json.loads(row["training_history_json"]): mastered.add(row["knowledge_id"])
        if path["learning_type"]=="GENERAL_LEARNING": mastered={i["id"] for i in items if i["progress_status"]=="MASTERED"}
        for item in items: item["training_mastered"]=item["id"] in mastered
        exam=self.rows("SELECT * FROM knowledge_exams WHERE path_id=:p",p=path["id"])
        attempts=self.rows("SELECT id,score,passed,attempt_no,submitted_at,path_version FROM knowledge_exam_attempts WHERE exam_id IN (SELECT id FROM knowledge_exams WHERE path_id=:p) AND user_id=:u AND path_version=:v ORDER BY id DESC",p=path["id"],u=user_id,v=path["version"])
        learned=sum(i["training_mastered"] for i in items)
        done=bool(items) and learned==len(items)
        return {"items":items,"learned":learned,"total":len(items),"eligible":self.audience_allowed(path,user_id),"exam":exam[0] if exam else None,"attempts":attempts,"learned_all":done,"completed":done and (not path["requires_exam"] or any(a["passed"] for a in attempts))}

    def start_exam(self,exam_id,user_id):
        self.lock()
        exam=self.rows("SELECT * FROM knowledge_exams WHERE id=:id AND status='PUBLISHED'",id=exam_id)
        if not exam: raise HTTPException(404,"考试未发布")
        exam=exam[0]; path=self.get(exam["path_id"],path=True)
        summary=self.training_summary(path,user_id)
        if not summary["eligible"]: raise HTTPException(403,"当前账号不符合本培训适用对象或培训尚未生效")
        if not summary["learned_all"] or any(i["status"]!="PUBLISHED" for i in summary["items"]): raise HTTPException(409,"请先完成当前版本全部知识学习")
        ongoing=self.rows("SELECT id FROM knowledge_exam_attempts WHERE exam_id=:e AND user_id=:u AND path_version=:v AND submitted_at IS NULL",e=exam_id,u=user_id,v=path["version"])
        if ongoing: return ongoing[0]["id"]
        count=len(summary["attempts"])
        if count>=exam["max_attempts"]: raise HTTPException(409,"已达到该培训版本的最大尝试次数")
        questions=self.rows("SELECT q.* FROM knowledge_exam_questions i JOIN knowledge_questions q ON q.id=i.question_id WHERE i.exam_id=:e ORDER BY i.position",e=exam_id)
        if not questions or any(q["status"]!="ACTIVE" for q in questions): raise HTTPException(409,"考试题目缺失或停用，请联系管理员")
        if any(q["knowledge_id"] not in {i["id"] for i in summary["items"]} for q in questions):
            raise HTTPException(409,"考试题目与当前路径不一致，请联系管理员更新考试")
        if exam["random_order"]: random.SystemRandom().shuffle(questions)
        from app.services.membership_access_service import service_member_identity
        identity=service_member_identity(self.db,user_id)
        snapshot={"path_id":path["id"],"version":path["version"],"path_title":path["title"],"exam_title":exam["title"],"pass_score":exam["pass_score"],"learned":summary["learned"],"total":summary["total"],"display_name":identity["user"].get("display_name",""),"organization":(identity["member"] or {}).get("organization_name",""),"questions":questions,"answers":{}}
        return self.db.execute(text("INSERT INTO knowledge_exam_attempts(exam_id,user_id,path_version,attempt_no,started_at,answers_json) VALUES (:e,:u,:v,:n,:at,:data)"),{"e":exam_id,"u":user_id,"v":path["version"],"n":count+1,"at":datetime.now().isoformat(),"data":json.dumps(snapshot,ensure_ascii=False)}).lastrowid

    def attempt(self,attempt_id,user_id,manager=False):
        rows=self.rows("SELECT * FROM knowledge_exam_attempts WHERE id=:id",id=attempt_id)
        if not rows or (rows[0]["user_id"]!=user_id and not manager): raise HTTPException(403,"无权查看该考试记录")
        row=rows[0]; row["snapshot"]=json.loads(row["answers_json"])
        return row

    def submit_exam(self,attempt_id,user_id,answers):
        self.lock()
        attempt=self.attempt(attempt_id,user_id)
        if attempt["submitted_at"]: return attempt_id
        snapshot=attempt["snapshot"]; graded={}; correct=0
        if any(str(k) not in {str(q["id"]) for q in snapshot["questions"]} for k in answers): raise HTTPException(422,"提交包含无效题目")
        for question in snapshot["questions"]:
            options=json.loads(question["options_json"])
            try: selected=sorted({int(v) for v in answers.get(str(question["id"]),[])})
            except (ValueError,TypeError): raise HTTPException(422,"选项无效")
            if any(v<1 or v>len(options) for v in selected) or (question["question_type"]!="MULTIPLE_CHOICE" and len(selected)>1): raise HTTPException(422,"答案与题型不符")
            graded[str(question["id"])]=selected
            correct+=selected==json.loads(question["correct_json"])
        score=round(correct*100/len(snapshot["questions"]),2)
        snapshot["answers"]=graded
        self.db.execute(text("UPDATE knowledge_exam_attempts SET submitted_at=:at,score=:s,passed=:p,answers_json=:j WHERE id=:id"),{"at":datetime.now().isoformat(),"s":score,"p":int(score>=snapshot["pass_score"]),"j":json.dumps(snapshot,ensure_ascii=False),"id":attempt_id})
        return attempt_id

    def training_records(self,user_id=None):
        records={}
        users=self.rows("SELECT id,display_name,role FROM v05a_users WHERE (:u IS NULL OR id=:u)",u=user_id)
        names={u["id"]:u["display_name"] for u in users}
        def entry(uid,pid,version,title,total,required,organization=""):
            return records.setdefault((uid,pid,version),{"user_id":uid,"name":names.get(uid,"已停用用户"),"organization":organization,"path_id":pid,"version":version,"title":title,"total":total,"learned_ids":set(),"learned":0,"requires_exam":required,"attempts":0,"best_score":None,"last_score":None,"passed":False,"completed_at":""})
        for path in self.rows("SELECT * FROM learning_paths WHERE status='PUBLISHED' AND learning_type='REQUIRED_TRAINING'"):
            total=len(self.path_items(path["id"],manager=True))
            for user in users:
                if self.audience_allowed(path,user["id"]): entry(user["id"],path["id"],path["version"],path["title"],total,path["requires_exam"])
        for progress in self.rows("SELECT user_id,knowledge_id,training_history_json FROM user_knowledge_progress WHERE (:u IS NULL OR user_id=:u)",u=user_id):
            for history in json.loads(progress["training_history_json"]).values():
                r=entry(progress["user_id"],history["path_id"],history["version"],history["title"],len(history["ids"]),history["requires_exam"])
                r["learned_ids"].add(progress["knowledge_id"]); r["learning_at"]=max(r.get("learning_at",""),history["at"])
        for attempt in self.rows("SELECT * FROM knowledge_exam_attempts WHERE (:u IS NULL OR user_id=:u) ORDER BY id",u=user_id):
            s=json.loads(attempt["answers_json"])
            r=entry(attempt["user_id"],s["path_id"],attempt["path_version"],s["path_title"],s["total"],1,s["organization"])
            r["learned"]=s["learned"]; r["attempts"]+=1; r["attempt_id"]=attempt["id"]
            r["organization"]=s["organization"]; r["name"]=s["display_name"]
            if attempt["submitted_at"]:
                r["last_score"]=attempt["score"]; r["best_score"]=max(r["best_score"] or 0,attempt["score"])
                if attempt["passed"]: r["passed"]=True; r["completed_at"]=r["completed_at"] or attempt["submitted_at"]
        from app.services.membership_access_service import service_member_identity
        for r in records.values():
            r["learned"]=max(r["learned"],len(r["learned_ids"]))
            r["completed"]=bool(r["total"]) and r["learned"]>=r["total"] and (not r["requires_exam"] or r["passed"])
            if r["completed"] and not r["completed_at"]: r["completed_at"]=r.get("learning_at","")
            if not r["organization"]: r["organization"]=(service_member_identity(self.db,r["user_id"])["member"] or {}).get("organization_name","")
        return list(records.values())
