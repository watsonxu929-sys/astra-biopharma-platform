"""Bounded offline structure extraction. Rules suggest; they never certify policy facts."""
from io import BytesIO
from pathlib import PurePosixPath
import hashlib
import re
import zipfile

from fastapi import HTTPException

PARSER_VERSION = 'structure-1'
MAX_BYTES = 8 * 1024 * 1024
MAX_TEXT = 600000
HEADING = re.compile(r'^(?:第[一二三四五六七八九十百零\d]+[章节条]|[一二三四五六七八九十]+、|#{1,6}\s|\d+(?:\.\d+)+\s)')


def parse_material(payload, filename):
    if not payload or len(payload) > MAX_BYTES:
        raise HTTPException(422, '资料为空或超过8MB限制')
    suffix = PurePosixPath(filename.replace('\\', '/')).suffix.lower()
    blocks, issues, publication_suggestions = [], [], []
    if suffix in {'.txt', '.md'}:
        try:
            value = payload.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise HTTPException(422, '文本资料请保存为UTF-8编码')
        if '\x00' in value:
            raise HTTPException(422, '文件不是可读取的文本')
        blocks = [{'text': line.strip(), 'locator': f'原文第{i}行', 'heading': bool(HEADING.match(line.strip()))}
                  for i, line in enumerate(value.splitlines(), 1) if line.strip()]
    elif suffix == '.docx':
        from lxml import etree
        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                entries = archive.infolist()
                if len(entries) > 2000 or sum(e.file_size for e in entries) > 32 * 1024 * 1024:
                    raise HTTPException(422, 'DOCX解包资源超过限制')
                if any(e.flag_bits & 1 or e.filename.startswith('/') or '..' in PurePosixPath(e.filename).parts for e in entries):
                    raise HTTPException(422, 'DOCX包含不安全或加密成员')
                if any('vbaProject' in e.filename for e in entries):
                    raise HTTPException(422, '不支持含宏文档')
                xml = archive.read('word/document.xml')
                tree = etree.fromstring(xml, parser=etree.XMLParser(resolve_entities=False, no_network=True))
                ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
                for i, node in enumerate(tree.find('w:body', ns), 1):
                    if node.tag.endswith('}tbl'):
                        if node.findall('.//w:vMerge', ns) or node.findall('.//w:gridSpan', ns):
                            issues.append(f'文档块{i}含合并表格，条件对应关系需人工核对')
                        lines = [' | '.join(''.join(cell.itertext()) for cell in row.findall('w:tc', ns)) for row in node.findall('w:tr', ns)]
                        value = '\n'.join(lines)
                    else:
                        value = ''.join(node.xpath('.//w:t/text()', namespaces=ns))
                    if value.strip():
                        style = node.find('w:pPr/w:pStyle', ns)
                        heading = bool(style is not None and re.search('heading|标题', str(style.attrib), re.I)) or bool(HEADING.match(value))
                        blocks.append({'text': value.strip(), 'locator': f'DOCX文档块{i}（非页码）', 'heading': heading})
                if archive.namelist() and b'oleObject' in xml:
                    issues.append('嵌入对象未执行、未解析，需补充独立附件')
        except (zipfile.BadZipFile, KeyError, etree.XMLSyntaxError):
            raise HTTPException(422, 'DOCX结构无法可靠解析')
    elif suffix == '.pdf':
        from pypdf import PdfReader
        from pypdf._configuration import Configuration
        Configuration.zlib_maximum_output_length = 16 * 1024 * 1024
        try:
            reader = PdfReader(BytesIO(payload), strict=True)
            if reader.is_encrypted:
                raise HTTPException(422, '不支持加密PDF，请上传授权的可提取文本版本')
            if len(reader.pages) > 200:
                raise HTTPException(422, 'PDF超过200页限制，请按章节提供')
            for i, page in enumerate(reader.pages, 1):
                value = page.extract_text() or ''
                if not value.strip():
                    issues.append(f'PDF实际页序{i}无可提取文字，可能为扫描页')
                for n, line in enumerate(value.splitlines(), 1):
                    if line.strip():
                        blocks.append({'text': line.strip(), 'locator': f'PDF实际页序{i}文本行{n}', 'heading': bool(HEADING.match(line.strip()))})
            issues.append('PDF文本抽取不证明复杂表格、公式及版式完整；请对照原文件核对')
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, 'PDF无法可靠解析，未执行OCR或外部解析')
    elif suffix in {'.html', '.htm'}:
        from bs4 import BeautifulSoup
        from app.services.collection_service import extract_html
        raw = payload.decode('utf-8', errors='replace')
        page = extract_html(raw, 'https://document.invalid/')
        value = page.text
        blocks = [{'text': s.strip(), 'locator': f'网页正文段落{i}', 'heading': bool(HEADING.match(s.strip()))}
                  for i, s in enumerate(value.splitlines(), 1) if s.strip()]
        # References remain text metadata; never fetch them while parsing.
        soup = BeautifulSoup(raw, 'html.parser')
        from app.services.processing.article_facts import publication_metadata
        publication_suggestions=publication_metadata(soup)['publication_candidates']
        attachments = [a.get_text(' ', strip=True) for a in soup.select('a[href]') if re.search(r'\.(pdf|docx?)(?:\?|$)', a.get('href',''),re.I)]
        if attachments:
            issues.append('附件引用未自动下载：' + '；'.join(attachments[:20]))
    else:
        raise HTTPException(422, '仅支持DOCX、文字PDF、TXT、Markdown及HTML')
    if not blocks or sum(len(b['text']) for b in blocks) > MAX_TEXT:
        raise HTTPException(422, '没有可靠正文或提取内容超过60万字限制')
    sections, current = [], []
    for block in blocks:
        if block['heading'] and current:
            sections.append(current); current = []
        current.append(block)
    if current:
        sections.append(current)
    if len(sections) > 200:
        raise HTTPException(422, '超过200个结构段，请按章节提供资料')
    prefix = sections[0] if not sections[0][0]['heading'] and len(sections) > 1 else []
    result = []
    for ordinal, section in enumerate(sections, 1):
        title = section[0]['text'][:200]
        result.append({'key': f'{ordinal}:{hashlib.sha256(title.encode()).hexdigest()[:16]}',
                       'title': title, 'body': '\n'.join(b['text'] for b in section),
                       'mappings': [{'locator': b['locator'], 'text': b['text']} for b in section],
                       'context': '\n'.join(b['text'] for b in prefix) if section is not prefix else '',
                       'suggested_title': not section[0]['heading']})
    # Explicit clause references retain both the quoted rule and its source range.
    clauses={re.match(r'^第[一二三四五六七八九十百零\d]+条',s['title']).group():s for s in result if re.match(r'^第[一二三四五六七八九十百零\d]+条',s['title'])}
    for section in result:
        references=set(re.findall(r'第[一二三四五六七八九十百零\d]+条',section['body']))
        for ref in references:
            linked=clauses.get(ref)
            if linked and linked is not section:
                section['context']+='\n\n引用条款原文：\n'+linked['body']
                section['mappings'].extend(m for m in linked['mappings'] if m not in section['mappings'])
    from app.services.processing.article_facts import business_times
    original_text='\n'.join(b['text'] for b in blocks)
    suggestions={'publication_candidates':publication_suggestions,'business_times':business_times(original_text,'')[:30]}
    basis='';category=''
    for pattern,label in [(r'安全操作规程|标准操作规程','SOP/操作流程'),(r'应急预案|应急处置','EHS/应急管理'),(r'管理制度|内部制度','内部制度/管理制度'),(r'孵化器运营|孵化服务','孵化器运营/运营管理'),(r'临床试验|临床研究','生物医药/临床研究'),(r'估值方法|现金流折现','投资分析/估值')]:
        match=re.search(pattern,original_text[:2000])
        if match:category=label;basis='原文关键词：'+match.group();break
    if re.search(r'申报指南|扶持政策|政策措施|资助办法',original_text[:2000]):
        category='政策/产业扶持';basis='政策文件类型关键词（分类建议须人工确认）'
    suggestions.update(category=category,classification_basis=basis)
    if len(result)>1:issues.append('按原章节生成结构草稿；跨章节前提、适用对象和例外须核对，必要时先合并，不把章节片段当作独立专业结论')
    return {'sections': result, 'issues': sorted(set(issues)), 'parser_version': PARSER_VERSION,'suggestions':suggestions}
