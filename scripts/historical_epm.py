"""Retain historical EPM readings with mandatory unresolved-scope disclosure."""
from copy import deepcopy
from datetime import date, datetime
import json
from pathlib import Path

from common import (DataError, digest, integer, normalize_name, number, now_iso,
                    player_row, read_json, resolve_player, validate_bundle, write_json)
from import_epm import KAGGLE_URL, parse_rows, selection_bytes, sha

ADAPTER = 'deocheng-historical-epm-v1'
FAMILY = 'EPM_HISTORICAL'
SID = 'EXT_IMPACT_EPM_HISTORICAL'
CSV_SHA = '2c50d0376da10cec54d6fba105d5f2a339d660f7f1db505075e83b6abac9a067'
NOTE = '历史 EPM 快照（口径待核验）：由 Kaggle 转引；估计类型、比赛范围和模型版本未独立核实，缺少可核验的球员场次及总分钟。仅作补充读数，不作为整季常规赛 Actual EPM、已验证预测、能力排名或确定性攻防结论。'


def select(rows, pid, season, source=None, snapshot_date=None):
    candidates = [r for r in rows if integer(r.get('nba_player_id'), 'historical NBA ID') == pid
                  and integer(r.get('season'), 'historical ending year') == int(season[:4]) + 1]
    matches = [r for r in candidates if (source is None or r.get('source') == source)
               and (snapshot_date is None or r.get('game_dt') == snapshot_date)]
    if len(matches) != 1:
        raise DataError('Historical EPM selector must resolve exactly one row; specify --source and/or --snapshot-date for duplicate candidates')
    return matches[0]


