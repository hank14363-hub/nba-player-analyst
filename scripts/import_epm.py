"""Offline Dunks & Threes Actual EPM import. Never fetches provider pages."""
from __future__ import annotations

import argparse
import csv
from copy import deepcopy
from datetime import datetime
import hashlib
import io
import json
from pathlib import Path
import re
import sys
from urllib.parse import parse_qs, urlsplit

from common import (DataError, digest, integer, normalize_name, number, now_iso,
                    player_row, read_json, resolve_player, validate_bundle,
                    validate_season, write_json)

ADAPTER = 'dunksandthrees-actual-offline-v1'
SID = 'EXT_IMPACT_EPM'
FIELDS = ('nba_id', 'player_name', 'season', 'games', 'minutes', 'tot', 'off', 'def')
OPTIONAL_FIELDS = ('season_type', 'estimate_type')
KAGGLE_URL = 'https://www.kaggle.com/datasets/deocheng/nba-data-1946-2026'
KAGGLE_ACTUAL_SHA = '7f57ca68ad1d1bd71367d27e207348a0c5c7a0c7823692677aee7fe400525d4a'


def sha(data):
    return hashlib.sha256(data).hexdigest()


def selection_bytes(snapshot):
    value = {k: v for k, v in snapshot.items() if k != 'snapshot_sha256'}
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + '\n').encode('utf-8')


def parse_rows(payload, file_format):
    try:
        text = payload.decode('utf-8-sig')
        if file_format == 'csv':
            reader = csv.DictReader(io.StringIO(text, newline=''))
            headers = reader.fieldnames
            if not headers or any(not h for h in headers) or len(headers) != len(set(headers)):
                raise DataError('EPM CSV requires unique, nonempty column names')
            rows = list(reader)
            if any(None in r or any(v is None for v in r.values()) for r in rows):
                raise DataError('EPM CSV row width differs from header')
        elif file_format == 'json':
            def unique_pairs(pairs):
                out = {}
                for key, value in pairs:
                    if key in out:
                        raise DataError('Duplicate EPM JSON key: ' + key)
                    out[key] = value
                return out
            rows = json.loads(text, object_pairs_hook=unique_pairs)
        else:
            raise DataError('EPM accepts UTF-8 CSV or a JSON array of row objects')
    except (UnicodeError, ValueError, csv.Error) as exc:
        raise DataError('Cannot parse EPM export: ' + str(exc)) from exc
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) and r for r in rows):
        raise DataError('EPM export must contain nonempty row objects')
    for row in rows:
        if any(not isinstance(k, str) or isinstance(v, (dict, list)) for k, v in row.items()):
            raise DataError('EPM supports flat rows; nested provider schemas require review')
    return rows


