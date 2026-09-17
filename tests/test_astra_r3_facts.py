"""Pure offline boundary checks: no application boot, DB, HTTP or scheduling."""
import sys
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.services.processing.article_facts import analyze_article, TZ, product_facts, matches_reading, publication_metadata
from bs4 import BeautifulSoup

NOW=datetime(2026,9,16,12,tzinfo=TZ)
URL='https://public.example/article'


class Facts(unittest.TestCase):
    def setUp(self):
        self.guard=patch('socket.getaddrinfo',side_effect=AssertionError('offline only'))
        self.guard.start();self.addCleanup(self.guard.stop)

    def analyze(self,title,text,date='2026-09-15',**kw):
        return analyze_article(title,text,URL,date,now=NOW,**kw)

    def test_finance_and_license_terms(self):
        f=self.analyze('创新药企业完成A轮融资','创新药企业完成数亿元A轮融资，由甲基金领投。所得资金用于推进临床试验。')
        self.assertEqual(f['category'],'financing');self.assertEqual(f['stage'],'完成')
        self.assertIn('数亿元',str(f['fields']));self.assertNotIn('估值',str(f['fields']))
        d=self.analyze('Biotech A signs licensing agreement with B','Biotech A signed an agreement for drug X. Upfront payment is $20 million. Contingent milestones are up to $1 billion. Royalties apply to global sales.')
        self.assertEqual(d['category'],'deal')
        self.assertIn('$20 million',next(x['value'] for x in d['fields'] if x['label']=='首付款'))
        self.assertIn('$1 billion',next(x['value'] for x in d['fields'] if x['label']=='条件性付款'))

    def test_old_news_not_created_now(self):
        data={'title':'Biotech financing completed','content':'Biotech raised $50 million in financing for clinical drug development.','published_at':'2025-01-02','created_at':'2026-09-16','updated_at':'2026-09-16'}
        f=product_facts(data,now=NOW);self.assertEqual(f['freshness'],'历史/补录')
        self.assertFalse(matches_reading(f,days='7days',now=NOW))

    def test_old_active_then_expired_refresh(self):
        body='上海创新药项目申报受理，企业可提交临床研发申请。申请人提交截止2026年9月20日。'
        f=self.analyze('上海创新药研发项目申报',body,'2026-06-01')
        self.assertTrue(f['actionable']);self.assertEqual(f['view'],'priority')
        self.assertTrue(matches_reading(f,view='latest',active=True,now=NOW))
        later=analyze_article('上海创新药研发项目申报',body,URL,'2026-06-01',now=datetime(2026,9,21,tzinfo=TZ))
        self.assertFalse(later['actionable']);self.assertEqual(later['business_status'],'已截止')

    def test_conflict_missing_and_future_year(self):
        f=self.analyze('2027年度创新药项目申报','创新药物研发专项公开申报，项目执行期限2027年1月1日。','')
        self.assertIsNone(f['disclosure_at']);self.assertFalse(f['business_times'])
        f=self.analyze('创新药临床试验结果','创新药临床试验公布患者结果。',metadata={'publication_candidates':[{'raw':'2026-09-14'},{'raw':'2026-09-15'}]})
        self.assertTrue(f['publication']['conflict']);self.assertEqual(f['view'],'verify')
        f=self.analyze('创新药临床试验结果','创新药临床试验公布患者结果。','2027-01-01')
        self.assertIsNone(f['disclosure_at'])

    def test_report_period_is_not_disclosure(self):
        f=self.analyze('Biotech reports financial results for 2025','Biotech announces annual revenue for the year ended December 31, 2025. Revenue was $20 million.','2026-09-15')
        self.assertEqual(f['category'],'capital');self.assertEqual(f['age_days'],1)

    def test_multiple_deadlines_no_latest_choice(self):
        f=self.analyze('创新药专项申报','创新药专项受理申请。申请人提交截止2026年9月10日。单位推荐截止2026年9月20日。')
        self.assertEqual(len(f['business_times']),2);self.assertFalse(f['actionable'])

    def test_mixed_notice_does_not_borrow_fields(self):
        f=self.analyze('新材料与多个专项通知','一、碳纤维专项资助500万元，截止2026年9月20日。\n二、创新药研发支持临床试验，具体条件见附件。')
        self.assertTrue(f['mixed_scope']);self.assertNotIn('500万元',str(f['fields']));self.assertFalse(f['actionable']);self.assertNotEqual(f['view'],'priority')
        f=self.analyze('上海碳纤维基地项目','上海新材料碳纤维研发基地宣布建设完成。')
        self.assertFalse(f['relevant']);self.assertNotEqual(f['view'],'priority')

    def test_routine_and_negative(self):
        f=self.analyze('药品再注册批件领取通知','药品再注册批件领取通知，请相关企业核对药品品种和办理手续。')
        self.assertEqual(f['view'],'routine')
        f=self.analyze('Biotech terminates clinical trial','Biotech terminates clinical trial after patients failed to meet the primary endpoint.')
        self.assertEqual(f['stage'],'终止/撤销')
        self.assertNotEqual(f['view'],'history')
        self.assertTrue(matches_reading(f,view='latest',now=NOW))

    def test_procurement_award_not_open(self):
        f=self.analyze('医疗设备采购中标公告','医疗设备采购中标结果公布，申请提交截止2026年9月20日。')
        self.assertFalse(f['actionable']);self.assertEqual(f['business_status'],'采购阶段非开放招标')

    def test_date_precision_and_metadata(self):
        soup=BeautifulSoup('<article><time datetime="2026-09-15">时间</time></article><footer>2026</footer><script type="application/ld+json">{"@type":"NewsArticle","datePublished":"2026-09-15","dateModified":"2026-09-16"}</script>','html.parser')
        meta=publication_metadata(soup)
        self.assertEqual(meta['source_modified_at'],'2026-09-16')
        f=self.analyze('Biotech financing','Biotech raised $5 million for drug trials.',metadata=meta)
        self.assertEqual(f['publication']['precision'],'date');self.assertEqual(f['disclosure_at'],'2026-09-15')
        meta=publication_metadata(BeautifulSoup('<time itemprop="datePublished">September 15, 2026</time>','html.parser'))
        self.assertEqual(self.analyze('Biotech financing','Biotech raised $5 million for drug trials.',metadata=meta)['disclosure_at'],'2026-09-15')

    def test_summary_preserves_manual_and_evidence(self):
        data={'title':'Biotech financing','content':'Biotech raised $20 million for drug trials.','summary':'人工核对摘要','published_at':'2026-09-15'}
        f=product_facts(data,now=NOW);self.assertEqual(f['summary'],'人工核对摘要')
        for field in f['fields']:
            if field['evidence']:self.assertIn(field['evidence'],data['content']);self.assertEqual(field['url'],data.get('source_url',''))

    def test_material_change_not_footer_or_typo(self):
        title='Biotech announces financing';body='Biotech raised $20 million for drug trials.'
        before=self.analyze(title,body)
        footer=self.analyze(title,body+' Copyright 2026. Contact us for more information.')
        self.assertEqual(before['material_signature'],footer['material_signature'])
        changed=self.analyze(title,body.replace('$20','$30'))
        self.assertNotEqual(before['material_signature'],changed['material_signature'])

    def test_review_and_reading_share_rules(self):
        title='Biotech reports interim results';body='Biotech announces revenue of $20 million for its clinical drug business.'
        review=self.analyze(title,body)
        reading=product_facts({'title':title,'content':body,'published_at':'2026-09-15'},now=NOW)
        for key in ['category','disclosure_at','freshness','business_status','view']:
            self.assertEqual(review[key],reading[key])


if __name__=='__main__':unittest.main(verbosity=2)
