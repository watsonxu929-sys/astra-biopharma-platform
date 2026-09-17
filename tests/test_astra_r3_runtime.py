"""Small isolated R3 collection checks; reuse R2's guarded fixture, no network."""
import unittest
from datetime import datetime, timedelta
from test_astra_r2_mainline import ArticleMainline, collection
from app.services.intelligence_flow_service import schedule_due_collection_jobs


class R3Runtime(unittest.TestCase):
    setUp = ArticleMainline.setUp
    run_collection = ArticleMainline.run_collection
    candidate = ArticleMainline.candidate

    def test_six_hour_frequency_not_each_worker_tick(self):
        with collection.db_connection(self.db) as conn:
            conn.execute('update v04g_monitoring_sources set is_enabled=0 where id<>?', (self.source['id'],))
            conn.execute("update v04g_monitoring_sources set check_frequency='six_hourly',last_checked_at=? where id=?", (datetime.now().isoformat(),self.source['id']))
        self.assertEqual(schedule_due_collection_jobs(db_path=self.db)['created'],0)
        with collection.db_connection(self.db) as conn:
            conn.execute('update v04g_monitoring_sources set last_checked_at=? where id=?', ((datetime.now()-timedelta(hours=7)).isoformat(),self.source['id']))
        result=schedule_due_collection_jobs(db_path=self.db)
        self.assertEqual(result['created'],1)
        self.assertEqual(schedule_due_collection_jobs(db_path=self.db)['created'],0)

    def test_footer_change_never_requeues_as_new_event(self):
        first=self.run_collection()
        self.assertEqual(first['automation']['created'],1)
        self.responses[self.article_url]=self.responses[self.article_url].replace('</article>','\n版权所有 Copyright 2026. Contact us.</article>')
        second=self.run_collection()
        self.assertEqual(second['automation']['created'],0)
        with collection.db_connection(self.db) as conn:
            seen=conn.execute('select metadata_json from v05f_collection_items where monitoring_source_id=? order by id',(self.source['id'],)).fetchall()
        import json
        self.assertEqual(json.loads(seen[0][0])['first_seen_at'],json.loads(seen[-1][0])['first_seen_at'])


if __name__=='__main__':
    unittest.main(defaultTest='R3Runtime',verbosity=2)