def validate_metadata(meta, season):
    if not isinstance(meta, dict) or meta.get('schema_version') != '0.1.0':
        raise DataError('EPM metadata requires schema_version=0.1.0')
    required = {'estimate_type': 'actual', 'league': 'NBA', 'season': season,
                'season_type': 'Regular Season', 'sample_scope': 'full_season',
                'minutes_unit': 'total'}
    for key, value in required.items():
        if meta.get(key) != value:
            raise DataError('EPM metadata scope mismatch: ' + key + '; predictions, stints and per-game minutes are unsupported')
    decimals = integer(meta.get('minutes_decimals'), 'minutes_decimals')
    if not 0 <= decimals <= 4:
        raise DataError('Declare exported total-minute precision from 0 to 4 decimals')
    if meta.get('season_format') not in ('nba', 'end_year'):
        raise DataError('EPM season_format must be nba or end_year; never infer year convention')
    if not isinstance(meta.get('model_version'), str) or not meta['model_version'].strip():
        raise DataError('Declare EPM model_version; use explicit unknown text when revision is unavailable')
    kaggle = meta.get('source_kind') == 'kaggle_deocheng_v1'
    if meta.get('source_kind') not in (None, 'kaggle_deocheng_v1'):
        raise DataError('Unknown EPM acquisition profile')
    timestamp_key = 'acquired_at' if kaggle else 'exported_at'
    try:
        if datetime.fromisoformat(meta[timestamp_key].replace('Z', '+00:00')).tzinfo is None:
            raise ValueError()
    except (KeyError, TypeError, AttributeError, ValueError) as exc:
        raise DataError('EPM ' + timestamp_key + ' requires a declared ISO timestamp with timezone') from exc
    if kaggle:
        if (meta.get('source_url') != KAGGLE_URL or meta.get('dataset_version') != 1
                or meta.get('snapshot_date') != '2026-08-18'
                or meta.get('dataset_file') != 'csv/public.player_epm_actual.csv'
                or meta.get('upstream_url') != 'https://dunksandthrees.com/epm/actual'
                or meta.get('season_format') != 'end_year' or season != '2025-26'
                or decimals < 2):
            raise DataError('Kaggle EPM supports only the reviewed v1 Actual file and 2025-26 scope; total-minute precision cannot be relaxed')
    try:
        url = urlsplit(meta['upstream_url'] if kaggle else meta['source_url'])
        if (url.scheme != 'https' or url.hostname not in ('dunksandthrees.com', 'www.dunksandthrees.com')
                or url.username or url.password or url.path.rstrip('/') != '/epm/actual'):
            raise ValueError()
        years = parse_qs(url.query).get('season', [])
        if years and years != [str(int(season[:4]) + 1)]:
            raise ValueError()
    except (KeyError, TypeError, ValueError) as exc:
        raise DataError('EPM source_url must identify the matching Dunks & Threes Actual page') from exc
    columns = meta.get('columns')
    if (not isinstance(columns, dict) or not set(FIELDS).issubset(columns)
            or set(columns) - set(FIELDS + OPTIONAL_FIELDS)
            or any(not isinstance(v, str) or not v for v in columns.values())
            or len(set(columns.values())) != len(columns)):
        raise DataError('EPM needs an explicit, unique column map for identity, season, games, total minutes and tot/off/def')


def row_season(value, convention):
    if convention == 'nba':
        value = str(value)
        validate_season(value, 'Regular Season')
        return value
    end = integer(value, 'EPM season end year')
    if not 1947 <= end <= 2200:
        raise DataError('Invalid EPM season end year')
    return f'{end - 1}-{end % 100:02d}'


