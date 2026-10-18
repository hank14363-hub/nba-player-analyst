import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from commentary_workflow import template,validate
from editorial_audit import audit
from render_research_book import Book
from book_contract import validate_content

class CommentaryWorkflowTests(unittest.TestCase):
    def setUp(self):
        p=ROOT/'examples/cade-cunningham-2024-25-official-v07'
        self.a=json.loads((p/'analysis.json').read_text(encoding='utf-8'))
        self.b=json.loads((p/'book_content.json').read_text(encoding='utf-8'))
        self.c=json.loads((p/'claims.json').read_text(encoding='utf-8'))
        s=json.loads((p/'sources.json').read_text(encoding='utf-8'));self.a['sources']=s['sources']
        self.card=self.b['commentary_cards'][0];self.sid=self.card['source_id'];self.source=self.a['sources'][self.sid]
        self.r=dict(schema_version='0.1.0',status='complete',reason='',queries=[dict(query='Cade Cunningham 2024-25 analysis',tool='TEST FIXTURE, not a live search',searched_at='2026-10-15T10:00:00+08:00')],articles=[dict(url=self.source['url'],status='read',source_id=self.sid,accessed_at='2026-10-15T10:01:00+08:00',reason='Fixture uses previously verified article metadata; no new reading claimed.')])
        self.r['identity']=template(self.a)['identity']
    def codes(self,b):return [f['code'] for f in audit(b,self.a,self.c)['findings']]
    def test_template_never_claims_search(self):
        r=template(self.a);self.assertEqual(r['status'],'pending');self.assertFalse(r['queries']);self.assertIn('Cade Cunningham',r['suggested_queries'][0])
    def test_valid_read_record(self):self.assertEqual(validate(self.r,self.a['sources']),[])
    def test_unread_cannot_be_complete(self):
        self.r['articles'][0].update(status='blocked');self.assertTrue(validate(self.r,self.a['sources']))
    def test_search_snippet_cannot_be_verified_source(self):
        self.a['sources'][self.sid]['direct_page_verified']=False;self.assertTrue(validate(self.r,self.a['sources']))
    def test_original_url_must_match(self):
        self.r['articles'][0]['url']='https://example.com/not-the-original';self.assertTrue(validate(self.r,self.a['sources']))
    def test_timestamp_timezone_required(self):
        self.r['queries'][0]['searched_at']='2026-10-15T10:00:00';self.assertTrue(validate(self.r,self.a['sources']))
    def test_query_plan_not_attempt_record(self):
        r=template(self.a);r.update(status='limited',reason='No article found');self.assertTrue(validate(r,self.a['sources']))
    def test_no_search_tool_honest_limit(self):
        r=template(self.a);r.update(status='limited',reason='search_tool_unavailable');self.assertEqual(validate(r,{}),[])
    def test_attempted_but_blocked_is_valid_limit(self):
        self.r.update(status='limited',reason='Original page access denied');self.r['articles'][0].update(status='blocked');self.assertEqual(validate(self.r,self.a['sources']),[])
    def test_no_articles_or_record_flagged(self):
        b=copy.deepcopy(self.b);b.pop('commentary_cards');self.assertIn('commentary_not_attempted',self.codes(b))
    def test_pending_flagged(self):
        b=copy.deepcopy(self.b);b['commentary_research']=template(self.a);self.assertIn('commentary_pending',self.codes(b))
    def test_read_but_unwritten_flagged(self):
        b=copy.deepcopy(self.b);b.update(commentary_research=self.r,commentary_cards=[]);self.assertIn('commentary_unwritten',self.codes(b))
    def test_old_verified_cards_compatible(self):self.assertNotIn('commentary_not_attempted',self.codes(self.b))
    def test_validation_rejects_false_complete(self):
        self.r['articles']=[];self.b['commentary_research']=self.r;self.assertTrue(any('original article' in s for s in validate_content(self.b,self.a,self.c)))
    def test_render_limit_escapes_html(self):
        self.b.update(commentary_cards=[],commentary_research=dict(status='limited',reason='<script>unsafe</script>',queries=[],articles=[]))
        html=Book(self.a,self.c,self.b,'').commentary();self.assertIn('球评研究受限',html);self.assertNotIn('<script>',html)
    def test_other_season_record_rejected(self):
        self.r['identity']['season']='2025-26';self.assertTrue(validate(self.r,self.a['sources'],self.a))
    def test_missing_author_rejected(self):
        self.a['sources'][self.sid]['author']='';self.assertTrue(validate(self.r,self.a['sources']))
    def test_classic_layout_also_displays_commentary(self):
        self.b.pop('presentation',None)
        html=Book(self.a,self.c,self.b,'').render();self.assertIn('commentary-card',html);self.assertIn(self.source['author'],html)

if __name__=='__main__':unittest.main()
