"""Offline unit, integration and mocked-network tests. These do not exercise NBA servers."""
from __future__ import annotations

import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import DataError, digest, load_bundle, player_row, read_json, resolve_player, validate_bundle, validate_season, write_json
from calculate_metrics import analyze, safe_ratio
from fetch_data import Fetcher, unpack_rows
from run_analysis import parser, run
from validate_report import validate


def fixture():
    return read_json(ROOT / 'examples/demo_bundle.json')


def request():
    return {'player':'MVP Demo Guard','player_id':None,'season':'2024-25','season_type':'Regular Season',
            'team_id':0,'target_team_id':None,'question':'Test only','words':2500}


def metric_map(analysis):
    return {m['metric_id']:m for m in analysis['metrics']}


class CalculationTests(unittest.TestCase):
    def setUp(self):
        self.bundle=fixture()
        self.req=request()

    def test_ts_formula(self):
        m=metric_map(analyze(self.bundle,self.req))
        self.assertAlmostEqual(m['TS_PCT']['value'],1400/(2*(1000+.44*300)))

    def test_efg_formula(self):
        self.assertAlmostEqual(metric_map(analyze(self.bundle,self.req))['EFG_PCT']['value'],.57)

    def test_weighted_league_ts(self):
        m=metric_map(analyze(self.bundle,self.req))
        league=12900/(2*(10500+.44*2750))
        self.assertAlmostEqual(m['LEAGUE_TS_PCT']['value'],league)
        simple=(6600/(2*(5200+.44*1450))+6300/(2*(5300+.44*1300)))/2
        self.assertNotAlmostEqual(league,simple,places=7)
        self.assertAlmostEqual(m['RTS_PP']['value'],(1400/2264-league)*100)
        self.assertEqual(m['RTS_PP']['unit'],'percentage_points')

    def test_per75_only_counts(self):
        m=metric_map(analyze(self.bundle,self.req))
        self.assertEqual(m['PTS_PER75']['value'],30)
        self.assertEqual(m['USG_PCT']['value'],.28)

    def test_no_offcourt_invention(self):
        m=metric_map(analyze(self.bundle,self.req))
        self.assertEqual(m['ONCOURT_NET_RATING']['value'],6)
        self.assertIsNone(m['ON_OFF_DIFFERENTIAL']['value'])
        self.assertIsNone(m['DEFENSIVE_ABILITY_SCORE']['value'])

    def test_no_minutes_based_per75_fallback(self):
        self.bundle['tables'].pop('player_per100')
        self.assertIsNone(metric_map(analyze(self.bundle,self.req))['PTS_PER75']['value'])

    def test_zero_turnovers_not_infinity(self):
        self.bundle['tables']['player_base'][0]['TOV']=0
        self.assertIsNone(metric_map(analyze(self.bundle,self.req))['AST_TOV']['value'])

    def test_zero_shooting_denominator(self):
        for field in ('PTS','FGM','FGA','FG3M','FG3A','FTM','FTA'):
            self.bundle['tables']['player_base'][0][field]=0
        m=metric_map(analyze(self.bundle,self.req))
        self.assertIsNone(m['TS_PCT']['value'])
        self.assertIsNone(m['RTS_PP']['value'])

    def test_missing_is_not_zero(self):
        self.bundle['tables']['player_base'][0].pop('REB')
        self.assertIsNone(metric_map(analyze(self.bundle,self.req))['REB_PER_GAME']['value'])

    def test_no_team_baseline_no_rts(self):
        self.bundle['tables'].pop('team_base')
        a=analyze(self.bundle,self.req)
        self.assertIsNone(metric_map(a)['RTS_PP']['value'])
        self.assertEqual(a['quality']['mode'],'limited')

    def test_baseline_needs_coverage(self):
        self.bundle['sources']['T_BASE'].pop('coverage')
        self.assertIsNone(metric_map(analyze(self.bundle,self.req))['LEAGUE_TS_PCT']['value'])

    def test_duplicate_league_rows_not_double_counted(self):
        self.bundle['tables']['team_base'].append(copy.deepcopy(self.bundle['tables']['team_base'][0]))
        self.assertIsNone(metric_map(analyze(self.bundle,self.req))['RTS_PP']['value'])

    def test_source_percent_scale_not_silently_repaired(self):
        self.bundle['tables']['player_advanced'][0]['USG_PCT']=28
        self.assertIsNone(metric_map(analyze(self.bundle,self.req))['USG_PCT']['value'])

    def test_advanced_mismatched_games_excluded(self):
        self.bundle['tables']['player_advanced'][0]['GP']=61
        a=analyze(self.bundle,self.req)
        self.assertIsNone(metric_map(a)['AST_PCT']['value'])
        self.assertTrue(any('GP differs' in w for w in a['quality']['warnings']))

    def test_negative_counts_rejected(self):
        self.bundle['tables']['player_base'][0]['STL']=-1
        with self.assertRaises(DataError): analyze(self.bundle,self.req)

    def test_points_identity_rejected(self):
        self.bundle['tables']['player_base'][0]['PTS']=1401
        with self.assertRaises(DataError): analyze(self.bundle,self.req)

    def test_nonfinite_rejected(self):
        self.bundle['tables']['player_base'][0]['AST']=float('nan')
        with self.assertRaises(DataError): analyze(self.bundle,self.req)

    def test_fractional_totals_rejected(self):
        self.bundle['tables']['player_base'][0]['PTS']=23.33
        with self.assertRaises(DataError): analyze(self.bundle,self.req)

    def test_synthetic_is_prominent(self):
        a=analyze(self.bundle,self.req)
        self.assertEqual(a['data_kind'],'synthetic')
        self.assertIn('SYNTHETIC',a['quality']['warnings'][0])

    def test_csv_and_json_equivalent(self):
        csv_bundle=load_bundle(ROOT/'examples/demo_csv')
        self.assertEqual(metric_map(analyze(csv_bundle,self.req)),metric_map(analyze(self.bundle,self.req)))

    def test_target_team_does_not_change_player(self):
        self.req['target_team_id']=9002
        a=analyze(self.bundle,self.req)
        self.assertEqual(a['target_team']['id'],9002)
        self.assertTrue(a['target_team']['hypothetical'])
        self.assertEqual(metric_map(a)['TEAM_PACE']['value'],101)
        self.assertAlmostEqual(metric_map(a)['PTS_PER_GAME']['value'],1400/60)

    def test_small_sample_is_flag_not_confidence_probability(self):
        self.bundle['tables']['player_base'][0]['GP']=15
        self.bundle['tables']['player_base'][0]['MIN']=400
        a=analyze(self.bundle,self.req)
        self.assertTrue(any('heuristic' in w for w in a['quality']['warnings']))

    def test_negative_per100_count_excluded(self):
        self.bundle['tables']['player_per100'][0]['PTS']=-1
        self.assertIsNone(metric_map(analyze(self.bundle,self.req))['PTS_PER75']['value'])

    def test_team_snapshot_mismatch_excluded(self):
        self.bundle['tables']['team_advanced'][0]['GP']=61
        self.assertIsNone(metric_map(analyze(self.bundle,self.req))['TEAM_PACE']['value'])

    def test_source_season_mismatch_rejected(self):
        self.bundle['sources']['P_ADV']['season']='2023-24'
        with self.assertRaises(DataError): analyze(self.bundle,self.req)

    def test_safe_ratio(self):
        self.assertIsNone(safe_ratio(None,10))
        self.assertIsNone(safe_ratio(10,0))
        self.assertEqual(safe_ratio(0,2),0)


