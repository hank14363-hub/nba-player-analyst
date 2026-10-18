"""Synthetic contract/disclosure tests, independent of real historical EPM readings."""
import copy
import csv
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
from common import DataError, digest, read_json
from historical_epm import (FAMILY, NOTE, SID, prepare_import, select, validate_import,
                            validate_files, sha, selection_bytes)
from calculate_metrics import analyze
from impact_visuals import impact_visuals
from render_research_book import Book
from book_sources import source_index
from player_comparisons import limitations
from validate_report import validate as validate_report
from retained_raw import verify_retained, copy_retained
from run_analysis import render_assets

PID = 999999999


class HistoricalEpmTests(unittest.TestCase):
    def setUp(self):
        self.base = read_json(ROOT/'examples/demo_output/data_bundle.json')
        self.base['sources']['P_BASE']['sha256_rows'] = digest(self.base['tables']['player_base'])
        embedded = dict(player_id=PID, player_name='MVP Demo Guard', season=2025,
                        game_dt='2025-06-13', tot=2.5, off=3, **{'def':-.5})
        self.rows = [dict(nba_player_id=str(PID), player_name='MVP Demo Guard', season='2025',
                         game_dt='2025-06-13', epm_tot='2.5', epm_off='3', epm_def='-0.5',
                         source='dunksandthrees.com/player/eskills', raw=json.dumps(embedded),
                         n='589', n_rapm='588', tot_rk='3', scraped_at='2026-08-05 18:01:08')]

    def payload(self):
        stream = io.StringIO(newline=''); writer = csv.DictWriter(stream, fieldnames=list(self.rows[0]))
        writer.writeheader(); writer.writerows(self.rows)
        return stream.getvalue().encode()

    def make(self, **kwargs):
        payload = self.payload()
        with patch('historical_epm.CSV_SHA', sha(payload)):
            return prepare_import(self.base, PID, payload, '2026-10-17T10:11:45+00:00', **kwargs)[0]

    def analyze(self, bundle=None):
        b = bundle or self.make()
        with patch('historical_epm.CSV_SHA', b['historical_epm_import']['snapshot']['files'][0]['sha256_raw']):
            return analyze(b,dict(player_id=PID,season='2024-25',season_type='Regular Season',team_id=0,comparisons=False,impact_policy='retained_only',words=2500,question='Synthetic fixture only'))

    def check(self, b):
        with patch('historical_epm.CSV_SHA', b['historical_epm_import']['snapshot']['files'][0]['sha256_raw']):
            validate_import(b)

    def write(self, root, b=None):
        b = b or self.make(); snap = b['historical_epm_import']['snapshot']
        (root/'raw').mkdir(parents=True)
        (root/'raw/historical_epm_export.csv').write_bytes(self.payload())
        (root/'raw/historical_epm_metadata.json').write_bytes((json.dumps(snap['metadata'],ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode())
        (root/'raw/historical_epm_selection.json').write_bytes(selection_bytes(snap))
        return b

    def test_separate_metric_ids_with_scope_and_date_notes(self):
        a = self.analyze(); m = {r['metric_id']:r for r in a['metrics']}
        self.assertEqual([m[k]['value'] for k in ('IMPACT_EPM_HIST','IMPACT_O_EPM_HIST','IMPACT_D_EPM_HIST')],[2.5,3,-.5])
        self.assertNotIn('IMPACT_EPM',m)
        for k in ('IMPACT_EPM_HIST','IMPACT_O_EPM_HIST','IMPACT_D_EPM_HIST'):
            self.assertIn('口径待核验',m[k]['label'])
            self.assertEqual(m[k]['snapshot_date'],'2025-06-13')
            self.assertEqual(m[k]['verification_status'],'archived_reading_only_scope_unverified')

    def test_no_gp_or_minutes_invented(self):
        d = self.analyze()['impact_context']['datasets'][0]
        self.assertIsNone(d['sample']['GP']); self.assertIsNone(d['sample']['MIN'])
        self.assertEqual(d['estimate_type'],'historical_snapshot_unverified')

    def test_actual_epm_and_historical_reading_can_coexist(self):
        from import_epm import prepare_import as actual_prepare
        meta=dict(schema_version='0.1.0',source_url='https://dunksandthrees.com/epm/actual?season=2025',
                  exported_at='2026-10-17T10:00:00+00:00',estimate_type='actual',league='NBA',season='2024-25',
                  season_type='Regular Season',sample_scope='full_season',minutes_unit='total',minutes_decimals=0,
                  season_format='nba',model_version='SYNTHETIC ONLY',
                  columns={k:k for k in ('nba_id','player_name','season','games','minutes','tot','off','def')})
        row=dict(nba_id=PID,player_name='MVP Demo Guard',season='2024-25',games=60,minutes=1800,tot=1.5,off=2,**{'def':-.5})
        self.base=actual_prepare(self.base,PID,json.dumps([row]).encode(),'json',json.dumps(meta).encode())
        a=self.analyze();m={r['metric_id']:r for r in a['metrics']}
        self.assertEqual(m['IMPACT_EPM']['value'],1.5)
        self.assertEqual(m['IMPACT_EPM_HIST']['value'],2.5)
        self.assertEqual(set(impact_visuals(a)),{'impact_retrospective','impact_historical'})

    def test_history_chart_never_in_actual_or_prediction_chart(self):
        visuals = impact_visuals(self.analyze())
        self.assertEqual(set(visuals),{'impact_historical'})
        self.assertIn('口径待核验',visuals['impact_historical']['svg'])
        self.assertIn('2025-06-13',visuals['impact_historical']['svg'])

    def test_book_note_visible_and_source_scope_not_mislabeled(self):
        a = self.analyze()
        text = Book(a,{'claims':[]},{},'').impacts()+source_index(a)
        self.assertIn('历史快照 · 口径待核验',text)
        self.assertIn('缺少可核验的场次及总分钟',text)
        self.assertNotIn('2025-06-13 历史预测',text)
        self.assertNotIn('生涯加权预测；不声称与单季分钟完全对应',text)

    def test_evidence_and_writing_brief_contain_note(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp); render_assets(root,self.analyze())
            self.assertIn('口径待核验',(root/'evidence.md').read_text(encoding='utf-8'))
            self.assertIn(NOTE,(root/'writing_brief.md').read_text(encoding='utf-8'))

    def test_missing_actual_still_disclosed(self):
        text = ' '.join(limitations(self.analyze()))
        self.assertIn('整季Actual EPM',text)
        self.assertIn('仍缺失',text)

    def test_unknown_original_file_rejected(self):
        with self.assertRaisesRegex(DataError,'reviewed Kaggle v1'):
            prepare_import(self.base,PID,self.payload(),'2026-10-17T10:00:00+00:00')

    def test_duplicate_candidates_require_explicit_source(self):
        self.rows.append(dict(self.rows[0],source='dunksandthrees.com/epm'))
        with self.assertRaisesRegex(DataError,'exactly one row'): self.make()
        b = self.make(source='dunksandthrees.com/epm')
        self.assertEqual(b['historical_epm_import']['snapshot']['raw_row']['source'],'dunksandthrees.com/epm')

    def test_duplicate_same_source_requires_explicit_date(self):
        row = copy.deepcopy(self.rows[0]); row['game_dt']='2025-04-13'
        embedded=json.loads(row['raw']); embedded['game_dt']=row['game_dt']; row['raw']=json.dumps(embedded)
        self.rows.append(row)
        with self.assertRaises(DataError): self.make()
        self.assertEqual(self.make(snapshot_date='2025-04-13')['impact_data']['datasets'][0]['cutoff'],'2025-04-13')

    def test_identical_duplicate_rows_not_silently_deduplicated(self):
        self.rows.append(copy.deepcopy(self.rows[0]))
        with self.assertRaises(DataError): self.make(source=self.rows[0]['source'],snapshot_date='2025-06-13')

    def test_wrong_name_rejected(self):
        self.rows[0]['player_name']='Other Synthetic Player'
        with self.assertRaisesRegex(DataError,'exact name'): self.make()

    def test_unknown_player_not_guessed(self):
        self.rows[0]['nba_player_id']=str(PID+1)
        with self.assertRaises(DataError): self.make()

    def test_other_year_not_retagged(self):
        self.rows[0]['season']='2024'
        with self.assertRaises(DataError): self.make()

    def test_embedded_values_mismatch_rejected(self):
        self.rows[0]['epm_tot']='9'
        with self.assertRaisesRegex(DataError,'retained provider JSON'): self.make()

    def test_component_sum_mismatch_rejected(self):
        self.rows[0]['epm_tot']='9'
        r=json.loads(self.rows[0]['raw']);r['tot']=9;self.rows[0]['raw']=json.dumps(r)
        with self.assertRaisesRegex(DataError,'components fail'): self.make()

    def test_embedded_date_mismatch_rejected(self):
        r=json.loads(self.rows[0]['raw']);r['game_dt']='2025-04-13';self.rows[0]['raw']=json.dumps(r)
        with self.assertRaisesRegex(DataError,'identity/date'): self.make()

    def test_unknown_upstream_source_rejected(self):
        self.rows[0]['source']='example.com/epm'
        with self.assertRaises(DataError): self.make()

    def test_no_model_rank_imported(self):
        self.assertNotIn('tot_rk',self.make()['impact_data']['datasets'][0]['raw_rows'][0])

    def test_missing_timezone_rejected(self):
        with patch('historical_epm.CSV_SHA',sha(self.payload())):
            with self.assertRaises(DataError): prepare_import(self.base,PID,self.payload(),'2026-10-17T10:00:00')

    def test_note_removed_from_dataset_rejected_on_replay(self):
        b=self.make();b['impact_data']['datasets'][0]['caveats']=[]
        with self.assertRaisesRegex(DataError,'mandatory disclosure'): self.check(b)

    def test_note_removed_from_source_rejected_on_replay(self):
        b=self.make();b['sources'][SID]['usage']='cleaned'
        with self.assertRaises(DataError): self.check(b)

    def test_metadata_scope_upgraded_rejected(self):
        b=self.make();s=b['historical_epm_import']['snapshot'];s['metadata']['sample_scope']='full_season'
        s['snapshot_sha256']=sha(selection_bytes(s))
        with self.assertRaises(DataError): self.check(b)

    def test_original_file_carried_and_reverified(self):
        with tempfile.TemporaryDirectory() as tmp:
            origin=Path(tmp)/'origin';dest=Path(tmp)/'destination';b=self.write(origin)
            with patch('historical_epm.CSV_SHA',sha(self.payload())):
                copy_retained(b,origin,dest);verify_retained(b,dest)
            self.assertEqual((dest/'raw/historical_epm_export.csv').read_bytes(),self.payload())

    def test_missing_raw_file_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'origin';b=self.write(root)
            (root/'raw/historical_epm_export.csv').unlink()
            with patch('historical_epm.CSV_SHA',sha(self.payload())):
                with self.assertRaises(DataError): verify_retained(b,root)

    def test_original_row_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/'origin';b=self.write(root)
            (root/'raw/historical_epm_export.csv').write_bytes(self.payload()+b'\n')
            with patch('historical_epm.CSV_SHA',sha(self.payload())):
                with self.assertRaises(DataError): verify_retained(b,root)

    def test_quote_without_nearby_note_fails_report_validation(self):
        a=self.analyze();q='归档读数为2.5。';report=q+' [EXT_IMPACT_EPM_HISTORICAL]'
        c=dict(schema_version='0.1.0',data_kind='synthetic',claims=[dict(id='H1',kind='fact',report_quote=q,
               metric_ids=['IMPACT_EPM_HIST'],source_ids=[SID],confidence='moderate',caveats=[NOTE],
               numeric_facts=[dict(metric_id='IMPACT_EPM_HIST',value=2.5)])])
        errors=validate_report(report,c,a,0)['errors']
        self.assertTrue(any('historical EPM requires' in e for e in errors))
        c['claims'][0]['report_quote']='历史EPM快照（口径待核验）的归档读数为2.5。'
        report=c['claims'][0]['report_quote']+' [EXT_IMPACT_EPM_HISTORICAL]'
        self.assertFalse(any('historical EPM requires' in e for e in validate_report(report,c,a,0)['errors']))

    def test_double_import_refused(self):
        b=self.make()
        with patch('historical_epm.CSV_SHA',sha(self.payload())):
            with self.assertRaisesRegex(DataError,'already present'):
                prepare_import(b,PID,self.payload(),'2026-10-17T10:00:00+00:00')


if __name__=='__main__': unittest.main()
