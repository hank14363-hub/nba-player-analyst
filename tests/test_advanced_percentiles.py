"""Synthetic samples: ties, scope, missingness, identity and original-file replay."""
from copy import deepcopy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError,digest,read_json
from advanced_percentiles import (context,register,summarize,nba_group,bref_group,
                                  historical_rows,verify_files,other_model_group,MIN_N)
from calculate_metrics import analyze
from run_analysis import parser
from validate_report import validate


class AdvancedPercentiles(unittest.TestCase):
    def setUp(self):
        self.b=read_json(ROOT/'examples/demo_output/data_bundle.json')
        base=deepcopy(self.b['tables']['player_base'][0])
        adv=deepcopy(self.b['tables']['player_advanced'][0])
        self.b['tables']['player_base']=[dict(base,PLAYER_ID=900000000+i,PLAYER_NAME='Synthetic '+str(i),GP=40,MIN=1000) for i in range(10)]
        self.b['tables']['player_advanced']=[dict(adv,PLAYER_ID=900000000+i,PLAYER_NAME='Synthetic '+str(i),GP=40,MIN=25,USG_PCT=.1+i*.01) for i in range(10)]
        for table,sid,measure in [('player_base','P_BASE','Base'),('player_advanced','P_ADV','Advanced')]:
            rows=self.b['tables'][table]
            self.b['sources'][sid].update(status='ok',endpoint='leaguedashplayerstats',row_count=len(rows),sha256_rows=digest(rows),
                parameters=dict(Season=self.b['season'],SeasonType=self.b['season_type'],PerMode='Totals',MeasureType=measure))
        self.pid=900000009

    def entry(self,rows,target):return summarize('X','X','ratio',target,rows,'x',['P_BASE'])

    def test_midrank_including_target_and_ties(self):
        rows=[{'x':i} for i in [1,2,2,2,2,2,3,4]]
        e=self.entry(rows,rows[1]);self.assertEqual(e['percentile'],43.75)
        self.assertEqual((e['lower_count'],e['equal_count'],e['n']),(1,5,8))

    def test_extremes_do_not_force_zero_or_hundred(self):
        rows=[{'x':i} for i in range(10)]
        self.assertEqual(self.entry(rows,rows[0])['percentile'],5)
        self.assertEqual(self.entry(rows,rows[-1])['percentile'],95)

    def test_all_tied_is_fifty(self):
        rows=[{'x':2} for _ in range(8)]
        self.assertEqual(self.entry(rows,rows[0])['percentile'],50)

    def test_field_missing_has_its_own_n(self):
        rows=[{'x':i} for i in range(9)]+[{'x':None}]
        e=self.entry(rows,rows[4]);self.assertEqual((e['n'],e['missing_count']),(9,1))

    def test_small_population_missing_not_zero(self):
        rows=[{'x':i} for i in range(MIN_N-1)]
        self.assertIsNone(self.entry(rows,rows[0])['percentile'])

    def test_absent_target_missing_not_zero(self):
        self.assertIsNone(self.entry([{'x':i} for i in range(10)],None)['percentile'])

    def test_nan_rejected(self):
        with self.assertRaises(DataError): self.entry([{'x':float('nan')}],{'x':1})

    def test_nba_uses_base_total_minutes_not_advanced_mpg(self):
        g=nba_group(self.b,self.pid)
        self.assertEqual(g['eligible_count'],10)
        self.assertEqual(g['entries'][0]['percentile'],95)

    def test_threshold_not_lowered_for_target(self):
        self.b['tables']['player_base'][-1]['MIN']=499
        self.b['tables']['player_advanced'][-1]['MIN']=499/40
        self.b['sources']['P_BASE']['sha256_rows']=digest(self.b['tables']['player_base'])
        self.b['sources']['P_ADV']['sha256_rows']=digest(self.b['tables']['player_advanced'])
        g=nba_group(self.b,self.pid)
        self.assertEqual(g['eligible_count'],9);self.assertIsNone(g['entries'][0]['percentile'])

    def test_filtered_league_source_rejected(self):
        self.b['sources']['P_ADV']['parameters']['TeamID']=123
        with self.assertRaises(DataError):nba_group(self.b,self.pid)

    def test_raw_hash_tampering_rejected(self):
        self.b['tables']['player_advanced'][0]['USG_PCT']=.8
        with self.assertRaises(DataError):nba_group(self.b,self.pid)

    def test_minutes_mismatch_rejected(self):
        self.b['tables']['player_advanced'][0]['MIN']=99
        self.b['sources']['P_ADV']['sha256_rows']=digest(self.b['tables']['player_advanced'])
        with self.assertRaises(DataError):nba_group(self.b,self.pid)

    def test_numeric_direction_not_silently_flipped(self):
        g=nba_group(self.b,self.pid)
        e=next(e for e in g['entries'] if e['metric_id']=='ONCOURT_DEF_RATING')
        self.assertEqual(e['direction'],'higher_numeric')
        self.assertIn('失分',e['label'])

    def test_exact_ts_comes_from_totals(self):
        g=nba_group(self.b,self.pid);b=self.b['tables']['player_base'][-1]
        e=next(e for e in g['entries'] if e['metric_id']=='TS_PCT')
        self.assertEqual(e['target'],b['PTS']/(2*(b['FGA']+.44*b['FTA'])))

    def bref(self):
        rows=[dict(provider_player_key='synthetic'+str(i),team_name_abbr='AAA',games='40',mp='1000',bpm=str(i)) for i in range(10)]
        return dict(raw_rows=rows,selector=dict(provider_player_key='synthetic9'),source_id='EXT_TEST')

    def test_bref_stints_keep_one_aggregate(self):
        d=self.bref();d['raw_rows'][-1]['team_name_abbr']='2TM'
        d['raw_rows'].append(dict(d['raw_rows'][-1],team_name_abbr='BBB',games='20',mp='500',bpm='100'))
        g=bref_group(self.b,d)
        self.assertEqual((g['eligible_count'],g['removed_stint_count']),(10,1))
        self.assertEqual(g['entries'][0]['percentile'],95)

    def test_bref_duplicate_without_aggregate_rejected(self):
        d=self.bref();d['raw_rows'].append(dict(d['raw_rows'][-1],team_name_abbr='BBB'))
        with self.assertRaises(DataError):bref_group(self.b,d)

    def test_team_stint_explicitly_unavailable(self):
        c=context(self.b,self.pid,123,[])
        self.assertEqual(c['status'],'missing');self.assertEqual(c['groups'],[])

    def test_missing_models_are_named(self):
        c=context(self.b,self.pid,0,[])
        self.assertTrue(all(g['status']=='missing' for g in c['groups'] if g['family']!='NBA'))
        self.assertEqual({g['family'] for g in c['groups']},{'NBA','BREF','LEBRON','EPM','DARKO'})

    def test_existing_target_disagreement_not_compared(self):
        c=context(self.b,self.pid,0,[dict(metric_id='USG_PCT',status='ok',value=.8)])
        e=c['groups'][0]['entries'][0]
        self.assertIsNone(e['percentile']);self.assertIn('不一致',e['reason'])

    def history(self):
        embedded=dict(player_id=123,player_name='Synthetic Only',season=2025,game_dt='2025-04-01',tot=2,off=3,**{'def':-1})
        return dict(nba_player_id='123',player_name='Synthetic Only',season='2025',game_dt='2025-04-01',
                    epm_tot='2',epm_off='3',epm_def='-1',source='dunksandthrees.com/player/eskills',raw=json.dumps(embedded))

    def test_historical_filters_same_year_and_source(self):
        r=self.history();other=dict(r,source='dunksandthrees.com/epm')
        self.assertEqual(len(historical_rows([r,other],'2024-25',r['source'])),1)

    def test_historical_duplicate_not_automatically_latest(self):
        r=self.history()
        with self.assertRaises(DataError):historical_rows([r,r],'2024-25',r['source'])

    def test_historical_embedded_values_checked(self):
        r=self.history();r['epm_off']='4'
        with self.assertRaises(DataError):historical_rows([r],'2024-25',r['source'])

    def test_provider_rows_replayed_from_original_file(self):
        rows=[dict(nba_id=123,Season='2024-25')]
        payload=json.dumps(rows).encode()
        from import_epm import sha
        b=dict(impact_data=dict(datasets=[dict(family='LEBRON',source_id='EXT_TEST',raw_rows=rows)]),
               sources=dict(EXT_TEST=dict(raw_file='raw/relay.json',sha256_raw=sha(payload))))
        with tempfile.TemporaryDirectory() as t:
            p=Path(t);(p/'raw').mkdir();(p/'raw/relay.json').write_bytes(payload)
            verify_files(b,p)
            b['impact_data']['datasets'][0]['raw_rows']=[dict(nba_id=456,Season='2024-25')]
            with self.assertRaises(DataError):verify_files(b,p)

    def test_cli_defaults_and_opt_out(self):
        args=['--player-id','123','--season','2024-25']
        self.assertTrue(parser().parse_args(args).advanced_percentiles)
        self.assertFalse(parser().parse_args(args+['--no-advanced-percentiles']).advanced_percentiles)

    def actual(self):
        from import_epm import prepare_import
        rows=[dict(nba_id=r['PLAYER_ID'],player_name=r['PLAYER_NAME'],season='2024-25',games=40,minutes=1000,tot=i,off=i+1,**{'def':-1}) for i,r in enumerate(self.b['tables']['player_base'])]
        meta=dict(schema_version='0.1.0',source_url='https://dunksandthrees.com/epm/actual?season=2025',
                  exported_at='2026-10-17T10:00:00+00:00',estimate_type='actual',league='NBA',season='2024-25',
                  season_type='Regular Season',sample_scope='full_season',minutes_unit='total',minutes_decimals=0,
                  season_format='nba',model_version='SYNTHETIC ONLY',
                  columns={k:k for k in ('nba_id','player_name','season','games','minutes','tot','off','def')})
        return prepare_import(self.b,self.pid,json.dumps(rows).encode(),'json',json.dumps(meta).encode())

    def test_actual_epm_rebuilds_each_row_with_full_reference(self):
        b=self.actual();g=other_model_group(b,b['impact_data']['datasets'][0])
        self.assertEqual(g['eligible_count'],10)
        self.assertEqual(g['entries'][0]['percentile'],95)
        self.assertEqual(g['entries'][0]['metric_id'],'IMPACT_EPM')

    def test_actual_minute_mismatch_excluded_with_reason(self):
        b=self.actual();b['tables']['player_base'][0]['MIN']=1005
        b['sources']['P_BASE']['sha256_rows']=digest(b['tables']['player_base'])
        g=other_model_group(b,b['impact_data']['datasets'][0])
        self.assertEqual(g['eligible_count'],9)
        self.assertIn('minute',g['excluded'][0]['reason'])

    def test_actual_duplicate_identity_rejected(self):
        b=self.actual();b['epm_import']['snapshot']['raw_rows'].append(deepcopy(b['epm_import']['snapshot']['raw_rows'][0]))
        with self.assertRaises(DataError):other_model_group(b,b['impact_data']['datasets'][0])

    def test_historical_wrong_date_year_rejected(self):
        r=self.history();r['game_dt']='2026-04-01'
        with self.assertRaises(DataError):historical_rows([r],'2024-25',r['source'])

    def test_historical_mixed_dates_are_preserved(self):
        a=self.history();b=deepcopy(a);b.update(nba_player_id='124',game_dt='2025-06-01')
        embedded=json.loads(b['raw']);embedded.update(player_id=124,game_dt='2025-06-01');b['raw']=json.dumps(embedded)
        out=historical_rows([a,b],'2024-25',a['source'])
        self.assertEqual({r['as_of'] for r in out},{'2025-04-01','2025-06-01'})

    def test_rehashed_historical_subset_still_fails_original_replay(self):
        import csv,io
        from import_epm import sha
        original=self.history();stream=io.StringIO(newline='');writer=csv.DictWriter(stream,fieldnames=list(original))
        writer.writeheader();writer.writerow(original);payload=stream.getvalue().encode()
        rows=historical_rows([original],'2024-25',original['source'])
        pop=dict(season='2024-25',upstream=original['source'],source_id='EXT_POP',raw_rows=rows)
        b=dict(advanced_percentile_populations=dict(historical_epm=pop),sources=dict(EXT_POP=dict(raw_file='raw/history.csv',sha256_raw=sha(payload))))
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'raw').mkdir();(root/'raw/history.csv').write_bytes(payload)
            verify_files(b,root)
            rows[0]['tot']=99;pop['sha256_rows']=digest(rows);b['sources']['EXT_POP']['sha256_rows']=digest(rows)
            with self.assertRaises(DataError):verify_files(b,root)

    def test_archive_source_discloses_mixed_dates_without_prediction_label(self):
        from book_sources import source_index
        a=dict(sample=dict(season='2024-25'),sources=dict(EXT_POP=dict(provider='Synthetic Only',status='ok',
               source_type='impact_data',source_kind='deocheng-historical-epm-distribution-v1',cutoff=None,
               season='2024-25',season_type='Regular Season',date_min='2024-10-21',date_max='2025-06-08')))
        text=source_index(a)
        self.assertIn('归档分布 · 口径待核验',text)
        self.assertIn('不同记录日期',text)
        self.assertNotIn('历史预测快照',text)

    def test_editorial_audit_requires_percentile_interpretation(self):
        from editorial_audit import audit
        a=dict(data_kind='synthetic',request={},percentile_context=dict(groups=[dict(family='NBA',entries=[dict(status='ok',percentile_metric_id='PCTL_USG_PCT')])]))
        result=audit({},a,dict(claims=[]))
        self.assertTrue(any(x['code']=='percentiles_unwritten' for x in result['findings']))

    def test_defense_missing_field_does_not_remove_other_metrics(self):
        self.b['tables']['player_advanced'][0]['DEF_RATING']=None
        self.b['sources']['P_ADV']['sha256_rows']=digest(self.b['tables']['player_advanced'])
        g=nba_group(self.b,self.pid)
        defense=next(e for e in g['entries'] if e['metric_id']=='ONCOURT_DEF_RATING')
        self.assertEqual(defense['n'],9);self.assertEqual(g['entries'][0]['n'],10)

    def test_old_request_does_not_gain_metrics(self):
        b=read_json(ROOT/'examples/demo_output/data_bundle.json')
        request=read_json(ROOT/'examples/demo_output/analysis.json')['request']
        a=analyze(b,request)
        self.assertNotIn('percentile_context',a)
        self.assertFalse(any(m['metric_id'].startswith('PCTL_') for m in a['metrics']))

    def test_historical_percentile_requires_disclosure_in_claim(self):
        b=read_json(ROOT/'examples/demo_output/data_bundle.json');request=read_json(ROOT/'examples/demo_output/analysis.json')['request']
        a=analyze(b,request)
        a['metrics'].append(dict(metric_id='PCTL_IMPACT_EPM_HIST',status='ok',value=90,source_ids=['P_BASE']))
        c=dict(schema_version='0.1.0',data_kind='synthetic',claims=[dict(id='P1',kind='fact',report_quote='百分位90',
               metric_ids=['PCTL_IMPACT_EPM_HIST'],source_ids=['P_BASE'],confidence='high',numeric_facts=[dict(metric_id='PCTL_IMPACT_EPM_HIST',value=90)])])
        report='合成测试数据\n## A\n## B\n## C\n## D\n百分位90 [P_BASE]'
        self.assertTrue(any('口径待核验' in x for x in validate(report,c,a,0)['errors']))


if __name__=='__main__':unittest.main()
