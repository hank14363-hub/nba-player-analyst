"""Structured human observation locators, NOT automatic video verification."""
import re
from datetime import datetime, date
from urllib.parse import urlsplit
from common import DataError, digest, integer, read_json


def load_registered_film(run_dir, analysis):
    source = analysis['sources'].get('FILM')
    if not source:
        return None
    records = read_json(run_dir / 'film_records.json')
    if source.get('source_type') != 'film_records' or source.get('sha256_records') != digest(records):
        raise DataError('FILM records changed or are missing a registered checksum. Re-import into a new run.')
    return validate_film(records, analysis)


def template(analysis):
    return dict(schema_version='0.1.0', data_kind=analysis['data_kind'],
                identity=dict(player_id=analysis['player']['id'], season=analysis['sample']['season'],
                              season_type=analysis['sample']['season_type']), observations=[])


def validate_film(records, analysis):
    if not isinstance(records, dict) or records.get('schema_version') != '0.1.0':
        raise DataError('film_records needs schema_version=0.1.0.')
    if records.get('identity') != template(analysis)['identity'] or records.get('data_kind') != analysis['data_kind']:
        raise DataError('Film player/season/type/data_kind differs from analysis.')
    items = records.get('observations')
    if not isinstance(items, list):
        raise DataError('Film observations must be a list.')
    known = {}
    start_year = int(analysis['sample']['season'][:4])
    game_prefix = ('002' if analysis['sample']['season_type'] == 'Regular Season' else '004') + f'{start_year % 100:02d}'
    for item in items:
        if not isinstance(item, dict):
            raise DataError('Each film observation must be an object.')
        oid = item.get('id', '')
        if not isinstance(oid, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]{0,63}', oid) or oid in known:
            raise DataError('Film observation needs a unique safe ID.')
        for field in ('game_id', 'game_date', 'game_clock', 'video_url', 'video_timecode', 'observer',
                      'observation', 'alternative_explanation', 'selection_basis', 'observed_at'):
            if not isinstance(item.get(field), str) or not item[field].strip():
                raise DataError(oid + ': missing film field ' + field)
        if not re.fullmatch(game_prefix + r'\d{5}', item['game_id']):
            raise DataError(oid + ': game ID belongs to another season/type.')
        try:
            day = date.fromisoformat(item['game_date'])
            observed = datetime.fromisoformat(item['observed_at'].replace('Z', '+00:00'))
        except ValueError as exc:
            raise DataError(oid + ': invalid film date/timestamp.') from exc
        if day.year not in {start_year, start_year + 1} or observed.tzinfo is None or day > observed.date():
            raise DataError(oid + ': film date/scope/timezone mismatch.')
        period = integer(item.get('period'), 'film period')
        match = re.fullmatch(r'(\d{1,2}):([0-5]\d)', item['game_clock'])
        if period <= 0 or not match:
            raise DataError(oid + ': invalid period or game clock.')
        seconds = int(match[1]) * 60 + int(match[2])
        if seconds > (720 if period <= 4 else 300):
            raise DataError(oid + ': game clock exceeds quarter length.')
        if not re.fullmatch(r'\d{2,}:[0-5]\d:[0-5]\d', item['video_timecode']):
            raise DataError(oid + ': video timecode must be HH:MM:SS, separate from game clock.')
        link = urlsplit(item['video_url'])
        if link.scheme not in {'http', 'https'} or not link.netloc:
            raise DataError(oid + ': use a traceable http/https video source.')
        if item.get('evidence_kind') not in {'direct_observation', 'user_reported'}:
            raise DataError(oid + ': label direct_observation or user_reported.')
        if item.get('outcome') not in {'success', 'failure', 'neutral'}:
            raise DataError(oid + ': label success/failure/neutral; keep contrasting samples.')
        known[oid] = item
    return known