class ContractTests(unittest.TestCase):
    def test_season_validation(self):
        validate_season('2024-25','Playoffs')
        for season, kind in (('2024','Regular Season'),('2024-26','Regular Season'),('2024-25','Pre Season')):
            with self.assertRaises(DataError): validate_season(season,kind)

    def test_no_mixed_season_type(self):
        with self.assertRaises(DataError): validate_bundle(fixture(),'2024-25','Playoffs')

    def test_wrong_source_mode_rejected(self):
        b=fixture(); b['sources']['P_BASE']['per_mode']='PerGame'
        with self.assertRaises(DataError): validate_bundle(b,'2024-25','Regular Season')

    def test_source_timezone_required(self):
        b=fixture(); b['sources']['P_BASE']['retrieved_at']='2026-10-11T00:00:00'
        with self.assertRaises(DataError): validate_bundle(b,'2024-25','Regular Season')

    def test_team_stint_scope_cannot_be_guessed(self):
        with self.assertRaises(DataError): validate_bundle(fixture(),'2024-25','Regular Season',9001)

    def test_hash_mismatch_rejected(self):
        b=fixture(); b['sources']['P_BASE']['sha256_rows']='bad'
        with self.assertRaises(DataError): validate_bundle(b,'2024-25','Regular Season')

    def test_chinese_alias_and_id(self):
        rows=[{'PLAYER_ID':1,'PLAYER_NAME':'Anthony Edwards'}]
        self.assertEqual(resolve_player(rows,'\u7231\u5fb7\u534e\u5179',None),(1,'Anthony Edwards'))

    def test_unicode_accents(self):
        rows=[{'PLAYER_ID':1,'PLAYER_NAME':'Nikola Joki\u0107'}]
        self.assertEqual(resolve_player(rows,'Nikola Jokic',None)[0],1)

    def test_ambiguous_name_rejected(self):
        rows=[{'PLAYER_ID':1,'PLAYER_NAME':'A Edwards'},{'PLAYER_ID':2,'PLAYER_NAME':'B Edwards'}]
        with self.assertRaises(DataError): resolve_player(rows,'Edwards',None)

    def test_name_id_disagreement_rejected(self):
        rows=[{'PLAYER_ID':1,'PLAYER_NAME':'Alpha'},{'PLAYER_ID':2,'PLAYER_NAME':'Beta'}]
        with self.assertRaises(DataError): resolve_player(rows,'Alpha',2)

    def test_total_row_not_double_counted(self):
        rows=[{'PLAYER_ID':1,'TEAM_ID':9001},{'PLAYER_ID':1,'TEAM_ID':9002},{'PLAYER_ID':1,'TEAM_ID':0}]
        self.assertEqual(player_row(rows,1)['TEAM_ID'],0)
        with self.assertRaises(DataError): player_row(rows[:2],1)


class NetworkContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.path=Path(self.tmp.name)
        self.calls=[]

    def tearDown(self): self.tmp.cleanup()

    def transport(self,module,cls,params,timeout):
        self.calls.append((module,cls,params,timeout))
        return {'resultSets':[{'name':cls,'headers':['PLAYER_ID','PLAYER_NAME','TEAM_ID'],'rowSet':[[1,'Mock Player',9001]]}]}, params

    def fetcher(self,**kwargs):
        return Fetcher(self.path,transport=self.transport,sleep=lambda _:None,**kwargs)

    def test_cache_avoids_repeated_network(self):
        f=self.fetcher()
        a,s=f.table('player_base','2024-25','Regular Season')
        b,t=f.table('player_base','2024-25','Regular Season')
        self.assertEqual(a,b); self.assertEqual(len(self.calls),1)
        self.assertTrue(t['from_cache']); self.assertEqual(s['retrieved_at'],t['retrieved_at'])

    def test_cache_separates_season_type(self):
        f=self.fetcher()
        f.table('player_base','2024-25','Regular Season')
        f.table('player_base','2024-25','Playoffs')
        self.assertEqual(len(self.calls),2)

    def test_offline_missing_never_calls_network(self):
        with self.assertRaises(DataError): self.fetcher(offline=True).table('player_base','2024-25','Regular Season')
        self.assertEqual(len(self.calls),0)

    def test_stale_cache_retains_original_timestamp(self):
        self.fetcher().table('player_base','2024-25','Regular Season')
        path=next(self.path.glob('*.json')); record=read_json(path)
        record['source']['retrieved_at']='2000-01-01T00:00:00+00:00'; write_json(path,record)
        _,source=self.fetcher(offline=True).table('player_base','2024-25','Regular Season')
        self.assertTrue(source['stale'])
        self.assertEqual(source['retrieved_at'],'2000-01-01T00:00:00+00:00')
        self.assertEqual(len(self.calls),1)

    def test_tampered_cache_fails_offline(self):
        self.fetcher().table('player_base','2024-25','Regular Season')
        path=next(self.path.glob('*.json')); record=read_json(path)
        record['rows'][0]['PLAYER_ID']=2;write_json(path,record)
        with self.assertRaises(DataError): self.fetcher(offline=True).table('player_base','2024-25','Regular Season')

    def test_optional_endpoint_failure_becomes_missing(self):
        def limited(module,cls,params,timeout):
            if params.get('measure_type_detailed_defense')=='Advanced': raise DataError('Unavailable optional table')
            return self.transport(module,cls,params,timeout)
        f=Fetcher(self.path,transport=limited,sleep=lambda _:None)
        b=f.collect('2024-25','Regular Season')
        self.assertEqual(b['sources']['P_ADV']['status'],'missing')
        self.assertTrue(b['tables']['player_base'])

    def test_required_endpoint_failure_is_fatal(self):
        def missing(*args): raise DataError('No base data')
        f=Fetcher(self.path,transport=missing,sleep=lambda _:None)
        with self.assertRaises(DataError): f.collect('2024-25','Regular Season')

    def test_retries_are_bounded(self):
        attempts=[]
        def failing(*args): attempts.append(1); raise TimeoutError('timeout')
        f=Fetcher(self.path,retries=2,transport=failing,sleep=lambda _:None)
        with self.assertRaises(DataError): f.table('player_base','2024-25','Regular Season')
        self.assertEqual(len(attempts),3)

    def test_scope_parameters(self):
        f=self.fetcher()
        f.table('player_base','2024-25','Regular Season',9001)
        self.assertEqual(self.calls[-1][2]['team_id_nullable'],9001)
        self.assertEqual(self.calls[-1][2]['league_id_nullable'],'00')
        f.table('team_base','2024-25','Regular Season',9001)
        self.assertNotIn('team_id_nullable',self.calls[-1][2])
        f.table('tracking_catchshoot','2024-25','Regular Season')
        self.assertEqual(self.calls[-1][2]['player_or_team'],'Player')
        self.assertEqual(self.calls[-1][2]['pt_measure_type'],'CatchShoot')
        self.assertEqual(self.calls[-1][2]['per_mode_simple'],'PerGame')

    def test_parser_detects_schema_changes(self):
        with self.assertRaises(DataError): unpack_rows({'resultSets':[]},'Expected')
        with self.assertRaises(DataError): unpack_rows({'resultSets':[{'name':'X','headers':['A','B'],'rowSet':[[1]]}]},'X')

    def test_incompatible_offline_refresh(self):
        with self.assertRaises(DataError): self.fetcher(offline=True,refresh=True)


