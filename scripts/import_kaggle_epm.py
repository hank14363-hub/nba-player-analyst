"""Read deocheng v1 historical EPM candidates; optionally import verified Actual."""
from __future__ import annotations

import argparse
from collections import Counter
from decimal import Decimal
import json
from pathlib import Path

from common import DataError, integer, number, read_json, validate_season, write_json
from import_epm import FIELDS, KAGGLE_ACTUAL_SHA, KAGGLE_URL, parse_rows, run as import_actual, sha

FILES = {
    'public.player_epm.csv': '2c50d0376da10cec54d6fba105d5f2a339d660f7f1db505075e83b6abac9a067',
    'public.player_epm_actual.csv': KAGGLE_ACTUAL_SHA,
}


def inspect_file(path, player_id, season):
    payload = path.read_bytes()
    if sha(payload) != FILES[path.name]:
        raise DataError('EPM file differs from reviewed Kaggle v1: ' + path.name)
    rows = parse_rows(payload, 'csv')
    end_year = int(season[:4]) + 1
    selected = [r for r in rows if integer(r['nba_player_id'], 'NBA ID') == player_id
                and integer(r['season'], 'season end year') == end_year]
    candidates = []
    for row in selected:
        delta = number(row['epm_tot']) - number(row['epm_off']) - number(row['epm_def'])
        candidates.append(dict(raw_row=row, component_difference=delta,
                               components_consistent=abs(delta) <= .15 + 1e-12,
                               verified_for_report=False,
                               reason='Await Actual import identity, sample and original-file checks' if 'actual' in path.name else
                               'Historical source/type and date scope unverified; no GP/total MIN; do not use as regular-season Actual or a validated prediction'))
    return dict(file=str(path.resolve()), sha256=sha(payload), bytes=len(payload), rows=len(rows),
                seasons=dict(sorted(Counter(r['season'] for r in rows).items())),
                sources=dict(Counter(r['source'] for r in rows)),
                selected_rows=candidates)


def actual_metadata(row, season, acquired_at):
    if row.get('source') != 'dunksandthrees.com/epm/actual':
        raise DataError('Only Actual table rows may be imported')
    # Never enlarge tolerance for an integer-looking serialized value.
    decimals = max(2, -Decimal(row['mp']).as_tuple().exponent)
    return dict(schema_version='0.1.0', source_kind='kaggle_deocheng_v1',
                source_url=KAGGLE_URL, upstream_url='https://dunksandthrees.com/epm/actual',
                dataset_version=1, snapshot_date='2026-08-18',
                dataset_file='csv/public.player_epm_actual.csv', acquired_at=acquired_at,
                estimate_type='actual', league='NBA', season=season,
                season_type='Regular Season', sample_scope='full_season', minutes_unit='total',
                minutes_decimals=decimals, season_format='end_year',
                model_version='unknown; Kaggle v1 retained Actual snapshot, provider revision not disclosed',
                columns=dict(zip(FIELDS, ('nba_player_id', 'player_name', 'season', 'gp', 'mp', 'epm_tot', 'epm_off', 'epm_def'))))


