#!/usr/bin/env python3
"""One bounded full-parameter NBA Stats probe; offline diagnostics never access the network."""
import argparse
import importlib.util
import json
import sys
from pathlib import Path
from common import now_iso, write_json, DataError, validate_season
from fetch_data import Fetcher, FetchError


def diagnose(season, season_type, cache_dir, timeout=12, offline=False):
    validate_season(season, season_type)
    deps = {m: importlib.util.find_spec(m) is not None for m in ('nba_api', 'requests')}
    result = {'checked_at': now_iso(), 'python_executable': sys.executable,
              'python_version': sys.version.split()[0], 'dependencies': deps,
              'season': season, 'season_type': season_type, 'offline': offline,
              'endpoint': 'leaguedashplayerstats', 'max_attempts': 1}
    if not offline and not all(deps.values()):
        result.update(status='failed', category='missing_dependency',
                      next_action='Install requirements.txt into this Python environment; never infer endpoint outage from missing packages.')
        return result
    try:
        rows, source = Fetcher(cache_dir, timeout=timeout, retries=0, offline=offline, refresh=not offline).table('player_base', season, season_type)
        result.update(status='ok', category='usable_cache' if offline else 'live_success',
                      row_count=len(rows), source=source,
                      next_action='Run the full analysis; each optional endpoint can still fail independently.')
    except FetchError as exc:
        result.update(status='failed', category=exc.category,
                      next_action='Use a verified previous cache or source-documented JSON/CSV import. Do not bypass access controls or invent data.')
    except DataError as exc:
        result.update(status='failed', category='dependency_cache_or_schema_error', reason=str(exc),
                      next_action='Check interpreter, response schema and matching-sample import metadata.')
    return result


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--season', required=True)
    p.add_argument('--season-type', default='Regular Season', choices=['Regular Season', 'Playoffs'])
    p.add_argument('--cache-dir', type=Path, default=Path('.nba-player-analyst/cache'))
    p.add_argument('--timeout', type=float, default=12)
    p.add_argument('--offline', action='store_true')
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    if a.out.exists():
        p.error('Choose a new diagnostic output file; existing evidence is protected.')
    r = diagnose(a.season, a.season_type, a.cache_dir, a.timeout, a.offline)
    write_json(a.out, r)
    print(json.dumps(r, ensure_ascii=False, indent=2))
    return 0 if r['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
