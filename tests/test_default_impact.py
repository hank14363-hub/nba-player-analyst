import copy,json,sys,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from default_impact import collect
from run_analysis import parser,run
from calculate_metrics import analyze
from editorial_audit import audit

class DefaultImpactTests(unittest.TestCase):
    def setUp(self):
        self.case=ROOT/'examples/cade-cunningham-2024-25-official-v081'
        self.b=json.loads((self.case/'data_bundle.json').read_text(encoding='utf-8'));self.b.pop('impact_data',None)
        self.b['sources']={k:v for k,v in self.b['sources'].items() if v.get('source_type')!='impact_data'}
        self.calls=[]
    def get(self,url,timeout):
        self.calls.append(url)
        if 'dunksandthrees' in url:return SimpleNamespace(status_code=403,url=url,content=b'')
        name='impact_bref.html' if 'basketball-reference' in url else 'impact_lebron_rows.json' if 'nbarapm' in url else 'impact_darko_history.html'
        return SimpleNamespace(status_code=200,url=url,content=(self.case/'raw'/name).read_bytes())
    def collect(self,**kw):return collect(self.b,1630595,'Cade Cunningham',get=self.get,**kw)
    def test_default_flags(self):self.assertTrue(parser().parse_args(['--season','2025-26']).impact)
    def test_explicit_optout(self):self.assertFalse(parser().parse_args(['--season','2025-26','--no-impact']).impact)
    def test_actual_snapshots_identity_model_validation(self):
        b,a,raw=self.collect();self.assertEqual(a['validated_families'],['BREF','LEBRON']);self.assertEqual(len(self.calls),3);self.assertEqual(a['requests'][-1]['category'],'access_restricted');self.assertNotIn('DARKO',[r['family'] for r in a['requests']])
        x=analyze(b,dict(player_id=1630595,season='2024-25',season_type='Regular Season',team_id=0));self.assertEqual(next(m['value'] for m in x['metrics'] if m['metric_id']=='IMPACT_BPM'),3.9)
    def test_explicit_historical_darko_only(self):
        _,a,_=self.collect(cutoff='2025-04-13');self.assertIn('DARKO',a['validated_families'])
    def test_all_failures_preserve_base(self):
        def fail(*args,**kw):raise TimeoutError('Injected network timeout')
        b,a,_=collect(self.b,1630595,'Cade Cunningham',get=fail);self.assertEqual(b['tables'],self.b['tables']);self.assertNotIn('impact_data',b);self.assertEqual(a['status'],'unavailable')
    def test_other_player_never_uses_cade(self):
        _,a,_=collect(self.b,1630595,'LeBron James',get=self.get);self.assertEqual(a['validated_families'],[])
    def test_wrong_year_rejected(self):
        self.b['season']='2025-26';_,a,_=self.collect();self.assertNotIn('LEBRON',a['validated_families'])
    def test_stint_no_fullseason_proxy(self):
        self.b['player_team_id']=1610612765;_,a,_=self.collect();self.assertEqual(a['status'],'scope_excluded');self.assertFalse(self.calls)
    def test_pipeline_default_collects_and_saves_snapshots(self):
        with tempfile.TemporaryDirectory() as t:
            args=parser().parse_args(['--player-id','1630595','--season','2024-25','--out',t])
            with patch('run_analysis.Fetcher.collect',return_value=self.b),patch.dict(sys.modules,{'requests':SimpleNamespace(get=self.get)}):run(args)
            self.assertTrue((Path(t)/'impact_collection_audit.json').exists());self.assertTrue((Path(t)/'raw/default_impact_bref.html').exists())
    def test_import_never_implicitly_uses_network(self):
        with tempfile.TemporaryDirectory() as t:
            inp=Path(t)/'input.json';inp.write_text(json.dumps(self.b),encoding='utf-8');out=Path(t)/'out'
            with patch('default_impact.collect',side_effect=AssertionError('Unexpected network')):run(parser().parse_args(['--input',str(inp),'--player-id','1630595','--season','2024-25','--out',str(out)]))
            self.assertEqual(json.loads((out/'analysis.json').read_text(encoding='utf-8'))['request']['impact_policy'],'retained_only')
    def test_impact_collected_but_not_written_flagged(self):
        b,_,_=self.collect();a=analyze(b,dict(player_id=1630595,season='2024-25',season_type='Regular Season',team_id=0));codes=[f['code'] for f in audit({'dimensions':[]},a,{'claims':[]},b)['findings']];self.assertIn('impact_unwritten',codes)
    def test_old_missing_attempt_flagged(self):
        a=analyze(self.b,dict(player_id=1630595,season='2024-25',season_type='Regular Season',team_id=0));self.assertIn('impact_not_attempted',[f['code'] for f in audit({'dimensions':[]},a,{'claims':[]},self.b)['findings']])

if __name__=='__main__':unittest.main()