def build_dataset(snapshot):
    """Rebuild normalized EPM only from retained original rows and declared mapping."""
    if snapshot.get('schema_version') != '0.1.0' or snapshot.get('adapter') != ADAPTER:
        raise DataError('Unsupported EPM import snapshot')
    season = snapshot['season']
    validate_season(season, snapshot['season_type'])
    if snapshot['season_type'] != 'Regular Season' or snapshot.get('player_team_id') != 0:
        raise DataError('EPM adapter supports complete regular seasons only')
    meta = snapshot['metadata']
    validate_metadata(meta, season)
    pid = integer(snapshot['player_id'], 'EPM player_id')
    base = snapshot['reference_player']
    if pid <= 0 or integer(base.get('PLAYER_ID'), 'reference NBA ID') != pid:
        raise DataError('EPM reference identity mismatch')
    rows = snapshot['raw_rows']
    if not isinstance(rows, list) or not rows or not all(isinstance(r, dict) for r in rows):
        raise DataError('EPM original provider rows required')
    files = snapshot.get('files')
    expected_paths = ['raw/epm_export.' + str(snapshot.get('format')), 'raw/epm_metadata.json']
    if (snapshot.get('format') not in ('csv', 'json') or not isinstance(files, list) or len(files) != 2
            or not all(isinstance(f, dict) and f.get('raw_file') == path
                       and isinstance(f.get('sha256_raw'), str) and re.fullmatch('[a-f0-9]{64}', f['sha256_raw'])
                       for f, path in zip(files, expected_paths))):
        raise DataError('EPM exact original export and metadata artifacts required')
    columns = meta['columns']
    candidates = []
    for row in rows:
        if any(key not in row for key in columns.values()):
            raise DataError('Declared EPM column absent in export')
        if integer(row[columns['nba_id']], 'EPM NBA ID') == pid and row_season(row[columns['season']], meta['season_format']) == season:
            candidates.append(row)
    if len(candidates) != 1:
        raise DataError('EPM identity/season selector must resolve exactly one row; never sum stints or choose duplicate exports')
    original = candidates[0]
    kaggle = meta.get('source_kind') == 'kaggle_deocheng_v1'
    if kaggle:
        if files[0]['sha256_raw'] != KAGGLE_ACTUAL_SHA:
            raise DataError('Kaggle Actual export differs from reviewed v1 bytes; review a new version before import')
        expected_columns = dict(zip(FIELDS, ('nba_player_id', 'player_name', 'season', 'gp', 'mp', 'epm_tot', 'epm_off', 'epm_def')))
        if columns != expected_columns or str(original.get('seasontype')) != '2' or original.get('source') != 'dunksandthrees.com/epm/actual':
            raise DataError('Kaggle Actual schema/source/type mismatch')
        try:
            embedded = json.loads(original['raw'])
            for col, key in [('nba_player_id', 'player_id'), ('season', 'season'), ('gp', 'gp'), ('mp', 'mp'), ('epm_tot', 'tot'), ('epm_off', 'off'), ('epm_def', 'def')]:
                if number(original[col]) != number(embedded[key]):
                    raise DataError('Kaggle CSV differs from retained provider JSON: ' + col)
            if (str(embedded['seasontype']) != '2' or number(embedded['scope_id']) != 0
                    or normalize_name(embedded['player_name']) != normalize_name(original['player_name'])):
                raise DataError('Kaggle embedded provider scope/name mismatch')
        except DataError:
            raise
        except (KeyError, ValueError, TypeError) as exc:
            raise DataError('Kaggle embedded Actual JSON cannot be verified') from exc
    row = {key: original[column] for key, column in columns.items()}
    if not isinstance(row['player_name'], str) or normalize_name(row['player_name']) != normalize_name(base['PLAYER_NAME']):
        raise DataError('EPM exact full-name and numeric NBA-ID bridge mismatch')
    for key, value in [('season_type', 'Regular Season'), ('estimate_type', 'actual')]:
        if key in row and row[key] != value:
            raise DataError('EPM raw competition/estimate type contradicts metadata')
    games = integer(row['games'], 'EPM games')
    minutes = number(row['minutes'], 'EPM total minutes')
    decimals = integer(meta['minutes_decimals'], 'minutes_decimals')
    tolerance = .5 * 10 ** (-decimals)
    if games <= 0 or games != number(base.get('GP'), 'reference GP'):
        raise DataError('EPM GP mismatch')
    if minutes <= 0 or abs(minutes - round(minutes, decimals)) > 1e-8:
        raise DataError('EPM minutes contradict declared total-minute precision')
    if abs(minutes - number(base.get('MIN'), 'reference MIN')) > tolerance + 1e-9:
        raise DataError('EPM minute coverage mismatch at declared export precision')
    normalized = dict(nba_id=pid, player_name=row['player_name'], season=season,
                      season_type='Regular Season', estimate_type='actual', games=games, minutes=minutes)
    for key in ('tot', 'off', 'def'):
        normalized[key] = number(row[key], 'EPM.' + key)
    if abs(normalized['tot'] - normalized['off'] - normalized['def']) > .15 + 1e-12:
        raise DataError('EPM components fail tot == off + def tolerance 0.15')
    model = meta['model_version']
    caveats = [
        'Dunks & Threes Actual EPM 用户离线导出；不是预测EPM或本次在线抓取，导出范围与版本由保留元数据声明。',
        '每百回合的提供者攻防影响力估计；防守分量不是个人防守能力评分，也不是未经调整的On/Off。',
        '场次与参考总量一致，分钟按明确导出精度核对；SHA-256证明保留文件一致，不证明提供者真实性或使用权。',
        '未取得模型置信区间；不导入排名，不与BPM、LEBRON等加总或平均。',
    ]
    dataset = dict(family='EPM', player_id=pid, player_team_id=0, season=season,
                   season_type='Regular Season', estimate_type='retrospective_adjusted',
                   model_version=model, cutoff=None, source_id=SID, raw_rows=[normalized],
                   selector={'nba_id': pid, 'season': season}, caveats=caveats,
                   minutes_decimals=decimals)
    source = dict(provider='Dunks & Threes / user-supplied offline Actual export',
                  url=meta['source_url'], retrieved_at=meta['acquired_at'] if kaggle else meta['exported_at'],
                  acquisition_time_basis='User-declared export timestamp; no provider request made',
                  status='ok', source_type='impact_data', season=season,
                  season_type='Regular Season', per_mode='Provider model', adapter=ADAPTER,
                  model_version=model, cutoff=None, row_count=1, sha256_rows=digest([normalized]),
                  raw_file='raw/epm_selection.json', sha256_raw=snapshot['snapshot_sha256'],
                  raw_artifacts=deepcopy(snapshot['files']),
                  display_title='Actual EPM · 用户离线导出', usage='；'.join(caveats),
                  sample_scope='full_season', estimate_type='actual', minutes_decimals=decimals)
    if kaggle:
        caveats[0] = 'Dunks & Threes Actual EPM 经 Kaggle deocheng v1 转引；不是官网直接导出或本次官网采集。'
        caveats.append('仅此球员与参考常规赛场次及分钟匹配；原表类型码2/scope_id0保留，未取得独立代码说明或模型版本；不宣称602行全部已验证。')
        source.update(provider='Dunks & Threes → Kaggle / deocheng v1', source_kind='kaggle_deocheng_v1',
                      retrieved_at=meta['acquired_at'],
                      acquisition_time_basis='Actual Kaggle download timestamp; upstream scraped_at has no declared timezone',
                      upstream_url=meta['upstream_url'], upstream_scraped_at=original.get('scraped_at'),
                      dataset_version=1, snapshot_date=meta['snapshot_date'], dataset_file=meta['dataset_file'],
                      display_title='Actual EPM · Kaggle 转引', usage='；'.join(caveats))
    return dataset, source


