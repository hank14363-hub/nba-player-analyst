"""Expression regressions: heuristic review must not change data or overstate its role."""
from __future__ import annotations
import copy
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from review_language import review_text,review_run,prose_fields
from poster_charts import Charts,T
from team_themes import select_theme
from render_player_poster import Poster,L

class LanguageTests(unittest.TestCase):
    def test_abstract_phrase_advisory(self):
        self.assertTrue(any(i['rule']=='abstract_phrase' for i in review_text('终结负荷下的机会转化结果很好。')))
    def test_plain_sentence(self):
        self.assertEqual(review_text('他的得分效率不错，但能否承担更多组织任务，还要再看。'),[])
    def test_abbreviation_needs_chinese(self):
        self.assertTrue(any(i['rule']=='unexplained_abbreviation' for i in review_text('TS为60%。')))
    def test_explained_abbreviation(self):
        self.assertEqual(review_text('真实命中率（TS%）综合考虑两分、三分和罚球。'),[])
    def test_rts_is_not_ts(self):
        self.assertEqual(review_text('相对真实命中率（rTS）用百分点表示。'),[])
    def test_code_blocks_ignored(self):
        self.assertEqual(review_text('```text\nTS=60\n```'),[])
    def test_reference_definition_ignored(self):
        self.assertEqual(review_text('[TS]: https://example.invalid/终结负荷'),[])
    def test_unqualified_hype_flagged(self):
        self.assertTrue(any(i['rule']=='strong_label' for i in review_text('他能完美适配这支球队。')))
    def test_negative_hype_example_not_flagged(self):
        self.assertEqual(review_text('不应称为完美适配。'),[])
    def test_long_sentence_advisory(self):
        self.assertTrue(any(i['rule']=='long_sentence' for i in review_text('我们需要更多记录'*20+'。')))
    def test_identity_and_ids_not_reviewed(self):
        self.assertEqual(list(prose_fields({'identity':{'name':'TS'},'claim_ids':['TS'],'text':'用具体表现说话。'})),[('text','用具体表现说话。')])
    def test_run_review_is_read_only(self):
        run=ROOT/'examples/demo_output'
        names=['report.md','analysis.json','data_bundle.json','sources.json','claims.json','book_content.json','poster_content.json']
        before={n:(run/n).read_bytes() for n in names}
        result=review_run(run)
        self.assertFalse(result['automatic_edits']);self.assertTrue(result['manual_review_required'])
        self.assertEqual(before,{n:(run/n).read_bytes() for n in names})
    def test_svg_labels_are_chinese_and_data_unchanged(self):
        a=json.loads((ROOT/'examples/demo_output/analysis.json').read_text(encoding='utf-8'))
        before=copy.deepcopy(a)
        charts=Charts(a,select_theme(a,'LAL')).build()
        self.assertIn('得分 / 75回合',charts['creation']['svg'])
        self.assertIn('三分命中率',charts['shot_mix']['svg'])
        self.assertIn('每百回合失分',charts['team_context']['svg'])
        self.assertEqual(before,a)
    def test_critical_denominator_and_scope_preserved(self):
        self.assertIn('已经投进',T['assisted_note'])
        self.assertIn('样本不同',T['context_note'])
        self.assertIn('百分点',T['ts_note'])
        self.assertIn('不含罚球',T['shot_note'])
    def test_unknown_defense_does_not_mean_bad_defense(self):
        p=json.loads((ROOT/'examples/demo_output/poster_content.json').read_text(encoding='utf-8'))
        self.assertIn('还需',p['roles']['defense']['text'])
        self.assertNotIn('防守差',p['roles']['defense']['text'])

if __name__=='__main__':unittest.main()
