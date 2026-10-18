"""Deterministic metrics; missing information never becomes a fabricated estimate."""
from __future__ import annotations

from typing import Any

from common import SKILL_ROOT, TABLES, VERSION, DataError, integer, now_iso, number, player_row, read_json, resolve_player, validate_bundle
from supplemental_metrics import onoff_context, tracking_metrics
from shot_charts import shot_context, register_shot_metrics


def safe_ratio(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def counts(row: dict, context: str) -> dict[str, float | None]:
    fields = ("GP", "MIN", "PTS", "FGM", "FGA", "FG3M", "FG3A", "FTM", "FTA", "REB", "AST", "TOV", "STL", "BLK", "PF")
    values = {f: number(row.get(f), f"{context}.{f}", optional=True) for f in fields}
    for field, value in values.items():
        if value is not None and (value < 0 or (field != "MIN" and value != int(value))):
            raise DataError(f"{context}.{field} must be a nonnegative season TOTAL (MIN may be fractional).")
    for made, attempted in (("FGM", "FGA"), ("FG3M", "FG3A"), ("FTM", "FTA"), ("FG3M", "FGM"), ("FG3A", "FGA")):
        if values[made] is not None and values[attempted] is not None and values[made] > values[attempted]:
            raise DataError(f"{context}: {made} exceeds {attempted}.")
    if all(values[f] is not None for f in ("PTS", "FGM", "FG3M", "FTM")):
        if abs(values["PTS"] - (2 * values["FGM"] + values["FG3M"] + values["FTM"])) > 0.01:
            raise DataError(f"{context}: PTS != 2*FGM + FG3M + FTM. Check totals, units, or data corruption.")
    return values


def sum_required(values: list[dict], fields: tuple[str, ...]) -> dict[str, float]:
    output = {}
    for field in fields:
        if any(row.get(field) is None for row in values):
            raise DataError(f"League totals are incomplete: missing {field}.")
        output[field] = sum(row[field] for row in values)
    return output


def display_value(value: float | None, unit: str) -> str:
    if value is None:
        return "N/A"
    if unit == "fraction":
        return f"{value * 100:.1f}%"
    if unit == "percentage_points":
        return f"{value:+.2f} pp"
    if unit == "count":
        return f"{value:.0f}"
    return f"{value:.2f}"


def analyze(bundle: dict, request: dict) -> dict:
    season, season_type = request["season"], request["season_type"]
    team_id = int(request.get("team_id") or 0)
    validate_bundle(bundle, season, season_type, team_id)
    tables = bundle["tables"]
    sources = bundle["sources"]
    player_id, player_name = resolve_player(tables["player_base"], request.get("player"), request.get("player_id"))
    base = player_row(tables["player_base"], player_id, team_id)
    totals = counts(base, "player_base")
    for field in ("GP", "MIN", "PTS", "FGA", "FTA"):
        if totals[field] is None:
            raise DataError(f"player_base.{field} is required.")
    if totals["GP"] <= 0 or totals["MIN"] <= 0:
        raise DataError("Player has no positive games/minutes in this sample.")
    if totals["MIN"] > totals["GP"] * 80:
        raise DataError("Implausible minutes per game. Check units.")
    warnings = list(bundle.get("warnings", []))
    if totals["GP"] < 20 or totals["MIN"] < 500:
        warnings.append("Small sample flag (project heuristic: GP < 20 or MIN < 500), NOT a calibrated statistical confidence threshold.")
    if totals.get("FG3A") is not None and totals["FG3A"] < 100:
        warnings.append("Fewer than 100 three-point attempts; shooting-talent conclusions are especially uncertain. This is a heuristic.")
    if bundle["data_kind"] == "synthetic":
        warnings.insert(0, "SYNTHETIC TEST DATA ONLY: not an NBA player, not real NBA statistics, not publishable analysis.")
    labels = read_json(SKILL_ROOT / "references" / "metric_labels.json")
    metrics: list[dict[str, Any]] = []

    def add(mid: str, value: float | None, unit: str, source_ids: list[str], formula: str = "", reason: str = "") -> None:
        metrics.append({"metric_id": mid, "label": labels.get(mid, mid), "value": value,
                        "display": display_value(value, unit), "unit": unit,
                        "status": "ok" if value is not None else "missing",
                        "source_ids": source_ids, "formula": formula,
                        "reason": reason if value is None else ""})

    for field, unit in (("GP", "count"), ("MIN", "minutes"), ("FGA", "count"), ("FG3A", "count"), ("FTA", "count")):
        add(field, totals[field], unit, ["P_BASE"], f"player_base.{field}", "Field unavailable")
    for field in ("PTS", "MIN", "REB", "AST", "TOV", "STL", "BLK", "PF"):
        add(f"{field}_PER_GAME", safe_ratio(totals[field], totals["GP"]), "per_game", ["P_BASE"], f"{field} / GP", "Missing count or zero games")
    tsa = 2 * (totals["FGA"] + 0.44 * totals["FTA"])
    ts = safe_ratio(totals["PTS"], tsa)
    add("TS_PCT", ts, "fraction", ["P_BASE"], "PTS / (2 * (FGA + 0.44 * FTA))", "Zero shooting denominator")
    efg_numerator = None if totals["FGM"] is None or totals["FG3M"] is None else totals["FGM"] + 0.5 * totals["FG3M"]
    add("EFG_PCT", safe_ratio(efg_numerator, totals["FGA"]), "fraction", ["P_BASE"], "(FGM + 0.5*FG3M) / FGA", "Missing makes or zero FGA")
    for mid, numerator, denominator, unit in (("FG3_PCT", "FG3M", "FG3A", "fraction"),
                                              ("FG3A_RATE", "FG3A", "FGA", "fraction"),
                                              ("FT_RATE", "FTA", "FGA", "ratio"),
                                              ("AST_TOV", "AST", "TOV", "ratio")):
        add(mid, safe_ratio(totals[numerator], totals[denominator]), unit, ["P_BASE"], f"{numerator} / {denominator}", "Missing input or zero denominator; no infinity")

    league_ts = None
    league_reason = "Full, unfiltered league team totals unavailable. Never average player TS%."
    if tables.get("team_base") and sources.get("T_BASE", {}).get("coverage") == "full_league":
        try:
            teams = tables["team_base"]
            ids = [integer(r.get("TEAM_ID"), "TEAM_ID") for r in teams]
            if len(ids) < 2 or len(ids) != len(set(ids)) or any(i <= 0 for i in ids):
                raise DataError("League team rows duplicate, contain aggregate IDs, or lack coverage.")
            sums = sum_required([counts(row, "team_base") for row in teams], ("PTS", "FGA", "FTA"))
            league_ts = safe_ratio(sums["PTS"], 2 * (sums["FGA"] + 0.44 * sums["FTA"]))
            if league_ts is None:
                league_reason = "League shooting denominator is zero."
        except DataError as exc:
            league_reason = str(exc)
            warnings.append("League baseline rejected: " + str(exc))
    add("LEAGUE_TS_PCT", league_ts, "fraction", ["T_BASE"], "sum(team PTS) / (2*(sum(team FGA)+0.44*sum(team FTA)))", league_reason)
    add("RTS_PP", None if ts is None or league_ts is None else (ts - league_ts) * 100,
        "percentage_points", ["P_BASE", "T_BASE"], "100 * (TS_PCT - LEAGUE_TS_PCT)", league_reason)

    selected: dict[str, dict] = {"player_base": base}
    for table in ("player_advanced", "player_per100", "player_scoring", "tracking_catchshoot", "tracking_pullup", "tracking_passing", "tracking_drives"):
        if not tables.get(table):
            continue
        try:
            row = player_row(tables[table], player_id, team_id)
            if row.get("GP") is not None:
                gp = number(row["GP"], f"{table}.GP")
                if gp != totals["GP"]:
                    if table.startswith("tracking_"):
                        warnings.append(f"{table}: tracking GP={gp} differs from base GP={totals['GP']}; keep separate denominators and state coverage.")
                    else:
                        raise DataError("GP differs from base; possible snapshot/sample mismatch")
            if table in {"player_advanced", "player_scoring"} and row.get("MIN") is not None:
                minutes = number(row["MIN"], f"{table}.MIN")
                source = sources.get(TABLES[table][0], {})
                official = source.get('endpoint') == 'leaguedashplayerstats'
                # Real NBA Scoring responses may return MIN as a rounded per-game
                # value despite PerMode=Totals; never rewrite original rows.
                mean_matches = official and number(row.get('GP'), f'{table}.GP', optional=True) == totals['GP'] and abs(minutes * totals['GP'] - totals['MIN']) <= max(1, .051 * totals['GP'])
                if abs(minutes - totals['MIN']) > 1.0 and not mean_matches:
                    raise DataError("MIN differs from base in both total and verified NBA per-game interpretations; possible sample mismatch")
                if table == 'player_scoring':
                    for field in ('FGM', 'FGA'):
                        if row.get(field) is not None and number(row[field], field) != totals[field]:
                            raise DataError('Scoring shot counts differ from base.')
            selected[table] = row
        except DataError as exc:
            warnings.append(f"{table} excluded: {exc}")

    def sourced(table: str, field: str, mid: str, unit: str, multiplier: float = 1.0) -> None:
        row = selected.get(table, {})
        reason = f"{table}.{field} missing or unverified; not inferred from box-score totals."
        try:
            value = number(row.get(field), f"{table}.{field}", optional=True)
            if value is not None and unit == "fraction" and not 0 <= value <= 1:
                raise DataError("Expected decimal fraction 0..1, not a 0..100 percentage.")
            if value is not None and unit == "per75" and value < 0:
                raise DataError("Per-possession counts cannot be negative.")
            if value is not None:
                value *= multiplier
        except DataError as exc:
            value, reason = None, str(exc)
            warnings.append(f"{mid} excluded: {exc}")
        add(mid, value, unit, [TABLES[table][0]], f"{table}.{field}" + (f" * {multiplier}" if multiplier != 1 else ""), reason)

    for field in ("USG_PCT", "AST_PCT"):
        sourced("player_advanced", field, field, "fraction")
    for field in ("OFF_RATING", "DEF_RATING", "NET_RATING"):
        raw = selected.get('player_advanced', {}).get(field)
        source = sources.get('P_ADV', {})
        official = source.get('endpoint') == 'leaguedashplayerstats' and source.get('parameters', {}).get('MeasureType') == 'Advanced'
        if raw is not None and bundle['data_kind'] != 'synthetic' and not official and source.get('metric_definition') != 'team_oncourt':
            add(f'ONCOURT_{field}', None, 'per100_team', ['P_ADV'], 'Not comparable', 'Provider player estimates are not verified team-oncourt ratings.')
            warnings.append('P_ADV ratings excluded: provider semantics differ from team-oncourt ratings.')
            continue
        sourced("player_advanced", field, f"ONCOURT_{field}", "per100_team")
    for field in ("PTS", "REB", "AST", "TOV"):
        sourced("player_per100", field, f"{field}_PER75", "per75", 0.75)
    for field in ("PCT_AST_FGM", "PCT_UAST_FGM", "PCT_AST_3PM"):
        sourced("player_scoring", field, field, "fraction")
    # Optional declared provider shooting-profile fields; old bundles keep their metric set.
    for field, unit in [('PCT_AST_2PM', 'fraction'), ('AVG_SHOT_DISTANCE_FT', 'feet')] + [
            (prefix + band, 'fraction') for band in ('0_3','3_10','10_16','16_3P','3P')
            for prefix in ('PCT_FGA_', 'FG_PCT_')]:
        if sources.get('P_SCORE', {}).get('adapter') in {'deocheng-v1','sumitro-v56'} and field in selected.get('player_scoring', {}):
            sourced('player_scoring', field, field, unit)
    scoring = selected.get('player_scoring', {})
    if scoring.get('PCT_AST_FGM') is not None and scoring.get('PCT_UAST_FGM') is not None:
        valid_pair = [m for m in metrics if m['metric_id'] in {'PCT_AST_FGM','PCT_UAST_FGM'} and m['status'] == 'ok']
        if len(valid_pair) == 2 and abs(sum(m['value'] for m in valid_pair) - 1) > .015:
            for m in valid_pair:
                m.update(value=None, display='N/A', status='missing', reason='Assisted plus unassisted made-shot shares fail sum-to-one check.')
            warnings.append('Assisted shot shares excluded: inconsistent complement.')
    tracking_metrics(selected, add, warnings)
    if bundle.get('sumitro_import'):
        from import_sumitro import register_pbp
        register_pbp(bundle, add)
    official_ts = selected.get("player_advanced", {}).get("TS_PCT")
    if official_ts is not None and ts is not None:
        try:
            if abs(number(official_ts, "official TS_PCT") - ts) > 0.002:
                warnings.append("Computed TS% differs from provider TS_PCT by >0.2 percentage points. Investigate scope/rounding; do not hide the discrepancy.")
        except DataError as exc:
            warnings.append(str(exc))

    target_id = int(request.get("target_team_id") or 0)
    default_team = integer(base.get("TEAM_ID", 0), "TEAM_ID")
    # Some endpoints label a traded player's aggregate with the most recent team.
    # Team context must never be asserted as the only team without a filtered sample.
    target_id = target_id or team_id or default_team
    target_base: dict = {}
    target_adv: dict = {}
    if target_id:
        for table in ("team_base", "team_advanced"):
            matches = [r for r in tables.get(table, []) if integer(r.get("TEAM_ID"), "TEAM_ID") == target_id]
            if len(matches) == 1:
                if table == "team_base":
                    target_base = matches[0]
                else:
                    target_adv = matches[0]
            elif len(matches) > 1:
                warnings.append(f"Duplicate target team in {table}; excluded.")
    if target_base and target_adv and target_base.get("GP") is not None and target_adv.get("GP") is not None:
        if number(target_base["GP"], "team_base.GP") != number(target_adv["GP"], "team_advanced.GP"):
            warnings.append("Target team advanced GP differs from team base; advanced context excluded.")
            target_adv = {}
    if not target_base and not target_adv:
        warnings.append("Target team context unavailable. Tactical fit must be conditional; no unverified roster/coach claims.")
    if not team_id:
        warnings.append("Player sample is full-season, not a team stint. TEAM_ID may label a latest team; do not assume all minutes were played for that team or that team context is a causal effect.")
    for field, unit in (("OFF_RATING", "per100_team"), ("DEF_RATING", "per100_team"), ("NET_RATING", "per100_team"), ("PACE", "possessions_per48"), ("AST_PCT", "fraction")):
        try:
            value = number(target_adv.get(field), f"team_advanced.{field}", optional=True)
            if value is not None and unit == "fraction" and not 0 <= value <= 1:
                raise DataError("Expected team fraction 0..1.")
            reason = "Target team advanced data missing."
        except DataError as exc:
            value, reason = None, str(exc)
        add(f"TEAM_{field}", value, unit, ["T_ADV"], f"team {target_id}: {field}", reason)
    try:
        target_counts = counts(target_base, "target_team_base") if target_base else {}
        team_3par = safe_ratio(target_counts.get("FG3A"), target_counts.get("FGA"))
        reason = "Team counts missing or zero FGA."
    except DataError as exc:
        team_3par, reason = None, str(exc)
        warnings.append("Target team counts rejected: " + str(exc))
    add("TEAM_FG3A_RATE", team_3par, "fraction", ["T_BASE"], f"team {target_id}: FG3A/FGA", reason)

    context = None
    if tables.get('player_onoff'):
        try:
            context = onoff_context(bundle, base, player_id, team_id)
        except DataError as exc:
            warnings.append('On/off excluded: ' + str(exc))
    if context:
        for state in ('ON', 'OFF'):
            for field in ('OFF_RATING', 'DEF_RATING', 'NET_RATING'):
                add(f'ONOFF_{state}_{field}', context[f'{state}_{field}'], 'per100_team', ['P_ONOFF'], f'team {context["team_id"]} / {state}: {field}')
        add('ON_OFF_DIFFERENTIAL', context['ON_NET_RATING'] - context['OFF_NET_RATING'], 'per100_team', ['P_ONOFF'], 'On NET_RATING - Off NET_RATING; descriptive, not causal player impact')
        metrics[-1]['label'] = '在场减不在场：净效率差（描述性）'
        add('ON_OFF_OFF_DIFFERENTIAL', context['ON_OFF_RATING'] - context['OFF_OFF_RATING'], 'per100_team', ['P_ONOFF'], 'On OFF_RATING - Off OFF_RATING; descriptive')
        metrics[-1]['label'] = '在场减不在场：进攻效率差'
        add('ON_OFF_DEF_DIFFERENTIAL', context['ON_DEF_RATING'] - context['OFF_DEF_RATING'], 'per100_team', ['P_ONOFF'], 'On DEF_RATING - Off DEF_RATING; positive means more points conceded')
        metrics[-1]['label'] = '在场减不在场：防守失分差（正值失分更多）'
    for mid, reason in (("ON_OFF_DIFFERENTIAL", "Matching reliable On and Off rows are unavailable or rejected. On-court or overall team ratings cannot substitute for Off."),
                        ("DEFENSIVE_ABILITY_SCORE", "No validated individual defensive model; never derive this from steals, blocks, or on-court defensive rating.")):
        if mid == 'ON_OFF_DIFFERENTIAL' and context:
            continue
        add(mid, None, "not_scored", [], "Not implemented", reason)
        if mid == 'ON_OFF_DIFFERENTIAL':
            metrics[-1].update(label='在场减不在场：净效率差（描述性）', formula='Requires validated On and Off rows')
    shots, shot_reason = None, 'Matching shot events are unavailable.'
    if tables.get('player_shots'):
        try:
            shots = shot_context(bundle, base, player_id, team_id,allow_partial=request.get('partial_shot_locations',False))
            if shots['anomalies']:
                warnings.append(f"P_SHOT: {len(shots['anomalies'])} provider zone/type conflicts retained in a separate unresolved bucket; raw events unchanged.")
            if shots.get('missing_location_count') or shots.get('missing_zone_count'):
                warnings.append(f"P_SHOT: missing coordinates {shots['missing_location_count']}; missing zone labels {shots['missing_zone_count']}. Location charts use known-coordinate events; all events remain in season and zone totals.")
        except (DataError, ValueError) as exc:
            shot_reason = str(exc)
            warnings.append('Shot locations excluded: ' + shot_reason)
    if 'player_shots' in tables:
        register_shot_metrics(shots, add, shot_reason)
    comparisons = None
    if request.get('comparisons'):
        from player_comparisons import comparison_context, register_comparisons
        try:
            comparisons = comparison_context(bundle, player_id, team_id)
            register_comparisons(comparisons, add, metrics)
        except DataError as exc:
            comparisons = dict(status='missing', reason=str(exc))
            warnings.append('Comparison excluded: '+str(exc))
    from impact_metrics import impact_context, register_impact
    impact = impact_context(bundle, player_id, player_name, totals, team_id)
    register_impact(impact, add, metrics)
    percentiles = None
    if request.get('advanced_percentiles'):
        from advanced_percentiles import context, register
        percentiles = context(bundle, player_id, team_id, metrics)
        register(percentiles, add, metrics)
    leaders = None
    if request.get('stat_leaders'):
        from stat_leaders import context as leader_context, register as register_leaders
        leaders = leader_context(bundle,player_id,team_id,metrics)
        register_leaders(leaders,add,metrics)
    ok = {m["metric_id"] for m in metrics if m["status"] == "ok"}
    evidence_map = {
        "scoring": {"metric_ids": sorted(ok & {"PTS_PER_GAME", "PTS_PER75", "TS_PCT", "RTS_PP", "USG_PCT", "FG3A_RATE", "FT_RATE"}),
                    "boundary": "Volume and efficiency describe performance, not isolation, difficult-shot making, or transferable talent by themselves."},
        "creation": {"metric_ids": sorted(ok & {"AST_PER75", "AST_PCT", "AST_TOV", "TOV_PER75", "USG_PCT"}),
                     "boundary": "Assist output does not establish advantage creation, decision speed, or passing reads; use tracking/actual observations when available."},
        "off_ball": {"metric_ids": sorted(ok & {"FG3_PCT", "FG3A_RATE", "PCT_AST_FGM", "PCT_AST_3PM"}),
                     "boundary": "Assisted made-shot share is NOT the share of all attempts, gravity, cutting quality, or catch-and-shoot efficiency."},
        "defense": {"metric_ids": sorted(ok & {"STL_PER_GAME", "BLK_PER_GAME", "PF_PER_GAME", "ONCOURT_DEF_RATING"}),
                    "boundary": "Only event/context description. Individual screen navigation, positioning, effort and matchup ability require observation or stronger data."},
        "tactical_fit": {"metric_ids": sorted(ok & {"TEAM_PACE", "TEAM_AST_PCT", "TEAM_FG3A_RATE", "USG_PCT", "FG3A_RATE", "AST_PCT"}),
                        "boundary": "State enabling conditions and conflicts. Pace/assist rate do not prove a named offensive system or causal fit."},
    }
    limited = league_ts is None or "USG_PCT" not in ok or not target_adv
    result = {"version": VERSION, "generated_at": now_iso(), "data_kind": bundle["data_kind"],
            "request": request, "player": {"id": player_id, "name": player_name, "reported_team_id": default_team},
            "sample": {"season": season, "season_type": season_type, "GP": totals["GP"], "MIN": totals["MIN"], "player_team_id": team_id},
            "target_team": {"id": target_id or None, "name": target_base.get("TEAM_NAME", target_adv.get("TEAM_NAME")),
                            "hypothetical": bool(request.get("target_team_id") and int(request["target_team_id"]) != default_team)},
            "quality": {"mode": "limited" if limited else "core", "metrics_available": len(ok),
                        "metrics_missing": len(metrics) - len(ok), "warnings": warnings},
            "metrics": metrics, "evidence_map": evidence_map, "selected_rows": selected, "shot_context": shots,
            "sources": sources}
    if comparisons is not None:
        result['comparison_context'] = comparisons
    if bundle.get('impact_collection'):
        result['impact_collection']=bundle['impact_collection']
    if impact is not None:
        result['impact_context'] = impact
    if percentiles is not None:
        result['percentile_context'] = percentiles
    if leaders is not None:
        result['stat_leader_context'] = leaders
    return result
