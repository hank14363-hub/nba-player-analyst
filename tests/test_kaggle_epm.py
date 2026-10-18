"""Synthetic Kaggle acquisition-profile checks; real-file acceptance is separately audited."""
import argparse
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import DataError, digest, read_json
from import_epm import prepare_import, sha, validate_import, validate_metadata
from import_kaggle_epm import actual_metadata, inspect_file, run

PID = 999999999


class KaggleEpmTests(unittest.TestCase):
    def setUp(self):
        self.base = read_json(ROOT / 'examples/demo_output/data_bundle.json')
        self.base['season'] = '2025-26'
        for source in self.base['sources'].values():
            source['season'] = '2025-26'
        self.base['sources']['P_BASE']['sha256_rows'] = digest(self.base['tables']['player_base'])
        self.row = dict(nba_player_id=str(PID), player_name='MVP Demo Guard', season='2026',
                        gp='60', mp='1800.00', epm_tot='2.5', epm_off='3.0', epm_def='-0.5',
                        source='dunksandthrees.com/epm/actual', seasontype='2',
                        scraped_at='2026-08-05 14:19:48.183688')
        self.embedded = dict(player_id=PID, player_name='MVP Demo Guard', season=2026,
                             gp=60, mp=1800, tot=2.5, off=3.0, **{'def': -.5},
                             seasontype=2, scope_id=0)
        self.meta = actual_metadata(self.row, '2025-26', '2026-10-17T10:11:43+00:00')

    def make(self, pin=True):
        row = dict(self.row, raw=json.dumps(self.embedded))
        data = json.dumps([row]).encode()
        if pin:
            with patch('import_epm.KAGGLE_ACTUAL_SHA', sha(data)):
                return prepare_import(self.base, PID, data, 'json', json.dumps(self.meta).encode())
        return prepare_import(self.base, PID, data, 'json', json.dumps(self.meta).encode())

    def test_verified_profile_labels_secondary_source_and_actual_acquisition_time(self):
        b = self.make()
        s = b['sources']['EXT_IMPACT_EPM']
        self.assertEqual(s['url'], 'https://www.kaggle.com/datasets/deocheng/nba-data-1946-2026')
        self.assertIn('Kaggle', s['display_title'])
        self.assertEqual(s['retrieved_at'], self.meta['acquired_at'])
        self.assertEqual(s['upstream_scraped_at'], self.row['scraped_at'])
        self.assertIn('Kaggle', b['impact_data']['datasets'][0]['caveats'][0])
        from book_sources import source_index
        rendered = source_index(dict(sources={'EXT_IMPACT_EPM': s}, sample=dict(season='2025-26')))
        self.assertIn('提供者模型 · Kaggle转引', rendered)
        self.assertNotIn('提供者模型 · 用户离线导出', rendered)

    def test_original_pin_rejects_unreviewed_bytes(self):
        with self.assertRaisesRegex(DataError, 'reviewed v1 bytes'): self.make(pin=False)

    def test_replay_rejects_source_changed_to_direct_export(self):
        b = self.make()
        snapshot = b['epm_import']['snapshot']
        with patch('import_epm.KAGGLE_ACTUAL_SHA', snapshot['files'][0]['sha256_raw']):
            validate_import(b)
            b['sources']['EXT_IMPACT_EPM']['display_title'] = 'Actual EPM · 用户离线导出'
            with self.assertRaisesRegex(DataError, 'conversion differs'): validate_import(b)

    def test_future_dataset_version_rejected(self):
        self.meta['dataset_version'] = 2
        with self.assertRaises(DataError): self.make()

    def test_old_actual_season_not_fabricated(self):
        self.meta['season'] = '2024-25'
        with self.assertRaises(DataError): validate_metadata(self.meta, '2024-25')

    def test_history_table_cannot_be_relabeled_actual(self):
        self.meta['dataset_file'] = 'csv/public.player_epm.csv'
        with self.assertRaises(DataError): self.make()

    def test_history_row_source_rejected(self):
        self.row['source'] = 'dunksandthrees.com/player/eskills'
        with self.assertRaises(DataError): self.make()

    def test_altered_embedded_total_rejected(self):
        self.embedded['tot'] = 8.5
        with self.assertRaisesRegex(DataError, 'retained provider JSON'): self.make()

    def test_embedded_team_scope_rejected(self):
        self.embedded['scope_id'] = 1
        with self.assertRaises(DataError): self.make()

    def test_competition_type_contradiction_rejected(self):
        self.row['seasontype'] = '4'
        with self.assertRaises(DataError): self.make()

    def test_embedded_competition_type_contradiction_rejected(self):
        self.embedded['seasontype'] = 4
        with self.assertRaises(DataError): self.make()

    def test_embedded_name_mismatch_rejected(self):
        self.embedded['player_name'] = 'Other Synthetic Player'
        with self.assertRaises(DataError): self.make()

    def test_rounding_tolerance_not_relaxed_for_integer_text(self):
        meta = actual_metadata(dict(self.row, mp='1800'), '2025-26', self.meta['acquired_at'])
        self.assertEqual(meta['minutes_decimals'], 2)
        self.meta['minutes_decimals'] = 0
        with self.assertRaises(DataError): self.make()

    def test_minutes_mismatch_still_rejected(self):
        self.row['mp'] = '1800.42'; self.embedded['mp'] = 1800.42
        with self.assertRaisesRegex(DataError, 'minute coverage'): self.make()

    def test_games_mismatch_still_rejected(self):
        self.row['gp'] = '59'; self.embedded['gp'] = 59
        with self.assertRaisesRegex(DataError, 'GP mismatch'): self.make()

    def test_components_mismatch_still_rejected(self):
        self.row['epm_tot'] = '9'; self.embedded['tot'] = 9
        with self.assertRaisesRegex(DataError, 'components fail'): self.make()

    def test_unknown_source_profile_rejected(self):
        self.meta['source_kind'] = 'arbitrary_mirror'
        with self.assertRaises(DataError): self.make()

    def test_no_timezone_in_acquired_at_rejected(self):
        self.meta['acquired_at'] = '2026-10-17T10:00:00'
        with self.assertRaises(DataError): self.make()

    def test_historical_rows_stay_candidates_even_with_consistent_components(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'public.player_epm.csv'
            p.write_text('nba_player_id,player_name,season,epm_tot,epm_off,epm_def,source\n'
                         f'{PID},MVP Demo Guard,2018,2.5,3,-0.5,dunksandthrees.com/player/eskills\n', encoding='utf-8')
            with patch.dict('import_kaggle_epm.FILES', {p.name: sha(p.read_bytes())}):
                result = inspect_file(p, PID, '2017-18')
            row = result['selected_rows'][0]
            self.assertTrue(row['components_consistent'])
            self.assertFalse(row['verified_for_report'])

    def test_missing_actual_rejected_with_audit_no_data_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'public.player_epm.csv'
            p.write_text('nba_player_id,season,epm_tot,epm_off,epm_def,source\n'
                         f'{PID},2026,2.5,3,-0.5,dunksandthrees.com/player/eskills\n', encoding='utf-8')
            ref = Path(tmp) / 'reference.json'; ref.write_text(json.dumps(self.base), encoding='utf-8')
            args = argparse.Namespace(csv_dir=Path(tmp), player_id=PID, season='2025-26',
                        out=Path(tmp) / 'out', import_actual=True, bundle=ref, acquired_at=self.meta['acquired_at'])
            with patch.dict('import_kaggle_epm.FILES', {p.name: sha(p.read_bytes())}):
                audit = run(args)
            self.assertEqual(audit['status'], 'actual_import_rejected')
            self.assertTrue((args.out / 'kaggle_epm_read_audit.json').is_file())
            self.assertFalse((args.out / 'imported/data_bundle.json').exists())


if __name__ == '__main__':
    unittest.main()
