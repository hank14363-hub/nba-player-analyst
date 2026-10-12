"""NBA Stats adapter. Network calls are bounded, cached, and never replaced with demo data."""
from __future__ import annotations

import importlib
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlencode
from common import VERSION, TABLES, DataError, digest, now_iso, read_json, write_json


class FetchError(DataError):
    """A classified failure, safe to persist without credentials or response bodies."""
    def __init__(self, category: str, attempts: int = 1):
        self.category, self.attempts = category, attempts
        super().__init__(f"NBA Stats request failed: {category}; attempts={attempts}. No substitute values were generated.")


def classify_error(exc: Exception) -> tuple[str, bool]:
    response = getattr(exc, "response", None)
    code = getattr(response, "status_code", None)
    if code in {401, 403}:
        return "access_denied", False
    if code == 429:
        return "rate_limited", False
    if code and 400 <= code < 500:
        return "http_client_error", False
    name = type(exc).__name__.lower()
    if "timeout" in name or isinstance(exc, TimeoutError):
        return "timeout", True
    if "ssl" in name:
        return "tls_error", False
    if "connection" in name or isinstance(exc, ConnectionError):
        return "connection_or_dns_error", True
    if "json" in name:
        return "non_json_response", False
    if code and code >= 500:
        return "server_error", True
    return "unexpected_transport_error", False

SPECS = {
    "player_base": ("leaguedashplayerstats", "LeagueDashPlayerStats", "Base", "Totals"),
    "team_base": ("leaguedashteamstats", "LeagueDashTeamStats", "Base", "Totals"),
    "player_advanced": ("leaguedashplayerstats", "LeagueDashPlayerStats", "Advanced", "Totals"),
    "player_per100": ("leaguedashplayerstats", "LeagueDashPlayerStats", "Base", "Per100Possessions"),
    "team_advanced": ("leaguedashteamstats", "LeagueDashTeamStats", "Advanced", "Totals"),
    "player_scoring": ("leaguedashplayerstats", "LeagueDashPlayerStats", "Scoring", "Totals"),
}
for _table, _measure in (("tracking_catchshoot", "CatchShoot"), ("tracking_pullup", "PullUpShot"),
                         ("tracking_passing", "Passing"), ("tracking_drives", "Drives")):
    SPECS[_table] = ("leaguedashptstats", "LeagueDashPtStats", _measure, "PerGame")


def unpack_rows(payload: dict, expected_name: str) -> list[dict]:
    sets = payload.get("resultSets", payload.get("resultSet", []))
    if isinstance(sets, dict):
        sets = [sets]
    matches = [s for s in sets if s.get("name") == expected_name]
    if len(matches) != 1:
        raise DataError(f"Missing or ambiguous NBA result set {expected_name}.")
    item = matches[0]
    headers, values = item.get("headers"), item.get("rowSet")
    if not isinstance(headers, list) or not headers or not all(isinstance(h, str) for h in headers):
        raise DataError("Unsupported NBA headers; provider schema may have changed.")
    if len(set(headers)) != len(headers) or not isinstance(values, list):
        raise DataError("Malformed NBA result set.")
    if any(not isinstance(row, list) or len(row) != len(headers) for row in values):
        raise DataError("NBA row/header lengths differ.")
    return [dict(zip(headers, row)) for row in values]


