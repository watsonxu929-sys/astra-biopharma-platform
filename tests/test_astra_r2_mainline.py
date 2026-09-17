"""Offline mainline checks. Run directly with ASTRA_R2_TEST_DB pointing to an isolated seed.

No pytest/conftest, no formal DB reads, no network and no scheduler startup.
"""
import json
from contextlib import closing
import os
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
SEED = Path(os.environ['ASTRA_R2_TEST_DB']).resolve()
if not SEED.is_relative_to(ROOT / 'data' / 'acceptance') or SEED == ROOT / 'data' / 'app.db':
    raise RuntimeError('Explicit isolated acceptance seed required')
os.environ['APP_DB_PATH'] = str(SEED)
os.environ['DATABASE_URL'] = 'sqlite:///' + SEED.as_posix()

from app.services import collection_service as collection
from app.services.intelligence_flow_service import process_collection_job_with_automation
from app.services.processing.processing_job_service import candidate_detail, list_review_queue
from app.services.intelligence_review_service import IntelligenceReviewService
from app.services.intelligence_product_service import IntelligenceProductService
from app.services.processing.content_quality_service import article_review_quality


class ArticleMainline(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='astra_r2_offline_')
        self.addCleanup(self.tmp.cleanup)
        self.db = Path(self.tmp.name) / 'isolated.db'
        with closing(sqlite3.connect(SEED.as_uri() + '?mode=ro', uri=True)) as src, closing(sqlite3.connect(self.db)) as dst:
            src.backup(dst)
        for target in ['socket.getaddrinfo', 'socket.create_connection', 'httpx.Client.send']:
            guard = patch(target, side_effect=AssertionError('Offline test attempted network'))
            guard.start()
            self.addCleanup(guard.stop)
        self.url = 'https://public.example/articles'
        self.article_url = self.url + '/clinical-2026?id=21&lang=en'
        self.body = ('上海生物医药企业宣布启动临床研究。该药物试验计划在上海研发中心进行，研究将评价安全性和有效性。\n'
                     '本次公开公告明确项目申报条件、受理范围和研究内容。\n'
                     '企业并未公布采购需求，也没有要求自动形成商机。\n') * 4
        self.source = collection.create_collection_source(name='ISOLATED article', source_type='list_page',
            url=self.url, crawl_detail_pages=True, max_links=2, db_path=self.db)
        self.responses = {self.url: '<main><a href="/articles/clinical-2026?id=21&amp;lang=en">上海生物医药项目启动临床研究的公开通知</a></main>',
            self.article_url: '<html><head><title>上海生物医药项目启动临床研究的公开通知</title></head><body><article>' + self.body + '</article></body></html>'}

    def run_collection(self):
        def fetch(url, *args, **kwargs):
            return self.responses[url], 200, 'text/html', {}
        with patch.object(collection, '_http_get', side_effect=fetch), patch.object(collection, 'check_robots', return_value={'allowed': True, 'status': 'allowed'}), patch.object(collection.time, 'sleep'):
            return process_collection_job_with_automation(collection.create_job(self.source['id'], db_path=self.db)['id'], db_path=self.db)

    def candidate(self):
        rows, _ = list_review_queue(self.db)
        return next(row for row in rows if row['source_url'] == self.article_url)

    def test_discovery_and_date_evidence(self):
        self.assertEqual(collection._source_request_url('https://public.example/news/?lang=zh&utm_source=x'), 'https://public.example/news/?lang=zh')
        source = collection.create_collection_source(name='ISOLATED slash', source_type='list_page', url=self.url+'/column/', db_path=self.db)
        self.assertEqual(source['url'], self.url+'/column/')
        html = '<nav><a href="/about">了解我们的一切产品和平台</a></nav><main><a href="/a?id=2&amp;lang=zh&amp;utm_source=x">上海药物研发中心启动新项目</a><a href="/policy.pdf">项目申报附件文件下载</a></main>'
        rows = collection.discover_links(html, self.url)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['normalized_url'], 'https://public.example/a?id=2&lang=zh')
        page = collection.extract_html('<title>产业申报</title><article>申请截止2027年12月20日，请提交临床研究材料。</article>', self.url)
        self.assertEqual(page.published_at, '')
        self.assertEqual(collection._next_column('', self.url + '/index_2.html', {'next_page_template': 'index_{page}.html'}), self.url + '/index_3.html')

    def test_automatic_article_and_duplicate(self):
        first = self.run_collection()
        self.assertEqual(first['new'], 1)
        self.assertEqual(first['automation']['created'], 1)
        c = self.candidate()
        self.assertEqual(c['field_name'], 'article_review')
        self.assertFalse(c['subject_id'])
        second = self.run_collection()
        self.assertEqual(second['new'], 0)
        self.assertEqual(second['duplicate'], 1)
        self.assertEqual(second['automation']['created'], 0)

    def test_publish_without_entity_full_body_and_lifecycle(self):
        self.run_collection()
        c = self.candidate()
        review = IntelligenceReviewService(self.db)
        writer = IntelligenceProductService(self.db)
        review.review_candidate(c['id'], decision='approved', actor='offline_operator', permissions={'review_data'})
        result = writer.publish_candidate(c['id'], actor='offline_operator', permissions={'review_data'})
        self.assertGreater(len(result['content']), 200)
        self.assertIsNone(result['published_at'])
        self.assertEqual(result['status'], 'published')
        self.assertEqual(writer.publish_candidate(c['id'], actor='offline_operator', permissions={'review_data'})['id'], result['id'])
        # Test-only lifecycle state; production lifecycle writer remains unchanged.
        with closing(sqlite3.connect(self.db)) as db:
            db.execute("UPDATE v06_intelligence_items SET status='withdrawn' WHERE id=?", (result['id'],))
            db.commit()
        self.assertEqual(IntelligenceProductService(self.db).publish_candidate(c['id'], actor='offline_operator', permissions={'review_data'})['status'], 'withdrawn')

    def test_permissions_and_edit_audit(self):
        self.run_collection()
        c = self.candidate()
        for action in [lambda: IntelligenceProductService(self.db).publish_candidate(c['id'], actor='viewer', permissions=set()),
                       lambda: IntelligenceReviewService(self.db).review_candidate(c['id'], decision='approved', actor='viewer', permissions=set())]:
            with self.assertRaises(PermissionError):
                action()
        IntelligenceReviewService(self.db).edit_article(c['id'], actor='offline_operator', permissions={'review_data'}, title=c['source_title'], content=self.body, note='核对原文')
        detail = candidate_detail(c['id'], self.db)
        self.assertEqual(detail['candidate']['pipeline_review_status'], 'pending')
        self.assertTrue(any(x['action'] == 'article_edited' for x in detail['history']))
        from fastapi import HTTPException
        from starlette.requests import Request
        from app.v05g_processing import _require_article_review
        with self.assertRaises(HTTPException) as denied:
            _require_article_review(Request({'type':'http','security_context':{'permissions':[]}}))
        self.assertEqual(denied.exception.status_code,403)

    def test_ignored_never_auto_revives(self):
        self.run_collection()
        c = self.candidate()
        IntelligenceReviewService(self.db).review_candidate(c['id'], decision='rejected', actor='offline_operator', permissions={'review_data'}, note='继续观察')
        self.run_collection()
        self.assertEqual(candidate_detail(c['id'], self.db)['candidate']['pipeline_review_status'], 'rejected')
        self.assertNotIn(c['id'], [r['id'] for r in list_review_queue(self.db)[0]])

    def test_failure_retry_is_persisted(self):
        valid = self.responses.pop(self.article_url)
        first = self.run_collection()
        self.assertEqual(first['failed'],1)
        with closing(sqlite3.connect(self.db)) as db:
            self.assertEqual(db.execute('SELECT status FROM v05f_discovered_links WHERE monitoring_source_id=?',(self.source['id'],)).fetchone()[0], 'failed')
        self.responses[self.article_url] = valid
        self.assertEqual(self.run_collection()['new'],1)

    def test_attachments_and_access_denied_not_publishable(self):
        q = article_review_quality('上海创新药临床试验公告', self.body, self.article_url, metadata={'attachments':[{'url':'https://public.example/p.pdf','status':'unparsed'}]})
        self.assertFalse(q['publishable'])
        self.assertTrue(any('附件' in x for x in q['gaps']))
        with self.assertRaises(RuntimeError):
            collection._validate_source_response('<title>Access Denied</title><body>captcha</body>', 'text/html', 'webpage')

    def test_real_sample_regression_topics_and_table(self):
        from app.services.processing.content_quality_service import _has_biopharma_keywords, _is_navigation_only
        for title in ['癌症和心脑血管疾病防治项目申报', '重大传染病防控项目申报', '合成生物学项目通知']:
            self.assertTrue(_has_biopharma_keywords(title, '公开申报通知'))
        self.assertFalse(_has_biopharma_keywords('制造业企业上市项目', 'research marketing innovation'))
        text = '经我局审核，同意核发下列品种药品再注册批准通知书。' * 5 + '\n受理号\n药品名称\n主送单位\nABC123\n创新药物\n某制药有限公司'
        self.assertFalse(_is_navigation_only(text))
        q=article_review_quality('药品再注册批件领取通知', text*2, self.article_url)
        self.assertEqual(q['reading_use'], '行业观察')

    def test_private_network_refused(self):
        import socket
        from app.services.member_import_service import validate_public_url
        with patch('socket.getaddrinfo', return_value=[(socket.AF_INET,socket.SOCK_STREAM,6,'',('127.0.0.1',0))]):
            with self.assertRaises(ValueError):validate_public_url('http://private.example/article')


if __name__ == '__main__':
    unittest.main(verbosity=2)
