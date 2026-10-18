"""Missing spatial fields are distinct from missing events; photo fallback is auditable."""
from pathlib import Path
from copy import deepcopy
import sys,tempfile,unittest
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import test_v05
from common import DataError,write_json
from shot_charts import shot_context,shot_visuals
from book_shot_explorer import explorer_rows,render_explorer
from comparison_visuals import density
from media_research import audit

class SpatialRecovery(unittest.TestCase):
    setUp=test_v05.ShotValidation.setUp
    def context(self):return shot_context(self.b,self.base,self.pid,0,allow_partial=True)
    def a(self):return dict(shot_context=self.context(),data_kind='synthetic',sample=dict(season='2024-25'),sources=self.b['sources'])
    def test_null_zone_not_a_whole_table_failure(self):
        self.b['tables']['player_shots'][0]['SHOT_ZONE_BASIC']=None
        c=self.context();self.assertEqual(c['counts']['FGA'],3);self.assertEqual(len(c['points']),3)
        self.assertEqual(next(z for z in c['zones'] if z['code']=='MISSING')['fga'],1)
        self.assertAlmostEqual(sum(z['share'] for z in c['zones']),1)
    def test_null_coordinates_not_fabricated(self):
        self.b['tables']['player_shots'][0].update(LOC_X=None,LOC_Y=None)
        c=self.context();self.assertEqual((c['counts']['FGA'],len(c['points']),c['missing_location_count']),(3,2,1))
        self.assertEqual(c['missing_locations'][0]['original_x'],None)
        self.assertEqual(sum(z['fga'] for z in c['zones']),3)
    def test_one_coordinate_missing_is_excluded(self):
        self.b['tables']['player_shots'][0]['LOC_X']=None
        self.assertEqual(self.context()['location_count'],2)
    def test_zero_is_real_coordinate(self):
        self.b['tables']['player_shots'][0].update(LOC_X=0,LOC_Y=0)
        self.assertEqual(self.context()['location_count'],3)
    def test_unknown_nonempty_zone_still_rejected(self):
        self.b['tables']['player_shots'][0]['SHOT_ZONE_BASIC']='new provider schema'
        with self.assertRaises(DataError):self.context()
    def test_missing_coordinate_does_not_hide_other_invalid_coordinate(self):
        self.b['tables']['player_shots'][0].update(LOC_X=None,LOC_Y=999)
        with self.assertRaises(DataError):self.context()
    def test_incomplete_events_still_rejected(self):
        self.b['tables']['player_shots'].pop()
        with self.assertRaises(DataError):self.context()
    def test_legacy_mode_retains_old_rejection(self):
        self.b['tables']['player_shots'][0]['SHOT_ZONE_BASIC']=None
        with self.assertRaises(DataError):shot_context(self.b,self.base,self.pid,0)
    def test_partial_plot_counts_not_season_counts(self):
        self.b['tables']['player_shots'][0].update(LOC_X=None,LOC_Y=None)
        a=self.a();vis=shot_visuals(a,dict(primary='#333'))
        self.assertIn('部分覆盖',vis['shot_locations']['title'])
        self.assertIn('缺坐标 1 次',vis['shot_locations']['svg'])
        self.assertIn('出手 2 ',vis['shot_locations']['svg'])
        self.assertIn('缺坐标1次',density(a)['note'])
    def test_no_coordinates_preserves_zone_plot(self):
        for r in self.b['tables']['player_shots']:r.update(LOC_X=None,LOC_Y=None)
        vis=shot_visuals(self.a(),dict(primary='#333'))
        self.assertEqual(vis['shot_locations']['status'],'missing');self.assertEqual(vis['shot_zones']['status'],'ok')
    def test_explorer_subset_disclosure_and_missing_details(self):
        self.b['tables']['player_shots'][0].update(LOC_X=None,LOC_Y=None,SHOT_ZONE_BASIC=None)
        a=self.a();rows=explorer_rows(self.b,a);self.assertEqual(len(rows),2)
        chart=shot_visuals(a,dict(primary='#333'))['shot_locations']['svg']
        html=render_explorer(rows,chart,a['shot_context'])
        self.assertIn('2 / 3',html);self.assertIn('data-partial-locations="true"',html)
        self.assertIn('事件 1',html);self.assertIn('有坐标出手',html)
    def test_explorer_cannot_silently_drop_event(self):
        a=self.a();a['shot_context']['points'].pop()
        with self.assertRaises(DataError):explorer_rows(self.b,a)
    def test_missing_zone_with_coords_interactive_bucket(self):
        self.b['tables']['player_shots'][0]['SHOT_ZONE_BASIC']=None
        rows=explorer_rows(self.b,self.a());self.assertEqual(rows[0]['zone'],'MISSING')
    def test_all_backcourt_preserves_outside_count(self):
        for r in self.b['tables']['player_shots']:r['LOC_Y']=749
        chart=density(self.a())
        self.assertEqual(chart['status'],'ok');self.assertIn('视窗外 3 次',chart['svg'])
    def test_zone_only_standalone_export(self):
        from calculate_metrics import analyze
        from render_shot_charts import render
        self.base.update(PTS=6,FTM=1,FTA=2,MIN=40)
        for r in self.b['tables']['player_shots']:r.update(LOC_X=None,LOC_Y=None)
        a=analyze(self.b,dict(player_id=self.pid,season='2024-25',season_type='Regular Season',team_id=0,partial_shot_locations=True))
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp);write_json(root/'run/analysis.json',a);write_json(root/'run/data_bundle.json',self.b)
            result=render(root/'run',root/'charts')
            self.assertEqual(result['spatial_coverage']['location_count'],0)
            self.assertFalse((root/'charts/shot_locations.svg').exists())
            self.assertTrue((root/'charts/shot_zones.svg').is_file())
    def test_repair_accepts_complete_events_with_missing_spatial_fields(self):
        from repair_data import repair
        b=deepcopy(self.b);b['data_kind']='nba'
        rows=b['tables'].pop('player_shots');source=b['sources'].pop('P_SHOT')
        rows[0].update(LOC_X=None,LOC_Y=None,SHOT_ZONE_BASIC=None)
        result,log=repair(b,['player_shots'],SimpleNamespace(shots=lambda *args:(rows,source)),player_id=self.pid)
        self.assertEqual(log['events'][0]['status'],'repaired')
        self.assertEqual(result['sources']['P_SHOT']['spatial_coverage']['missing_location_count'],1)
        self.assertIsNone(result['tables']['player_shots'][0]['LOC_X'])

