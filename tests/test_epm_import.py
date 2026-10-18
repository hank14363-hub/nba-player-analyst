"""Synthetic offline EPM contract tests. No real player EPM values or network use."""
import argparse
import copy
import csv
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from common import DataError, digest, read_json, write_json
from import_epm import (SID, build_dataset, parse_rows, prepare_import, run,
                        selection_bytes, sha, validate_files, validate_import)
from calculate_metrics import analyze
from impact_visuals import impact_visuals
from player_comparisons import limitations
from retained_raw import checked_path, verify_retained

PID = 999999999


def metadata():
    return dict(schema_version='0.1.0', source_url='https://dunksandthrees.com/epm/actual?season=2025',
                exported_at='2026-10-15T15:00:00+08:00', estimate_type='actual', league='NBA',
                season='2024-25', season_type='Regular Season', sample_scope='full_season',
                minutes_unit='total', minutes_decimals=0, season_format='nba',
                model_version='SYNTHETIC FIXTURE ONLY; no real export observed',
                columns={k: k for k in ('nba_id', 'player_name', 'season', 'games', 'minutes', 'tot', 'off', 'def')})


def provider_row():
    return dict(nba_id=PID, player_name='MVP Demo Guard', season='2024-25',
                games=60, minutes=1800, tot=2.5, off=3.0, **{'def': -.5})


def payload(rows, file_format):
    if file_format == 'json':
        return json.dumps(rows, ensure_ascii=False).encode('utf-8')
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return stream.getvalue().encode('utf-8-sig')