class WorkflowTests(unittest.TestCase):
    def test_complete_offline_evidence_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            out=Path(tmp)/'run'
            args=parser().parse_args(['--player','MVP Demo Guard','--season','2024-25','--input',str(ROOT/'examples/demo_bundle.json'),'--out',str(out)])
            self.assertEqual(run(args),out)
            for name in ('analysis.json','data_bundle.json','metrics.csv','sources.json','evidence.md','writing_brief.md','report.template.md','claims.template.json'):
                self.assertTrue((out/name).exists(),name)
            self.assertFalse((out/'report.md').exists())
            with self.assertRaises(DataError): run(args)

    def report_case(self):
        analysis=analyze(fixture(),request())
        statement='The synthetic fixture has TS ' + metric_map(analysis)['TS_PCT']['display'] + '.'
        report='# SYNTHETIC TEST REPORT\n\n## Finding\n'+statement+' [P_BASE]\n\n## Creation\nNot assessed.\n\n## Defense\nNot assessed.\n\n## Fit\nConditional only.\n'
        claims={'schema_version':'0.1.0','data_kind':'synthetic','claims':[
          {'id':'C1','kind':'fact','report_quote':statement,'metric_ids':['TS_PCT'],'source_ids':['P_BASE'],
           'confidence':'high','caveats':['Synthetic fixture, not basketball evidence'],
           'numeric_facts':[{'metric_id':'TS_PCT','value':metric_map(analysis)['TS_PCT']['value']}]}]}
        return report,claims,analysis

    def test_report_checker_accepts_registered_facts(self):
        report,claims,analysis=self.report_case()
        self.assertEqual(validate(report,claims,analysis,min_chars=0)['status'],'pass')

    def test_report_checker_rejects_wrong_declared_number(self):
        report,claims,analysis=self.report_case()
        claims['claims'][0]['numeric_facts'][0]['value']=.7
        self.assertEqual(validate(report,claims,analysis,min_chars=0)['status'],'fail')

    def test_report_checker_rejects_missing_source(self):
        report,claims,analysis=self.report_case()
        report += '\n[P_UNKNOWN]\n'
        self.assertEqual(validate(report,claims,analysis,min_chars=0)['status'],'fail')

    def test_observation_requires_locator(self):
        report,claims,analysis=self.report_case()
        claims['claims'][0]['kind']='observation'
        self.assertEqual(validate(report,claims,analysis,min_chars=0)['status'],'fail')

    def test_synthetic_disclosure_required(self):
        report,claims,analysis=self.report_case()
        report=report.replace('SYNTHETIC','EXAMPLE')
        self.assertEqual(validate(report,claims,analysis,min_chars=0)['status'],'fail')

    def test_no_template_as_final_article(self):
        report,claims,analysis=self.report_case()
        self.assertEqual(validate(report+'\nNOT_FINAL',claims,analysis,min_chars=0)['status'],'fail')


if __name__=='__main__': unittest.main()
