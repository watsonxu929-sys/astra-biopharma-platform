"""Published reading must keep the list/detail visibility contract. No DB writes."""
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from fastapi import HTTPException
from app.services.unified_intelligence_service import UnifiedIntelligenceService


class ReadingVisibility(unittest.TestCase):
    def test_allowed_published(self):
        for visibility in ('public', 'organization'):
            item = SimpleNamespace(status='published', visibility=visibility)
            self.assertIs(UnifiedIntelligenceService(Mock(get=Mock(return_value=item))).detail(1), item)

    def test_restricted_or_unknown_visibility(self):
        for visibility in ('private', None, '', 'unknown'):
            with self.subTest(visibility=visibility):
                item = SimpleNamespace(status='published', visibility=visibility)
                with self.assertRaises(HTTPException) as result:
                    UnifiedIntelligenceService(Mock(get=Mock(return_value=item))).detail(1)
                self.assertEqual(result.exception.status_code, 404)

    def test_unpublished(self):
        for status in ('draft', 'offline', 'archived', None):
            with self.subTest(status=status):
                item = SimpleNamespace(status=status, visibility='public')
                with self.assertRaises(HTTPException) as result:
                    UnifiedIntelligenceService(Mock(get=Mock(return_value=item))).detail(1)
                self.assertEqual(result.exception.status_code, 404)

    def test_missing(self):
        with self.assertRaises(HTTPException) as result:
            UnifiedIntelligenceService(Mock(get=Mock(return_value=None))).detail(1)
        self.assertEqual(result.exception.status_code, 404)


if __name__ == '__main__':
    unittest.main(verbosity=2)
