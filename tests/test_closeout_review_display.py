"""Presentation-only checks: no app boot, database or network."""
import unittest
import sys
from pathlib import Path
from jinja2 import Environment, FileSystemLoader, select_autoescape
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
ENV = Environment(loader=FileSystemLoader(ROOT / 'app/templates'), autoescape=select_autoescape())


class ReviewDisplay(unittest.TestCase):
    def render(self, fields, summary='主体甲完成融资。', **extra):
        facts = dict(fields=fields, summary=summary, category_label='企业融资', actionable=False,
                     mixed_scope=False, business_times=[], publication={'label':'', 'candidates':[]},
                     disclosure_at=None, first_seen_at=None, fetched_at=None)
        facts.update(extra)
        html = ENV.get_template('platform/_review_facts.html').module.review_facts(facts, {'gaps':[]})
        return BeautifulSoup(str(html), 'html.parser').get_text(' ', strip=True)

    def test_summary_not_repeated_as_fields(self):
        f={'label':'金额','value':'主体甲完成融资。','evidence':'主体甲完成融资。'}
        text=self.render([f,f])
        self.assertEqual(text.count('主体甲完成融资。'),1)

    def test_distinct_evidence_preserved_and_deduplicated(self):
        f={'label':'资金用途','value':'资金用于临床研究。','evidence':'资金用于临床研究。'}
        text=self.render([f,f])
        self.assertEqual(text.count('资金用于临床研究。'),1)
        self.assertIn('主体甲完成融资。',text)

    def test_missing_evidence_is_not_fake_fact(self):
        text=self.render([{'label':'金额','value':'未披露或待核对','evidence':''}],summary='关键事实待核对，请查看原文。')
        self.assertIn('事实抽取不足，请查看原文',text)
        self.assertNotIn('未披露或待核对',text)
        self.assertNotIn('关键事实待核对',text)

    def test_unknown_time_is_explicit(self):
        text=self.render([])
        self.assertIn('原文披露：待核对',text)
        self.assertIn('不等于事件发生时间',text)

    def test_template_actions_keep_contract(self):
        source=(ROOT/'app/templates/v05g_processing.html').read_text(encoding='utf-8-sig')
        self.assertIn('通过并发布',source)
        self.assertIn('<details><summary>忽略此情报</summary>',source)
        self.assertIn('name="decision" value="rejected"',source)
        self.assertIn('事实不足先查看原文',source)
        self.assertNotIn('待审核文章',source)

    def test_conference_location_does_not_match_avenue(self):
        from app.services.processing.article_facts import analyze_article
        text=('Citi Biopharma Conference\nLocation: JW Marriott Essex House, New York\n'
              'Another Healthcare Conference\nLocation: Lotte Palace, 455 Madison Avenue, New York\n')
        facts=analyze_article('Biopharma investor conferences',text,'https://public.example/news','2026-09-02')
        location=next(f['value'] for f in facts['fields'] if f['label']=='时间/地点/对象')
        self.assertIn('JW Marriott',location)
        self.assertNotIn('Lotte',location)
        no_location=analyze_article('Biopharma investor conferences','Citi Biopharma Conference\nMeet us near Madison Avenue next month.','https://public.example/news','2026-09-02')
        self.assertFalse(next(f['evidence'] for f in no_location['fields'] if f['label']=='时间/地点/对象'))


if __name__=='__main__':unittest.main(verbosity=2)
