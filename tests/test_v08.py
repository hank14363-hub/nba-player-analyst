import copy,json,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError,digest
from calculate_metrics import analyze
from player_comparisons import comparison_context,percentile,choose_profile,limitations
from core_metrics import select_core
from comparison_visuals import comparison_visuals
from book_contract import load_context,validate_content


class Comparisons(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.case=ROOT/'examples/cade-cunningham-2024-25-official-v073'
        cls.bundle=json.loads((cls.case/'data_bundle.json').read_text(encoding='utf-8'))
        cls.request=json.loads((cls.case/'analysis.json').read_text(encoding='utf-8'))['request']|{'comparisons':True}
        cls.a=analyze(cls.bundle,cls.request)

    def test_independent_population_and_quantiles(self):
        c=self.a['comparison_context'];self.assertEqual(c['status'],'ok')
        bases={r['PLAYER_ID']:r for r in self.bundle['tables']['player_base']}
        expected={r['PLAYER_ID'] for r in self.bundle['tables']['player_advanced'] if bases[r['PLAYER_ID']]['GP']>=40 and bases[r['PLAYER_ID']]['MIN']>=1000 and r['USG_PCT']>=.25 and r['AST_PCT']>=.30}
        self.assertEqual({r['player_id'] for r in c['players']},expected)
        self.assertEqual(len(expected),12);self.assertEqual(c['eligible_count'],266)
        self.assertAlmostEqual(c['axes'][1]['percentile'],100*9.5/12)
        self.assertAlmostEqual(c['axes'][2]['percentile'],100*2.5/12)
        self.assertAlmostEqual(c['axes'][5]['percentile'],100*1.5/12)
        self.assertEqual([s['n'] for s in c['sensitivity']],[27,11])

    def test_ties_and_direction(self):
        self.assertEqual(percentile(2,[1,2,2,4]),50)
        self.assertEqual(percentile(2,[1,2,2,4],-1),50)
        self.assertEqual(percentile(1,[1,2,3],-1),100*2.5/3)

    def reject(self,mutator,refresh=False):
        b=copy.deepcopy(self.bundle);mutator(b)
        if refresh:
            for table,sid in [('player_base','P_BASE'),('player_advanced','P_ADV'),('player_scoring','P_SCORE')]:
                b['sources'][sid]['sha256_rows']=digest(b['tables'][table]);b['sources'][sid]['row_count']=len(b['tables'][table])
        with self.assertRaises(DataError):comparison_context(b,1630595,0)

    def test_filtered_sources_rejected(self):self.reject(lambda b:b['sources']['P_ADV']['parameters'].update(TeamID=1610612765))
    def test_mode_rejected(self):self.reject(lambda b:b['sources']['P_100']['parameters'].update(PerMode='PerGame'))
    def test_wrong_season_rejected(self):self.reject(lambda b:b['sources']['P_ADV']['parameters'].update(Season='2025-26'))
    def test_raw_tampering_rejected(self):self.reject(lambda b:b['tables']['player_base'][0].update(PTS=9999))
    def test_duplicate_stints_rejected(self):self.reject(lambda b:b['tables']['player_base'].append(copy.deepcopy(b['tables']['player_base'][0])),True)
    def test_incomplete_eligible_not_silently_removed(self):
        self.reject(lambda b:next(r for r in b['tables']['player_advanced'] if r['PLAYER_ID']==1630595).update(AST_PCT=None),True)
    def test_gp_mismatch_rejected(self):
        self.reject(lambda b:next(r for r in b['tables']['player_scoring'] if r['PLAYER_ID']==1630595).update(GP=69),True)
    def test_minutes_scope_rejected(self):
        self.reject(lambda b:next(r for r in b['tables']['player_advanced'] if r['PLAYER_ID']==1630595).update(MIN=7.0),True)
    def test_team_stint_cannot_mix(self):
        with self.assertRaises(DataError):comparison_context(self.bundle,1630595,1610612765)
    def test_small_target_not_forced(self):
        with self.assertRaises(DataError):comparison_context(self.bundle,1630639,0)
    def test_role_profiles(self):
        row=dict(USG_PCT=.3,AST_PCT=.4,OREB_PCT=.02,DREB_PCT=.1,FG3A_RATE=.3,FG3A=300)
        self.assertEqual(choose_profile(row),'creator')
        self.assertEqual(choose_profile(row|dict(AST_PCT=.1,USG_PCT=.15,OREB_PCT=.12,DREB_PCT=.24)),'rebounder')
        self.assertEqual(choose_profile(row|dict(AST_PCT=.1,USG_PCT=.15,FG3A_RATE=.6)),'shooter')
    def test_cover_creator_and_shooter(self):
        self.assertEqual([c['metric_id'] for c in select_core(self.a)],['AST_PCT','PCT_UAST_FGM','DRIVES_PER_GAME','PTS_PER75'])
        a=copy.deepcopy(self.a);a['comparison_context']['profile']='shooter'
        self.assertEqual([c['metric_id'] for c in select_core(a)],['FG3_PCT','FG3A_RATE','CATCH_SHOOT_EFG_PCT','TS_PCT'])
    def test_cover_missing_tracking_falls_back(self):
        a=copy.deepcopy(self.a);next(m for m in a['metrics'] if m['metric_id']=='DRIVES_PER_GAME')['status']='missing'
        selected=select_core(a);self.assertEqual(len(selected),4);self.assertNotIn('DRIVES_PER_GAME',[c['metric_id'] for c in selected])
    def test_dynamic_limits(self):
        text=' '.join(limitations(self.a));self.assertIn('已核验投篮坐标',text);self.assertIn('已提供同角色',text)
        a=copy.deepcopy(self.a);a.pop('shot_context');a.pop('comparison_context');self.assertIn('不绘制',' '.join(limitations(a)))
    def test_density_no_fictional_efficiency(self):
        entries=comparison_visuals(self.a,{})
        self.assertIn('1453 / 全部 1457；视窗外 4 次',entries['shot_density']['svg'])
        self.assertIn('颜色越深 = 出手次数越多',entries['shot_density']['svg'])
        self.assertNotIn('league',entries['shot_density']['svg'])
        a=copy.deepcopy(self.a);a['shot_context']=None;self.assertEqual(comparison_visuals(a,{})['shot_density']['status'],'missing')
    def test_core_claim_required(self):
        a,claims,_,_=load_context(self.case);book=json.loads((self.case/'book_content.json').read_text(encoding='utf-8'))
        book['core_metrics']=[dict(metric_id=c['metric_id'],label=c['label'],note=c['note'],claim_ids=['C01']) for c in select_core(a)]
        self.assertTrue(any('Core metric must' in e for e in validate_content(book,a,claims)))


if __name__=='__main__':unittest.main()
