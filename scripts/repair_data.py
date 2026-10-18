#!/usr/bin/env python3
"""Fetch only selected missing tables into a NEW bundle; preserve successful snapshots."""
import argparse
import copy
import json
import sys
from pathlib import Path
from common import TABLES, DataError, digest, integer, load_bundle, now_iso, player_row, validate_bundle, write_json
from fetch_data import Fetcher
from shot_charts import shot_context
from supplemental_metrics import onoff_context


def repair(bundle, tables, fetcher, player_id=None, onoff_team_id=0, replace_existing=False):
    season, kind = bundle['season'], bundle['season_type']
    team_id = integer(bundle.get('player_team_id', 0), 'player_team_id')
    validate_bundle(bundle, season, kind, team_id)
    if bundle['data_kind'] != 'nba':
        raise DataError('Do not merge live NBA data into synthetic bundles.')
    tables = list(dict.fromkeys(tables))
    if not tables or any(t not in TABLES for t in tables):
        raise DataError('Select one or more registered tables.')
    if any(bundle['tables'].get(t) for t in tables) and not replace_existing:
        raise DataError('Selected table already has rows. Use --replace-existing explicitly or select only missing tables.')
    if 'player_shots' in tables and not player_id:
        raise DataError('Shot repair needs --player-id.')
    if player_id:
        player_row(bundle['tables']['player_base'], player_id, team_id)
    if 'player_onoff' in tables and not onoff_team_id:
        raise DataError('On/off repair needs --on-off-team-id; never use a hypothetical target team.')
    if 'player_onoff' in tables and not player_id:
        raise DataError('On/off repair needs --player-id to validate coverage against the base row.')
    old = copy.deepcopy(bundle)
    result = copy.deepcopy(bundle)
    log = dict(created_at=now_iso(), original_bundle_sha256=digest(bundle),
               sample=dict(season=season, season_type=kind, player_team_id=team_id),
               events=[], next='Re-run run_analysis.py with this bundle into a new directory, then re-audit claims and render. Existing articles were not changed.')
    for table in tables:
        sid = TABLES[table][0]
        before = dict(rows_sha256=digest(result['tables'].get(table, [])), source=copy.deepcopy(result['sources'].get(sid)))
        try:
            if table == 'player_shots':
                rows, source = fetcher.shots(season, kind, player_id, team_id)
            elif table == 'player_onoff':
                rows, source = fetcher.onoff(season, kind, onoff_team_id)
            else:
                rows, source = fetcher.table(table, season, kind, team_id)
            candidate = copy.deepcopy(result)
            candidate['tables'][table], candidate['sources'][sid] = rows, source
            validate_bundle(candidate, season, kind, team_id)
            if table == 'player_shots':
                spatial=shot_context(candidate, player_row(candidate['tables']['player_base'], player_id, team_id), player_id, team_id, allow_partial=True)
                if spatial['missing_location_count'] or spatial['missing_zone_count']:
                    source['spatial_coverage']={k:spatial[k] for k in ('location_count','missing_location_count','missing_zone_count','location_coverage')}
            if table == 'player_onoff' and player_id:
                onoff_context(candidate, player_row(candidate['tables']['player_base'], player_id, team_id), player_id, team_id)
            result = candidate
            # Remove only warnings for the repaired missing source. Preserve unrelated diagnostics.
            result['warnings'] = [w for w in result.get('warnings', []) if not w.startswith(sid + ':')]
            if table in {'player_base', 'team_base'} and old['tables'].get(table):
                result['warnings'].append(sid + ': explicitly refreshed base snapshot; all dependent sources require scope review.')
            if source.get('stale'):
                result['warnings'].append(sid + ': stale offline cache; original retrieval timestamp retained.')
            event = dict(table=table, status='repaired', before=before, after=dict(rows_sha256=digest(rows), source=source))
        except (DataError, ValueError) as exc:
            # Leave the old table/source untouched, even during an explicit refresh failure.
            event = dict(table=table, status='failed', before=before, reason=str(exc))
        log['events'].append(event)
    for table in TABLES:
        if table not in tables:
            sid = TABLES[table][0]
            if result['tables'].get(table) != old['tables'].get(table) or result['sources'].get(sid) != old['sources'].get(sid):
                raise DataError('Unselected table/source changed: ' + table)
    validate_bundle(result, season, kind, team_id)
    log['result_bundle_sha256'] = digest(result)
    return result, log


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--tables', nargs='+', choices=list(TABLES), help='Default: empty/missing tables already present in input')
    p.add_argument('--player-id', type=int)
    p.add_argument('--on-off-team-id', type=int, default=0)
    p.add_argument('--replace-existing', action='store_true')
    p.add_argument('--out', type=Path, required=True, help='New/empty directory')
    p.add_argument('--cache-dir', type=Path, default=Path('.nba-player-analyst/cache'))
    p.add_argument('--timeout', type=float, default=20)
    p.add_argument('--retries', type=int, default=2)
    p.add_argument('--offline', action='store_true')
    p.add_argument('--refresh', action='store_true')
    args = p.parse_args()
    try:
        if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
            raise DataError('Output must be new/empty; old bundles and reports are never overwritten.')
        bundle = load_bundle(args.input)
        from retained_raw import verify_retained, copy_retained
        input_root = args.input.parent if args.input.is_file() else args.input
        verify_retained(bundle, input_root)
        chosen = args.tables or [t for t in bundle['tables'] if not bundle['tables'][t]]
        updated, log = repair(bundle, chosen, Fetcher(args.cache_dir, timeout=args.timeout, retries=args.retries,
                               offline=args.offline, refresh=args.refresh), args.player_id, args.on_off_team_id, args.replace_existing)
        args.out.mkdir(parents=True, exist_ok=True)
        copy_retained(updated, input_root, args.out)
        write_json(args.out/'data_bundle.json', updated)
        write_json(args.out/'repair_log.json', log)
        failed = any(e['status'] == 'failed' for e in log['events'])
        print(json.dumps(dict(status='partial_failure' if failed else 'repaired', events=log['events'], next=log['next']), ensure_ascii=False, indent=2))
        return 1 if failed else 0
    except (DataError, OSError, ValueError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
