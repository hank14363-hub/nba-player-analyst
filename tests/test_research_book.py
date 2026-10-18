"""Deterministic presentation, evidence integrity and safe rendering tests."""
from __future__ import annotations
import copy
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from book_contract import make_template, validate_content, load_context
from common import DataError
from render_research_book import Book, build, markdown_body, safe_url, bars_svg
from validate_book import check, inspect_html


class ResearchBookTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.run=Path(self.tmp.name)/'run'
        self.run.mkdir()
        for name in ('data_bundle.json','analysis.json','sources.json','claims.json','report.md','book_content.json'):
            shutil.copy2(ROOT/'examples/demo_output'/name,self.run/name)
        self.analysis=json.loads((self.run/'analysis.json').read_text(encoding='utf-8'))
        self.claims=json.loads((self.run/'claims.json').read_text(encoding='utf-8'))
        self.content=json.loads((self.run/'book_content.json').read_text(encoding='utf-8'))
        self.report=(self.run/'report.md').read_text(encoding='utf-8')

    def tearDown(self):
        self.tmp.cleanup()

    def save(self,name,value):
        (self.run/name).write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')

    def errors(self):
        return validate_content(self.content,self.analysis,self.claims)

    def test_real_demo_content_valid(self):
        self.assertEqual(self.errors(),[])

    def test_template_explicitly_draft(self):
        t=make_template(self.analysis)
        self.assertEqual(t['status'],'draft')
        self.assertTrue(validate_content(t,self.analysis,self.claims))

    def test_identity_mismatch_rejected(self):
        self.content['identity']['season']='2023-24'
        self.assertTrue(self.errors())

    def test_data_kind_mismatch_rejected(self):
        self.content['data_kind']='nba'
        self.assertTrue(self.errors())

    def test_unknown_claim_rejected(self):
        self.content['executive_claim_ids']=['C404']
        self.assertTrue(self.errors())

    def test_duplicate_reference_rejected(self):
        self.content['summary_claim_ids']=['C02','C02']
        self.assertTrue(self.errors())

    def test_quantitative_free_text_rejected(self):
        self.content['strategies'][0]['action']='Increase efficiency by 20 percent'
        self.assertTrue(self.errors())

    def test_missing_dimension_rejected(self):
        self.content['dimensions'].pop()
        self.assertTrue(self.errors())

    def test_empty_dimension_is_explicit_gap(self):
        self.content['dimensions'][0]['claim_ids']=[]
        self.assertEqual(self.errors(),[])
        text=Book(self.analysis,self.claims,self.content,self.report).dimension('scoring')
        self.assertIn('class="empty"',text)

    def test_missing_conditions_rejected(self):
        self.content['strategies'][0]['conditions']=[]
        self.assertTrue(self.errors())

    def test_missing_tradeoffs_rejected(self):
        self.content['strategies'][0]['tradeoffs']=[]
        self.assertTrue(self.errors())

    def test_uncovered_challenge_rejected(self):
        self.content['next_actions']=[a for a in self.content['next_actions'] if 'Q03' not in a['challenge_ids']]
        self.assertTrue(self.errors())

    def test_research_action_without_premature_strategy(self):
        self.content['strategies']=[]
        self.assertEqual(self.errors(),[])

    def test_unsafe_id_rejected(self):
        self.content['challenges'][0]['id']='bad" onclick="x'
        self.assertTrue(self.errors())

    def test_no_forced_padding_or_fixed_strategy_count(self):
        self.content['strategies']=[]
        self.content['challenges']=[]
        for a in self.content['next_actions']:
            a['challenge_ids']=[]
        self.assertEqual(self.errors(),[])

    def test_title_html_escaped(self):
        self.content['title']='<script>alert("bad")</script>'
        text=Book(self.analysis,self.claims,self.content,self.report).render()
        self.assertNotIn('<script>alert(',text)
        self.assertIn('&lt;script&gt;',text)

    def test_markdown_html_not_executed(self):
        text=markdown_body('## Test\n\n<img src="https://evil" onerror="alert(1)">\n\n[P_BASE]',self.analysis['sources'])
        self.assertNotIn('<img ',text)
        self.assertIn('href="#source-P_BASE"',text)

    def test_synthetic_url_not_clickable(self):
        self.assertIsNone(safe_url('synthetic://demo/data'))

    def test_javascript_url_not_clickable(self):
        self.assertIsNone(safe_url('javascript:alert(1)'))

    def test_safe_url(self):
        self.assertEqual(safe_url('https://www.nba.com/stats'), 'https://www.nba.com/stats')

    def test_credential_url_rejected(self):
        self.assertIsNone(safe_url('https://user:pass@example.com'))

    def test_control_character_url_rejected(self):
        self.assertIsNone(safe_url('https://example.com\n'))

    def test_build_and_check(self):
        manifest=build(self.run)
        result=check(self.run)
        self.assertEqual(result['status'],'pass')
        self.assertEqual(result['section_count'],9)
        self.assertGreaterEqual(result['svg_count'],6)
        self.assertTrue(manifest['recomputed_metrics'])

    def test_existing_outputs_not_silently_overwritten(self):
        build(self.run)
        with self.assertRaises(DataError): build(self.run)

    def test_force_preserves_source_article(self):
        before=(self.run/'report.md').read_bytes()
        build(self.run)
        build(self.run,force=True)
        self.assertEqual((self.run/'report.md').read_bytes(),before)

    def test_raw_metric_tampering_rejected(self):
        self.analysis['metrics'][0]['value']=999
        self.save('analysis.json',self.analysis)
        with self.assertRaises(DataError): build(self.run)

    def test_base_source_tampering_rejected(self):
        sources=json.loads((self.run/'sources.json').read_text(encoding='utf-8'))
        sources['sources']['P_BASE']['url']='https://fake.example'
        self.save('sources.json',sources)
        with self.assertRaises(DataError): build(self.run)

    def test_article_edit_after_render_detected(self):
        build(self.run)
        with (self.run/'report.md').open('a') as f: f.write('\nChanged text\n')
        self.assertEqual(check(self.run)['status'],'fail')

    def test_html_edit_after_render_detected(self):
        build(self.run)
        with (self.run/'research_book.html').open('a') as f: f.write('\n<!--changed-->')
        self.assertEqual(check(self.run)['status'],'fail')

    def test_broken_anchor_rejected(self):
        text=Book(self.analysis,self.claims,self.content,self.report).render()
        result=inspect_html(text+'<a href="#missing">bad</a>',self.analysis)
        self.assertTrue(result['errors'])

    def test_external_image_dependency_rejected(self):
        text=Book(self.analysis,self.claims,self.content,self.report).render()
        self.assertTrue(inspect_html(text+'<img src="https://example.com/x.png">',self.analysis)['errors'])

    def test_duplicate_html_id_rejected(self):
        text=Book(self.analysis,self.claims,self.content,self.report).render()
        self.assertTrue(inspect_html(text+'<div id="cover"></div>',self.analysis)['errors'])

    def test_missing_chart_does_not_invent_baseline(self):
        for m in self.analysis['metrics']:
            if m['metric_id']=='LEAGUE_TS_PCT':
                m.update(status='missing',value=None,display='N/A')
        book=Book(self.analysis,self.claims,self.content,self.report)
        book.scoring()
        self.assertNotIn('efficiency.svg',book.charts)
        self.assertIn('shot_mix.svg',book.charts)

    def test_chart_can_show_above_one_fraction(self):
        svg=bars_svg([('A',1.5),('B',.5)],'Test')
        self.assertIn('150%',svg)
        self.assertIn('150.0%',svg)

    def test_summary_keeps_synthetic_warning_and_caveats(self):
        build(self.run)
        text=(self.run/'summary.md').read_text(encoding='utf-8')
        self.assertIn('\u5408\u6210\u6d4b\u8bd5\u6570\u636e',text)
        self.assertIn(self.claims['claims'][1]['report_quote'],text)

    def test_manifest_traversal_rejected(self):
        build(self.run)
        m=json.loads((self.run/'book_manifest.json').read_text(encoding='utf-8'))
        m['sha256']['../outside']='abc'
        self.save('book_manifest.json',m)
        self.assertEqual(check(self.run)['status'],'fail')


if __name__=='__main__':
    unittest.main()
