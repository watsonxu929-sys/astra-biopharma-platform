"""Small knowledge subdomain using the existing session and canonical object IDs."""
from datetime import datetime
import json
import random
import re
import hashlib
from urllib.parse import urlsplit

from fastapi import HTTPException
from sqlalchemy import inspect, text

CATEGORIES = {
    "政策": ("产业扶持", "招商", "研发资助", "人才", "空间载体", "成果转化", "融资支持"),
    "孵化器运营": ("运营管理",),
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


def validate_policy(value):
    from app.services.processing.article_facts import parse_time
    if not isinstance(value, dict):
        raise HTTPException(422, '政策元数据必须是字段对象')
    allowed = {'official_title','issuer','document_number','country','province','city','district','park',
               'scope_text','industry','applicable_to','conditions','support_text','publication_date',
               'effective_date','expiry_date','effect_status','effect_basis','windows','relations'}
    result = {k:str(v).strip()[:10000] for k,v in value.items() if k in allowed-{'windows','relations'}}
    result.setdefault('effect_status','UNVERIFIED')
    if result['effect_status'] not in {'UNVERIFIED','VERIFIED','REPEALED'}:
        raise HTTPException(422, '文件效力核对状态无效')
    if result['effect_status'] != 'UNVERIFIED' and not result.get('effect_basis'):
        raise HTTPException(422, '效力确认必须保留明确文件依据')
    for key in ('publication_date','effective_date','expiry_date'):
        if result.get(key) and parse_time(result[key])[0] is None:
            raise HTTPException(422, '日期无法解析；未知日期请留空，不得填入采集时间')
    windows = value.get('windows',[])
    if not isinstance(windows,list) or len(windows)>20:
        raise HTTPException(422,'申报窗口最多20个，须分别保留期限含义')
    result['windows'] = []
    for w in windows:
        if not isinstance(w,dict) or not w.get('label') or not w.get('basis'):
            raise HTTPException(422,'每个期限需要事项名称与原文依据')
        out = {k:str(w.get(k,'')).strip()[:2000] for k in ('label','basis','start','end')}
        times = [parse_time(out[k])[0] if out[k] else None for k in ('start','end')]
        if any(out[k] and times[i] is None for i,k in enumerate(('start','end'))) or (all(times) and times[0]>times[1]):
            raise HTTPException(422,'期限日期无效或起止倒置')
        result['windows'].append(out)
    relations=value.get('relations',[])
    if not isinstance(relations,list) or len(relations)>30:
        raise HTTPException(422,'关联文件最多30条')
    result['relations']=[]
    for relation in relations:
        if not isinstance(relation,dict) or not relation.get('basis') or relation.get('type') not in {'原政策','细则','年度通知','更正','延期','废止','替代'}:
            raise HTTPException(422,'关联文件必须有关系类型和文件依据')
        target=urlsplit(str(relation.get('url','')))
        if target.scheme not in {'http','https'} or not target.hostname or target.username:
            raise HTTPException(422,'关联文件需要有效公开URL')
        result['relations'].append({k:str(relation.get(k,''))[:2000] for k in ('type','url','basis')})
    return result


def policy_view(value):
    from app.services.processing.article_facts import parse_time,TZ
    from datetime import timedelta
    result=validate_policy(value)
    result['region_label']=' / '.join(dict.fromkeys(result[k] for k in ('country','province','city','district','park') if result.get(k)))
    current=datetime.now(TZ)
    for w in result['windows']:
        start,_=parse_time(w['start']); end,precision=parse_time(w['end'])
        if end and precision=='date':end=end+timedelta(days=1)
        w['status']='期限待核对' if not start or not end else '即将开放' if current<start else '已截止' if current>=end else '开放中'
    return result


def process_material_task(payload, db_path=None):
    """Existing task runner handler. No parsing or fetching in GET/submit handlers."""
    from pathlib import Path
    from sqlalchemy import create_engine,event
    from sqlalchemy.orm import Session
    from app.settings import resolved_db_path
    from app.services.collection_scheduler import _pytest_database_is_safe
    from app.services.knowledge_material_parser import parse_material
    from app.services.collection_service import _http_get,check_robots,_validate_source_response,FREQUENCY_HOURS
    from app.services.member_import_service import validate_public_url
    from datetime import timedelta
    path=Path(db_path).resolve() if db_path else resolved_db_path()
    if not _pytest_database_is_safe(path):raise RuntimeError('isolated_database_required')
    engine=create_engine('sqlite:///'+path.as_posix())
    @event.listens_for(engine,'connect')
    def protect(conn,_):
        conn.execute('PRAGMA foreign_keys=ON')
        if conn.execute('PRAGMA foreign_keys').fetchone()[0]!=1:raise RuntimeError('FK_required')
    try:
        with Session(engine) as db:
            service=KnowledgeService(db,user_id=int(payload['owner_user_id']))
            mid=int(payload['material_id']); material=service.material(mid)
            if material['source_id']:
                # Source subscriptions reuse collected evidence; never fetch a second copy
                # or require the collection to have been published as Intelligence.
                config=json.loads(material['config_json']);cursor=int(config.get('snapshot_cursor',0))
                snapshots=service.rows("SELECT id,url,page_title,raw_html,cleaned_text,raw_content,http_status,evidence_status FROM v04g_source_snapshots WHERE monitoring_source_id=:s AND id>:cursor AND http_status=200 ORDER BY id LIMIT 10",s=material['source_id'],cursor=cursor)
                queued=[]
                for sn in snapshots:
                    if not (sn['raw_html'] or sn['cleaned_text'] or sn['raw_content']):continue
                    body=sn['raw_html'] or sn['cleaned_text'] or sn['raw_content']
                    if sn['raw_html']:_validate_source_response(body,'text/html','html')
                    child=service.register_material({'title':sn['page_title'] or material['title'],'url':sn['url'],'access_scope':material['access_scope'],'category':config.get('category',''),'policy':config.get('policy',{})},body.encode('utf-8'),'snapshot.html' if sn['raw_html'] else 'snapshot.txt')
                    child_config=json.loads(service.material(child)['config_json']);child_config.update(source_subscription_id=mid,collection_snapshot_id=sn['id'])
                    service.db.execute(text('UPDATE knowledge_materials SET config_json=:c WHERE id=:id'),{'c':json.dumps(child_config,ensure_ascii=False),'id':child});queued.append(child)
                source=service.rows('SELECT check_frequency FROM v04g_monitoring_sources WHERE id=:id',id=material['source_id'])
                interval=FREQUENCY_HOURS.get(source[0]['check_frequency'],24) if source else 24
                if snapshots:config['snapshot_cursor']=snapshots[-1]['id']
                service.db.execute(text("UPDATE knowledge_materials SET config_json=:c,last_checked_at=:at,next_check_at=:next,error_summary='' WHERE id=:id"),{'c':json.dumps(config,ensure_ascii=False),'at':datetime.now().isoformat(),'next':(datetime.now()+timedelta(hours=interval)).isoformat(),'id':mid});db.commit()
                from app.services.tasks import create_task
                for child in queued:
                    version=service.material(child)['latest_version_id']
                    create_task('knowledge_material',queue_name='knowledge',payload={'material_id':child,'owner_user_id':service.user_id},idempotency_key=f'material:{child}:upload:{version}',created_by='source-evidence',db_path=path)
                return {'status':'source_evidence_queued','created':len(queued),'snapshot_cursor':config.get('snapshot_cursor',0)}
            raw=service.rows("SELECT * FROM knowledge_versions WHERE id=:v AND material_id=:m AND parser_version='raw'",v=material['latest_version_id'],m=mid)
            if material['source_url'] and (material['latest_version_id'] is None or payload.get('fetch')):
                url=validate_public_url(material['source_url'])
                if not check_robots(url).get('allowed'):raise HTTPException(422,'来源访问规则不允许自动获取')
                config=json.loads(material['config_json'])
                source=service.rows('SELECT check_frequency FROM v04g_monitoring_sources WHERE id=:id',id=material['source_id']) if material['source_id'] else []
                interval=FREQUENCY_HOURS.get(source[0]['check_frequency'],24) if source else 24
                headers={k:v for k,v in [('If-None-Match',config.get('etag')),('If-Modified-Since',config.get('last_modified'))] if v}
                db.rollback()  # Network is outside the write transaction.
                content,status,mime,response_headers=_http_get(url,conditional_headers=headers,retries=1,binary=True)
                service.lock()
                at=datetime.now().isoformat()
                config.update(etag=response_headers.get('etag'),last_modified=response_headers.get('last-modified'))
                if status!=304:
                    extension='.pdf' if 'pdf' in mime else '.docx' if 'wordprocessingml' in mime else '.html' if 'html' in mime else '.txt'
                    if extension=='.html':_validate_source_response(content.decode('utf-8',errors='replace'),mime,'html')
                    vid=service.accept_material_bytes(mid,content,'source'+extension)
                    raw=service.rows('SELECT * FROM knowledge_versions WHERE id=:v',v=vid)
                service.db.execute(text("UPDATE knowledge_materials SET last_checked_at=:at,next_check_at=:next,config_json=:c,error_summary='' WHERE id=:m"),{'at':at,'next':(datetime.now()+timedelta(hours=interval)).isoformat(),'c':json.dumps(config,ensure_ascii=False),'m':mid})
                db.commit()
                if status==304:return {'status':'unchanged','created':0}
            if not raw:return {'status':'already_processed','created':0}
            data=raw[0]; db.rollback()
            parsed=parse_material(data['payload'],data['filename'])
            result=service.generate_candidates(mid,data['id'],parsed); db.commit()
            return result
    except Exception as exc:
        # Runner logs this sanitized message, never the URL, file text, or credentials.
        message=str(exc.detail) if isinstance(exc,HTTPException) else '资料获取或解析失败，请核对格式、来源访问和任务状态'
        with Session(engine) as db:
            db.execute(text('UPDATE knowledge_materials SET error_summary=:e,next_check_at=:next WHERE id=:m AND owner_user_id=:u'),{'e':message[:200],'next':(datetime.now()+timedelta(days=1)).isoformat(),'m':int(payload['material_id']),'u':int(payload['owner_user_id'])});db.commit()
        raise RuntimeError(message) from None
    finally:
        engine.dispose()


class KnowledgeService:
    def __init__(self, db, *, user_id=None):
        self.db = db
        self.user_id = user_id

    def materials_ready(self):
        return inspect(self.db.get_bind()).has_table('knowledge_materials')

    def visible(self, item):
        from app.security import auth_disabled
        if item.get('access_scope')=='PRIVATE' and auth_disabled():return False
        return item.get('access_scope', 'PUBLIC') == 'PUBLIC' or (self.user_id is not None and item.get('owner_user_id') == self.user_id)

    def rows(self, sql, **params):
        return [dict(r) for r in self.db.execute(text(sql), params).mappings()]

    def get(self, item_id, *, manager=False, path=False):
        table = "learning_paths" if path else "knowledge_items"
        rows = self.rows(f"SELECT * FROM {table} WHERE id=:id", id=item_id)
        if not rows or (not manager and rows[0]["status"] != "PUBLISHED"):
            raise HTTPException(404, "内容不存在或尚未发布")
        if not path and not self.visible(rows[0]):
            raise HTTPException(404, "内容不存在或无访问权限")
        return rows[0]

    def listing(self, *, q="", category="", status="", manager=False, user_id=None, progress=""):
        clauses, params = [], {"q": f"%{q}%", "category": category, "uid": user_id}
        if self.materials_ready():
            from app.security import auth_disabled
            clauses.append("k.access_scope='PUBLIC'" if auth_disabled() else "(k.access_scope='PUBLIC' OR k.owner_user_id=:actor_uid)")
            params['actor_uid'] = self.user_id
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
        versioned = not path and self.materials_ready()
        if versioned:
            data['access_scope'] = original.get('access_scope', str(fields.get('access_scope', 'PUBLIC')))
            if data['access_scope'] not in {'PUBLIC','PRIVATE'}:
                raise HTTPException(422, '请选择明确访问范围')
            from app.security import auth_disabled
            if data['access_scope']=='PRIVATE' and auth_disabled():raise HTTPException(403,'内部知识需要真实登录认证，开发免登录模式不可写入')
            data['owner_user_id'] = original.get('owner_user_id') or self.user_id
            if data['access_scope'] == 'PRIVATE' and not data['owner_user_id']:
                raise HTTPException(403, '私人资料必须有可靠登录身份')
            data['policy_json'] = json.dumps(validate_policy(fields.get('policy', json.loads(original.get('policy_json') or '{}'))), ensure_ascii=False)
            data['content_revision'] = original.get('content_revision', 0) + 1
            if original and original.get('content_revision',0) == 0:
                self.snapshot_knowledge(original, None)
        if item_id:
            self.db.execute(text(f"UPDATE {table} SET " + ",".join(f"{k}=:{k}" for k in data) + " WHERE id=:id"), {**data, "id": item_id})
        else:
            data["created_at"] = data["updated_at"]
            result = self.db.execute(text(f"INSERT INTO {table} (" + ",".join(data) + ") VALUES (" + ",".join(f":{k}" for k in data) + ")"), data)
            item_id = result.lastrowid
        if versioned:
            self.snapshot_knowledge(self.get(item_id,manager=True), fields.get('_source_version_id'))
        return item_id

    def snapshot_knowledge(self, item, source_version_id):
        content = json.dumps(item,ensure_ascii=False,sort_keys=True)
        self.db.execute(text("INSERT INTO knowledge_versions(knowledge_id,kind,content_hash,content_json,source_version_id,revision,created_by,created_at) VALUES (:k,'KNOWLEDGE',:h,:c,:v,:r,:u,:at)"),
                        {'k':item['id'],'h':hashlib.sha256(content.encode()).hexdigest(),'c':content,'v':source_version_id,'r':item.get('content_revision',0),'u':self.user_id,'at':datetime.now().isoformat()})

    def require_material_manager(self):
        if not self.materials_ready():
            raise HTTPException(503,'资料沉淀结构尚未迁移，请联系管理员')
        users=self.rows("SELECT role FROM v05a_users WHERE id=:u AND status='active' AND deactivated_at IS NULL",u=self.user_id)
        if not users or users[0]['role'] not in {'admin','operator'}:
            raise HTTPException(403,'需要知识管理权限和有效登录身份')

    def material(self, material_id):
        self.require_material_manager()
        rows=self.rows('SELECT * FROM knowledge_materials WHERE id=:i',i=material_id)
        if not rows or not self.visible(rows[0]):
            raise HTTPException(404,'资料不存在或无访问权限')
        return rows[0]

    def materials(self):
        self.require_material_manager()
        from app.security import auth_disabled
        clause="access_scope='PUBLIC'" if auth_disabled() else "(access_scope='PUBLIC' OR owner_user_id=:u)"
        return self.rows("SELECT m.*,(SELECT COUNT(*) FROM knowledge_candidates c WHERE c.material_id=m.id AND c.state='PENDING') AS pending FROM knowledge_materials m WHERE "+clause+" ORDER BY updated_at DESC LIMIT 200",u=self.user_id)

    def register_material(self, fields, payload=None, filename='', material_id=None):
        from app.services.member_import_service import validate_public_url
        from app.services.knowledge_material_parser import MAX_BYTES
        self.require_material_manager(); self.lock()
        original=self.material(material_id) if material_id else None
        title=str(fields.get('title','')).strip()[:300]
        url=str(fields.get('url','')).strip()
        source_id=int(fields.get('source_id') or 0) or None
        if source_id:
            sources=self.rows('SELECT id,url,name FROM v04g_monitoring_sources WHERE id=:id AND deactivated_at IS NULL',id=source_id)
            if not sources:raise HTTPException(422,'请选择现有未退役来源')
            url=sources[0]['url']; title=title or sources[0]['name']
        if url:validate_public_url(url)
        if not title or (not url and not payload):raise HTTPException(422,'请填写资料名称并提供链接或文件')
        if payload and len(payload)>MAX_BYTES:raise HTTPException(422,'文件超过8MB限制')
        scope=str(fields.get('access_scope','PRIVATE'))
        if scope not in {'PUBLIC','PRIVATE'}:raise HTTPException(422,'请选择公开资料或仅自己可见；不推断机构共享权限')
        from app.security import auth_disabled
        if scope=='PRIVATE' and auth_disabled():raise HTTPException(403,'当前为开发免登录模式；内部/私人资料必须启用真实登录认证后上传，不能改为公开来绕过保护')
        category=str(fields.get('category','')).strip()
        if category and category not in CATEGORY_VALUES:raise HTTPException(422,'分类无效')
        config={'category':category,'policy':validate_policy(fields.get('policy',{})), 'follow_updates':str(fields.get('tracking','')) in {'1','on'},'classification_rule_enabled':True}
        at=datetime.now().isoformat()
        identity_target=f'source:{source_id}' if source_id else url or hashlib.sha256(payload).hexdigest()
        identity=hashlib.sha256(f"{self.user_id}|{identity_target}".encode()).hexdigest()
        if original:
            if original['owner_user_id']!=self.user_id:raise HTTPException(403,'仅资料提交者可上传新版或变更跟踪配置')
            if scope!=original['access_scope'] or url!=original['source_url']:raise HTTPException(409,'新版不能改变资料身份或扩大可见范围')
        else:
            found=self.rows('SELECT id FROM knowledge_materials WHERE identity_key=:key',key=identity)
            if found:
                material_id=found[0]['id']; original=self.material(material_id)
                if original['access_scope']!=scope:raise HTTPException(409,'相同资料已有不同访问范围，不能通过重复提交改变范围')
            else:
                material_id=self.db.execute(text('INSERT INTO knowledge_materials(identity_key,title,source_id,source_url,owner_user_id,access_scope,config_json,tracking,created_at,updated_at) VALUES (:key,:t,:s,:url,:u,:scope,:c,:track,:at,:at)'),{'key':identity,'t':title,'s':source_id,'url':url,'u':self.user_id,'scope':scope,'c':json.dumps(config,ensure_ascii=False),'track':int(config['follow_updates'] and bool(url)),'at':at}).lastrowid
        if payload:
            self.accept_material_bytes(material_id,payload,filename)
        return material_id

    def accept_material_bytes(self, material_id, payload, filename):
        from pathlib import PurePosixPath
        from app.services.knowledge_material_parser import MAX_BYTES
        material=self.material(material_id); self.lock()
        if not payload or len(payload)>MAX_BYTES:raise HTTPException(422,'文件为空或超过8MB限制')
        filename=PurePosixPath(str(filename).replace('\\','/')).name[:200]
        if PurePosixPath(filename).suffix.lower() not in {'.pdf','.docx','.txt','.md','.html','.htm'}:
            raise HTTPException(422,'不支持此资料格式')
        digest=hashlib.sha256(payload).hexdigest()
        prior=self.rows("SELECT id FROM knowledge_versions WHERE material_id=:m AND kind='MATERIAL' AND content_hash=:h AND parser_version='raw'",m=material_id,h=digest)
        if prior:return prior[0]['id']
        at=datetime.now().isoformat()
        vid=self.db.execute(text("INSERT INTO knowledge_versions(material_id,kind,content_hash,parser_version,filename,payload,content_json,created_by,created_at) VALUES (:m,'MATERIAL',:h,'raw',:f,:b,'{}',:u,:at)"),{'m':material_id,'h':digest,'f':filename,'b':payload,'u':self.user_id,'at':at}).lastrowid
        self.db.execute(text("UPDATE knowledge_materials SET latest_version_id=:v,updated_at=:at,error_summary='' WHERE id=:m"),{'v':vid,'at':at,'m':material_id})
        return vid

    def generate_candidates(self, material_id, raw_id, parsed):
        from app.services.knowledge_material_parser import PARSER_VERSION
        self.lock(); material=self.material(material_id)
        if material['latest_version_id']!=raw_id:return {'status':'superseded','created':0}
        raw=self.rows("SELECT * FROM knowledge_versions WHERE id=:v AND material_id=:m AND parser_version='raw'",v=raw_id,m=material_id)
        if not raw:raise HTTPException(409,'资料版本不匹配')
        previous=self.rows("SELECT * FROM knowledge_versions WHERE material_id=:m AND parser_version=:p ORDER BY id DESC LIMIT 1",m=material_id,p=PARSER_VERSION)
        digest=hashlib.sha256(json.dumps([(s['title'],s['body'],s['context']) for s in parsed['sections']],ensure_ascii=False).encode()).hexdigest()
        same=self.rows('SELECT id FROM knowledge_versions WHERE material_id=:m AND parser_version=:p AND content_hash=:h',m=material_id,p=PARSER_VERSION,h=digest)
        if same:
            self.db.execute(text('UPDATE knowledge_materials SET latest_version_id=:v WHERE id=:m'),{'v':same[0]['id'],'m':material_id})
            return {'status':'unchanged','created':0}
        at=datetime.now().isoformat()
        vid=self.db.execute(text("INSERT INTO knowledge_versions(material_id,kind,content_hash,parser_version,filename,content_json,source_version_id,created_by,created_at) VALUES (:m,'MATERIAL',:h,:p,:f,:c,:raw,:u,:at)"),{'m':material_id,'h':digest,'p':PARSER_VERSION,'f':raw[0]['filename'],'c':json.dumps(parsed,ensure_ascii=False),'raw':raw_id,'u':self.user_id,'at':at}).lastrowid
        config=json.loads(material['config_json']); old_sections=json.loads(previous[0]['content_json'])['sections'] if previous else []
        old_keys={s['key'] for s in old_sections}; new_keys={s['key'] for s in parsed['sections']}
        old_by_key={s['key']:s for s in old_sections}
        config['last_change']={'added':[s['title'] for s in parsed['sections'] if s['key'] not in old_keys],
                              'modified':[s['title'] for s in parsed['sections'] if s['key'] in old_keys and (s['body'],s['context'])!=(old_by_key[s['key']]['body'],old_by_key[s['key']]['context'])],
                              'removed':[s['title'] for s in old_sections if s['key'] not in new_keys]}
        for section in parsed['sections']:
            old_section=next((s for s in old_sections if s['key']==section['key']),None)
            if old_section and (old_section['body'],old_section['context'])==(section['body'],section['context']):
                settled=self.rows("SELECT id FROM knowledge_candidates WHERE material_id=:m AND version_id=:v AND section_key=:k AND state IN ('CONFIRMED','IGNORED')",m=material_id,v=previous[0]['id'],k=section['key'])
                if settled:continue
            matches=self.rows("SELECT target_knowledge_id FROM knowledge_candidates WHERE material_id=:m AND section_key=:k AND state='CONFIRMED' AND target_knowledge_id IS NOT NULL ORDER BY id DESC LIMIT 1",m=material_id,k=section['key'])
            target=self.get(matches[0]['target_knowledge_id'],manager=True) if matches else None
            issues=list(parsed['issues'])
            if previous and section['key'] not in old_keys:issues.append('章节对应关系待确认，不自动匹配旧知识')
            category=config.get('category','') if config.get('classification_rule_enabled',True) else ''
            rule_basis='本资料/来源的管理员配置'
            if not category:
                category=parsed.get('suggestions',{}).get('category','')
                rule_basis=parsed.get('suggestions',{}).get('classification_basis','来源未配置，待人工分类')
            if not category:issues.append('待分类：来源未配置已确认分类规则')
            metadata={'policy':config.get('policy',{}),'source_context':section['context'],'title_is_suggestion':section['suggested_title'], 'change':'修改' if section['key'] in old_keys else '新增','removed_sections':sorted(old_keys-new_keys),'rule_basis':rule_basis,'suggestions':parsed.get('suggestions',{}),'collection_snapshot_id':config.get('collection_snapshot_id')}
            self.db.execute(text('INSERT INTO knowledge_candidates(material_id,version_id,section_key,title,category,body,mappings_json,metadata_json,issues_json,target_knowledge_id,base_revision,created_at) VALUES (:m,:v,:key,:title,:category,:body,:maps,:meta,:issues,:target,:base,:at)'),{'m':material_id,'v':vid,'key':section['key'],'title':section['title'],'category':category,'body':section['body'],'maps':json.dumps(section['mappings'],ensure_ascii=False),'meta':json.dumps(metadata,ensure_ascii=False),'issues':json.dumps(issues,ensure_ascii=False),'target':target['id'] if target else None,'base':target.get('content_revision',0) if target else None,'at':at})
        self.db.execute(text("UPDATE knowledge_materials SET latest_version_id=:v,config_json=:c,updated_at=:at,error_summary='' WHERE id=:m"),{'v':vid,'c':json.dumps(config,ensure_ascii=False),'at':at,'m':material_id})
        return {'status':'candidates','created':self.rows('SELECT COUNT(*) AS n FROM knowledge_candidates WHERE version_id=:v',v=vid)[0]['n']}

    def candidates(self, material_id):
        material=self.material(material_id)
        rows=self.rows('SELECT * FROM knowledge_candidates WHERE material_id=:m ORDER BY id DESC LIMIT 500',m=material_id)
        for c in rows:
            c['metadata']=json.loads(c['metadata_json']); c['mappings']=json.loads(c['mappings_json']); c['issues']=json.loads(c['issues_json'])
            c['stale']=c['version_id']!=material['latest_version_id']
            c['previous']=self.get(c['target_knowledge_id'],manager=True) if c['target_knowledge_id'] else None
        return rows

    def reshape_candidates(self, material_id, identifiers, revisions, *, split_before=''):
        import uuid
        self.lock();m=self.material(material_id)
        all_rows=self.rows("SELECT * FROM knowledge_candidates WHERE material_id=:m AND version_id=:v ORDER BY id",m=material_id,v=m['latest_version_id'])
        selected=[(i,c) for i,c in enumerate(all_rows) if c['id'] in identifiers]
        if not selected or len(selected)!=len(set(identifiers)) or any(c['state']!='PENDING' or c['edit_revision']!=revisions.get(c['id']) for _,c in selected):
            raise HTTPException(409,'候选或预览已变化，请刷新')
        if split_before:
            if len(selected)!=1:raise HTTPException(422,'拆分时仅选择一条候选')
            c=selected[0][1];body=c['body']
            if body.count(split_before)!=1 or body.startswith(split_before):raise HTTPException(422,'拆分定位句必须在正文中唯一且不在开头')
            offset=body.index(split_before);parts=[body[:offset].strip(),body[offset:].strip()]
        else:
            positions=[i for i,_ in selected]
            if len(selected)<2 or len(selected)>20 or positions!=list(range(positions[0],positions[-1]+1)):raise HTTPException(422,'仅合并同版本相邻的2至20条候选')
            parts=['\n\n'.join(c['body'] for _,c in selected)]
        maps=[mapping for _,c in selected for mapping in json.loads(c['mappings_json'])]
        metadata=json.loads(selected[0][1]['metadata_json']);metadata['reshaped_from']=identifiers
        metadata['source_context']='\n\n'.join(dict.fromkeys(json.loads(c['metadata_json']).get('source_context','') for _,c in selected))
        issues=sorted(set(issue for _,c in selected for issue in json.loads(c['issues_json'])))+['管理员调整结构，须再次核对前提、例外及原文映射']
        at=datetime.now().isoformat()
        for part in parts:
            self.db.execute(text("INSERT INTO knowledge_candidates(material_id,version_id,section_key,title,category,body,mappings_json,metadata_json,issues_json,created_at) VALUES (:m,:v,:key,:title,:cat,:b,:maps,:meta,:issues,:at)"),{'m':material_id,'v':m['latest_version_id'],'key':'manual:'+uuid.uuid4().hex,'title':part.splitlines()[0][:200],'cat':selected[0][1]['category'],'b':part,'maps':json.dumps(maps,ensure_ascii=False),'meta':json.dumps(metadata,ensure_ascii=False),'issues':json.dumps(issues,ensure_ascii=False),'at':at})
        for _,c in selected:
            self.db.execute(text("UPDATE knowledge_candidates SET state='SUPERSEDED',edit_revision=edit_revision+1,decision_json=:d,reviewed_at=:at WHERE id=:id"),{'d':json.dumps({'actor':self.user_id,'action':'split' if split_before else 'merge','at':at}), 'at':at,'id':c['id']})

    def review_candidate(self, candidate_id, fields, action='draft'):
        self.require_material_manager(); self.lock()
        rows=self.rows('SELECT * FROM knowledge_candidates WHERE id=:id',id=candidate_id)
        if not rows:raise HTTPException(404,'候选不存在')
        c=rows[0]; material=self.material(c['material_id'])
        if c['state']!='PENDING':return {'id':candidate_id,'status':'已处理'}
        if c['version_id']!=material['latest_version_id'] or int(fields.get('edit_revision',-1))!=c['edit_revision']:
            raise HTTPException(409,'资料或预览已更新，请刷新差异后处理')
        if action not in {'draft','publish','ignore','edit'}:raise HTTPException(422,'操作无效')
        meta=json.loads(c['metadata_json']); category=str(fields.get('category',c['category'])); title=str(fields.get('title',c['title'])).strip()
        if action!='ignore' and (category not in CATEGORY_VALUES or not title):raise HTTPException(422,'请确认标题和分类')
        selection=str(fields.get('target_selection',''))
        if selection:
            if selection=='new':fields={**fields,'target_knowledge_id':'0','base_revision':-1}
            else:
                parts=selection.split(':')
                if len(parts)!=2 or not all(p.isdigit() for p in parts):raise HTTPException(422,'请选择有效知识目标')
                fields={**fields,'target_knowledge_id':parts[0],'base_revision':parts[1]}
        target_id=int(fields.get('target_knowledge_id') or c['target_knowledge_id'] or 0) or None
        original=self.get(target_id,manager=True) if target_id else {}
        expected=int(fields.get('base_revision',c['base_revision'] if c['base_revision'] is not None else -1))
        if target_id and expected!=original.get('content_revision',0):raise HTTPException(409,'目标知识已更新，请刷新差异；旧预览不能覆盖新版本')
        if target_id and original.get('access_scope','PUBLIC')!=material['access_scope']:raise HTTPException(409,'不能通过更新扩大来源可见范围')
        if target_id!=c['target_knowledge_id'] and action not in {'edit','ignore'}:
            raise HTTPException(409,'目标已改变，请先保存建议并重新查看该知识与候选的差异，再确认')
        policy=validate_policy(fields.get('policy',meta.get('policy',{})))
        if action in {'draft','publish'} and json.loads(c['issues_json']) and fields.get('acknowledge')!='1':raise HTTPException(409,'请先核对解析限制及原文后明确确认')
        if target_id and original['status']=='PUBLISHED' and action=='draft':raise HTTPException(409,'已发布知识仍保留；请明确确认更新并发布，或暂留待审')
        result_id=target_id
        if action in {'draft','publish'}:
            maps=json.loads(c['mappings_json'])
            body=c['body']
            if meta.get('source_context'):body=meta['source_context']+'\n\n'+body
            values={**original,'title':title,'category':category,'body':body,'summary':title,'difficulty':original.get('difficulty','入门'),'status':'PUBLISHED' if action=='publish' else 'DRAFT','source_name':material['title'],'source_url':material['source_url'],'source_section':'；'.join(m['locator'] for m in maps),'source_version':str(c['version_id']),'access_scope':material['access_scope'],'knowledge_type':'REGULATION' if category.startswith('政策/') else original.get('knowledge_type','INDUSTRY'),'policy':policy,'_source_version_id':c['version_id']}
            result_id=self.save(values,target_id)
        at=datetime.now().isoformat(); meta['policy']=policy
        if fields.get('reuse_rule')=='1':
            if material['owner_user_id']!=self.user_id:raise HTTPException(403,'仅资料提交者可保存来源分类规则')
            config=json.loads(material['config_json']); config.update(category=category,classification_rule_enabled=True,confirmed_by=self.user_id,confirmed_at=at)
            self.db.execute(text('UPDATE knowledge_materials SET config_json=:c WHERE id=:m'),{'c':json.dumps(config,ensure_ascii=False),'m':material['id']})
        state='IGNORED' if action=='ignore' else 'PENDING' if action=='edit' else 'CONFIRMED'
        decision=json.dumps({'actor':self.user_id,'action':action,'at':at},ensure_ascii=False)
        self.db.execute(text('UPDATE knowledge_candidates SET title=:t,category=:cat,metadata_json=:meta,state=:s,target_knowledge_id=:k,base_revision=:base,edit_revision=edit_revision+1,decision_json=:d,reviewed_at=:at WHERE id=:id'),{'t':title,'cat':category,'meta':json.dumps(meta,ensure_ascii=False),'s':state,'k':result_id,'base':original.get('content_revision') if target_id else None,'d':decision,'at':at,'id':candidate_id})
        return {'id':candidate_id,'status':'成功','knowledge_id':result_id}

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
        scope = " AND k.access_scope='PUBLIC'" if self.materials_ready() else ''
        return self.rows("SELECT k.id,k.title FROM knowledge_links l JOIN knowledge_items k ON k.id=l.knowledge_id WHERE l.target_type=:kind AND l.target_id=:id AND k.status='PUBLISHED'" + scope + " ORDER BY k.updated_at DESC", kind=kind, id=target_id)

    def progress(self, item_id, user_id, status, note):
        self.lock()
        self.get(item_id)
        if user_id is None or not self.rows("SELECT id FROM v05a_users WHERE id=:id", id=user_id):
            raise HTTPException(403, "请使用正式登录账号保存自己的学习进度")
        if status not in PROGRESS or len(note) > 3000:
            raise HTTPException(422, "学习状态或备注无效")
        self.db.execute(text("INSERT INTO user_knowledge_progress(user_id,knowledge_id,status,note,updated_at) VALUES (:u,:k,:s,:n,:at) ON CONFLICT(user_id,knowledge_id) DO UPDATE SET status=excluded.status,note=excluded.note,updated_at=excluded.updated_at"), {"u": user_id, "k": item_id, "s": status, "n": note, "at": datetime.now().isoformat()})
        if self.materials_ready():
            self.db.execute(text('UPDATE user_knowledge_progress SET knowledge_revision=:r WHERE user_id=:u AND knowledge_id=:k'),{'r':self.get(item_id).get('content_revision'),'u':user_id,'k':item_id})
        if status == "MASTERED":
            history = json.loads(self.rows("SELECT training_history_json FROM user_knowledge_progress WHERE user_id=:u AND knowledge_id=:k",u=user_id,k=item_id)[0]["training_history_json"])
            for path in self.rows("SELECT p.* FROM learning_paths p JOIN learning_path_items i ON i.path_id=p.id WHERE i.knowledge_id=:k AND p.status='PUBLISHED' AND p.learning_type='REQUIRED_TRAINING'",k=item_id):
                if self.audience_allowed(path,user_id):
                    key=f"{path['id']}:{path['version']}"
                    ids=[r["knowledge_id"] for r in self.rows("SELECT knowledge_id FROM learning_path_items WHERE path_id=:p ORDER BY position",p=path["id"])]
                    history.setdefault(key,{"path_id":path["id"],"version":path["version"],"title":path["title"],"ids":ids,"requires_exam":path["requires_exam"],"at":datetime.now().isoformat()})
            self.db.execute(text("UPDATE user_knowledge_progress SET training_history_json=:h WHERE user_id=:u AND knowledge_id=:k"),{"h":json.dumps(history,ensure_ascii=False),"u":user_id,"k":item_id})

    def path_items(self, path_id, *, manager=False, user_id=None):
        scope = " AND k.access_scope='PUBLIC'" if self.materials_ready() else ''
        return self.rows("SELECT k.*,i.position,COALESCE(p.status,'NOT_STARTED') AS progress_status FROM learning_path_items i JOIN knowledge_items k ON k.id=i.knowledge_id LEFT JOIN user_knowledge_progress p ON p.knowledge_id=k.id AND p.user_id=:u WHERE i.path_id=:id" + ("" if manager else " AND k.status='PUBLISHED'") + scope + " ORDER BY i.position", id=path_id, u=user_id)

    def set_path_items(self, path_id, item_ids):
        path = self.get(path_id, manager=True, path=True)
        previous=[r["knowledge_id"] for r in self.rows("SELECT knowledge_id FROM learning_path_items WHERE path_id=:p ORDER BY position",p=path_id)]
        if previous!=item_ids and self.path_locked(path_id,path["version"]):
            raise HTTPException(409,"该版本已有学习/考试历史，请先设置新版本再调整知识顺序")
        if len(item_ids) > 200 or len(item_ids) != len(set(item_ids)):
            raise HTTPException(422, "学习路径最多200条且不能重复")
        for item_id in item_ids:
            if self.get(item_id, manager=True).get('access_scope','PUBLIC') != 'PUBLIC':
                raise HTTPException(409, '私人资料不能加入共享学习路径，请先核对授权范围')
        self.db.execute(text("DELETE FROM learning_path_items WHERE path_id=:id"), {"id": path_id})
        for position, item_id in enumerate(item_ids, 1):
            self.db.execute(text("INSERT INTO learning_path_items(path_id,knowledge_id,position) VALUES (:p,:k,:n)"), {"p": path_id, "k": item_id, "n": position})

    def delete(self, item_id):
        item = self.get(item_id, manager=True)
        references = sum(self.rows(f"SELECT COUNT(*) AS n FROM {table} WHERE knowledge_id=:id", id=item_id)[0]["n"] for table in ("knowledge_links", "learning_path_items", "user_knowledge_progress", "knowledge_annotations", "knowledge_questions"))
        if self.materials_ready():
            references+=self.rows('SELECT COUNT(*) AS n FROM knowledge_versions WHERE knowledge_id=:id',id=item_id)[0]['n']
        if item["status"] != "DRAFT" or references:
            raise HTTPException(409, "只有无关联、无学习及版本记录的草稿可删除；请使用归档保留历史")
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
        self.get(knowledge_id,manager=True)
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
            inserted=self.db.execute(text("INSERT INTO knowledge_annotations(knowledge_id,user_id,type,content,visibility,parent_id,created_at,updated_at) VALUES (:k,:u,:t,:c,:v,:p,:at,:at)"),{"k":knowledge_id,"u":user_id,"t":kind,"c":content,"v":visibility,"p":parent_id,"at":at})
            if self.materials_ready():
                self.db.execute(text('UPDATE knowledge_annotations SET knowledge_revision=(SELECT content_revision FROM knowledge_items WHERE id=:k) WHERE id=:id'),{'k':knowledge_id,'id':inserted.lastrowid})

    def delete_annotation(self,knowledge_id,annotation_id,user_id,admin=False):
        self.get(knowledge_id,manager=True)
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
        if self.get(knowledge_id,manager=True).get('access_scope','PUBLIC') != 'PUBLIC':
            raise HTTPException(409, '私人资料不能进入共享题库')
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
        needs_content_review=False
        if self.materials_ready():
            studied={r['knowledge_id']:r['knowledge_revision'] for r in self.rows('SELECT knowledge_id,knowledge_revision FROM user_knowledge_progress WHERE user_id=:u',u=user_id)}
            for item in items:
                if item.get('content_revision',0)>0 and studied.get(item['id'])!=item['content_revision']:
                    item['training_mastered']=False;needs_content_review=True
        exam=self.rows("SELECT * FROM knowledge_exams WHERE path_id=:p",p=path["id"])
        attempts=self.rows("SELECT id,score,passed,attempt_no,submitted_at,path_version FROM knowledge_exam_attempts WHERE exam_id IN (SELECT id FROM knowledge_exams WHERE path_id=:p) AND user_id=:u AND path_version=:v ORDER BY id DESC",p=path["id"],u=user_id,v=path["version"])
        learned=sum(i["training_mastered"] for i in items)
        done=bool(items) and learned==len(items)
        if self.materials_ready() and attempts:
            current={str(i['id']):i.get('content_revision',0) for i in items}
            for a in attempts:
                snapshot=json.loads(self.rows('SELECT answers_json FROM knowledge_exam_attempts WHERE id=:i',i=a['id'])[0]['answers_json'])
                a['current_knowledge_version']=snapshot.get('knowledge_revisions')==current
            needs_content_review=needs_content_review or not any(a['passed'] and a['current_knowledge_version'] for a in attempts)
        return {"items":items,"learned":learned,"total":len(items),"eligible":self.audience_allowed(path,user_id),"exam":exam[0] if exam else None,"attempts":attempts,"learned_all":done,"needs_content_review":needs_content_review,"completed":done and not needs_content_review and (not path["requires_exam"] or any(a["passed"] for a in attempts))}

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
        if self.materials_ready():snapshot['knowledge_revisions']={str(i['id']):i.get('content_revision',0) for i in summary['items']}
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
