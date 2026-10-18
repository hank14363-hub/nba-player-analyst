import copy
import sys
import tempfile
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError, digest, read_json, write_json
from shot_charts import shot_context, shot_visuals
from film_evidence import template, validate_film, load_registered_film
from fetch_data import Fetcher, FetchError
from repair_data import repair
from calculate_metrics import analyze
from book_contract import load_context
from team_themes import select_theme
from validate_report import validate
from render_shot_charts import render
from run_analysis import parser, run


class ShotValidation(unittest.TestCase):
    def setUp(self):
        self.b=read_json(ROOT/'examples/demo_bundle.json')
        self.base=self.b['tables']['player_base'][0]
        self.pid=self.base['PLAYER_ID']
        self.base.update(FGA=3, FGM=2, FG3A=1, FG3M=1, GP=4)
        rows=[]
        for i,(made,kind,zone,y) in enumerate([(1,'2PT Field Goal','Restricted Area',3),
                  (0,'2PT Field Goal','Mid-Range',150),(1,'3PT Field Goal','Backcourt',749)]):
            rows.append(dict(PLAYER_ID=self.pid,TEAM_ID=self.base['TEAM_ID'],GAME_ID='0022400001',
               GAME_EVENT_ID=i+1,SHOT_ATTEMPTED_FLAG=1,SHOT_MADE_FLAG=made,SHOT_TYPE=kind,SHOT_ZONE_BASIC=zone,
               LOC_X=0,LOC_Y=y,GAME_DATE='20241025',PERIOD=4,MINUTES_REMAINING=0,SECONDS_REMAINING=1))
        self.b['tables']['player_shots']=rows
        self.b['sources']['P_SHOT']=dict(self.b['sources']['P_BASE'],per_mode='Events',player_id=self.pid,
            player_team_id=0,coordinate_units='tenths_of_foot',context_measure='FGA')

    def context(self):
        return shot_context(self.b,self.base,self.pid,0)

    def test_complete_counts_but_zero_fga_appearance_is_allowed(self):
        self.assertEqual(self.context()['shot_games'],1)
        self.assertEqual(self.context()['appearance_games'],4)

    def test_event_loss_rejected(self):
        self.b['tables']['player_shots'].pop()
        with self.assertRaises(DataError):self.context()

    def test_made_count_mismatch_rejected(self):
        self.b['tables']['player_shots'][0]['SHOT_MADE_FLAG']=0
        with self.assertRaises(DataError):self.context()

    def test_duplicate_event_rejected(self):
        self.b['tables']['player_shots'][1]['GAME_EVENT_ID']=1
        with self.assertRaises(DataError):self.context()

    def test_foreign_player_rejected(self):
        self.b['tables']['player_shots'][0]['PLAYER_ID']=self.pid+1
        with self.assertRaises(DataError):self.context()

    def test_foreign_season_rejected(self):
        self.b['tables']['player_shots'][0]['GAME_ID']='0022300001'
        with self.assertRaises(DataError):self.context()

    def test_playoffs_mixing_rejected(self):
        self.b['tables']['player_shots'][0]['GAME_ID']='0042400001'
        with self.assertRaises(DataError):self.context()

    def test_undocumented_units_rejected(self):
        self.b['sources']['P_SHOT']['coordinate_units']='pixels'
        with self.assertRaises(DataError):self.context()

    def test_bad_coordinate_rejected_without_clipping(self):
        self.b['tables']['player_shots'][0]['LOC_Y']=999
        with self.assertRaises(DataError):self.context()

    def test_blank_zone_has_no_rate(self):
        self.assertIsNone(next(z for z in self.context()['zones'] if z['code']=='LC3')['fg_pct'])

    def test_official_label_conflict_is_preserved_in_separate_bucket(self):
        self.b['tables']['player_shots'][0]['SHOT_ZONE_BASIC']='Above the Break 3'
        c=self.context()
        self.assertEqual(len(c['anomalies']),1)
        self.assertEqual(next(z for z in c['zones'] if z['code']=='UNRESOLVED')['fga'],1)
        self.assertEqual(self.b['tables']['player_shots'][0]['SHOT_ZONE_BASIC'],'Above the Break 3')

    def test_backcourt_shot_preserved_in_full_court_svg(self):
        a=analyze(read_json(ROOT/'examples/demo_bundle.json'),dict(player='MVP Demo Guard',season='2024-25',season_type='Regular Season',team_id=0))
        a['shot_context']=self.context()
        svg=shot_visuals(a,select_theme(a))['shot_locations']['svg']
        self.assertIn('472.810',svg)
        self.assertIn('SYNTHETIC TEST DATA',svg)

    def test_standalone_figures_require_no_finished_article(self):
        self.base.update(PTS=6,FTM=1,FTA=2,MIN=40)
        a=analyze(self.b,dict(player_id=self.pid,season='2024-25',season_type='Regular Season',team_id=0))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            write_json(root/'evidence'/'analysis.json',a)
            write_json(root/'evidence'/'data_bundle.json',self.b)
            result=render(root/'evidence',root/'figures')
            self.assertEqual(result['coverage']['FGA'],3)
            self.assertTrue((root/'figures'/'shot_locations.svg').is_file())
            self.assertFalse((root/'evidence'/'report.md').exists())

    def test_standalone_rejects_hand_edited_coordinates(self):
        self.base.update(PTS=6,FTM=1,FTA=2,MIN=40)
        a=analyze(self.b,dict(player_id=self.pid,season='2024-25',season_type='Regular Season',team_id=0))
        a['shot_context']['points'][0]['x']=99
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            write_json(root/'evidence'/'analysis.json',a)
            write_json(root/'evidence'/'data_bundle.json',self.b)
            with self.assertRaises(DataError):render(root/'evidence',root/'figures')


