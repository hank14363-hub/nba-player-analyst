"""Impact scope, identity, integrity and model-family regression tests."""
import copy, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from common import DataError, digest
from collect_impact import dataset, parse_bref, parse_darko
from impact_metrics import impact_context, register_impact
from impact_visuals import impact_visuals

def fixture():
    rows={'BREF':[dict(provider_player_key='testpl01',name_display='Test Player',team_name_abbr='DET',games='70',mp='2452',bpm='3.9',obpm='3.8',dbpm='0.1',vorp='3.7',ws='5.9',ows='3.0',dws='2.9',ws_per_48='.115')],
          'LEBRON':[{'nba_id':'999001','player_name':'test player','Season':'2024-25','Minutes':2451.95,'LEBRON':1.56,'O-LEBRON':1.67,'D-LEBRON':-.11}],
          'DARKO':[dict(nba_id=999001,player_name='Test Player',season='2024-25',as_of='2025-04-13',dpm='+1.8',o_dpm='+2.3',d_dpm='-0.6')]}
    b=dict(season='2024-25',season_type='Regular Season',sources={},impact_data=dict(schema_version='0.1.0',datasets=[],excluded=[]))
    for f,r in rows.items():
        d,s=dataset(f,r,dict(url='https://example.com/'+f,retrieved_at='2026-10-12T00:00:00+00:00',sha256='0'*64),999001,'Test Player','2024-25','testpl01','2025-04-13' if f=='DARKO' else None)
        b['impact_data']['datasets'].append(d);b['sources'][d['source_id']]=s
    return b