def validate_import(bundle):
    contract = bundle.get('epm_import')
    if not isinstance(contract, dict) or contract.get('schema_version') != '0.1.0':
        raise DataError('EPM requires its retained offline import contract')
    snapshot = contract.get('snapshot')
    if not isinstance(snapshot, dict) or sha(selection_bytes(snapshot)) != snapshot.get('snapshot_sha256'):
        raise DataError('EPM retained original-row selection checksum mismatch')
    for key in ('season', 'season_type', 'player_team_id', 'data_kind'):
        if snapshot.get(key) != bundle.get(key):
            raise DataError('EPM imported sample differs: ' + key)
    base = player_row(bundle['tables']['player_base'], snapshot['player_id'], 0)
    if digest(base) != digest(snapshot['reference_player']) or bundle['sources'].get('P_BASE') != snapshot['reference_source']:
        raise DataError('EPM reference totals/identity/provenance changed')
    dataset, source = build_dataset(snapshot)
    actual = [d for d in bundle.get('impact_data', {}).get('datasets', []) if d.get('family') == 'EPM']
    if digest(actual) != digest([dataset]) or bundle['sources'].get(SID) != source:
        raise DataError('EPM conversion differs from retained original rows/metadata')


def validate_files(bundle, root):
    """Tie parsed selection back to the exact original export and metadata bytes."""
    if bundle.get('epm_import') is None:
        return
    validate_import(bundle)
    snapshot = bundle['epm_import']['snapshot']
    from retained_raw import checked_path
    export, metadata = snapshot['files']
    payload = checked_path(root, export['raw_file']).read_bytes()
    meta_payload = checked_path(root, metadata['raw_file']).read_bytes()
    if sha(payload) != export['sha256_raw'] or sha(meta_payload) != metadata['sha256_raw']:
        raise DataError('EPM original export/metadata file checksum mismatch')
    if digest(parse_rows(payload, snapshot['format'])) != digest(snapshot['raw_rows']):
        raise DataError('EPM retained rows differ from original export file')
    if digest(json.loads(meta_payload.decode('utf-8-sig'))) != digest(snapshot['metadata']):
        raise DataError('EPM retained scope/mapping differs from original metadata file')