class Recovery(unittest.TestCase):
    def setUp(self):
        self.b=read_json(ROOT/'examples/demo_bundle.json')
        self.b['data_kind']='nba' # Adapter contract tests use explicitly mocked transport only.
        self.rows=self.b['tables']['player_scoring']
        self.b['tables']['player_scoring']=[]
        self.b['sources']['P_SCORE']=dict(status='missing')
        self.calls=[]
    def transport(self,module,cls,params,timeout):
        self.calls.append(module)
        headers=list(self.rows[0])
        return dict(resultSets=[dict(name=cls,headers=headers,rowSet=[[r[k] for k in headers] for r in self.rows])]),params
    def test_only_selected_endpoint_called_and_other_sources_unchanged(self):
        before=copy.deepcopy(self.b)
        with tempfile.TemporaryDirectory() as temp:
            updated,log=repair(self.b,['player_scoring'],Fetcher(Path(temp),transport=self.transport,sleep=lambda _:None))
        self.assertEqual(self.calls,['leaguedashplayerstats'])
        self.assertEqual(log['events'][0]['status'],'repaired')
        self.assertEqual(updated['sources']['P_BASE'],before['sources']['P_BASE'])
        self.assertEqual(updated['tables']['team_base'],before['tables']['team_base'])
        self.assertEqual(self.b,before)
    def test_failure_preserves_original_source_and_rows(self):
        def failed(*args):raise TimeoutError()
        with tempfile.TemporaryDirectory() as temp:
            updated,log=repair(self.b,['player_scoring'],Fetcher(Path(temp),retries=0,transport=failed,sleep=lambda _:None))
        self.assertEqual(updated,self.b)
        self.assertEqual(log['events'][0]['status'],'failed')
    def test_healthy_replacement_requires_explicit_option(self):
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(DataError):repair(self.b,['player_base'],Fetcher(Path(temp),transport=self.transport))
    def test_synthetic_bundle_never_merges_live(self):
        self.b['data_kind']='synthetic'
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(DataError):repair(self.b,['player_scoring'],Fetcher(Path(temp),transport=self.transport))
    def test_shot_fetch_cache_offline_preserves_retrieval_date(self):
        calls=[]
        def transport(module,cls,params,timeout):
            calls.append(params)
            return dict(resultSets=[dict(name='Shot_Chart_Detail',headers=['PLAYER_ID'],rowSet=[[1]])]),dict(ContextMeasure='FGA')
        with tempfile.TemporaryDirectory() as temp:
            rows,s=Fetcher(Path(temp),transport=transport,sleep=lambda _:None).shots('2024-25','Regular Season',1)
            rows2,s2=Fetcher(Path(temp),offline=True,transport=transport).shots('2024-25','Regular Season',1)
            self.assertEqual(len(calls),1)
            self.assertEqual(calls[0]['context_measure_simple'],'FGA')
            self.assertEqual(s['retrieved_at'],s2['retrieved_at'])
            self.assertTrue(s2['from_cache'])
    def test_shot_fetch_403_stops(self):
        class E(Exception):response=type('Response',(),{'status_code':403})()
        calls=[]
        def transport(*args):calls.append(1);raise E()
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(FetchError):Fetcher(Path(temp),transport=transport,sleep=lambda _:None).shots('2024-25','Regular Season',1)
        self.assertEqual(len(calls),1)
    def test_import_shots_option_is_not_silently_ignored(self):
        args=parser().parse_args(['--input','unused.json','--player-id','1','--season','2024-25','--shots'])
        with self.assertRaisesRegex(DataError,'repair_data'):run(args)
    def test_import_tracking_option_is_not_silently_ignored(self):
        args=parser().parse_args(['--input','unused.json','--player-id','1','--season','2024-25','--tracking'])
        with self.assertRaisesRegex(DataError,'repair_data'):run(args)


