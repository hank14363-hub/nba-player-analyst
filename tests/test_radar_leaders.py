"""Synthetic scope failures and league maxima, independent of real player values."""
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import sys
import unittest
from math import hypot
from xml.etree import ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError,digest,read_json
from radar_visuals import profiles,svg,radar_entries,award,PROFILES
from radar_geometry import CENTER,INNER,OUTER,RING_LEVELS
from stat_leaders import maximum,unique_bref,context

class RadarAndLeaders(unittest.TestCase):
    def analysis(self):
        metrics=[];entries=[]
        for i,(mid,label) in enumerate(PROFILES[1]['axes']):
            raw=2+i;pc=80+i
            metrics.extend([dict(metric_id=mid,status='ok',value=raw,display=str(raw),unit='ratio'),
                            dict(metric_id='PCTL_'+mid,status='ok',value=pc)])
            entries.append(dict(metric_id=mid,status='ok',n=10,missing_count=0,target=raw,percentile=pc,source_ids=['EXT_TEST']))
        return dict(metrics=metrics,player=dict(name='SYNTHETIC ONLY'),data_kind='synthetic',
            sample=dict(season='2024-25',season_type='Regular Season'),
            percentile_context=dict(groups=[dict(family='BREF',status='ok',entries=entries,
                population_keys=list(range(10)),eligible_count=10,source_ids=['EXT_TEST'],scope='synthetic')]))

    def test_complete_same_source_profile(self):
        p=profiles(self.analysis());self.assertEqual(len(p),1);self.assertEqual(len(p[0]['axes']),6)

    def test_partial_axis_omits_entire_radar(self):
        a=self.analysis();a['percentile_context']['groups'][0]['entries'].pop()
        self.assertEqual(profiles(a),[])

    def test_axis_with_different_n_omits_radar(self):
        a=self.analysis();a['percentile_context']['groups'][0]['entries'][0]['n']=9
        self.assertEqual(profiles(a),[])

    def test_missing_even_with_same_n_omits_radar(self):
        a=self.analysis();a['percentile_context']['groups'][0]['entries'][0]['missing_count']=1
        self.assertEqual(profiles(a),[])

    def test_population_duplicate_rejected(self):
        a=self.analysis();a['percentile_context']['groups'][0]['population_keys'][-1]=0
        self.assertEqual(profiles(a),[])

    def test_percentile_tamper_rejected(self):
        a=self.analysis();a['metrics'][1]['value']=99
        self.assertEqual(profiles(a),[])

    def test_raw_tamper_rejected(self):
        a=self.analysis();a['metrics'][0]['value']=100
        self.assertEqual(profiles(a),[])

    def test_nan_not_drawn(self):
        a=self.analysis();a['metrics'][1]['value']=float('nan')
        self.assertEqual(profiles(a),[])

    def test_history_not_mixed_in_radar(self):
        a=self.analysis();a['percentile_context']['groups'][0]['family']='EPM_HISTORICAL'
        self.assertEqual(profiles(a),[])

    def test_percentile_high_is_not_leader(self):
        a=self.analysis();s=svg(profiles(a)[0],a,{})
        self.assertNotIn('NO.1',s)
        self.assertIn('SYNTHETIC TEST DATA',s)

    def test_svg_preserves_metric_ids_and_no_network(self):
        a=self.analysis();s=svg(profiles(a)[0],a,{})
        self.assertIn('data-metric-id="PCTL_IMPACT_VORP"',s)
        self.assertNotIn('<script',s);self.assertNotIn('<image',s)

    def geometry(self,values):
        a=self.analysis()
        for i,value in enumerate(values):
            a['metrics'][i*2+1]['value']=value
            a['percentile_context']['groups'][0]['entries'][i]['percentile']=value
        tree=ET.fromstring(svg(profiles(a)[0],a,{}))
        polygon=next(el for el in tree.iter() if el.get('class')=='radar-shape')
        return tree,[tuple(map(float,point.split(','))) for point in polygon.get('points').split()]

    def test_breakout_keeps_linear_percentile_distances(self):
        values=[0,25,50,75,99.5,100]
        tree,points=self.geometry(values)
        for value,(x,y) in zip(values,points):
            self.assertAlmostEqual(hypot(x-CENTER[0],y-CENTER[1]),INNER+(OUTER-INNER)*value/100,delta=.001)

    def test_breakout_p50_frame_is_half_p100_on_same_axes(self):
        tree,_=self.geometry([50]*6)
        guide=next(el for el in tree.iter() if el.get('class')=='radar-grid' and el.get('data-level')=='50')
        self.assertEqual(float(guide.get('r')),INNER+(OUTER-INNER)*.5)
        self.assertEqual((float(guide.get('cx')),float(guide.get('cy'))),CENTER)

    def test_ring_ticks_are_registered_real_quantiles(self):
        a=self.analysis()
        entries=a['percentile_context']['groups'][0]['entries']
        for e in entries:e['ring_quantiles']={str(x):float(x) for x in (5,18,32,46,60,75,90)}
        s=svg(profiles(a)[0],a,{})
        self.assertIn('class="radar-ring-tick"',s)
        self.assertIn('>5.00</text>',s)
        self.assertIn('radar-ring-tick',radar_entries(a,{})['percentile_bref_radar']['svg'])

    def test_breakout_extremes_stay_inside_p100_and_export_canvas(self):
        for values in ([0]*6,[100]*6,[0,100,0,100,0,100]):
            tree,points=self.geometry(values)
            w,h=map(float,tree.get('viewBox').split()[2:])
            for x,y in points:
                self.assertLessEqual(hypot(x-CENTER[0],y-CENTER[1]),OUTER+.001)
                self.assertTrue(0<=x<=w and 0<=y<=h)

    def test_missing_quantiles_are_never_estimated(self):
        a=self.analysis()
        self.assertNotIn('class="radar-ring-tick"',svg(profiles(a)[0],a,{}))
        a['data_kind']='observed'
        self.assertNotIn('class="radar-ring-tick"',svg(profiles(a)[0],a,{}))

    def test_invalid_quantile_ladder_is_omitted(self):
        for bad in ({'5':1},{str(q):-q for q in RING_LEVELS},{str(q):float('nan') for q in RING_LEVELS}):
            a=self.analysis()
            for e in a['percentile_context']['groups'][0]['entries']:e['ring_quantiles']=bad
            self.assertNotIn('class="radar-ring-tick"',svg(profiles(a)[0],a,{}))

    def test_quantile_tick_uses_same_radial_mapping(self):
        a=self.analysis()
        for e in a['percentile_context']['groups'][0]['entries']:
            e['ring_quantiles']={str(q):float(q) for q in RING_LEVELS}
        tree=ET.fromstring(svg(profiles(a)[0],a,{}))
        ticks=[el for el in tree.iter() if el.get('class')=='radar-ring-tick']
        self.assertEqual(len(ticks),6*len(RING_LEVELS))
        for el in ticks:
            q=int(el.get('data-level'));x=float(el.get('x'));y=float(el.get('y'))
            self.assertAlmostEqual(hypot(x-CENTER[0],y-CENTER[1]),INNER+(OUTER-INNER)*q/100,delta=.001)
            self.assertEqual(float(el.get('data-quantile-value')),q)

    def test_rich_profile_uses_same_population_and_falls_back(self):
        a=self.analysis();g=a['percentile_context']['groups'][0]
        for mid,label in PROFILES[3]['axes']:
            if any(e['metric_id']==mid for e in g['entries']):continue
            a['metrics'] += [dict(metric_id=mid,status='ok',value=3,display='3',unit='ratio'),dict(metric_id='PCTL_'+mid,status='ok',value=50)]
            g['entries'].append(dict(metric_id=mid,status='ok',n=10,missing_count=0,target=3,percentile=50,source_ids=['EXT_TEST']))
        self.assertEqual(len(profiles(a)[0]['axes']),11)
        g['entries'][-1]['missing_count']=1
        self.assertEqual(len(profiles(a)[0]['axes']),6)

    def test_unique_and_tied_maxima(self):
        rows=[dict(x=i) for i in range(8)]
        m=dict(value=7,label='synthetic')
        l=maximum('X',m,rows,'x','EXT_TEST','BREF','test')
        self.assertEqual((l['rank'],l['ties'],l['n']),(1,1,8))
        rows[0]['x']=7
        l=maximum('X',m,rows,'x','EXT_TEST','BREF','test')
        self.assertEqual(l['ties'],2);self.assertIn('并列',l['text'])

    def test_missing_raw_never_claims_all_league(self):
        rows=[dict(x=i) for i in range(8)]+[dict(x=None)]
        self.assertIsNone(maximum('X',dict(value=7),rows,'x','EXT_TEST','BREF','test'))

    def test_higher_outside_eligible_sample_prevents_leader(self):
        rows=[dict(x=i) for i in range(9)]
        self.assertIsNone(maximum('X',dict(value=7),rows,'x','EXT_TEST','BREF','test'))

    def test_small_or_absent_target_no_leader(self):
        for rows in ([dict(x=i) for i in range(7)],[dict(x=i) for i in range(8)]):
            self.assertIsNone(maximum('X',dict(value=20),rows,'x','EXT_TEST','BREF','test'))

    def test_stint_uses_unique_aggregate(self):
        rows=[dict(provider_player_key='synthetic',team_name_abbr=t,x=x) for t,x in [('AAA',99),('BBB',1),('2TM',7)]]
        self.assertEqual(unique_bref(rows)[0]['x'],7)

    def test_stint_without_aggregate_refused(self):
        rows=[dict(provider_player_key='synthetic',team_name_abbr=t) for t in ('AAA','BBB')]
        with self.assertRaises(DataError):unique_bref(rows)

    def bref(self):
        b=read_json(ROOT/'examples/demo_output/data_bundle.json')
        rows=[dict(provider_player_key='synthetic'+str(i),team_name_abbr='AAA',vorp=str(i)) for i in range(10)]
        sid='EXT_TEST'
        b['sources'][sid]=dict(url=f"https://www.basketball-reference.com/leagues/NBA_{int(b['season'][:4])+1}_advanced.html",
            status='ok',season=b['season'],season_type=b['season_type'],table_id='advanced',row_count=10,sha256_rows=digest(rows))
        b['impact_data']=dict(datasets=[dict(family='BREF',raw_rows=rows,source_id=sid,selector=dict(provider_player_key='synthetic9'))])
        return b,[dict(metric_id='IMPACT_VORP',status='ok',value=9,label='Synthetic VORP')]

    def test_leader_source_must_be_complete_page(self):
        b,m=self.bref();self.assertEqual(context(b,123,0,m)['leaders'][0]['n'],10)
        b['sources']['EXT_TEST']['url']='https://example.com/player-only'
        self.assertEqual(context(b,123,0,m)['leaders'],[])

    def test_leader_source_hash_checked(self):
        b,m=self.bref();b['impact_data']['datasets'][0]['raw_rows'][0]['vorp']='99'
        self.assertEqual(context(b,123,0,m)['leaders'],[])

    def test_source_season_and_type_checked(self):
        for key,value in [('season','2000-01'),('season_type','Playoffs')]:
            b,m=self.bref();b['sources']['EXT_TEST'][key]=value
            self.assertEqual(context(b,123,0,m)['leaders'],[])

    def test_team_stint_not_league_maximum(self):
        b,m=self.bref();self.assertEqual(context(b,123,456,m)['status'],'missing')

    def test_tied_badge_and_registry_scope(self):
        a=self.analysis()
        a['stat_leader_context']=dict(leaders=[dict(metric_id='IMPACT_VORP',text='全联盟并列第1',n=50,ties=2)])
        s=svg(profiles(a)[0],a,{})
        self.assertIn('=NO.1',s);self.assertIn('完整联盟样本50人',s)
        entry=radar_entries(a,{})['percentile_bref_radar']
        self.assertIn('STAT_LEADER_IMPACT_VORP_N',entry['metric_ids'])

    def test_prominent_award_keeps_full_n_distinct_from_radar_n(self):
        a=self.analysis()
        a['stat_leader_context']=dict(leaders=[dict(metric_id='IMPACT_VORP',text='全联盟并列第1',n=40,ties=2,family='BREF')])
        for suffix,value in [('RANK',1),('N',40),('TIES',2)]:
            a['metrics'].append(dict(metric_id='STAT_LEADER_IMPACT_VORP_'+suffix,status='ok',value=value,display=str(value)))
        book=SimpleNamespace(metrics={m['metric_id']:m for m in a['metrics']})
        output=award(profiles(a)[0],book)
        self.assertIn('全联盟并列第1',output)
        self.assertIn('data-metric-id="STAT_LEADER_IMPACT_VORP_N" data-value="40"',output)
        self.assertIn('10 人出勤合格样本',output)
        self.assertIn('data-metric-id="IMPACT_VORP"',output)

    def test_prominent_award_absent_without_verified_leader(self):
        a=self.analysis();book=SimpleNamespace(metrics={m['metric_id']:m for m in a['metrics']})
        self.assertEqual(award(profiles(a)[0],book),'')

if __name__=='__main__':unittest.main()
