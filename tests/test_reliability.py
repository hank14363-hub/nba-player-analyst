import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from common import DataError, DATA_SCHEMA_VERSION, RELEASE_VERSION, VERSION
from fetch_data import Fetcher, FetchError
from collect_impact import parse_bref, parse_darko, validate_provider_rows, ProviderError
from repair_plan import plan, command
from check_release import check
from review_language import load_rules, review_text
from run_analysis import parser, run, main

class HTTPFailure(Exception):
    def __init__(self,code,headers=None):self.response=SimpleNamespace(status_code=code,headers=headers or {})

class ReliabilityTests(unittest.TestCase):
    def fetcher(self,path):return Fetcher(Path(path),sleep=lambda _:None,jitter=lambda lo,hi:hi)

    def test_release_and_schema_distinct(self):self.assertEqual(VERSION,DATA_SCHEMA_VERSION);self.assertEqual(RELEASE_VERSION,json.loads((ROOT/'PACKAGE_INFO.json').read_text(encoding='utf-8'))['release_version']);self.assertEqual(VERSION,'0.1.0')
    def test_release_labels(self):self.assertEqual(check()['status'],'pass')
    def test_renderer_uses_current_release(self):
        from render_research_book import APP_VERSION
        self.assertEqual(APP_VERSION,RELEASE_VERSION)
    def test_historical_poster_keeps_render_parity(self):
        from validate_poster import check as poster_check
        p=poster_check(ROOT/'examples/cade-cunningham-2024-25-official-v081');self.assertEqual(p['status'],'pass',p['errors']);self.assertTrue(p['render_parity'])
    def test_release_mismatch_detected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)
            for name in ('README.md','SKILL.md','PACKAGE_INFO.json'):(p/name).write_bytes((ROOT/name).read_bytes())
            (p/'README.md').write_text('# NBA Player Analyst v0.1.0',encoding='utf-8');self.assertEqual(check(p)['status'],'fail')

    def test_actual_bref_snapshot_replay(self):
        rows=parse_bref((ROOT/'examples/cade-cunningham-2024-25-official-v081/raw/impact_bref.html').read_bytes());validate_provider_rows('BREF',rows)
        r=next(r for r in rows if r['provider_player_key']=='cunnica01');self.assertEqual(r['bpm'],'3.9');self.assertEqual(len(rows),735)

    def test_actual_darko_snapshot_replay(self):
        rows=parse_darko((ROOT/'examples/cade-cunningham-2024-25-official-v081/raw/impact_darko_history.html').read_bytes(),'2025-04-13','2024-25');validate_provider_rows('DARKO',rows)
        r=next(r for r in rows if r['nba_id']==1630595);self.assertEqual(r['dpm'],'+1.8');self.assertEqual(len(rows),50)

    def test_table_structure_change_category(self):
        with self.assertRaises(ProviderError) as c:parse_bref('<table id="changed"></table>')
        self.assertEqual(c.exception.category,'schema_changed')

    def test_required_field_structure_change(self):
        with self.assertRaises(ProviderError) as c:validate_provider_rows('DARKO',[dict(nba_id=2544)])
        self.assertEqual(c.exception.category,'schema_changed')

    def test_wrong_historical_date_category(self):
        with self.assertRaises(ProviderError) as c:parse_darko('<html>Current season only</html>','2025-04-13','2024-25')
        self.assertEqual(c.exception.category,'sample_unavailable')

    def test_timeout_backoff_has_bounded_jitter(self):
        f=self.fetcher('.');self.assertEqual(f.retry_delay(TimeoutError(),0),2);self.assertEqual(f.retry_delay(TimeoutError(),4),8)

    def test_429_missing_header_stops(self):self.assertIsNone(self.fetcher('.').retry_delay(HTTPFailure(429),0))
    def test_429_short_retry_after_respected(self):self.assertEqual(self.fetcher('.').retry_delay(HTTPFailure(429,{'Retry-After':'3'}),0),3.5)
    def test_429_long_retry_after_stops(self):self.assertIsNone(self.fetcher('.').retry_delay(HTTPFailure(429,{'Retry-After':'120'}),0))
    def test_invalid_retry_after_stops(self):self.assertIsNone(self.fetcher('.').retry_delay(HTTPFailure(429,{'Retry-After':'nonsense'}),0))
    def test_access_denied_never_retries(self):self.assertIsNone(self.fetcher('.').retry_delay(HTTPFailure(403),0))

    def test_429_actual_attempts_bounded(self):
        with tempfile.TemporaryDirectory() as t:
            calls=[]
            def transport(*args):calls.append(1);raise HTTPFailure(429,{'Retry-After':'0'})
            f=Fetcher(Path(t),retries=2,transport=transport,sleep=lambda _:None,jitter=lambda lo,hi:lo)
            with self.assertRaises(FetchError):f.table('player_base','2024-25','Regular Season')
            self.assertEqual(len(calls),3)

    def data(self):
        b=json.loads((ROOT/'examples/cade-cunningham-2024-25-official-v081/data_bundle.json').read_text(encoding='utf-8'))
        a=json.loads((ROOT/'examples/cade-cunningham-2024-25-official-v081/analysis.json').read_text(encoding='utf-8'));return b,a

    def test_missing_table_repair_command(self):
        b,a=self.data();b['tables']['player_scoring']=[];p=plan(b,a,Path('test-output'));self.assertEqual(p['commands'][0]['table'],'player_scoring');self.assertIn('--tables',p['commands'][0]['argv']);self.assertFalse(p['automatic_execution'])

    def test_onoff_needs_verified_team(self):
        b,a=self.data();b['tables']['player_onoff']=[];a['request'].pop('on_off_team_id',None);self.assertTrue(plan(b,a,Path('test-output'))['blocked'])

    def test_onoff_command_includes_ids(self):
        b,a=self.data();b['tables']['player_onoff']=[];a['request']['on_off_team_id']=1610612765;argv=plan(b,a,Path('test-output'))['commands'][0]['argv'];self.assertIn('1630595',argv);self.assertIn('1610612765',argv)

    def test_retained_import_not_mixed(self):
        b,a=self.data();b['sumitro_import']={};b['tables']['player_scoring']=[];p=plan(b,a,Path('test-output'));self.assertFalse(p['commands']);self.assertTrue(p['blocked'])

    def test_command_quote_is_literal(self):self.assertEqual(command(['python',"O'Brien $x;file"]),"& 'python' 'O''Brien $x;file'")

    def test_pipeline_writes_repair_artifacts(self):
        with tempfile.TemporaryDirectory() as t:
            b,_=self.data();b.pop('impact_data',None)
            b['sources']={k:v for k,v in b['sources'].items() if v.get('source_type')!='impact_data'}
            b['tables']['player_scoring']=[];b['sources']['P_SCORE']=dict(status='missing',reason='Timeout')
            input_path=Path(t)/'input.json';input_path.write_text(json.dumps(b),encoding='utf-8');out=Path(t)/'evidence'
            run(parser().parse_args(['--input',str(input_path),'--season','2024-25','--player-id','1630595','--out',str(out)]))
            p=json.loads((out/'repair_commands.json').read_text(encoding='utf-8'));self.assertEqual(p['commands'][0]['table'],'player_scoring');self.assertTrue((out/'repair_commands.md').is_file())
            s=json.loads((out/'sources.json').read_text(encoding='utf-8'));self.assertEqual(s['producer_release'],RELEASE_VERSION);self.assertEqual(s['version'],'0.1.0')

    def test_fatal_base_fetch_writes_retry_diagnostic(self):
        with tempfile.TemporaryDirectory() as t:
            out=Path(t)/'failed'
            argv=['run_analysis.py','--season','2024-25','--player-id','1630595','--out='+str(out)]
            with patch('sys.argv',argv),patch('run_analysis.run',side_effect=FetchError('timeout',3)):
                self.assertEqual(main(),2)
            p=json.loads((out/'fetch_failure.json').read_text(encoding='utf-8'));self.assertEqual(p['category'],'timeout');self.assertEqual(p['attempts'],3);self.assertFalse(p['automatic_execution']);self.assertIn('--out='+str(out.with_name('failed-retry').resolve()),p['argv'])

    def test_language_rules_loaded_from_json(self):self.assertTrue(load_rules()['jargon']);self.assertTrue(review_text('他全面碾压对手。'))
    def test_bad_language_rules_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            p=Path(t)/'rules.json';p.write_text('{"schema_version":"0.1.0","jargon":[],"terms":{}}',encoding='utf-8')
            with self.assertRaises(DataError):load_rules(p)

if __name__=='__main__':unittest.main()