class FilmValidation(unittest.TestCase):
    def setUp(self):
        self.a=analyze(read_json(ROOT/'examples/demo_bundle.json'),dict(player='MVP Demo Guard',season='2024-25',season_type='Regular Season',team_id=0))
        self.f=template(self.a)
        self.f['observations']=[dict(id='O01',game_id='0022400001',game_date='2024-10-25',period=1,game_clock='10:45',
            video_url='https://example.com/synthetic-film-fixture',video_timecode='00:15:07',observer='Synthetic test fixture',
            observation='Synthetic observation',alternative_explanation='Synthetic alternative',selection_basis='Synthetic test only',
            observed_at='2024-11-01T10:00:00+00:00',evidence_kind='user_reported',outcome='failure')]
    def test_empty_template_is_valid_without_claiming_observation(self):
        self.assertEqual(validate_film(template(self.a),self.a),{})
    def test_structured_record_accepted(self):
        self.assertEqual(list(validate_film(self.f,self.a)),['O01'])
    def test_impossible_game_clock_rejected(self):
        self.f['observations'][0]['game_clock']='13:00'
        with self.assertRaises(DataError):validate_film(self.f,self.a)
    def test_video_clock_and_game_clock_are_not_interchangeable(self):
        self.f['observations'][0]['video_timecode']='10:45'
        with self.assertRaises(DataError):validate_film(self.f,self.a)
    def test_overtime_clock_rejected(self):
        self.f['observations'][0].update(period=5,game_clock='06:00')
        with self.assertRaises(DataError):validate_film(self.f,self.a)
    def test_foreign_sample_rejected(self):
        self.f['identity']['season']='2023-24'
        with self.assertRaises(DataError):validate_film(self.f,self.a)
    def test_missing_observer_not_allowed(self):
        del self.f['observations'][0]['observer']
        with self.assertRaises(DataError):validate_film(self.f,self.a)
    def test_duplicate_observation_rejected(self):
        self.f['observations'].append(copy.deepcopy(self.f['observations'][0]))
        with self.assertRaises(DataError):validate_film(self.f,self.a)
    def test_unsafe_video_link_rejected(self):
        self.f['observations'][0]['video_url']='javascript:alert(1)'
        with self.assertRaises(DataError):validate_film(self.f,self.a)
    def test_unlocated_film_claim_fails(self):
        self.a['sources']['FILM']=dict(status='ok')
        c=dict(schema_version='0.1.0',data_kind='synthetic',claims=[dict(id='C1',kind='observation',report_quote='观察',metric_ids=[],source_ids=['FILM'],confidence='low',caveats=['synthetic'],observation_reference='O99',observation_ids=['O99'])])
        r=validate('SYNTHETIC\n## a\n## b\n## c\n## d\n观察[FILM]',c,self.a,0,validate_film(self.f,self.a))
        self.assertTrue(any('observation_ids' in e for e in r['errors']))