class EpmImportTests(unittest.TestCase):
    def setUp(self):
        self.base = read_json(ROOT / 'examples/demo_output/data_bundle.json')
        self.rehash_base()
        self.meta = metadata()
        self.rows = [provider_row()]

    def make(self, file_format='json'):
        return prepare_import(self.base, PID, payload(self.rows, file_format), file_format,
                              json.dumps(self.meta).encode('utf-8'), 'synthetic-fixture.' + file_format)

    def analysis(self, bundle=None):
        return analyze(bundle or self.make(), dict(player_id=PID, season='2024-25',
                        season_type='Regular Season', team_id=0, comparisons=False, impact_policy='retained_only'))

    def rehash_base(self):
        self.base['sources']['P_BASE']['sha256_rows'] = digest(self.base['tables']['player_base'])

    def write_import(self, root, bundle=None):
        bundle = bundle or self.make()
        root.mkdir(parents=True, exist_ok=True)
        (root / 'raw').mkdir(exist_ok=True)
        snapshot = bundle['epm_import']['snapshot']
        (root / 'raw/epm_export.json').write_bytes(payload(self.rows, 'json'))
        (root / 'raw/epm_metadata.json').write_bytes(json.dumps(self.meta).encode('utf-8'))
        (root / 'raw/epm_selection.json').write_bytes(selection_bytes(snapshot))
        write_json(root / 'data_bundle.json', bundle)
        return bundle

    def test_json_registers_total_offense_defense_and_coverage(self):
        a = self.analysis()
        m = {m['metric_id']: m for m in a['metrics']}
        self.assertEqual([m[k]['value'] for k in ('IMPACT_EPM', 'IMPACT_O_EPM', 'IMPACT_D_EPM')], [2.5, 3.0, -.5])
        self.assertEqual(m['IMPACT_EPM_GP']['value'], 60)
        self.assertEqual(m['IMPACT_EPM_MIN']['value'], 1800)
        self.assertEqual(a['data_kind'], 'synthetic')

    def test_csv_bom_original_rows_kept_as_strings(self):
        b = self.make('csv')
        self.assertEqual(b['epm_import']['snapshot']['raw_rows'][0]['minutes'], '1800')
        self.assertEqual(self.analysis(b)['impact_context']['datasets'][0]['values']['EPM'], 2.5)

    def test_explicit_column_mapping(self):
        self.rows[0]['provider_name'] = self.rows[0].pop('player_name')
        self.meta['columns']['player_name'] = 'provider_name'
        self.assertEqual(self.analysis()['impact_context']['datasets'][0]['family'], 'EPM')

    def test_end_year_requires_explicit_convention(self):
        self.rows[0]['season'] = 2025
        self.meta['season_format'] = 'end_year'
        self.assertEqual(self.analysis()['sample']['season'], '2024-25')

    def test_wrong_year_convention_rejected(self):
        self.rows[0]['season'] = 2025
        with self.assertRaises(DataError): self.make()

    def test_wrong_season_rejected(self):
        self.rows[0]['season'] = '2023-24'
        with self.assertRaises(DataError): self.make()

    def test_wrong_nba_id_rejected(self):
        self.rows[0]['nba_id'] = PID + 1
        with self.assertRaises(DataError): self.make()

    def test_wrong_name_even_matching_nba_id_rejected(self):
        self.rows[0]['player_name'] = 'MVP Other Guard'
        with self.assertRaises(DataError): self.make()

    def test_abbreviation_not_exact_identity_bridge(self):
        self.rows[0]['player_name'] = 'M. Guard'
        with self.assertRaises(DataError): self.make()

    def test_missing_nba_id_not_guessed_from_name(self):
        self.rows[0].pop('nba_id')
        with self.assertRaises(DataError): self.make()

    def test_duplicate_selected_rows_not_deduplicated_or_summed(self):
        self.rows.append(copy.deepcopy(self.rows[0]))
        with self.assertRaises(DataError): self.make()

    def test_other_players_and_seasons_retained_not_selected(self):
        self.rows.append(dict(self.rows[0], nba_id=PID + 1, player_name='Other Synthetic Player', tot=99))
        self.rows.append(dict(self.rows[0], season='2023-24', tot=99))
        b = self.make()
        self.assertEqual(len(b['epm_import']['snapshot']['raw_rows']), 3)
        self.assertEqual(self.analysis(b)['impact_context']['datasets'][0]['values']['EPM'], 2.5)

    def test_gp_mismatch(self):
        self.rows[0]['games'] = 59
        with self.assertRaises(DataError): self.make()

    def test_fractional_games_rejected(self):
        self.rows[0]['games'] = 59.5
        with self.assertRaises(DataError): self.make()

    def test_minute_mismatch(self):
        self.rows[0]['minutes'] = 1801
        with self.assertRaises(DataError): self.make()

    def test_declared_integer_minute_rounding(self):
        self.base['tables']['player_base'][0]['MIN'] = 1800.49
        self.rehash_base()
        self.assertEqual(self.make()['impact_data']['datasets'][0]['raw_rows'][0]['minutes'], 1800)

    def test_rounding_not_an_arbitrary_relaxed_tolerance(self):
        self.base['tables']['player_base'][0]['MIN'] = 1800.51
        self.rehash_base()
        with self.assertRaises(DataError): self.make()

    def test_decimal_minute_precision_checked(self):
        self.meta['minutes_decimals'] = 2
        self.base['tables']['player_base'][0]['MIN'] = 1800.004
        self.rehash_base()
        self.make()
        self.base['tables']['player_base'][0]['MIN'] = 1800.006
        self.rehash_base()
        with self.assertRaises(DataError): self.make()

    def test_precision_cannot_discard_exported_fractional_minutes(self):
        self.rows[0]['minutes'] = 1800.123
        with self.assertRaises(DataError): self.make()

    def test_per_game_minutes_not_multiplied(self):
        self.meta['minutes_unit'] = 'per_game'
        self.rows[0]['minutes'] = 30
        with self.assertRaises(DataError): self.make()

    def test_predictive_metadata_rejected(self):
        self.meta['estimate_type'] = 'predictive'
        with self.assertRaises(DataError): self.make()

    def test_predictive_original_field_contradiction_rejected(self):
        self.meta['columns']['estimate_type'] = 'estimate_type'
        self.rows[0]['estimate_type'] = 'predictive'
        with self.assertRaises(DataError): self.make()

    def test_playoff_metadata_rejected(self):
        self.meta['season_type'] = 'Playoffs'
        with self.assertRaises(DataError): self.make()

    def test_raw_competition_contradiction(self):
        self.meta['columns']['season_type'] = 'season_type'
        self.rows[0]['season_type'] = 'Playoffs'
        with self.assertRaises(DataError): self.make()

    def test_team_stint_metadata_rejected(self):
        self.meta['sample_scope'] = 'team_stint'
        with self.assertRaises(DataError): self.make()

    def test_non_actual_or_wrong_year_source_url_rejected(self):
        for url in ('https://dunksandthrees.com/epm', 'https://example.com/epm/actual',
                    'https://dunksandthrees.com/epm/actual?season=2024'):
            with self.subTest(url=url):
                self.meta['source_url'] = url
                with self.assertRaises(DataError): self.make()

    def test_missing_explicit_metadata_rejected(self):
        for field in ('exported_at', 'minutes_decimals', 'season_format', 'columns', 'model_version'):
            with self.subTest(field=field):
                self.meta = metadata()
                self.meta.pop(field)
                with self.assertRaises(DataError): self.make()

    def test_export_timestamp_requires_timezone(self):
        self.meta['exported_at'] = '2026-10-15T15:00:00'
        with self.assertRaises(DataError): self.make()

    def test_components_at_point_fifteen_boundary_pass(self):
        self.rows[0]['tot'] = 2.65
        self.make()

    def test_components_beyond_point_fifteen_fail(self):
        self.rows[0]['tot'] = 2.6501
        with self.assertRaises(DataError): self.make()

    def test_missing_component_not_zero_filled(self):
        for key in ('tot', 'off', 'def'):
            with self.subTest(key=key):
                self.rows = [provider_row()]
                self.rows[0][key] = None
                with self.assertRaises(DataError): self.make()

    def test_zero_and_negative_estimates_are_valid(self):
        self.rows[0].update(tot=0, off=-1, **{'def': 1})
        self.assertEqual(self.analysis()['impact_context']['datasets'][0]['values']['EPM'], 0)

    def test_nonfinite_or_boolean_numeric_values_rejected(self):
        for value in ('NaN', 'inf', True):
            with self.subTest(value=value):
                self.rows[0]['tot'] = value
                with self.assertRaises((DataError, ValueError)): self.make()

    def test_raw_selection_tampering_rejected(self):
        b = self.make()
        b['epm_import']['snapshot']['raw_rows'][0]['tot'] = 8
        with self.assertRaises(DataError): self.analysis(b)

    def test_normalized_rows_and_hash_edit_still_fail_deterministic_rebuild(self):
        b = self.make()
        b['impact_data']['datasets'][0]['raw_rows'][0]['tot'] = 8
        b['sources'][SID]['sha256_rows'] = digest(b['impact_data']['datasets'][0]['raw_rows'])
        with self.assertRaises(DataError): self.analysis(b)

    def test_unverified_direct_epm_dataset_rejected(self):
        b = self.make()
        b.pop('epm_import')
        with self.assertRaises(DataError): self.analysis(b)

    def test_reimport_not_silent_overwrite(self):
        self.base = self.make()
        with self.assertRaises(DataError): self.make()

    def test_unhashed_reference_rejected(self):
        self.base['sources']['P_BASE'].pop('sha256_rows')
        with self.assertRaises(DataError): self.make()

    def test_registered_model_metadata_edit_rejected(self):
        b = self.make()
        b['sources'][SID]['model_version'] = 'Unverified replacement revision'
        with self.assertRaises(DataError): self.analysis(b)

    def test_reference_identity_or_totals_changed_rejected(self):
        b = self.make()
        b['tables']['player_base'][0]['MIN'] += 1
        b['sources']['P_BASE']['sha256_rows'] = digest(b['tables']['player_base'])
        with self.assertRaises(DataError): validate_import(b)

    def test_old_impact_models_and_exclusions_preserved(self):
        from test_impact import fixture
        existing = fixture()
        self.base['impact_data'] = existing['impact_data']
        self.base['sources'].update(existing['sources'])
        self.base['impact_data']['excluded'] = [dict(family='EPM', reason='Old online failure'), dict(family='RAPM', reason='Unknown window')]
        b = self.make()
        self.assertEqual([d['family'] for d in b['impact_data']['datasets']], ['BREF', 'LEBRON', 'DARKO', 'EPM'])
        self.assertEqual(b['impact_data']['excluded'], [dict(family='RAPM', reason='Unknown window')])
        self.assertEqual(b['impact_data']['datasets'][:3], existing['impact_data']['datasets'])

    def test_epm_chart_and_source_label_and_missing_state(self):
        a = self.analysis()
        visual = impact_visuals(a)['impact_retrospective']
        self.assertIn('Actual EPM', visual['svg'])
        self.assertEqual(visual['metric_ids'], ['IMPACT_EPM', 'IMPACT_O_EPM', 'IMPACT_D_EPM'])
        self.assertNotIn('impact_predictive', impact_visuals(a))
        self.assertNotIn('EPM与范围未核验', ''.join(limitations(a)))
        from book_sources import source_index
        self.assertIn('提供者模型 · 用户离线导出', source_index(a))

    def test_compatible_box_model_and_epm_render_together(self):
        from collect_impact import dataset
        rows = [dict(provider_player_key='syntheticdemo', name_display='MVP Demo Guard',
                     games='60', mp='1800', bpm='2.0', obpm='2.5', dbpm='-0.5')]
        d, s = dataset('BREF', rows, dict(url='https://example.com/synthetic',
                         retrieved_at='2026-10-15T00:00:00Z', sha256='0'*64),
                         PID, 'MVP Demo Guard', '2024-25', 'syntheticdemo')
        self.base['impact_data'] = dict(schema_version='0.1.0', datasets=[d], excluded=[])
        self.base['sources'][d['source_id']] = s
        a = self.analysis()
        self.assertEqual([d['family'] for d in a['impact_context']['datasets']], ['BREF', 'EPM'])
        self.assertEqual(len(impact_visuals(a)['impact_retrospective']['metric_ids']), 6)

    def test_editorial_requires_epm_value_analysis_not_only_coverage(self):
        from editorial_audit import audit
        a = self.analysis()
        claims = {'claims': [dict(metric_ids=['IMPACT_EPM_MIN'])]}
        self.assertIn('impact_unwritten', [f['code'] for f in audit({}, a, claims)['findings']])
        claims['claims'][0]['metric_ids'].append('IMPACT_EPM')
        self.assertNotIn('impact_unwritten', [f['code'] for f in audit({}, a, claims)['findings']])

    def test_original_and_metadata_bytes_verified(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b = self.write_import(root)
            verify_retained(b, root)
            (root / 'raw/epm_export.json').write_text('[]', encoding='utf-8')
            with self.assertRaises(DataError): verify_retained(b, root)

    def test_rehashed_snapshot_cannot_disagree_with_retained_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b = self.write_import(root)
            snapshot = b['epm_import']['snapshot']
            snapshot['raw_rows'][0].update(tot=5.5, off=6.0)
            snapshot['snapshot_sha256'] = sha(selection_bytes(snapshot))
            d, s = build_dataset(snapshot)
            b['impact_data']['datasets'] = [d]
            b['sources'][SID] = s
            (root / 'raw/epm_selection.json').write_bytes(selection_bytes(snapshot))
            with self.assertRaisesRegex(DataError, 'original export'): verify_retained(b, root)

    def test_metadata_byte_tampering_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b = self.write_import(root)
            (root / 'raw/epm_metadata.json').write_text('{}', encoding='utf-8')
            with self.assertRaises(DataError): verify_retained(b, root)

    def test_missing_original_file_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            b = self.write_import(root)
            (root / 'raw/epm_export.json').unlink()
            with self.assertRaises(DataError): verify_retained(b, root)

    def test_paths_cannot_escape_raw(self):
        for path in ('../secret', 'raw/../../secret', 'data.json', 'C:/outside.csv'):
            with self.subTest(path=path):
                with self.assertRaises(DataError): checked_path(Path('run'), path)

    def test_bad_csv_headers_and_json_shapes_rejected(self):
        for data, fmt in [(b'a,a\n1,2', 'csv'), (b'a,b\n1,2,3', 'csv'),
                          (b'{"rows":[]}', 'json'), (b'[{"a":1,"a":2}]', 'json'),
                          (b'[{"a":{}}]', 'json'), (b'[]', 'json')]:
            with self.subTest(data=data):
                with self.assertRaises(DataError): parse_rows(data, fmt)

    def test_offline_import_run_rejects_nonempty_destination(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / 'existing').write_text('keep')
            with self.assertRaises(DataError): run(argparse.Namespace(out=out))

    def test_offline_cli_chain_raw_copy_book_and_tamper_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_json(root / 'base.json', self.base)
            (root / 'export.csv').write_bytes(payload(self.rows, 'csv'))
            write_json(root / 'metadata.json', self.meta)
            imported = root / 'imported'
            with patch('socket.socket', side_effect=AssertionError('Network forbidden')):
                run(argparse.Namespace(bundle=root / 'base.json', file=root / 'export.csv',
                    metadata=root / 'metadata.json', player_id=PID, out=imported))
            self.assertEqual(read_json(imported / 'epm_import_audit.json')['network_requests'], 0)
            result = root / 'research'
            command = [sys.executable, '-X', 'utf8', str(ROOT / 'scripts/run_analysis.py'), '--input',
                       str(imported / 'data_bundle.json'), '--player-id', str(PID), '--season', '2024-25',
                       '--no-comparisons', '--out', str(result)]
            process = subprocess.run(command, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(process.returncode, 0, process.stderr)
            for name in ('epm_export.csv', 'epm_metadata.json', 'epm_selection.json'):
                self.assertEqual((imported / 'raw' / name).read_bytes(), (result / 'raw' / name).read_bytes())
            for name in ('report.md', 'claims.json', 'book_content.json'):
                shutil.copy2(ROOT / 'examples/demo_output' / name, result / name)
            from render_research_book import build
            from validate_book import check
            build(result, 'CLE', False)
            self.assertEqual(check(result)['status'], 'pass')
            html = (result / 'research_book.html').read_text(encoding='utf-8')
            self.assertIn('IMPACT_EPM', html)
            self.assertNotIn('class="impact-scope predictive"', html)
            self.assertNotIn('<h4>仍未纳入的指标</h4>', html)
            (result / 'raw/epm_export.csv').write_bytes(b'changed')
            with self.assertRaises(DataError): build(result, 'CLE', True)


if __name__ == '__main__':
    unittest.main()