class ImpactTests(unittest.TestCase):
    def setUp(self):self.b=fixture()
    def run_ctx(self):return impact_context(self.b,999001,'Test Player',dict(GP=70,MIN=2452),0)
    def rehash(self,i):
        d=self.b['impact_data']['datasets'][i];self.b['sources'][d['source_id']]['sha256_rows']=digest(d['raw_rows'])
    def test_three_families_separate(self):
        c=self.run_ctx();self.assertEqual(len(c['datasets']),3);self.assertIsNone(c['datasets'][2]['sample']['MIN'])
    def test_optional_absent_backward_compatibility(self):
        self.assertIsNone(impact_context({},999001,'Test Player',{},0))
    def test_wrong_identity(self):
        self.b['impact_data']['datasets'][0]['player_id']=999002
        with self.assertRaises(DataError):self.run_ctx()
    def test_provider_nba_id_wrong(self):
        d=self.b['impact_data']['datasets'][1];d['raw_rows'][0]['nba_id']='999002';d['selector']['nba_id']='999002';self.rehash(1)
        with self.assertRaises(DataError):self.run_ctx()
    def test_name_mapping_wrong(self):
        self.b['impact_data']['datasets'][0]['raw_rows'][0]['name_display']='Other Player';self.rehash(0)
        with self.assertRaises(DataError):self.run_ctx()
    def test_wrong_season(self):
        self.b['impact_data']['datasets'][1]['season']='2025-26'
        with self.assertRaises(DataError):self.run_ctx()
    def test_wrong_competition(self):
        self.b['impact_data']['datasets'][0]['season_type']='Playoffs'
        with self.assertRaises(DataError):self.run_ctx()
    def test_bref_postseason_table(self):
        self.b['sources']['EXT_IMPACT_BREF']['table_id']='advanced_post'
        with self.assertRaises(DataError):self.run_ctx()
    def test_wrong_minutes(self):
        self.b['impact_data']['datasets'][1]['raw_rows'][0]['Minutes']=2699;self.rehash(1)
        with self.assertRaises(DataError):self.run_ctx()
    def test_bref_rounding_allowed(self):
        self.assertAlmostEqual(self.run_ctx()['datasets'][0]['sample']['minutes_difference'],0)
    def test_wrong_gp(self):
        self.b['impact_data']['datasets'][0]['raw_rows'][0]['games']='76';self.rehash(0)
        with self.assertRaises(DataError):self.run_ctx()
    def test_current_date_rejected(self):
        self.b['impact_data']['datasets'][2]['cutoff']='2026-06-03';self.b['sources']['EXT_IMPACT_DARKO']['cutoff']='2026-06-03'
        with self.assertRaises(DataError):self.run_ctx()
    def test_current_raw_date_rejected(self):
        self.b['impact_data']['datasets'][2]['raw_rows'][0]['as_of']='2026-06-03';self.rehash(2)
        with self.assertRaises(DataError):self.run_ctx()
    def test_undated_prediction_rejected(self):
        self.b['impact_data']['datasets'][2]['cutoff']=None;self.b['sources']['EXT_IMPACT_DARKO']['cutoff']=None
        with self.assertRaises(DataError):self.run_ctx()
    def test_model_metadata_conflict(self):
        self.b['sources']['EXT_IMPACT_LEBRON']['model_version']='different revision'
        with self.assertRaises(DataError):self.run_ctx()
    def test_raw_hash_tamper(self):
        self.b['impact_data']['datasets'][0]['raw_rows'][0]['bpm']='9.9'
        with self.assertRaises(DataError):self.run_ctx()
    def test_duplicate_selected_row(self):
        d=self.b['impact_data']['datasets'][0];d['raw_rows']*=2;self.rehash(0)
        with self.assertRaises(DataError):self.run_ctx()
    def test_components_conflict(self):
        self.b['impact_data']['datasets'][1]['raw_rows'][0]['LEBRON']=9;self.rehash(1)
        with self.assertRaises(DataError):self.run_ctx()
    def test_rounded_darko_components_allowed(self):
        self.assertEqual(self.run_ctx()['datasets'][2]['values']['DPM'],1.8)
    def test_missing_not_zero(self):
        self.b['impact_data']['datasets'][0]['raw_rows'][0]['dbpm']='';self.rehash(0)
        self.assertIsNone(self.run_ctx()['datasets'][0]['values']['DBPM'])
    def test_duplicate_family(self):
        self.b['impact_data']['datasets'].append(copy.deepcopy(self.b['impact_data']['datasets'][0]))
        with self.assertRaises(DataError):self.run_ctx()
    def test_rapm_unknown_family_rejected(self):
        self.b['impact_data']['datasets'][0]['family']='RAPM'
        with self.assertRaises(DataError):self.run_ctx()
    def test_team_stint_mismatch(self):
        self.b['impact_data']['datasets'][0]['player_team_id']=1610612765
        with self.assertRaises(DataError):self.run_ctx()
    def test_collection_time_requires_zone(self):
        self.b['sources']['EXT_IMPACT_BREF']['retrieved_at']='2026-10-12'
        with self.assertRaises(DataError):self.run_ctx()
    def test_visual_units_split(self):
        c=self.run_ctx();metrics=[]
        def add(mid,v,unit,sids,formula='',reason=''):metrics.append(dict(metric_id=mid,value=v,unit=unit,status='ok' if v is not None else 'missing',source_ids=sids))
        register_impact(c,add,metrics);a=dict(impact_context=c,metrics=metrics);vs=impact_visuals(a)
        self.assertEqual(len(vs),2);self.assertNotIn('IMPACT_WS',vs['impact_retrospective']['metric_ids']);self.assertEqual(next(m for m in metrics if m['metric_id']=='IMPACT_WS48')['display'],'0.115')
    def test_bref_aggregate_not_stints(self):
        rows=[dict(provider_player_key='testpl01',team_name_abbr=t) for t in ['DET','LAL','2TM']]
        d,_=dataset('BREF',rows,dict(url='https://example.com',retrieved_at='2026-10-12T00:00:00Z',sha256='0'*64),999001,'Test Player','2024-25','testpl01')
        self.assertEqual(d['selector']['team_name_abbr'],'2TM')
    def test_bref_duplicate_aggregates_rejected(self):
        rows=[dict(provider_player_key='testpl01',team_name_abbr=t) for t in ['2TM','TOT']]
        with self.assertRaises(DataError):dataset('BREF',rows,dict(url='https://example.com',retrieved_at='2026-10-12T00:00:00Z',sha256='0'*64),999001,'Test Player','2024-25','testpl01')
    def test_html_bref_selects_regular_only(self):
        try:import bs4
        except ImportError:self.skipTest('Optional bs4 not installed')
        row='<tr><td data-stat="name_display" data-append-csv="testpl01">Test Player</td><td data-stat="bpm">VALUE</td></tr>'
        payload='<table id="advanced"><tbody>'+row.replace('VALUE','3.9')+'</tbody></table><table id="advanced_post"><tbody>'+row.replace('VALUE','99')+'</tbody></table>'
        self.assertEqual(parse_bref(payload)[0]['bpm'],'3.9')
    def test_partial_family_book_no_missing_chart_or_method_link(self):
        from render_research_book import Book
        c=self.run_ctx();c['datasets']=c['datasets'][:1]
        book=Book.__new__(Book);book.a=dict(impact_context=c,sources={});book.metrics={};book.claims={};book.visual_entries={'impact_retrospective':{}}
        book.chart=lambda key:'<figure>'+key+'</figure>' if key in book.visual_entries else self.fail('Attempt to render missing impact chart')
        book.referenced_claims=lambda ids:''
        rendered=book.impacts();self.assertIn('impact_retrospective',rendered);self.assertNotIn('href="#source-EXT_METHOD',rendered)
    def test_darko_visible_history_not_now(self):
        try:import bs4
        except ImportError:self.skipTest('Optional bs4 not installed')
        row='<tr><td><a class="player-link" href="/player/999001?asof=2025-04-13"><span class="player-text"><span>Test Player</span></span></a></td><td class="leaderboard-cell--dpm"><span class="dpm-figure">+1.8</span></td><td class="leaderboard-cell--o-dpm">+2.3</td><td class="leaderboard-cell--d-dpm">-0.6</td><td class="leaderboard-cell--now-dpm">+9.9</td></tr>'
        payload='DARKO as of April 13, 2025 · 2024-25 season<table>'+row+row+'</table>'
        parsed=parse_darko(payload,'2025-04-13','2024-25');self.assertEqual(len(parsed),1);self.assertEqual(parsed[0]['dpm'],'+1.8')
        with self.assertRaises(DataError):parse_darko(payload,'2026-06-03','2024-25')
    def test_darko_conflicting_responsive_rows_rejected(self):
        try:import bs4
        except ImportError:self.skipTest('Optional bs4 not installed')
        row='<tr><td><a class="player-link" href="/player/999001?asof=2025-04-13"><span class="player-text"><span>Test Player</span></span></a></td><td class="leaderboard-cell--dpm">+1.8</td></tr>'
        with self.assertRaises(DataError):parse_darko('DARKO as of April 13, 2025 · 2024-25 season<table>'+row+row.replace('+1.8','+9.9')+'</table>','2025-04-13','2024-25')

if __name__=='__main__':unittest.main()
