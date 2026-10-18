"""Poster regression tests: themes, chart semantics, evidence integrity, and safety."""
from __future__ import annotations
import copy
import json
import math
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError
from team_themes import select_theme,PALETTES,contrast,foreground,css_vars
from poster_contract import make_template,validate_poster,derived_metrics
from poster_charts import Charts
from render_player_poster import build,Poster,portrait_data
from validate_poster import check
from export_poster import export
from render_research_book import build as build_book
from validate_book import check as check_book

class PosterTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.run=Path(self.tmp.name)/'run';self.run.mkdir()
        for n in ('data_bundle.json','analysis.json','sources.json','report.md','claims.json','book_content.json','poster_content.json'):
            shutil.copy2(ROOT/'examples/demo_output'/n,self.run/n)
        self.a=json.loads((self.run/'analysis.json').read_text(encoding='utf-8'));self.c=json.loads((self.run/'poster_content.json').read_text(encoding='utf-8'))
        self.claims=json.loads((self.run/'claims.json').read_text(encoding='utf-8'));self.book=json.loads((self.run/'book_content.json').read_text(encoding='utf-8'))
        self.t=select_theme(self.a,'LAL')
    def tearDown(self):self.tmp.cleanup()
    def save(self,n,data):(self.run/n).write_text(json.dumps(data,ensure_ascii=False),encoding='utf-8')
    def errors(self):return validate_poster(self.c,self.a,self.claims)
    def poster(self):return Poster(self.a,self.claims,self.book,self.c,self.t)
    def test_complete_example_valid(self):self.assertEqual(self.errors(),[])
    def test_draft_cannot_publish(self):self.assertTrue(validate_poster(make_template(self.a),self.a,self.claims))
    def test_wrong_season_rejected(self):
        self.c['identity']['season']='2023-24';self.assertTrue(self.errors())
    def test_wrong_player_rejected(self):
        self.c['identity']['player_id']=10;self.assertTrue(self.errors())
    def test_wrong_data_kind_rejected(self):
        self.c['data_kind']='nba';self.assertTrue(self.errors())
    def test_unknown_claim_rejected(self):
        self.c['verdict']['claim_ids']=['UNKNOWN'];self.assertTrue(self.errors())
    def test_duplicate_claim_rejected(self):
        self.c['verdict']['claim_ids']=['C01','C01'];self.assertTrue(self.errors())
    def test_numbers_in_editorial_text_rejected(self):
        self.c['verdict']['text']='Rating 99';self.assertTrue(self.errors())
    def test_missing_chart_note_rejected(self):
        del self.c['chart_notes']['creation'];self.assertTrue(self.errors())
    def test_undefined_chart_rejected(self):
        self.c['chart_notes']['radar']=self.c['chart_notes']['creation'];self.assertTrue(self.errors())
    def test_role_without_evidence_rejected(self):
        self.c['roles']['defense']['claim_ids']=[];self.assertTrue(self.errors())
    def test_long_headline_rejected(self):
        self.c['headline']='x'*33;self.assertTrue(self.errors())
    def test_unresolved_team_is_neutral(self):self.assertEqual(select_theme(self.a)['key'],'NEUTRAL')
    def test_auto_player_team_not_destination(self):
        self.a['player']['reported_team_id']=1610612747;self.a['target_team']['id']=1610612750
        self.assertEqual(select_theme(self.a)['key'],'LAL')
    def test_scoped_team_priority(self):
        self.a['sample']['player_team_id']=1610612750;self.a['player']['reported_team_id']=1610612747
        self.assertEqual(select_theme(self.a)['key'],'MIN')
    def test_explicit_team_palette(self):self.assertEqual(select_theme(self.a,'MIN')['accent'],'#A8E348')
    def test_all_thirty_palettes_pass_contrast(self):
        self.assertEqual(len(PALETTES),31)
        for name in PALETTES:
            t=select_theme(self.a,name)
            self.assertGreaterEqual(contrast(t['accent'],t['panel']),4.5,name)
            self.assertGreaterEqual(contrast(t['on_primary'],t['primary']),4.5,name)
    def test_hex_css_injection_rejected(self):
        with self.assertRaises(DataError):select_theme(self.a,'LAL',{'primary':'red;display:none','accent':'#FFFFFF'})
    def test_low_contrast_accent_rejected(self):
        with self.assertRaises(DataError):select_theme(self.a,'LAL',{'primary':'#444444','accent':'#222222'})
    def test_unknown_theme_rejected(self):
        with self.assertRaises(DataError):select_theme(self.a,'FAKE')
    def test_custom_theme_extra_css_rejected(self):
        with self.assertRaises(DataError):select_theme(self.a,'LAL',{'primary':'#442288','accent':'#FFFFFF','background':'x'})
    def test_custom_theme_valid(self):
        self.assertEqual(select_theme(self.a,'LAL',{'primary':'#223344','accent':'#FFDD88'})['accent'],'#FFDD88')
    def test_theme_does_not_mutate_player_identity(self):
        before=copy.deepcopy(self.a);select_theme(self.a,'LAL');self.assertEqual(before,self.a)
    def test_all_six_charts_present(self):
        c=self.poster().charts;self.assertEqual(len(c),6);self.assertTrue(all(v['status']=='ok' for v in c.values()))
    def test_score_shares_correct(self):
        d={m['metric_id']:m for m in derived_metrics(self.a)}
        self.assertAlmostEqual(d['V_PTS_2P_SHARE']['value'],600/1400)
        self.assertAlmostEqual(d['V_PTS_3P_SHARE']['value'],540/1400)
        self.assertAlmostEqual(d['V_PTS_FT_SHARE']['value'],260/1400)
    def test_attempt_share_not_score_share(self):
        d={m['metric_id']:m for m in derived_metrics(self.a)}
        self.assertNotEqual(d['V_FG2A_RATE']['value'],d['V_PTS_2P_SHARE']['value'])
    def test_invalid_points_identity_rejected(self):
        self.a['selected_rows']['player_base']['PTS']=1401
        with self.assertRaises(DataError):derived_metrics(self.a)
    def test_scoring_missing_no_fake_zero(self):
        del self.a['selected_rows']['player_base']['FTM']
        c=self.poster().charts['scoring_mix'];self.assertEqual(c['status'],'missing');self.assertIsNone(c['svg'])
    def test_missing_advanced_is_missing_chart(self):
        for m in self.a['metrics']:
            if m['metric_id']=='ONCOURT_DEF_RATING':m.update(status='missing',value=None)
        self.assertIsNone(self.poster().charts['team_context']['svg'])
    def test_missing_chart_hides_assertive_takeaway(self):
        for m in self.a['metrics']:
            if m['metric_id']=='AST_PER75':m.update(status='missing',value=None)
        output=self.poster().figure('creation');self.assertNotIn(self.c['chart_notes']['creation']['takeaway'],output)
    def test_nonfinite_metric_rejected(self):
        for m in self.a['metrics']:
            if m['metric_id']=='TS_PCT':m['value']=float('nan')
        with self.assertRaises(DataError):self.poster()
    def test_share_sum_inconsistent_rejected(self):
        for m in self.a['metrics']:
            if m['metric_id']=='PCT_UAST_FGM':m['value']=.8
        with self.assertRaises(DataError):self.poster()
    def test_ts_above_one_not_clipped(self):
        for m in self.a['metrics']:
            if m['metric_id']=='TS_PCT':m['value']=1.1
        svg=self.poster().charts['efficiency']['svg'];self.assertIn('110.0%',svg);self.assertIn('125%',svg)
    def test_synthetic_label_in_each_svg(self):
        for c in self.poster().charts.values():self.assertIn('SYNTHETIC TEST DATA',c['svg'])
    def test_svg_includes_source_and_season(self):
        for c in self.poster().charts.values():
            self.assertIn('2024-25',c['svg']);self.assertTrue(any(s in c['svg'] for s in c['source_ids']))
    def test_no_empty_radar_or_fake_rank(self):
        self.assertNotIn('radar',self.poster().charts);self.assertNotIn('rank',self.poster().charts)
    def test_renderer_escapes_editorial_html(self):
        self.c['headline']='<script>alert(x)</script>'
        h=self.poster().render();self.assertIn('&lt;script&gt;',h);self.assertNotIn('<script>alert(x)</script>',h)
    def test_portrait_rights_required(self):
        self.c['portrait']={'path':'photo.png','credit':'User','rights_confirmed':False};self.assertTrue(self.errors())
    def test_portrait_absolute_path_rejected(self):
        self.c['portrait']={'path':'/tmp/a.png','credit':'User','rights_confirmed':True};self.assertTrue(self.errors())
    def test_portrait_traversal_rejected(self):
        self.c['portrait']={'path':'../a.png','credit':'User','rights_confirmed':True};self.assertTrue(self.errors())
    def test_portrait_svg_rejected(self):
        (self.run/'portrait.svg').write_text('<svg></svg>')
        with self.assertRaises(DataError):portrait_data(self.run,{'path':'portrait.svg'})
    def test_portrait_local_png_embedded(self):
        # Small test signature, no external asset fetch; browser validation is separate.
        (self.run/'portrait.png').write_bytes(b'\x89PNG\r\n\x1a\n'+b'test')
        self.assertTrue(portrait_data(self.run,{'path':'portrait.png'}).startswith('data:image/png;base64,'))
    def test_build_and_validate_end_to_end(self):
        build(self.run,'LAL');self.assertEqual(check(self.run)['status'],'pass')
    def test_existing_output_protection(self):
        build(self.run,'LAL')
        with self.assertRaises(DataError):build(self.run,'LAL')
    def test_forced_theme_switch_preserves_data(self):
        before=(self.run/'analysis.json').read_bytes();build(self.run,'LAL');build(self.run,'MIN',force=True)
        self.assertEqual(check(self.run)['status'],'pass');self.assertEqual(before,(self.run/'analysis.json').read_bytes())
    def test_html_edit_detected(self):
        build(self.run,'LAL');p=self.run/'player_poster.html';p.write_text(p.read_text(encoding='utf-8')+'edited',encoding='utf-8')
        self.assertEqual(check(self.run)['status'],'fail')
    def test_chart_edit_detected(self):
        build(self.run,'LAL');p=self.run/'poster_charts/efficiency.svg';p.write_text('<svg/>')
        self.assertEqual(check(self.run)['status'],'fail')
    def test_changed_metric_detected(self):
        build(self.run,'LAL');self.a['metrics'][0]['value']=61;self.save('analysis.json',self.a)
        with self.assertRaises(DataError):check(self.run)
    def test_derived_file_edit_detected(self):
        build(self.run,'LAL');p=self.run/'poster_metrics.json';x=json.loads(p.read_text(encoding='utf-8'));x['derived_metrics'][0]['value']=.99;self.save('poster_metrics.json',x)
        self.assertEqual(check(self.run)['status'],'fail')
    def test_manifest_path_escape_detected(self):
        build(self.run,'LAL');p=self.run/'poster_manifest.json';x=json.loads(p.read_text(encoding='utf-8'));x['sha256']['../outside']='x';self.save('poster_manifest.json',x)
        self.assertEqual(check(self.run)['status'],'fail')
    def test_theme_injection_manifest_detected(self):
        build(self.run,'LAL');p=self.run/'poster_manifest.json';x=json.loads(p.read_text(encoding='utf-8'));x['theme']['panel']='red;display:none';self.save('poster_manifest.json',x)
        self.assertEqual(check(self.run)['status'],'fail')
    def test_theme_book_back_compat(self):
        build_book(self.run,theme='MIN');self.assertEqual(check_book(self.run)['status'],'pass')
    def test_unknown_export_extension(self):
        with self.assertRaises(DataError):export(self.run,self.run/'x.html')
    def test_invalid_export_width(self):
        with self.assertRaises(DataError):export(self.run,self.run/'x.png',width=10)

if __name__=='__main__':unittest.main()