def nba_transport(module_name: str, class_name: str, params: dict, timeout: float) -> tuple[dict, dict]:
    try:
        module = importlib.import_module(f"nba_api.stats.endpoints.{module_name}")
    except ModuleNotFoundError as exc:
        raise DataError("Online mode requires nba_api. Install requirements.txt in your project virtual environment, or use --input/--offline.") from exc
    # Construct first, so HTTP status and non-JSON failures do not disappear in
    # nba_api's eager JSON parsing. Keep the client's complete default parameters.
    endpoint = getattr(module, class_name)(**params, timeout=timeout, get_request=False)
    import requests
    from nba_api.stats.library.http import STATS_HEADERS
    response = requests.get(f"https://stats.nba.com/stats/{module_name}",
                            params=endpoint.parameters, headers=STATS_HEADERS, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    return payload, dict(endpoint.parameters)


class Fetcher:
    def __init__(self, cache_dir: Path, timeout: float = 20, retries: int = 2,
                 ttl_hours: float = 24, offline: bool = False, refresh: bool = False,
                 transport: Callable = nba_transport, sleep: Callable = time.sleep):
        if timeout <= 0 or not 0 <= retries <= 5 or ttl_hours < 0:
            raise DataError("timeout must be positive; retries must be 0..5; cache TTL must be nonnegative.")
        if offline and refresh:
            raise DataError("--offline and --refresh are incompatible.")
        self.cache_dir, self.timeout, self.retries = cache_dir, timeout, retries
        self.ttl_hours, self.offline, self.refresh = ttl_hours, offline, refresh
        self.transport, self.sleep = transport, sleep
        self.last_call = 0.0

    def table(self, table: str, season: str, season_type: str, team_id: int = 0) -> tuple[list[dict], dict]:
        module, cls, measure, mode = SPECS[table]
        params: dict[str, Any] = {"season": season, "season_type_all_star": season_type,
                                  "league_id_nullable": "00"}
        if table.startswith("tracking_"):
            params.update(per_mode_simple=mode, player_or_team="Player", pt_measure_type=measure,
                          team_id_nullable=team_id or "")
        else:
            params.update(measure_type_detailed_defense=measure, per_mode_detailed=mode)
            if table.startswith("player_"):
                params["team_id_nullable"] = team_id or ""
        key = digest({"schema": VERSION, "endpoint": module, "params": params})
        cache_path = self.cache_dir / f"{key}.json"
        cache = None
        if cache_path.exists() and not self.refresh:
            try:
                cache = read_json(cache_path)
                if cache["key"] != key or digest(cache["rows"]) != cache["source"]["sha256_rows"]:
                    raise DataError("Cache integrity failure.")
                retrieved = datetime.fromisoformat(cache["source"]["retrieved_at"].replace("Z", "+00:00"))
                age = (datetime.now(timezone.utc) - retrieved).total_seconds() / 3600
                if retrieved.tzinfo is None or age < -0.1:
                    raise DataError("Invalid cache timestamp.")
            except (KeyError, TypeError, ValueError) as exc:
                if self.offline:
                    raise DataError(f"Corrupt cache: {cache_path}") from exc
                cache = None
            if cache is not None and (self.offline or age <= self.ttl_hours):
                source = dict(cache["source"], from_cache=True, stale=age > self.ttl_hours,
                              accessed_at=now_iso())
                return cache["rows"], source
        if self.offline:
            raise DataError(f"No usable cache for {table}; supply --input or fetch online once.")
        error = None
        for attempt in range(self.retries + 1):
            self.sleep(max(0.0, 1.1 - (time.monotonic() - self.last_call)))
            self.last_call = time.monotonic()
            try:
                payload, actual_params = self.transport(module, cls, params, self.timeout)
                rows = unpack_rows(payload, cls)
                if not rows:
                    raise DataError(f"Empty {table}; season/sample may not exist or tracking may be unavailable.")
                source = {"provider": "NBA Stats via nba_api", "status": "ok", "endpoint": module,
                          "url": f"https://stats.nba.com/stats/{module}?{urlencode(actual_params)}",
                          "parameters": actual_params, "season": season, "season_type": season_type,
                          "per_mode": mode, "measure": measure, "retrieved_at": now_iso(),
                          "row_count": len(rows), "sha256_rows": digest(rows), "from_cache": False,
                          "stale": False, "player_team_id": team_id if not table.startswith("team_") else 0}
                if table == "team_base":
                    source["coverage"] = "full_league"
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                write_json(cache_path, {"key": key, "rows": rows, "source": source})
                return rows, source
            except DataError:
                # Dependency/schema/empty-result failures are not transient network failures.
                raise
            except Exception as exc:
                error = exc
                category, retryable = classify_error(exc)
                if not retryable:
                    raise FetchError(category, attempt + 1) from exc
                if attempt < self.retries:
                    self.sleep(min(2 ** attempt * 2, 8))
        raise FetchError(classify_error(error)[0], self.retries + 1) from error

    def onoff(self, season: str, season_type: str, team_id: int) -> tuple[list[dict], dict]:
        if team_id <= 0:
            raise DataError("On/off requires a positive team ID; do not infer a traded player's stint.")
        params = {"team_id": team_id, "season": season,
                  "season_type_all_star": season_type, "league_id_nullable": "00",
                  "measure_type_detailed_defense": "Advanced", "per_mode_detailed": "Totals"}
        key = digest({"schema": VERSION, "endpoint": "teamplayeronoffsummary", "params": params})
        path = self.cache_dir / f"{key}.json"
        if path.exists() and not self.refresh:
            cache = read_json(path)
            if cache.get('key') != key or digest(cache.get('rows')) != cache.get('source', {}).get('sha256_rows'):
                raise DataError("On/off cache integrity failure; refresh or remove only this cache entry.")
            retrieved = datetime.fromisoformat(cache['source']['retrieved_at'].replace('Z', '+00:00'))
            if retrieved.tzinfo is None:
                raise DataError("Invalid on/off cache timestamp.")
            age = (datetime.now(timezone.utc) - retrieved).total_seconds() / 3600
            if age < -0.1:
                raise DataError("Invalid on/off cache timestamp.")
            if self.offline or age <= self.ttl_hours:
                return cache['rows'], dict(cache['source'], from_cache=True, stale=age > self.ttl_hours, accessed_at=now_iso())
        if self.offline:
            raise DataError("No usable on/off cache.")
        for attempt in range(self.retries + 1):
            self.sleep(max(0.0, 1.1 - (time.monotonic() - self.last_call)))
            self.last_call = time.monotonic()
            try:
                payload, actual = self.transport('teamplayeronoffsummary', 'TeamPlayerOnOffSummary', params, self.timeout)
                rows = []
                for state, name in (('On', 'PlayersOnCourtTeamPlayerOnOffSummary'), ('Off', 'PlayersOffCourtTeamPlayerOnOffSummary')):
                    for row in unpack_rows(payload, name):
                        if row.get('COURT_STATUS') != state:
                            raise DataError("Unexpected COURT_STATUS in on/off result set.")
                        rows.append(dict(row, PLAYER_ID=row['VS_PLAYER_ID']))
                if not rows:
                    raise DataError("Empty on/off data.")
                source = {'provider': 'NBA Stats via nba_api', 'status': 'ok',
                          'endpoint': 'teamplayeronoffsummary', 'parameters': actual,
                          'url': 'https://stats.nba.com/stats/teamplayeronoffsummary?' + urlencode(actual),
                          'season': season, 'season_type': season_type, 'per_mode': 'Totals',
                          'team_id': team_id, 'sample_scope': 'full_team_season',
                          'metric_definition': 'team_oncourt', 'retrieved_at': now_iso(),
                          'row_count': len(rows), 'sha256_rows': digest(rows), 'from_cache': False, 'stale': False}
                write_json(path, {'key': key, 'rows': rows, 'source': source})
                return rows, source
            except DataError:
                raise
            except Exception as exc:
                category, retryable = classify_error(exc)
                if not retryable or attempt == self.retries:
                    raise FetchError(category, attempt + 1) from exc
                self.sleep(min(2 ** attempt * 2, 8))

    def shots(self, season: str, season_type: str, player_id: int, team_id: int = 0) -> tuple[list[dict], dict]:
        if player_id <= 0 or team_id < 0:
            raise DataError('Shot chart requires a positive player ID and nonnegative team filter.')
        params = dict(team_id=team_id, player_id=player_id, context_measure_simple='FGA',
                      season_nullable=season, season_type_all_star=season_type)
        key = digest({'schema': VERSION, 'endpoint': 'shotchartdetail', 'params': params})
        path = self.cache_dir / (key + '.json')
        if path.exists() and not self.refresh:
            cache = read_json(path)
            if cache.get('key') != key or digest(cache.get('rows')) != cache.get('source', {}).get('sha256_rows'):
                raise DataError('Shot cache integrity failure.')
            retrieved = datetime.fromisoformat(cache['source']['retrieved_at'].replace('Z', '+00:00'))
            if retrieved.tzinfo is None:
                raise DataError('Shot cache needs a timezone.')
            age = (datetime.now(timezone.utc) - retrieved).total_seconds() / 3600
            if age < -.1:
                raise DataError('Shot cache timestamp is in the future.')
            if self.offline or age <= self.ttl_hours:
                return cache['rows'], dict(cache['source'], from_cache=True, stale=age > self.ttl_hours, accessed_at=now_iso())
        if self.offline:
            raise DataError('No usable shot cache.')
        for attempt in range(self.retries + 1):
            self.sleep(max(0., 1.1 - (time.monotonic() - self.last_call)))
            self.last_call = time.monotonic()
            try:
                payload, actual = self.transport('shotchartdetail', 'ShotChartDetail', params, self.timeout)
                rows = unpack_rows(payload, 'Shot_Chart_Detail')
                if not rows:
                    raise DataError('No shot events returned; no substitute coordinates generated.')
                source = dict(provider='NBA Stats via nba_api', status='ok', endpoint='shotchartdetail',
                    parameters=actual, url='https://stats.nba.com/stats/shotchartdetail?' + urlencode(actual),
                    season=season, season_type=season_type, per_mode='Events', player_id=player_id,
                    player_team_id=team_id, coordinate_units='tenths_of_foot', context_measure='FGA',
                    retrieved_at=now_iso(), row_count=len(rows), sha256_rows=digest(rows), from_cache=False, stale=False)
                write_json(path, dict(key=key, rows=rows, source=source))
                return rows, source
            except DataError:
                raise
            except Exception as exc:
                category, retryable = classify_error(exc)
                if not retryable or attempt == self.retries:
                    raise FetchError(category, attempt + 1) from exc
                self.sleep(min(2 ** attempt * 2, 8))

    def collect(self, season: str, season_type: str, team_id: int = 0, tracking: bool = False, onoff_team_id: int = 0) -> dict:
        bundle = {"schema_version": VERSION, "data_kind": "nba", "season": season,
                  "season_type": season_type, "player_team_id": team_id,
                  "tables": {}, "sources": {}, "warnings": []}
        for table, (source_id, _) in TABLES.items():
            if table in {'player_onoff', 'player_shots'}:
                continue
            if table.startswith("tracking_") and not tracking:
                continue
            try:
                rows, source = self.table(table, season, season_type, team_id)
                bundle["tables"][table] = rows
                bundle["sources"][source_id] = source
                if source.get("stale"):
                    bundle["warnings"].append(f"{source_id}: stale offline cache; retrieval date was NOT updated.")
            except DataError as exc:
                if table == "player_base":
                    raise
                bundle["tables"][table] = []
                bundle["sources"][source_id] = {"status": "missing", "reason": str(exc)}
                bundle["warnings"].append(f"{source_id}: {exc}")
        if onoff_team_id:
            try:
                rows, source = self.onoff(season, season_type, onoff_team_id)
                bundle['tables']['player_onoff'] = rows
                bundle['sources']['P_ONOFF'] = source
            except DataError as exc:
                bundle['tables']['player_onoff'] = []
                bundle['sources']['P_ONOFF'] = {'status': 'missing', 'reason': str(exc)}
                bundle['warnings'].append('P_ONOFF: ' + str(exc))
        return bundle
