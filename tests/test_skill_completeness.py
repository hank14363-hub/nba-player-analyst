import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from run_analysis import parser
from calculate_metrics import analyze
from editorial_audit import audit
from render_research_book import Book
from common import digest


class CompletenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case=ROOT/'examples/cade-cunningham-2024-25-official-v081'
        cls.bundle=json.loads((cls.case/'data_bundle.json').read_text(encoding='utf-8'))
        cls.a=json.loads((cls.case/'analysis.json').read_text(encoding='utf-8'))
        cls.c=json.loads((cls.case/'claims.json').read_text(encoding='utf-8'))
        cls.b=json.loads((cls.case/'book_content.json').read_text(encoding='utf-8'))

    def test_cli_default_comparison(self):self.assertTrue(parser().parse_args(['--season','2025-26']).comparisons)
    def test_cli_explicit_optout(self):self.assertFalse(parser().parse_args(['--season','2025-26','--no-comparisons']).comparisons)

    def test_cli_default_import_recomputes_cohort(self):
        with tempfile.TemporaryDirectory() as t:
            p=subprocess.run([sys.executable,str(ROOT/'scripts/run_analysis.py'),'--input',str(self.case/'data_bundle.json'),'--player-id','1630595','--season','2024-25','--out',t],capture_output=True,text=True,encoding='utf-8')
            self.assertEqual(p.returncode,0,p.stderr);a=json.loads((Path(t)/'analysis.json').read_text(encoding='utf-8'));self.assertEqual(a['comparison_context']['status'],'ok')

    def test_old_analyze_request_preserved(self):
        a=analyze(self.bundle,self.a['request']);self.assertEqual(digest(a['metrics']),digest(self.a['metrics']))

    def test_available_but_never_requested_flag(self):
        a=copy.deepcopy(self.a);a.pop('comparison_context',None);a['request'].pop('comparisons',None)
        self.assertIn('comparison_not_enabled',[x['code'] for x in audit(self.b,a,self.c,self.bundle)['findings']])

    def test_optout_not_false_omission(self):
        a=copy.deepcopy(self.a);a.pop('comparison_context',None);a['request']['comparisons']=False
        self.assertNotIn('comparison_not_enabled',[x['code'] for x in audit(self.b,a,self.c,self.bundle)['findings']])

    def test_incomplete_source_not_claimed_available(self):
        a=copy.deepcopy(self.a);a.pop('comparison_context',None);a['request'].pop('comparisons',None);b=copy.deepcopy(self.bundle);b['tables'].pop('player_scoring')
        self.assertNotIn('comparison_not_enabled',[x['code'] for x in audit(self.b,a,self.c,b)['findings']])

    def test_comparison_computed_but_unwritten(self):
        claims={'claims':[c for c in self.c['claims'] if not any(m.startswith('COHORT_') for m in c['metric_ids'])]}
        self.assertIn('comparison_unwritten',[x['code'] for x in audit(self.b,self.a,claims)['findings']])

    def test_generic_and_repeated_notes(self):
        b=copy.deepcopy(self.b)
        for d in b['dimensions']:
            d['reading_cards']=[dict(application='把结论用于具体分工与回合核验。')]
        flags=[x['code'] for x in audit(b,self.a,self.c)['findings']];self.assertIn('generic_reading_note',flags);self.assertIn('repeated_reading_note',flags)

    def test_no_semantic_pass_claim(self):self.assertFalse(audit(self.b,self.a,self.c)['semantic_truth_verified'])

    def test_br_complete_comparison_renderer(self):
        a=json.loads((ROOT/'examples/sumitro-cade-2024-25/analysis.json').read_text(encoding='utf-8'))
        book=Book(a,{'claims':[]},{'dimensions':[]},'')
        html=book.comparisons();self.assertIn('BR五轴',html);self.assertIn('class="target-player"',html);self.assertNotIn('<th>PIE</th>',html);self.assertNotIn('<th>非受助攻命中</th>',html);self.assertIn('USG≥23%',html)

    def test_br_other_role_sensitivity_renderer(self):
        a=json.loads((ROOT/'examples/sumitro-cade-2024-25/analysis.json').read_text(encoding='utf-8'))
        a['comparison_context']['sensitivity'][0]['label']='更高出勤门槛'
        self.assertIn('GP≥50',Book(a,{'claims':[]},{'dimensions':[]},'').comparisons())

    def test_disabled_renderer_distinguishes_missing(self):
        a=copy.deepcopy(self.a);a.pop('comparison_context',None)
        self.assertIn('本次未启用',Book(a,self.c,self.b,'').comparisons())

if __name__=='__main__':unittest.main()
