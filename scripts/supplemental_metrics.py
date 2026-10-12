"""Strict descriptive On/Off and tracking metrics; no player ability scores."""
from common import DataError, number, integer


def onoff_context(bundle, base, player_id, team_id):
    rows = bundle['tables'].get('player_onoff', [])
    source = bundle['sources'].get('P_ONOFF', {})
    if not rows:
        return None
    context_team = integer(source.get('team_id'), 'P_ONOFF.team_id')
    if source.get('sample_scope') != 'full_team_season' or source.get('metric_definition') != 'team_oncourt':
        raise DataError('On/off requires verified full-team-season team_oncourt semantics.')
    if (team_id and context_team != team_id) or context_team != integer(base.get('TEAM_ID'), 'base.TEAM_ID'):
        raise DataError('On/off team differs from the player sample; do not combine teams.')
    selected = [r for r in rows if integer(r.get('PLAYER_ID'), 'onoff.PLAYER_ID') == player_id
                and integer(r.get('TEAM_ID'), 'onoff.TEAM_ID') == context_team]
    on = [r for r in selected if r.get('COURT_STATUS') == 'On']
    off = [r for r in selected if r.get('COURT_STATUS') == 'Off']
    if len(on) != 1 or len(off) != 1 or len(selected) != 2:
        raise DataError('On/off needs exactly one On and one Off row for the player/team.')
    on, off = on[0], off[0]
    on_min, off_min = number(on.get('MIN'), 'On.MIN'), number(off.get('MIN'), 'Off.MIN')
    if on_min <= 0 or off_min <= 0 or abs(on_min - number(base.get('MIN'), 'base.MIN')) > 2:
        raise DataError('On minutes differ from player sample or one state has no minutes.')
    teams = [r for r in bundle['tables'].get('team_base', []) if integer(r.get('TEAM_ID'), 'team.TEAM_ID') == context_team]
    if len(teams) != 1 or abs(on_min + off_min - number(teams[0].get('MIN'), 'team.MIN')) > 2:
        raise DataError('On plus Off minutes do not cover matching team floor minutes. Five-player minute totals are incompatible.')
    result = {'team_id': context_team, 'on_minutes': on_min, 'off_minutes': off_min}
    for state, row in (('ON', on), ('OFF', off)):
        for field in ('OFF_RATING', 'DEF_RATING', 'NET_RATING'):
            val = number(row.get(field), f'{state}.{field}')
            if field != 'NET_RATING' and val < 0:
                raise DataError('Negative offensive/defensive rating.')
            result[f'{state}_{field}'] = val
        if abs(result[f'{state}_OFF_RATING'] - result[f'{state}_DEF_RATING'] - result[f'{state}_NET_RATING']) > .3:
            raise DataError('On/off net rating fails rounded OFF minus DEF identity.')
    return result


def tracking_metrics(selected, add, warnings):
    specs = (
        ('tracking_catchshoot', 'TR_CATCH', 'CATCH_SHOOT_FG_PCT', 'CATCH_SHOOT_FG_PCT', 'fraction'),
        ('tracking_catchshoot', 'TR_CATCH', 'CATCH_SHOOT_FGA', 'CATCH_SHOOT_FGA_PER_GAME', 'per_game'),
        ('tracking_catchshoot', 'TR_CATCH', 'CATCH_SHOOT_EFG_PCT', 'CATCH_SHOOT_EFG_PCT', 'fraction'),
        ('tracking_pullup', 'TR_PULL', 'PULL_UP_FG_PCT', 'PULL_UP_FG_PCT', 'fraction'),
        ('tracking_pullup', 'TR_PULL', 'PULL_UP_FGA', 'PULL_UP_FGA_PER_GAME', 'per_game'),
        ('tracking_pullup', 'TR_PULL', 'PULL_UP_EFG_PCT', 'PULL_UP_EFG_PCT', 'fraction'),
        ('tracking_drives', 'TR_DRIVE', 'DRIVES', 'DRIVES_PER_GAME', 'per_game'),
        ('tracking_passing', 'TR_PASS', 'POTENTIAL_AST', 'POTENTIAL_AST_PER_GAME', 'per_game'),
    )
    for table, sid, field, mid, unit in specs:
        if table not in selected:
            continue
        row = selected[table]
        try:
            gp = number(row.get('GP'), table + '.GP')
            if gp <= 0:
                raise DataError('Tracking needs positive sample GP.')
            value = number(row.get(field), table + '.' + field, optional=True)
            if value is not None and (value < 0 or (unit == 'fraction' and value > 1)):
                raise DataError('Tracking percentage/count out of range.')
            reason = 'Tracking field unavailable; do not impute.'
            if unit == 'fraction':
                attempt_field = 'CATCH_SHOOT_FGA' if table == 'tracking_catchshoot' else 'PULL_UP_FGA'
                attempts = number(row.get(attempt_field), table + '.' + attempt_field, optional=True)
                if attempts is None or attempts <= 0:
                    value, reason = None, 'No positive tracking attempts; zero FG% is not evidence of poor shooting.'
            add(mid, value, unit, [sid], f'{table}.{field}; tracking GP={gp:g}; independent coverage', reason)
        except DataError as exc:
            warnings.append(mid + ' excluded: ' + str(exc))
            add(mid, None, unit, [sid], table + '.' + field, str(exc))