def build_dataset(snapshot):
    if snapshot.get('schema_version') != '0.1.0' or snapshot.get('adapter') != ADAPTER:
        raise DataError('Unsupported historical EPM contract')
    base = snapshot['reference_player']; meta = snapshot['metadata']; row = snapshot['raw_row']
    pid = integer(snapshot['player_id'], 'historical NBA ID'); season = snapshot['season']
    if snapshot['season_type'] != 'Regular Season' or snapshot['player_team_id'] != 0:
        raise DataError('Historical EPM attachment currently requires a full regular-season reference; provider scope remains unverified')
    if not 2002 <= int(season[:4]) + 1 <= 2026:
        raise DataError('Historical EPM year outside reviewed v1 file')
    if (meta.get('source_url') != KAGGLE_URL or meta.get('dataset_version') != 1
            or meta.get('sample_scope') != 'unverified' or meta.get('estimate_type') != 'historical_snapshot_unverified'
            or meta.get('snapshot_date') != '2026-08-18'):
        raise DataError('Historical EPM must retain its unverified scope and Kaggle v1 provenance')
    try:
        if datetime.fromisoformat(meta['acquired_at'].replace('Z', '+00:00')).tzinfo is None:
            raise ValueError()
        stamp = date.fromisoformat(row['game_dt'])
        if not date(int(season[:4]), 7, 1) <= stamp <= date(int(season[:4]) + 1, 6, 30):
            raise ValueError()
    except (KeyError, ValueError, TypeError) as exc:
        raise DataError('Historical EPM needs a timezone acquisition timestamp and recorded date within its season year') from exc
    files = snapshot.get('files')
    if (not isinstance(files, list) or len(files) != 2
            or files[0] != dict(raw_file='raw/historical_epm_export.csv', sha256_raw=CSV_SHA)
            or files[1].get('raw_file') != 'raw/historical_epm_metadata.json'
            or files[1].get('sha256_raw') != sha((json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode())):
        raise DataError('Historical EPM original CSV/metadata artifacts mismatch')
    if (integer(base['PLAYER_ID'], 'reference NBA ID') != pid or integer(row['nba_player_id'], 'historical NBA ID') != pid
            or integer(row['season'], 'historical year') != int(season[:4]) + 1
            or normalize_name(row['player_name']) != normalize_name(base['PLAYER_NAME'])):
        raise DataError('Historical EPM exact name/NBA ID/season mismatch')
    if row.get('source') not in ('dunksandthrees.com/player/eskills', 'dunksandthrees.com/epm'):
        raise DataError('Unexpected historical EPM upstream source')
    try:
        embedded = json.loads(row['raw'])
        for col, key in [('nba_player_id', 'player_id'), ('season', 'season'), ('epm_tot', 'tot'), ('epm_off', 'off'), ('epm_def', 'def')]:
            if number(row[col]) != number(embedded[key]):
                raise DataError('Historical CSV and retained provider JSON differ: ' + col)
        if normalize_name(embedded['player_name']) != normalize_name(row['player_name']) or embedded['game_dt'] != row['game_dt']:
            raise DataError('Historical embedded identity/date mismatch')
    except DataError:
        raise
    except (KeyError, ValueError, TypeError) as exc:
        raise DataError('Cannot verify historical EPM embedded JSON') from exc
    normalized = dict(nba_id=pid, player_name=row['player_name'], season=season,
                      as_of=row['game_dt'], provider_source=row['source'], sample_scope='unverified',
                      tot=number(row['epm_tot']), off=number(row['epm_off']), **{'def': number(row['epm_def'])})
    if abs(normalized['tot'] - normalized['off'] - normalized['def']) > .15 + 1e-12:
        raise DataError('Historical EPM components fail tolerance 0.15')
    model = 'unknown; archived Kaggle v1 historical EPM, estimate definition unverified'
    caveats = [NOTE, '原始记录日期为' + row['game_dt'] + '；该日期可能晚于常规赛结束，不声称为当时已公布的历史模型版本。',
               '原表n/n_rapm不是球员场次或已核验回合数；不导入原表排名，不用其他表拼接GP/MIN制造覆盖已验证的印象。',
               '原始文件SHA-256和身份/分量核验只确认本次保留与转换一致，不证明提供者真实性、授权、模型正确性或不确定性。']
    dataset = dict(family=FAMILY, player_id=pid, player_team_id=0, season=season,
                   season_type='Regular Season', provider_season_type='unverified', sample_scope='unverified',
                   estimate_type='historical_snapshot_unverified', model_version=model,
                   cutoff=row['game_dt'], source_id=SID, raw_rows=[normalized],
                   selector=dict(nba_id=pid, season=season, as_of=row['game_dt'], provider_source=row['source']), caveats=caveats)
    source = dict(provider='Dunks & Threes → Kaggle / deocheng v1 · historical EPM',
                  url=KAGGLE_URL, upstream_url='https://' + row['source'], retrieved_at=meta['acquired_at'],
                  acquisition_time_basis='Actual Kaggle download time; provider release time unverified',
                  upstream_scraped_at=row.get('scraped_at'), status='ok', source_type='impact_data',
                  source_kind=ADAPTER, season=season, season_type='Regular Season', provider_season_type='unverified',
                  sample_scope='unverified', estimate_type='historical_snapshot_unverified', per_mode='Archived provider reading',
                  model_version=model, cutoff=row['game_dt'], row_count=1, sha256_rows=digest([normalized]),
                  raw_file='raw/historical_epm_selection.json', sha256_raw=snapshot['snapshot_sha256'],
                  raw_artifacts=deepcopy(files), display_title='历史 EPM 快照（口径待核验）',
                  dataset_version=1, dataset_file='csv/public.player_epm.csv', usage='；'.join(caveats))
    return dataset, source


def validate_import(bundle):
    contract = bundle.get('historical_epm_import')
    if not isinstance(contract, dict) or contract.get('schema_version') != '0.1.0':
        raise DataError('Historical EPM requires a retained import contract')
    snapshot = contract['snapshot']
    if sha(selection_bytes(snapshot)) != snapshot.get('snapshot_sha256'):
        raise DataError('Historical EPM selection checksum mismatch')
    for key in ('season', 'season_type', 'player_team_id', 'data_kind'):
        if snapshot.get(key) != bundle.get(key):
            raise DataError('Historical EPM reference scope changed: ' + key)
    base = player_row(bundle['tables']['player_base'], snapshot['player_id'], 0)
    if digest(base) != digest(snapshot['reference_player']) or bundle['sources']['P_BASE'] != snapshot['reference_source']:
        raise DataError('Historical EPM reference identity/provenance changed')
    dataset, source = build_dataset(snapshot)
    actual = [d for d in bundle.get('impact_data', {}).get('datasets', []) if d.get('family') == FAMILY]
    if digest(actual) != digest([dataset]) or bundle['sources'].get(SID) != source:
        raise DataError('Historical EPM conversion or mandatory disclosure differs from retained inputs')


def validate_files(bundle, root):
    if bundle.get('historical_epm_import') is None:
        return
    validate_import(bundle)
    from retained_raw import checked_path
    snap = bundle['historical_epm_import']['snapshot']
    for record in snap['files']:
        if sha(checked_path(root, record['raw_file']).read_bytes()) != record['sha256_raw']:
            raise DataError('Historical EPM original file checksum mismatch')
    meta = json.loads(checked_path(root, snap['files'][1]['raw_file']).read_text(encoding='utf-8'))
    if meta != snap['metadata']:
        raise DataError('Historical EPM metadata file differs')
    rows = parse_rows(checked_path(root, snap['files'][0]['raw_file']).read_bytes(), 'csv')
    row = select(rows, snap['player_id'], snap['season'], snap['raw_row']['source'], snap['raw_row']['game_dt'])
    if row != snap['raw_row']:
        raise DataError('Historical EPM row differs from original CSV')


def prepare_import(bundle, pid, payload, acquired_at, source=None, snapshot_date=None):
    validate_bundle(bundle, bundle['season'], bundle['season_type'], bundle.get('player_team_id', 0))
    if bundle['season_type'] != 'Regular Season' or bundle.get('player_team_id', 0) != 0:
        raise DataError('Historical EPM currently attaches only to a full regular-season reference')
    if bundle.get('historical_epm_import') or SID in bundle['sources'] or any(d.get('family') == FAMILY for d in bundle.get('impact_data', {}).get('datasets', [])):
        raise DataError('Historical EPM already present; never silently overwrite')
    if sha(payload) != CSV_SHA:
        raise DataError('Historical EPM file differs from reviewed Kaggle v1 bytes')
    pid, _ = resolve_player(bundle['tables']['player_base'], None, pid)
    if bundle['sources']['P_BASE'].get('sha256_rows') != digest(bundle['tables']['player_base']):
        raise DataError('Historical EPM needs hashed reference identity')
    row = select(parse_rows(payload, 'csv'), pid, bundle['season'], source, snapshot_date)
    meta = dict(schema_version='0.1.0', source_url=KAGGLE_URL, dataset_version=1,
                snapshot_date='2026-08-18', acquired_at=acquired_at,
                estimate_type='historical_snapshot_unverified', sample_scope='unverified')
    meta_bytes = (json.dumps(meta, ensure_ascii=False, sort_keys=True, indent=2) + '\n').encode()
    snapshot = dict(schema_version='0.1.0', adapter=ADAPTER, season=bundle['season'],
                    season_type=bundle['season_type'], player_team_id=0, data_kind=bundle['data_kind'],
                    player_id=pid, raw_row=row, metadata=meta,
                    reference_player=deepcopy(player_row(bundle['tables']['player_base'], pid, 0)),
                    reference_source=deepcopy(bundle['sources']['P_BASE']),
                    files=[dict(raw_file='raw/historical_epm_export.csv', sha256_raw=sha(payload)),
                           dict(raw_file='raw/historical_epm_metadata.json', sha256_raw=sha(meta_bytes))])
    snapshot['snapshot_sha256'] = sha(selection_bytes(snapshot))
    dataset, entry = build_dataset(snapshot)
    result = deepcopy(bundle)
    result['historical_epm_import'] = dict(schema_version='0.1.0', snapshot=snapshot)
    result.setdefault('impact_data', dict(schema_version='0.1.0', datasets=[], excluded=[]))['datasets'].append(dataset)
    result['sources'][SID] = entry
    result.setdefault('warnings', []).append(NOTE + ' 原始记录日期：' + row['game_dt'] + '。')
    validate_import(result)
    return result, meta_bytes


def run(args):
    if args.out.exists() and any(args.out.iterdir()):
        raise DataError('Choose a new empty historical EPM output directory')
    from retained_raw import verify_retained, copy_retained
    bundle = read_json(args.bundle); verify_retained(bundle, args.bundle.parent)
    result, metadata = prepare_import(bundle, args.player_id, args.file.read_bytes(), args.acquired_at,
                                      getattr(args, 'source', None), getattr(args, 'snapshot_date', None))
    from calculate_metrics import analyze
    analyze(result, dict(player_id=args.player_id, season=bundle['season'], season_type=bundle['season_type'], team_id=0))
    args.out.mkdir(parents=True, exist_ok=True); copy_retained(bundle, args.bundle.parent, args.out)
    (args.out / 'raw').mkdir(exist_ok=True)
    (args.out / 'raw/historical_epm_export.csv').write_bytes(args.file.read_bytes())
    (args.out / 'raw/historical_epm_metadata.json').write_bytes(metadata)
    (args.out / 'raw/historical_epm_selection.json').write_bytes(selection_bytes(result['historical_epm_import']['snapshot']))
    verify_retained(result, args.out)
    write_json(args.out / 'data_bundle.json', result)
    write_json(args.out / 'historical_epm_import_audit.json', dict(status='archived_reading_imported_scope_unverified',
               imported_at=now_iso(), player_id=args.player_id, season=bundle['season'],
               raw_date=result['historical_epm_import']['snapshot']['raw_row']['game_dt'],
               source_id=SID, note=NOTE, gp_verified=False, minutes_verified=False,
               estimate_type_verified=False, provider_competition_verified=False, network_requests=0))
    return args.out