def prepare_import(bundle, player_id, export_bytes, file_format, metadata_bytes, original_name='user-export'):
    validate_bundle(bundle, bundle['season'], bundle['season_type'], bundle.get('player_team_id', 0))
    if bundle['season_type'] != 'Regular Season' or bundle.get('player_team_id', 0) != 0:
        raise DataError('EPM needs a matching full regular-season reference bundle')
    if bundle.get('epm_import') or any(d.get('family') == 'EPM' for d in bundle.get('impact_data', {}).get('datasets', [])) or SID in bundle['sources']:
        raise DataError('Reference already contains EPM; use the original pre-EPM bundle, never silently overwrite')
    pid, name = resolve_player(bundle['tables']['player_base'], None, player_id)
    pbase = bundle['sources']['P_BASE']
    if pbase.get('status', 'ok') != 'ok' or pbase.get('sha256_rows') != digest(bundle['tables']['player_base']):
        raise DataError('EPM needs hashed reference player totals and an exact identity bridge')
    try:
        metadata = json.loads(metadata_bytes.decode('utf-8-sig'))
    except (ValueError, UnicodeError) as exc:
        raise DataError('Cannot parse EPM metadata JSON') from exc
    files = [dict(raw_file='raw/epm_export.' + file_format, sha256_raw=sha(export_bytes)),
             dict(raw_file='raw/epm_metadata.json', sha256_raw=sha(metadata_bytes))]
    snapshot = dict(schema_version='0.1.0', adapter=ADAPTER, season=bundle['season'],
                    season_type=bundle['season_type'], player_team_id=0, data_kind=bundle['data_kind'],
                    player_id=pid, original_name=Path(original_name).name, format=file_format,
                    raw_rows=parse_rows(export_bytes, file_format), metadata=metadata, files=files,
                    reference_player=deepcopy(player_row(bundle['tables']['player_base'], pid, 0)),
                    reference_source=deepcopy(pbase))
    snapshot['snapshot_sha256'] = sha(selection_bytes(snapshot))
    dataset, source = build_dataset(snapshot)
    result = deepcopy(bundle)
    result['epm_import'] = dict(schema_version='0.1.0', snapshot=snapshot)
    impact = result.setdefault('impact_data', dict(schema_version='0.1.0', datasets=[], excluded=[]))
    impact['datasets'].append(dataset)
    impact['excluded'] = [e for e in impact.get('excluded', []) if e.get('family') != 'EPM']
    result['sources'][SID] = source
    result['warnings'] = [w for w in result.get('warnings', []) if not w.startswith('Impact EPM:')]
    validate_import(result)
    return result


def run(args):
    if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
        raise DataError('Choose a new empty EPM output directory')
    bundle = read_json(args.bundle)
    from retained_raw import verify_retained, copy_retained
    verify_retained(bundle, args.bundle.parent)
    payload, meta = args.file.read_bytes(), args.metadata.read_bytes()
    result = prepare_import(bundle, args.player_id, payload, args.file.suffix.lower().lstrip('.'), meta, args.file.name)
    from calculate_metrics import analyze
    analysis = analyze(result, dict(player_id=args.player_id, season=result['season'],
                                    season_type='Regular Season', team_id=0))
    args.out.mkdir(parents=True, exist_ok=True)
    copy_retained(bundle, args.bundle.parent, args.out)
    (args.out / 'raw').mkdir(exist_ok=True)
    snapshot = result['epm_import']['snapshot']
    (args.out / snapshot['files'][0]['raw_file']).write_bytes(payload)
    (args.out / 'raw/epm_metadata.json').write_bytes(meta)
    (args.out / 'raw/epm_selection.json').write_bytes(selection_bytes(snapshot))
    verify_retained(result, args.out)
    write_json(args.out / 'data_bundle.json', result)
    write_json(args.out / 'epm_import_audit.json', dict(status='validated_offline', adapter=ADAPTER,
               imported_at=now_iso(), player=analysis['player'], sample=analysis['sample'],
               source_id=SID, raw_files=snapshot['files'],
               reference_source_id='P_BASE', minutes_decimals=snapshot['metadata']['minutes_decimals'],
               component_tolerance=.15, network_requests=0,
               source_kind=snapshot['metadata'].get('source_kind', 'user_offline_export'),
               note='Raw export and metadata retained locally. No site access, subscription bypass, rank import or composite score.'))
    return args.out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True, help='Matching reference data_bundle.json')
    parser.add_argument('--file', type=Path, required=True, help='User-authorized UTF-8 Actual EPM CSV or JSON array')
    parser.add_argument('--metadata', type=Path, required=True, help='Explicit export scope, precision and column map JSON')
    parser.add_argument('--player-id', type=int, required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    try:
        print(run(args))
        return 0
    except (DataError, OSError, ValueError, KeyError, TypeError) as exc:
        print('ERROR: ' + str(exc), file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