def run(args):
    validate_season(args.season, 'Regular Season')
    if args.out.exists() and any(args.out.iterdir()):
        raise DataError('Choose a new empty Kaggle EPM output directory')
    csv_dir = args.csv_dir / 'csv' if (args.csv_dir / 'csv').is_dir() else args.csv_dir
    files = [inspect_file(csv_dir / name, args.player_id, args.season)
             for name in FILES if (csv_dir / name).is_file()]
    if not files:
        raise DataError('No reviewed EPM CSV found')
    audit = dict(dataset_url=KAGGLE_URL, dataset_version=1, snapshot_date='2026-08-18',
                 season=args.season, player_id=args.player_id, files=files,
                 historical_candidates_are_report_metrics=False, status='read_only_candidates',
                 note='Full original CSVs remain at recorded paths; selected rows are not validated model metrics. No network request.')
    args.out.mkdir(parents=True, exist_ok=True)
    if getattr(args, 'import_historical', False):
        try:
            if not args.bundle or not args.acquired_at:
                raise DataError('--import-historical requires --bundle and actual --acquired-at timestamp')
            reference = read_json(args.bundle)
            if reference.get('season') != args.season:
                raise DataError('Reference season differs from requested historical EPM season')
            history = next((f for f in files if Path(f['file']).name == 'public.player_epm.csv'), None)
            if history is None:
                raise DataError('Historical EPM CSV is missing')
            from historical_epm import run as import_history
            imported = import_history(argparse.Namespace(bundle=args.bundle, file=Path(history['file']),
                     acquired_at=args.acquired_at, player_id=args.player_id, out=args.out/'imported',
                     source=getattr(args, 'source', None), snapshot_date=getattr(args, 'snapshot_date', None)))
            audit.update(status='historical_reading_imported_scope_unverified', imported_bundle=str(imported/'data_bundle.json'),
                         historical_candidates_are_report_metrics=True,
                         note='Selected historical reading imported with mandatory unverified-scope disclosure. This is not an Actual or validated prediction import.')
        except (DataError, OSError, ValueError, KeyError, TypeError) as exc:
            audit.update(status='historical_import_rejected', rejection_reason=str(exc))
    elif args.import_actual:
        try:
            if not args.bundle or not args.acquired_at:
                raise DataError('--import-actual requires --bundle and actual --acquired-at timestamp')
            reference = read_json(args.bundle)
            if reference.get('season') != args.season:
                raise DataError('Reference season differs from requested EPM season')
            actual = next((f for f in files if Path(f['file']).name == 'public.player_epm_actual.csv'), None)
            if actual is None or len(actual['selected_rows']) != 1:
                raise DataError('No unique Actual EPM row for this player and season; historical candidates cannot fill the gap')
            meta = actual_metadata(actual['selected_rows'][0]['raw_row'], args.season, args.acquired_at)
            metadata_path = args.out / 'kaggle_epm_metadata.json'
            write_json(metadata_path, meta)
            imported = import_actual(argparse.Namespace(bundle=args.bundle, file=Path(actual['file']),
                         metadata=metadata_path, player_id=args.player_id, out=args.out / 'imported'))
            audit.update(status='actual_import_validated', imported_bundle=str(imported / 'data_bundle.json'))
            actual['selected_rows'][0]['verified_for_report'] = True
            actual['selected_rows'][0]['reason'] = 'Selected Actual row passed retained-original, exact identity, GP, total MIN and component checks'
        except (DataError, OSError, ValueError, KeyError, TypeError) as exc:
            audit.update(status='actual_import_rejected', rejection_reason=str(exc))
    write_json(args.out / 'kaggle_epm_read_audit.json', audit)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv-dir', type=Path, required=True)
    parser.add_argument('--player-id', type=int, required=True)
    parser.add_argument('--season', required=True)
    parser.add_argument('--out', type=Path, required=True)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument('--import-actual', action='store_true')
    mode.add_argument('--import-historical', action='store_true', help='Attach archived reading with mandatory unresolved-scope note; never substitute for Actual')
    parser.add_argument('--source', choices=['dunksandthrees.com/player/eskills', 'dunksandthrees.com/epm'], help='Explicit historical source when candidates are ambiguous')
    parser.add_argument('--snapshot-date', help='Exact original game_dt when multiple historical rows exist')
    parser.add_argument('--bundle', type=Path)
    parser.add_argument('--acquired-at', help='Actual Kaggle file download timestamp, ISO 8601 with timezone')
    args = parser.parse_args()
    try:
        audit = run(args)
        print(json.dumps({k: v for k, v in audit.items() if k != 'files'}, ensure_ascii=False, indent=2))
        return 2 if audit['status'] in ('actual_import_rejected','historical_import_rejected') else 0
    except (DataError, OSError, ValueError, KeyError, TypeError) as exc:
        print('ERROR: ' + str(exc))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
