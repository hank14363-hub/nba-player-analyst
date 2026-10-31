"""Direction disclosures and source-specific background concordance invariants."""
import copy
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import test_advanced_percentiles as percentile_fixtures
import test_kaggle_epm as epm_fixtures
from common import DataError,digest
from metric_polarity import describe,acknowledge
from advanced_percentiles import context,other_model_group
from import_epm import normalize_actual_row,prepare_import,sha,validate_import
from epm_population import collect,POLICY


class PolarityTests(unittest.TestCase):
    def test_protocol_preserves_all_numeric_percentiles(self):
        f=percentile_fixtures.AdvancedPercentiles();f.setUp()
        old=context(f.b,f.pid,0,[]);new=context(f.b,f.pid,0,[],protocol='0.2.0')
        for previous,current in zip(old['groups'][0]['entries'],new['groups'][0]['entries']):
            self.assertEqual(previous['percentile'],current['percentile'])
            self.assertEqual(previous['direction'],current['direction'])
            self.assertNotIn('polarity',previous)
            self.assertIn(current['polarity'],{'higher_better','lower_better','role_neutral'})
            self.assertTrue(current['polarity_note'])

    def test_sensitive_metric_definitions(self):
        for mid in ('ADV_NBA_TOV_PCT','ADV_BREF_TOV_PCT','ONCOURT_DEF_RATING'):
            self.assertEqual(describe(mid)['polarity'],'lower_better')
        for mid in ('USG_PCT','ADV_NBA_PACE','IMPACT_EPM_HIST'):
            self.assertEqual(describe(mid)['polarity'],'role_neutral')
        for mid in ('TS_PCT','AST_TOV','IMPACT_EPM','IMPACT_DBPM'):
            self.assertEqual(describe(mid)['polarity'],'higher_better')

    def claim(self):
        entry=describe('ONCOURT_DEF_RATING')
        return dict(metric_ids=['PCTL_ONCOURT_DEF_RATING'],report_quote='这是球队失分，高数值不是优势。'),{'PCTL_ONCOURT_DEF_RATING':entry}

    def test_sensitive_citation_requires_declaration(self):
        claim,entries=self.claim();self.assertTrue(acknowledge(claim,entries))

    def test_visible_matching_declaration_is_accepted(self):
        claim,entries=self.claim()
        claim['percentile_interpretations']=[dict(metric_id='PCTL_ONCOURT_DEF_RATING',polarity='lower_better',disclosure='高数值不是优势')]
        self.assertEqual(acknowledge(claim,entries),[])

    def test_wrong_direction_and_invisible_disclosure_rejected(self):
        claim,entries=self.claim()
        claim['percentile_interpretations']=[dict(metric_id='PCTL_ONCOURT_DEF_RATING',polarity='higher_better',disclosure='不存在的声明')]
        self.assertEqual(len(acknowledge(claim,entries)),2)

    def test_unused_and_duplicate_declarations_rejected(self):
        claim,entries=self.claim();row=dict(metric_id='PCTL_UNKNOWN',polarity='lower_better',disclosure='高数值不是优势')
        claim['percentile_interpretations']=[row,row]
        self.assertGreaterEqual(len(acknowledge(claim,entries)),3)

    def test_higher_metric_needs_no_extra_declaration(self):
        self.assertEqual(acknowledge(dict(metric_ids=['PCTL_TS_PCT']),{'PCTL_TS_PCT':describe('TS_PCT')}),[])


