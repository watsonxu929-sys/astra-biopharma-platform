"""Deterministic article presentation. No writes, inferred amounts, or entity creation."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

TZ = ZoneInfo('Asia/Shanghai')
# One configuration shared by review, publication and reading (days, not validity).
CATEGORIES = {
    'financing': ('企业融资', 7, r'融资|series\s+[a-f]|financing|funding round'),
    'fund': ('投资机构与基金', 7, r'基金|fund\s+[IVX\d]+|fundrais|venture fund|capital fund'),
    'capital': ('IPO与上市公司', 7, r'\bIPO\b|财报|年度业绩|季度业绩|上市进程|登陆.*交易所|首次公开|financial results|(?:quarter|interim|annual).*results|reports?.*(?:profitable growth|revenue)|earnings|share offering|dividend'),
    'deal': ('BD、许可与并购', 7, r'并购|收购|许可协议|授权协议|license|licensing|acquisition|acquires?|divestment|asset sale|merger|collaboration agreement'),
    'clinical': ('研发与临床', 14, r'临床|入组|试验|适应症|trial|phase\s*[123I]|clinical|pipeline|研究结果'),
    'regulatory': ('监管与市场准入', 14, r'获批|审批|注册|批件|医保|集采|召回|监管|受理|approved|approval|regulator|recall|clearance|pharmacovigilance|medicinal products|shortage'),
    'project': ('企业经营与项目建设', 14, r'扩建|扩产|基地|研发中心|迁址|停产|重组|manufactur|facility|facilities|expansion|new site'),
    'people': ('人物与团队', 14, r'任命|离职|加盟|聘任|招聘|appoint|chief executive|leadership|resign'),
    'procurement': ('采购、需求与供给', 14, r'采购|招标|中标|设备转让|技术需求|tender|procurement|request for proposal'),
    'research': ('科研成果与知识产权', 14, r'专利|论文|技术转让|成果转化|patent|publication|published in|research findings'),
    'policy': ('产业政策与园区资源', 30, r'申报|扶持|专项|资助|园区|grant|funding call'),
    'event': ('活动与产业网络', 14, r'会议|路演|对接会|报名|论坛|conference|congress|symposium|webinar|summit'),
}
REVIEW_VIEWS = {'priority':'重点待审核','observation':'行业观察','routine':'常规事务','history':'历史/已截止','verify':'待核对'}
READ_VIEWS = {'latest':'最新动态','capital':'资本与交易','project':'项目与资源','policy':'政策与申报','observation':'行业观察','history':'历史资料','all':'全部资料'}
DOMAIN = re.compile(r'生物医药|生物医学|药物|药品|制药|创新药|疫苗|抗体|临床|医疗|医药|诊断|肿瘤|癌症|传染病|疾病|基因治疗|细胞治疗|检测服务|CRO|CDMO|\b(?:biotech|biopharma|biologics|pharmaceuticals?|drugs?|medicines?|medicinal|vaccines?|antibod(?:y|ies)|clinical|therap(?:y|ies)|diagnostic|cancer|disease|medical|healthcare)\b', re.I)
DATE = r'(?:20\d{2}[年/.-]\d{1,2}[月/.-]\d{1,2}日?(?:[ T]?\d{1,2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?)'
STAGES = [('终止/撤销',r'终止|撤销|取消|terminat|cancel|discontinu'),('交割',r'交割|closing of|closed the acquisition'),('完成',r'完成|completed|successfully raised'),('批准',r'获批|批准|approved'),('受理',r'受理|accepted.*application'),('签约',r'签署|签约|entered into|signed'),('计划',r'计划|拟|plans to|intends to'),('宣布',r'宣布|公布|announc')]
FIELD_PATTERNS = {
    'financing': [('轮次',r'[A-F][+＋]?轮|天使轮|战略融资|债务融资|Series\s+[A-F]'),('融资金额（原文口径）',r'融资|raised|financing|funding'),('投资方及角色',r'领投|跟投|投资方|led by|participat.*invest'),('资金用途',r'(?:资金|融资|募集|所得款).*(?:用于|投入)|use.*proceeds|proceeds.*used')],
    'fund': [('基金动作/规模口径',r'基金|fund|commitments'),('阶段/方向',r'投资方向|投资于|专注|focus|invest in'),('投资组合',r'投资组合|portfolio')],
    'capital': [('披露事项/报告期',r'季度|年度|报告期|quarter|year ended|financial'),('金额/指标口径',r'收入|利润|营收|revenue|income|loss|earnings')],
    'deal': [('双方/资产',r'与|收购|协议|agreement|acqui|license'),('首付款',r'首付款|upfront|up-front'),('条件性付款',r'里程碑|milestone|contingent'),('分成/区域',r'分成|版税|royalt|territor|全球|大中华')],
    'clinical': [('产品/适应症',r'适应症|患者|治疗|patients|treatment|indication'),('阶段/动作',r'[一二三123]期|Phase\s*[123I]|入组|试验|trial'),('公开结果',r'结果|终点|result|endpoint|failed|未达到')],
    'regulatory': [('机构/产品与事项',r'药品|产品|监管|FDA|EMA|NMPA|approval|approved|recall'),('阶段/适用范围',r'受理|批准|获批|适用|indication|patients|approved')],
    'project': [('建设/经营事项',r'新建|建设|扩产|迁址|facility|manufactur|expand'),('地点',r'位于|落户|选址|located|in [A-Z]|上海|苏州'),('投资/产能口径',r'投资|产能|investment|capacity')],
    'people': [('人物/任职变化',r'任命|聘任|离职|appoint|resign|chief'),('原/新机构职位',r'原任|加入|担任|formerly|join|officer|president')],
    'procurement': [('发布方/标的',r'采购|招标|设备|tender|procurement'),('预算口径',r'预算|限价|budget'),('资格/采购阶段',r'资格|资质|意向|中标|终止|eligib|award')],
    'research': [('机构/成果事件',r'研究|团队|论文|专利|research|patent|published'),('公开转化信息',r'转化|转让|许可|licens|transfer')],
    'policy': [('事项/方向',r'申报|专项|研究|grant'),('适用条件',r'条件|申请人|依托单位|应当|eligib'),('资助口径',r'资助|经费|万元|funding|grant amount')],
    'event': [('名称/主办方',r'会议|论坛|主办|conference|host'),('时间/地点/对象',r'举办|举行|地点|参会|\b(?:held|venue|participants|location)\b')],
}


def parse_time(value):
    raw = str(value or '').strip()
    if not raw:
        return None, 'unknown'
    precision = 'minute' if re.search(r'\d:\d', raw) else 'date'
    cleaned = re.sub(r'(\d{4})年(\d{1,2})月(\d{1,2})日?', lambda m:f'{int(m[1]):04d}-{int(m[2]):02d}-{int(m[3]):02d} ', raw).strip()
    cleaned = re.sub(r'^(\d{4})[/.](\d{1,2})[/.](\d{1,2})', r'\1-\2-\3', cleaned)
    try:
        if re.fullmatch(r'\d{4}-\d{1,2}-\d{1,2}', cleaned):
            dt = datetime(*map(int, cleaned.split('-')))
        else:
            try:
                dt = datetime.fromisoformat(cleaned.replace('Z', '+00:00'))
            except ValueError:
                try:dt = parsedate_to_datetime(raw)
                except (ValueError,TypeError):
                    dt = None
                    for fmt in ('%B %d, %Y','%b %d, %Y','%b. %d, %Y','%d %B %Y','%d %b %Y'):
                        try:dt=datetime.strptime(raw,fmt);break
                        except ValueError:pass
                    if dt is None:return None,'unknown'
        return (dt.replace(tzinfo=TZ) if not dt.tzinfo else dt.astimezone(TZ)), precision
    except (ValueError, TypeError, OverflowError):
        return None, 'unknown'


def display_title(title):
    # Display only; original title and snapshot remain immutable.
    parts=re.split(r'\s*[|｜]\s*|_(?:[^_]*局|[^_]*委员会|药品、医疗器械)', title or '')
    return max(parts,key=len).strip() if parts else ''


def publication_metadata(soup):
    candidates=[];modified=None
    for node in soup.select('meta[property="article:published_time"], meta[name="publishdate"], meta[name="PubDate"], meta[name="pubdate"], meta[name="publishDate"], meta[name="date"]'):
        if node.get('content'):candidates.append({'raw':node['content'],'position':'meta:'+str(node.get('name') or node.get('property'))})
    for node in soup.select('article time[datetime], time[itemprop="datePublished"]'):
        if node.get('itemprop')!='dateModified':candidates.append({'raw':node.get('datetime') or node.get('content') or node.get_text(' ',strip=True),'position':'article time'})
    for node in soup.select('script[type="application/ld+json"]'):
        try:data=json.loads(node.get_text())
        except (ValueError,TypeError):continue
        stack=data if isinstance(data,list) else [data]
        while stack:
            item=stack.pop()
            if not isinstance(item,dict):continue
            stack.extend(item.get('@graph') or [])
            if 'Article' in str(item.get('@type','')) and item.get('datePublished'):
                candidates.append({'raw':str(item['datePublished']),'position':'article structured datePublished'})
            if 'Article' in str(item.get('@type','')) and item.get('dateModified'):
                modified=str(item['dateModified'])
    visible=soup.get_text(' ',strip=True)
    for m in re.finditer(r'(?:发布时间|发布日期|Published\s*:)\s*[：:]?\s*('+DATE+')',visible,re.I):
        candidates.append({'raw':m.group(1),'position':m.group(0)})
    node=soup.select_one('meta[property="article:modified_time"], meta[itemprop="dateModified"]')
    return {'publication_candidates':candidates,'source_modified_at':node.get('content') if node else modified}


def publication(supplied, metadata, now):
    candidates = list(metadata.get('publication_candidates') or [])
    if not candidates and supplied:
        candidates = [{'raw':str(supplied),'position':metadata.get('publication_basis') or 'existing_source_date'}]
    parsed = [(c, *parse_time(c.get('raw'))) for c in candidates]
    valid = [(c,d,p) for c,d,p in parsed if d]
    days = {d.date() for _,d,_ in valid}
    conflict = len(days)>1 or any(d.date()>now.date() for _,d,_ in valid)
    selected = valid[0] if valid and not conflict else (None,None,'unknown')
    return {'value':selected[1].isoformat() if selected[1] and selected[2]!='date' else selected[1].date().isoformat() if selected[1] else None,
            'precision':selected[2], 'candidates':candidates, 'conflict':conflict,
            'label':'发布时间冲突/未来日期待核对' if conflict else '发布时间待核对' if not valid else '',
            'timezone_assumption':'无时区时按Asia/Shanghai解释，保留原精度'}


def business_times(text, url):
    rows=[]
    for m in re.finditer(DATE, text):
        start=max(text.rfind('\n',0,m.start()),text.rfind('。',0,m.start()))+1
        end=re.search(r'[。\n]',text[m.end():]);end=m.end()+end.start() if end else min(len(text),m.end()+140)
        sentence=text[start:end].strip()
        if len(sentence)>400:continue
        if re.search(r'执行期限|实施周期|项目周期|报告期',sentence):continue
        clause_start=max(start,text.rfind('，',start,m.start())+1,text.rfind('；',start,m.start())+1)
        prefix=text[clause_start:m.start()]
        role = '截止' if re.search(r'截止|不晚于|deadline|closing date|due by',prefix,re.I) else '开放' if re.search(r'开始受理|开放申请|开放报名|申请开始|填报起始|opens? on',prefix,re.I) else '活动' if re.search(r'举行|举办|held on',prefix,re.I) else None
        if not role:continue
        # A sentence with several dates needs role resolution; never choose the latest.
        clause_end=re.search(r'[，；。\n]',text[m.end():]);clause_end=m.end()+clause_end.start() if clause_end else end
        ambiguous=len(re.findall(DATE,text[clause_start:clause_end]))>1
        dt,precision=parse_time(m.group())
        rows.append({'kind':role,'raw':m.group(),'value':dt.isoformat() if dt and precision!='date' else dt.date().isoformat() if dt else None,'precision':precision,'evidence':sentence,'position':m.start(),'url':url,'ambiguous':ambiguous})
    for m in re.finditer(r'(?<![\d年])\d{1,2}月\d{1,2}日至\d{1,2}月\d{1,2}日',text):
        if any(abs(m.start()-r['position'])<20 for r in rows):continue
        rows.append({'kind':'业务时间范围（年份待核对）','raw':m.group(),'value':None,'precision':'month_day','evidence':m.group(),'position':m.start(),'url':url,'ambiguous':True})
    return rows


def analyze_article(title, text, url, published_at='', metadata=None, *, now=None, manual_summary=''):
    metadata=metadata or {};now=now or datetime.now(TZ)
    if now.tzinfo is None:now=now.replace(tzinfo=TZ)
    title=display_title(title);text=text or '';combined=title+'\n'+text
    sentences=[(m.group().strip(),m.start()) for m in re.finditer(r'.+?(?:[。！？]|\n|(?<=[a-z0-9])[.!?]\s+(?=[A-Z])|$)',text,re.S) if len(m.group().strip())>=12]
    core=[(s,p) for s,p in sentences if not re.search(r'联系电话|电子邮箱|通讯地址|版权所有|copyright|forward-looking|safe harbor|about (?:the |our )?company',s,re.I)]
    domain=DOMAIN.search(title) or next((DOMAIN.search(s) for s,p in core if DOMAIN.search(s)),None)
    # Broad cross-industry titles require explicit biomedical paragraphs, not boilerplate.
    mixed=bool(re.search(r'新材料|碳纤维|绿色燃料|农业|多个专项|若干方向',title) or re.search(r'等[三四五六七八九十\d]+个专题',text))
    relevant_core=[(s,p) for s,p in core if DOMAIN.search(s)] if mixed else core
    category_scores={k:len(re.findall(spec[2],title,re.I))*8+min(3,len(re.findall(spec[2],text[:6000],re.I))) for k,spec in CATEGORIES.items()}
    category=max(category_scores,key=category_scores.get) if any(category_scores.values()) else 'research'
    routine=bool(re.search(r'批件领取|领取通知|证书领取',title))
    if routine:category='regulatory'
    stage=next((label for label,pat in STAGES if re.search(pat,title,re.I)),None)
    if not stage:stage=next((label for label,pat in STAGES if re.search(pat,text[:1500],re.I)),'阶段待核对')
    fields=[]
    for label,pattern in FIELD_PATTERNS[category]:
        match=next(((s,p) for s,p in relevant_core if re.search(pattern,s,re.I) and len(s)<=450),None)
        # In a mixed notice do not borrow a sum/condition from an adjacent topic.
        if match and (not mixed or DOMAIN.search(match[0])):
            s,p=match;fields.append({'label':label,'value':s[:240],'evidence':s,'position':p,'url':url})
        else:fields.append({'label':label,'value':'未披露或待核对','evidence':'','position':None,'url':url})
    evidence=[f['evidence'] for f in fields if f['evidence']]
    selected=list(dict.fromkeys(evidence))
    excerpt=' '.join(selected[:2])
    chinese=bool(re.search(r'[\u4e00-\u9fff]',title))
    limit=160 if chinese else 320
    summary=manual_summary or (excerpt[:limit]+('…' if len(excerpt)>limit else '')) or '关键事实待核对，请查看原文。'
    pub=publication(published_at,metadata,now);dt,precision=parse_time(pub['value'])
    age=(now.date()-dt.date()).days if dt else None
    freshness='待核对' if age is None else '近期' if age<=CATEGORIES[category][1] else '观察期' if age<=30 else '历史/补录'
    times=business_times(text,url) if category in {'policy','procurement','event'} and not mixed else []
    deadlines=[r for r in times if r['kind']=='截止'];starts=[r for r in times if r['kind']=='开放']
    business='有效性待核对';actionable=False
    cancelled=stage=='终止/撤销'
    closed_stage=category=='procurement' and bool(re.search(r'中标|成交|采购结果|采购意向|award|procurement intention',title,re.I))
    if cancelled:business='撤销/终止'
    elif deadlines and not closed_stage and not any(t['ambiguous'] for t in times) and len({t['value'] for t in deadlines})==1:
        deadline,prec=parse_time(deadlines[0]['value']);start=parse_time(starts[0]['value'])[0] if len(starts)==1 else None
        if deadline and (now.date()>deadline.date() if prec=='date' else now>deadline):business='已截止'
        elif deadline and start and now<start:business='即将开放'
        elif deadline and re.search(r'受理|申报|报名|投标|申请|applications?|submit|registration',text,re.I):
            business='仍有效/正在开放';actionable=True
            if prec!='date' and deadline-now<=timedelta(hours=72):business='临近截止'
            elif prec=='date' and deadline.date()==now.date():business='当日截止，具体时间未注明'
    elif closed_stage:business='采购阶段非开放招标'
    business_related=bool(metadata.get('priority_subject') or (category in {'policy','project','procurement','event'} and re.search(r'上海|长三角',title+' '.join(selected))))
    specific=bool(evidence) and category_scores[category]>0
    priority=bool(domain and specific and not routine and (actionable or (freshness=='近期' and business_related)) and not mixed)
    window_closed=category in {'policy','procurement','event'} and business in {'已截止','撤销/终止'}
    view='verify' if not domain or not specific or pub['conflict'] or not dt else 'history' if (freshness=='历史/补录' and not actionable) or window_closed else 'routine' if routine else 'priority' if priority else 'observation'
    reason=(f'原文涉及{CATEGORIES[category][0]}：'+(selected[0][:100] if selected else '关键事实待核对')) if domain else '未取得明确生物医药关联，不进入重点流'
    seen,sp=parse_time(metadata.get('first_seen_at') or metadata.get('captured_at'))
    delay=f'{(seen.date()-dt.date()).days}天（日期精度）' if seen and dt and seen>=dt else '待核对'
    material_values=sorted(set(re.findall(r'[$€£¥]\s*\d[\d,.]*(?:\s*(?:million|billion|m|bn))?|\d[\d,.]*\s*(?:亿元|万元|亿美元|百万|million|billion|%)|(?:数|近|超)?[一二三四五六七八九十数\d]+亿元|(?:Phase\s*[123IV]+|[一二三123]期)|[A-Z]{2,}[ -]?\d{2,}', ' '.join(selected), re.I)))
    signature=hashlib.sha256(json.dumps([category,stage,material_values,[(t['kind'],t['raw']) for t in times]],ensure_ascii=False).encode()).hexdigest()
    return {'category':category,'category_label':CATEGORIES[category][0],'tags':[CATEGORIES[k][0] for k in CATEGORIES if k!=category and category_scores[k]>=8][:2],
        'title':title,'summary':summary,'fields':fields,'stage':stage,'relevant':bool(domain),'industry_evidence':domain.group() if domain else '',
        'mixed_scope':mixed,'specific':specific,'business_related':business_related,'reason':reason,'publication':pub,'source_modified_at':metadata.get('source_modified_at'),
        'event_occurred_at':None,'disclosure_at':pub['value'],'first_seen_at':metadata.get('first_seen_at'),'fetched_at':metadata.get('captured_at'),
        'freshness':freshness,'age_days':age,'business_times':times,'business_status':business,'actionable':actionable,'view':view,'view_label':REVIEW_VIEWS[view],
        'discovery_delay':delay,'sort_time':dt.timestamp() if dt else 0,'material_signature':signature,'material_values':material_values,'human_value_confirmed':False}


def product_facts(item, *, now=None):
    get=item.get if isinstance(item,dict) else lambda k,d=None:getattr(item,k,d)
    try:notes=json.loads(get('analysis_notes') or '{}')
    except (ValueError,TypeError):notes={}
    metadata=notes.get('article_metadata') or {}
    # Generated summaries can be recalculated; pre-existing/manual summaries are retained.
    saved=(notes.get('article_assessment') or {}).get('facts') or {}
    summary=get('summary') or ''
    manual=summary if not saved or summary != saved.get('summary') else ''
    return analyze_article(get('title') or '',get('content') or get('summary') or '',get('source_url') or '',get('published_at') or '',metadata,now=now,manual_summary=manual)


def matches_reading(facts, view='all', days='', start='', end='', active=False, *, now=None):
    now=now or datetime.now(TZ);dt,_=parse_time(facts['disclosure_at'])
    if active and not facts['actionable']:return False
    if view=='latest' and not active and (facts['freshness']!='近期' or facts['view'] in {'routine','verify','history'}):return False
    if view=='history' and facts['view'] not in {'history','verify'}:return False
    if view=='observation' and facts['view']!='observation':return False
    groups={'capital':{'financing','fund','capital','deal'},'project':{'project','procurement','people'},'policy':{'policy'}}
    if view in groups and facts['category'] not in groups[view]:return False
    windows={'today':1,'24hours':1,'7days':7,'30days':30,'90days':90}
    if days in windows and (not dt or now-dt>timedelta(days=windows[days]) or dt>now):return False
    a,_=parse_time(start);b,_=parse_time(end)
    if a and (not dt or dt.date()<a.date()):return False
    if b and (not dt or dt.date()>b.date()):return False
    return True
