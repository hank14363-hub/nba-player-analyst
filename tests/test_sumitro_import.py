"""Real v56 retained rows; mutations only exercise rejection paths."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError, validate_bundle
from import_sumitro import build, payload, comparison_context
from calculate_metrics import analyze
from comparison_visuals import comparison_visuals


class SumitroTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.original=json.loads((ROOT/'examples/sumitro-cade-2024-25/data_bundle.json').read_text(encoding='utf-8'))

    def setUp(self):self.s=copy.deepcopy(self.original['sumitro_import']['snapshot'])

    def bundle(self):
        self.s['snapshot_sha256']=hashlib.sha256(payload(self.s)).hexdigest()
        b,_=build(self.s);b['sumitro_import']=dict(schema_version='0.1.0',snapshot=self.s)
        return b

    def metrics(self,b=None):
        a=analyze(b or self.bundle(),dict(player_id=self.s['player_id'],season=self.s['season'],season_type='Regular Season',team_id=self.s['team_id'],comparisons=True))
        return a,{m['metric_id']:m for m in a['metrics']}

    def target(self,kind):return next(r for r in self.s['inputs'][kind] if r['player_id']==self.s['bref_key'] and r['team']=='DET')

    def test_real_totals(self):
        a,m=self.metrics();self.assertEqual(m['GP']['value'],70);self.assertEqual(m['FGA']['value'],1457);self.assertAlmostEqual(m['PTS_PER_GAME']['value'],1830/70)

    def test_real_shooting_denominators(self):
        _,m=self.metrics();self.assertEqual(m['PCT_AST_2PM']['value'],.228);self.assertEqual(m['PCT_AST_3PM']['value'],.57);self.assertEqual(m['AVG_SHOT_DISTANCE_FT']['value'],12.6);self.assertEqual(m['PCT_AST_FGM']['status'],'missing')

    def test_real_pbp(self):
        _,m=self.metrics();self.assertEqual(m['BR_BAD_PASS_TOV']['value'],173);self.assertEqual(m['BR_LOST_BALL_TOV']['value'],105);self.assertEqual(m['BR_TOV_TWO_TYPE_RESIDUAL']['value'],31);self.assertEqual(m['BR_ASSIST_GENERATED_POINTS']['value'],1511)

    def test_real_models(self):
        _,m=self.metrics();self.assertEqual(m['IMPACT_BPM']['value'],3.9);self.assertEqual(m['IMPACT_VORP']['value'],3.7)

    def test_team_minutes_and_coverage(self):
        b=self.bundle();rows=b['tables']['team_base'];self.assertEqual(len(rows),30);self.assertEqual(next(r['MIN'] for r in rows if r['TEAM_ID']==1610612765),3961);self.assertEqual(b['sources']['T_BASE']['league_average_rows_excluded'],1)

    def test_true_league_baseline_available(self):
        _,m=self.metrics();self.assertEqual(m['RTS_PP']['status'],'ok')

    def test_actual_cohort(self):
        a,m=self.metrics();c=a['comparison_context'];self.assertEqual(c['status'],'ok');self.assertEqual(c['raw_player_count'],569);self.assertEqual(c['eligible_count'],266);self.assertEqual(len(c['axes']),5);self.assertEqual(c['target_id'],'cunnica01');self.assertNotIn('NBA_PIE',m);self.assertNotIn('PCT_UAST_FGM',[r['metric_id'] for r in c['axes']])

    def test_radar_five_axis_geometry(self):
        a,_=self.metrics();svg=comparison_visuals(a,{})['role_profile']['svg'];tree=ET.fromstring(svg);p=tree.find('{http://www.w3.org/2000/svg}polygon');self.assertEqual(len(p.attrib['points'].split()),5)

    def test_wrong_numeric_identity(self):
        self.s['player_id']=1629029
        with self.assertRaises(DataError):self.bundle()

    def test_synthetic_identity(self):
        self.s['identity']['data_kind']='synthetic'
        with self.assertRaises(DataError):self.bundle()

    def test_identity_other_season(self):
        self.s['identity']['source']['season']='2023-24'
        with self.assertRaises(DataError):self.bundle()

    def test_identity_hash_modified(self):
        self.s['identity']['rows'][0]['PLAYER_NAME']='Altered'
        with self.assertRaises(DataError):self.bundle()

    def test_version_not_reviewed(self):
        self.s['dataset_version']=57
        with self.assertRaises(DataError):self.bundle()

    def test_old_scope(self):
        self.s['season']='2010-11'
        with self.assertRaises(DataError):self.bundle()

    def test_cross_table_minutes(self):
        self.target('shooting')['mp']='2000'
        with self.assertRaises(DataError):self.bundle()

    def test_scoring_identity(self):
        self.target('totals')['pts']='26'
        with self.assertRaises(DataError):self.bundle()

    def test_pbp_wrong_name(self):
        self.target('pbp')['player']='Different Player'
        with self.assertRaises(DataError):self.bundle()

    def test_negative_residual(self):
        self.target('pbp')['bad_pass_turnover']='400'
        with self.assertRaises(DataError):self.bundle()

    def test_missing_pbp(self):
        self.s['inputs']['pbp']=[];_,m=self.metrics();self.assertNotIn('BR_BAD_PASS_TOV',m)

    def test_na_not_zero(self):
        self.target('pbp')['lost_ball_turnover']='NA';_,m=self.metrics();self.assertEqual(m['BR_LOST_BALL_TOV']['status'],'missing');self.assertEqual(m['BR_TOV_TWO_TYPE_RESIDUAL']['status'],'missing')

    def test_missing_shooting(self):
        self.s['inputs']['shooting']=[];self.assertNotIn('player_scoring',self.bundle()['tables'])

    def test_partial_cohort_rejected(self):
        self.s['inputs']['per100'].pop();a,_=self.metrics();self.assertEqual(a['comparison_context']['status'],'missing')

    def test_raw_snapshot_tamper(self):
        b=self.bundle();b['sumitro_import']['snapshot']['inputs']['totals'][0]['pts']='0'
        with self.assertRaises(DataError):validate_bundle(b,'2024-25','Regular Season',0)

    def test_converted_tamper(self):
        b=self.bundle();b['sumitro_pbp']['BR_BAD_PASS_TOV']=0
        with self.assertRaises(DataError):validate_bundle(b,'2024-25','Regular Season',0)

    def test_source_tamper(self):
        b=self.bundle();b['sources']['P_BASE']['provider']='NBA Stats'
        with self.assertRaises(DataError):validate_bundle(b,'2024-25','Regular Season',0)

    def test_luka_total_not_stints_added(self):
        self.s.update(player_id=1629029,bref_key='doncilu01');b=self.bundle();r=b['tables']['player_base'][0];self.assertEqual(r['GP'],50);self.assertEqual(r['MIN'],1769);self.assertEqual(r['TEAM_ID'],0)

    def test_luka_lal_stint_no_full_model_or_cohort(self):
        self.s.update(player_id=1629029,bref_key='doncilu01',team_id=1610612747);b=self.bundle();self.assertEqual(b['tables']['player_base'][0]['GP'],28);self.assertEqual(b['tables']['player_base'][0]['MIN'],984);self.assertNotIn('impact_data',b);a,_=self.metrics(b);self.assertEqual(a['comparison_context']['status'],'missing')

    def test_no_fabricated_missing_domains(self):
        b=self.bundle();_,m=self.metrics(b);self.assertNotIn('player_shots',b['tables']);self.assertNotIn('player_onoff',b['tables']);self.assertEqual(m['ON_OFF_DIFFERENTIAL']['status'],'missing');self.assertNotIn('OFF_RATING',b['tables']['player_advanced'][0])

if __name__=='__main__':unittest.main()
