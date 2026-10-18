import copy
import sys
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import read_json
from book_contract import validate_content
from book_shot_explorer import explorer_rows
from render_research_book import Book

class TextSampleRoutes(unittest.TestCase):
    def setUp(self):
        case=ROOT/'examples/cade-cunningham-2024-25-official-v072'
        self.a=read_json(case/'analysis.json');self.c=read_json(case/'claims.json');self.b=read_json(case/'book_content.json')
        self.a['sources'].update(read_json(case/'sources.json')['sources'])
        self.raw=read_json(case/'data_bundle.json');self.report=(case/'report.md').read_text(encoding='utf-8')
        self.card=self.b['dimensions'][0]['reading_cards'][2];self.card['shot_zone']='MID'
    def test_route_requires_original_event_evidence(self):
        self.a.pop('shot_context')
        self.assertTrue(any('validated shot events' in e for e in validate_content(self.b,self.a,self.c)))
    def test_unknown_filter_cannot_be_published(self):
        self.card['shot_zone']='DEFENDER_DISTANCE'
        self.assertTrue(any('Unsupported reading card shot_zone' in e for e in validate_content(self.b,self.a,self.c)))
    def test_card_and_article_route_to_same_original_sample(self):
        self.assertEqual(validate_content(self.b,self.a,self.c),[])
        before=copy.deepcopy(self.raw)
        book=Book(self.a,self.c,self.b,self.report,shot_rows=explorer_rows(self.raw,self.a))
        card_html=book.dimension('scoring');article_html=book.linked_article(self.report)
        self.assertIn('data-shot-zone="MID"',card_html)
        self.assertIn('data-shot-return="reading-scoring-3"',card_html)
        self.assertIn('id="article-shot-C17"',article_html)
        self.assertIn('data-shot-return="article-shot-C17"',article_html)
        self.assertEqual(self.raw,before)
    def test_no_event_bundle_keeps_article_without_filter_routes(self):
        book=Book(self.a,self.c,self.b,self.report)
        self.assertNotIn('data-shot-zone=',book.linked_article(self.report))

if __name__=='__main__':unittest.main()