class PhotoRecovery(unittest.TestCase):
    def setUp(self):
        self.a=dict(player=dict(id=123),sample=dict(season='2024-25',season_type='Regular Season'),
            data_kind='nba',request=dict(media_research_audit=True),sources={})
        self.record=dict(identity=dict(player_id=123,season='2024-25',season_type='Regular Season'),
            status='limited',reason='download rejected',queries=[],candidates=[dict(page_url='https://example.com/photo1',
            accessed_at='2026-10-18T01:00:00+00:00',decision='not_downloaded',reason='HTTP 403')])
    def check(self,record):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            if record is not None:write_json(p/'media_research.json',record)
            return audit(p,self.a)
    def codes(self,result):return [f['code'] for f in result['findings']]
    def test_one_failed_image_requires_fallback(self):
        self.assertIn('media_fallback_not_attempted',self.codes(self.check(self.record)))
    def test_retrying_same_candidate_is_not_independent_fallback(self):
        self.record['candidates']*=2
        self.assertIn('media_fallback_not_attempted',self.codes(self.check(self.record)))
    def test_independent_candidates_and_actual_stop_reason(self):
        self.record['candidates'].append(dict(self.record['candidates'][0],page_url='https://elsewhere.example/photo2',reason='license unclear'))
        self.record['stop_reason']='Both available independent origins were checked; no embeddable asset confirmed.'
        self.assertEqual(self.check(self.record)['status'],'pass')
    def test_complete_without_adopted_asset_fails(self):
        self.record['status']='complete'
        self.assertIn('media_complete_without_asset',self.codes(self.check(self.record)))
    def test_adoption_must_match_real_item(self):
        self.record['candidates'][0].update(decision='adopted',source_id='EXT_MEDIA_X',media_id='missing')
        self.assertIn('media_adoption_unlinked',self.codes(self.check(self.record)))
    def test_missing_new_work_record_flagged(self):
        self.assertIn('media_research_missing',self.codes(self.check(None)))
    def test_old_work_without_record_is_compatible(self):
        self.a['request']={};self.assertEqual(self.check(None)['status'],'not_required')
    def test_offline_scope_can_skip(self):
        self.record.update(status='skipped',scope='offline',reason='User explicitly requested offline work')
        self.assertEqual(self.check(self.record)['status'],'pass')
    def test_skipped_needs_real_scope(self):
        self.record['status']='skipped'
        self.assertIn('media_skip_scope_missing',self.codes(self.check(self.record)))
    def test_wrong_player_not_reused(self):
        self.record['identity']['player_id']=999
        self.assertIn('media_identity_mismatch',self.codes(self.check(self.record)))
    def test_no_retrieval_tools_records_actual_limitation(self):
        self.record.update(candidates=[],queries=[],limitation='search_and_browse_unavailable',
                           stop_reason='No search/browser or public HTTP retrieval tool is available in this runtime.')
        self.assertEqual(self.check(self.record)['status'],'pass')
    def test_one_403_cannot_be_excused_as_no_tools(self):
        self.record.update(limitation='search_and_browse_unavailable',stop_reason='One source denied download')
        self.assertIn('media_fallback_not_attempted',self.codes(self.check(self.record)))
    def test_actual_empty_search_does_not_require_invented_candidates(self):
        self.record.update(candidates=[],queries=[dict(query='specific player and year licensed photo',
            tool='public search',searched_at='2026-10-18T01:00:00+00:00')],
            limitation='no_relevant_candidates',stop_reason='Search returned no relevant photo origins.')
        self.assertEqual(self.check(self.record)['status'],'pass')

if __name__=='__main__':unittest.main()