class EpmPopulationTests(unittest.TestCase):
    def setUp(self):
        self.f=epm_fixtures.KaggleEpmTests();self.f.setUp()
        self.b=self.f.make();self.s=self.b['epm_import']['snapshot']
        self.row=self.s['raw_rows'][0];self.base=self.s['reference_player']
        self.pin=patch('import_epm.KAGGLE_ACTUAL_SHA',self.s['files'][0]['sha256_raw']);self.pin.start();self.addCleanup(self.pin.stop)

    def row_minutes(self,minutes):
        row=copy.deepcopy(self.row);row['mp']=minutes
        embedded=json.loads(row['raw']);embedded['mp']=float(minutes);row['raw']=json.dumps(embedded)
        return row

    def normalize(self,row=None,base=None,policy=POLICY):
        return normalize_actual_row(self.s,row or self.row,base or self.base,population_policy=policy)

    def test_strict_target_unchanged_and_still_replays(self):
        before=copy.deepcopy(self.b['impact_data']);validate_import(self.b)
        result=self.normalize();self.assertEqual(result['tot'],before['datasets'][0]['raw_rows'][0]['tot'])
        self.assertEqual(self.b['impact_data'],before)
        with self.assertRaisesRegex(DataError,'minute coverage'):
            self.normalize(self.row_minutes('1800.42'),policy=None)
        self.assertAlmostEqual(self.normalize(self.row_minutes('1800.42'))['minute_match']['absolute_difference'],.42)

    def test_background_boundary_and_precision(self):
        self.assertEqual(self.normalize(self.row_minutes('1802.00000'))['minute_match']['serialized_decimals'],5)
        with self.assertRaises(DataError):self.normalize(self.row_minutes('1802.00001'))
        with self.assertRaisesRegex(DataError,'precision'):self.normalize(self.row_minutes('1800.000001'))

    def test_unknown_policy_rejected(self):
        with self.assertRaisesRegex(DataError,'Unknown'):self.normalize(policy='relaxed')

    def test_name_games_season_and_identity_stay_strict(self):
        for field,value in [('player_name','Other Player'),('gp','59'),('season','2025'),('nba_player_id','123')]:
            row=copy.deepcopy(self.row);row[field]=value
            with self.subTest(field=field),self.assertRaises(DataError):self.normalize(row)

    def test_embedded_json_source_type_and_components_stay_strict(self):
        for field,value in [('scope_id',1),('seasontype',4),('mp',1801),('tot',20)]:
            row=copy.deepcopy(self.row);embedded=json.loads(row['raw']);embedded[field]=value;row['raw']=json.dumps(embedded)
            with self.subTest(field=field),self.assertRaises(DataError):self.normalize(row)
        row=copy.deepcopy(self.row);row['source']='dunksandthrees.com/player/eskills'
        with self.assertRaises(DataError):self.normalize(row)

    def population(self,duplicate=False):
        b=copy.deepcopy(self.f.base);rows=[];reference=[]
        template=b['tables']['player_base'][0]
        for i,delta in enumerate([0,.1,.3,.49,.8,1.2,1.9,2,2.1,4]):
            pid=epm_fixtures.PID+i;name='MVP Demo Guard' if i==0 else 'Synthetic '+str(i)
            reference.append(dict(template,PLAYER_ID=pid,PLAYER_NAME=name))
            row=copy.deepcopy(self.f.row);embedded=copy.deepcopy(self.f.embedded)
            row.update(nba_player_id=str(pid),player_name=name,mp=str(1800+delta))
            embedded.update(player_id=pid,player_name=name,mp=1800+delta)
            row['raw']=json.dumps(embedded);rows.append(row)
        if duplicate:rows.append(copy.deepcopy(rows[1]))
        b['tables']['player_base']=reference;b['sources']['P_BASE']['row_count']=len(reference)
        b['sources']['P_BASE']['sha256_rows']=digest(reference)
        b['sources']['P_BASE'].update(endpoint='leaguedashplayerstats',status='ok',parameters=dict(Season=b['season'],SeasonType=b['season_type'],PerMode='Totals',MeasureType='Base'))
        payload=json.dumps(rows).encode();pin=sha(payload)
        with patch('import_epm.KAGGLE_ACTUAL_SHA',pin):
            bundle=prepare_import(b,epm_fixtures.PID,payload,'json',json.dumps(self.f.meta).encode())
        return bundle,pin

    def test_population_coverage_exclusions_and_sensitivity(self):
        b,pin=self.population()
        with patch('import_epm.KAGGLE_ACTUAL_SHA',pin):
            audit=collect(b)
            dataset=b['impact_data']['datasets'][0]
            old=other_model_group(b,dataset);new=other_model_group(b,dataset,protocol='0.2.0')
        self.assertEqual((len(audit['rows']),len(audit['excluded'])),(8,2))
        self.assertEqual(audit['reference_coverage'],.8)
        self.assertEqual(audit['sensitivity'],{'0.25':2,'0.5':4,'1.0':5,'2.0':8})
        self.assertEqual((old['eligible_count'],new['eligible_count']),(1,8))
        self.assertIsNone(old['entries'][0]['percentile']);self.assertIsNotNone(new['entries'][0]['percentile'])
        self.assertEqual(new['population_audit']['policy'],POLICY)

    def test_duplicate_population_ids_fail_closed(self):
        b,pin=self.population(duplicate=True)
        with patch('import_epm.KAGGLE_ACTUAL_SHA',pin),self.assertRaisesRegex(DataError,'Duplicate'):collect(b)


if __name__=='__main__':unittest.main()
