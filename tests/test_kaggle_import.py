"""Provider-row fixtures from Kaggle v1; failure tests never become player reports."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError, validate_bundle, write_json
from import_kaggle import build_bundle, validate_import
from calculate_metrics import analyze


class KaggleImportTests(unittest.TestCase):
    def setUp(self):
        self.snapshot=json.loads((ROOT/'tests/fixtures/kaggle_cade.json').read_text(encoding='utf-8'))

    def bundle(self,snapshot=None):
        return build_bundle(snapshot or self.snapshot)[0]

    def metrics(self,b):
        req=dict(player_id=1630595,season='2024-25',season_type='Regular Season',team_id=0)
        return {m['metric_id']:m for m in analyze(b,req)['metrics']}

    def test_real_cade_totals_and_provider_models(self):
        b=self.bundle();m=self.metrics(b)
        self.assertEqual(b['tables']['player_base'][0]['FGA'],1457)
        self.assertEqual(m['GP']['value'],70)
        self.assertAlmostEqual(m['PTS_PER_GAME']['value'],1830/70)
        self.assertEqual(m['IMPACT_BPM']['value'],3.9)

    def test_real_shooting_denominators_and_distance(self):
        m=self.metrics(self.bundle())
        self.assertEqual(m['PCT_AST_2PM']['value'],.228)
        self.assertEqual(m['PCT_AST_3PM']['value'],.57)
        self.assertEqual(m['AVG_SHOT_DISTANCE_FT']['value'],12.6)
        self.assertEqual(m['PCT_AST_FGM']['status'],'missing')
        self.assertEqual(m['PCT_UAST_FGM']['status'],'missing')

    def test_real_onoff_uses_other_court_group(self):
        m=self.metrics(self.bundle())
        self.assertEqual(m['ONOFF_OFF_OFF_RATING']['value'],113.0)
        self.assertEqual(m['ONOFF_ON_DEF_RATING']['value'],114.1)
        self.assertAlmostEqual(m['ON_OFF_DIFFERENTIAL']['value'],3.7)

    def test_individual_bref_ratings_not_oncourt(self):
        b=self.bundle();a=b['tables']['player_advanced'][0]
        self.assertNotIn('OFF_RATING',a)
        self.assertEqual(self.metrics(b)['ONCOURT_OFF_RATING']['status'],'missing')

    def test_onoff_requires_independent_team_baseline(self):
        self.snapshot['reference']=None
        b=self.bundle()
        self.assertNotIn('player_onoff',b['tables'])
        self.assertEqual(self.metrics(b)['ON_OFF_DIFFERENTIAL']['status'],'missing')

    def test_rejects_mismatched_on_minutes_without_losing_base(self):
        for r in self.snapshot['inputs']['onoff']:
            if r['split']=='On Court':r['mp']='2000'
        b,excluded=build_bundle(self.snapshot)
        self.assertNotIn('player_onoff',b['tables'])
        self.assertTrue(any(e['domain']=='player_onoff' for e in excluded))
        self.assertEqual(b['tables']['player_base'][0]['FGA'],1457)

    def test_different_reference_season_rejected(self):
        self.snapshot['reference']['season']='2023-24'
        with self.assertRaises(DataError):self.bundle()

    def test_conflicting_numeric_bridge_rejected(self):
        self.snapshot['inputs']['bridge'].append(dict(br_player_id='cunnica01',nba_player_id='999999',player_name='Cade Cunningham',match_strategy='exact_name'))
        with self.assertRaises(DataError):self.bundle()

    def test_missing_exact_name_bridge_rejected(self):
        self.snapshot['inputs']['bridge']=[r for r in self.snapshot['inputs']['bridge'] if r['match_strategy']!='exact_name']
        with self.assertRaises(DataError):self.bundle()

    def test_forged_per_game_totals_fail_scoring_identity(self):
        self.snapshot['inputs']['season'][0]['pts']='26.1'
        with self.assertRaises(DataError):self.bundle()

    def test_shooting_scope_mismatch_rejected(self):
        self.snapshot['inputs']['shooting'][0]['g']='69'
        with self.assertRaises(DataError):self.bundle()

    def test_fraction_out_of_range_rejected(self):
        self.snapshot['inputs']['shooting'][0]['percent_assisted_x2p_fg']='22.8'
        with self.assertRaises(DataError):self.bundle()

    def test_missing_shooting_remains_missing(self):
        self.snapshot['inputs']['shooting']=[]
        self.assertNotIn('player_scoring',self.bundle()['tables'])

    def test_zero_band_attempts_not_zero_efficiency(self):
        row=self.snapshot['inputs']['shooting'][0]
        row['percent_fga_from_x0_3_range']='0'
        row['fg_percent_from_x0_3_range']='0'
        row['percent_fga_from_x3_10_range']='0.529'
        m=self.metrics(self.bundle())
        self.assertEqual(m['FG_PCT_0_3']['status'],'missing')
        self.assertEqual(m['PCT_FGA_0_3']['value'],0)

    def test_distance_share_inconsistency_rejected(self):
        self.snapshot['inputs']['shooting'][0]['percent_fga_from_x0_3_range']='0.9'
        with self.assertRaises(DataError):self.bundle()

    def test_wrong_dataset_version_rejected(self):
        self.snapshot['dataset_version']=2
        with self.assertRaises(DataError):self.bundle()

    def test_luka_transfer_total_not_double_counted(self):
        snap=json.loads((ROOT/'tests/fixtures/kaggle_luka.json').read_text(encoding='utf-8'))
        b,_=build_bundle(snap);base=b['tables']['player_base'][0]
        self.assertEqual(base['GP'],50)
        self.assertEqual(base['MIN'],1769)
        self.assertEqual(base['TEAM_ID'],0)
        self.assertEqual(base['TEAM_ABBREVIATION'],'2TM')
        self.assertNotIn('player_onoff',b['tables'])

    def test_luka_without_total_refuses_to_add_stints(self):
        snap=json.loads((ROOT/'tests/fixtures/kaggle_luka.json').read_text(encoding='utf-8'))
        snap['inputs']['season']=[r for r in snap['inputs']['season'] if r['team']!='2TM']
        with self.assertRaises(DataError):build_bundle(snap)

    def test_luka_explicit_lakers_stint(self):
        snap=json.loads((ROOT/'tests/fixtures/kaggle_luka.json').read_text(encoding='utf-8'))
        snap['team_id']=1610612747
        b,_=build_bundle(snap)
        self.assertEqual(b['tables']['player_base'][0]['GP'],28)
        self.assertEqual(b['tables']['player_base'][0]['MIN'],984)
        self.assertNotIn('impact_data',b)

    def test_epm_and_shots_never_imported(self):
        b=self.bundle()
        self.assertNotIn('player_shots',b['tables'])
        self.assertEqual([d['family'] for d in b['impact_data']['datasets']],['BREF'])

    def test_converted_table_tampering_rejected(self):
        b=self.bundle();b['kaggle_import']=dict(schema_version='0.1.0',snapshot=self.snapshot)
        validate_bundle(b,'2024-25','Regular Season')
        b['tables']['player_base'][0]['AST']=999
        with self.assertRaises(DataError):validate_bundle(b,'2024-25','Regular Season')

    def test_retained_raw_row_tampering_rejected(self):
        b=self.bundle();b['kaggle_import']=dict(schema_version='0.1.0',snapshot=self.snapshot)
        self.snapshot['inputs']['season'][0]['ast']='999'
        with self.assertRaises(DataError):validate_import(b)

    def test_raw_snapshot_tampering_rejected_by_cli(self):
        b=self.bundle();b['kaggle_import']=dict(schema_version='0.1.0',snapshot=self.snapshot)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'raw').mkdir();write_json(p/'data_bundle.json',b)
            (p/'raw/kaggle_selection.json').write_text('{}',encoding='utf-8')
            result=subprocess.run([sys.executable,str(ROOT/'scripts/run_analysis.py'),'--input',str(p/'data_bundle.json'),
                '--player-id','1630595','--season','2024-25','--out',str(p/'output')],capture_output=True,text=True)
            self.assertEqual(result.returncode,2)
            self.assertIn('raw snapshot differs',result.stderr)
            self.assertFalse((p/'output/analysis.json').exists())


if __name__=='__main__':unittest.main()
