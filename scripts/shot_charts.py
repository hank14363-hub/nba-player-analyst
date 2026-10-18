"""Validate complete event coverage before deriving location visuals. No synthetic heatmap."""
from collections import defaultdict
from datetime import datetime
from html import escape
from common import DataError, integer, number

ZONES = {
    'Restricted Area': ('RA', '合理冲撞区'),
    'In The Paint (Non-RA)': ('PAINT', '油漆区（非合理冲撞区）'),
    'Mid-Range': ('MID', '中距离'),
    'Left Corner 3': ('LC3', '左底角三分'),
    'Right Corner 3': ('RC3', '右底角三分'),
    'Above the Break 3': ('ATB3', '弧顶及两翼三分'),
    'Backcourt': ('BACK', '后场'),
}


def shot_context(bundle, base, player_id, team_id, allow_partial=False):
    rows = bundle['tables'].get('player_shots', [])
    source = bundle['sources'].get('P_SHOT', {})
    if not rows:
        raise DataError('Matching shot events are unavailable.')
    if integer(source.get('player_id'), 'shot source player_id') != player_id:
        raise DataError('Shot source belongs to a different player.')
    if integer(source.get('player_team_id', -1), 'shot source team filter') != team_id:
        raise DataError('Shot source team filter differs from the base sample.')
    if source.get('context_measure') != 'FGA' or source.get('coordinate_units') != 'tenths_of_foot':
        raise DataError('Need all FGA events and documented tenths-of-foot coordinates.')
    params = source.get('parameters', {})
    if source.get('endpoint') == 'shotchartdetail':
        expected = dict(PlayerID=player_id, TeamID=team_id, Season=bundle['season'],
                        SeasonType=bundle['season_type'], ContextMeasure='FGA')
        if any(str(params.get(k)) != str(v) for k, v in expected.items()):
            raise DataError('Actual shot request parameters disagree with source scope.')
        for field in ('DateFrom', 'DateTo', 'GameID', 'SeasonSegment', 'GameSegment', 'ClutchTime',
                      'AheadBehind', 'Outcome', 'Location', 'VsConference', 'VsDivision', 'PlayerPosition',
                      'Position', 'PointDiff', 'ContextFilter'):
            if params.get(field) not in ('', None):
                raise DataError('Shot request contains a restricted sample filter: ' + field)
        for field in ('LastNGames', 'Month', 'OpponentTeamID', 'Period'):
            if params.get(field) not in ('', None, 0, '0'):
                raise DataError('Shot request contains a restricted sample filter: ' + field)
    seen, games, points, zones, anomalies = set(), set(), [], defaultdict(lambda: {'fga': 0, 'fgm': 0}), []
    event_totals=dict(FGA=0,FGM=0,FG3A=0,FG3M=0)
    missing_locations=[];missing_zones=[]
    start_year = int(bundle['season'][:4])
    required_prefix = '002' if bundle['season_type'] == 'Regular Season' else '004'
    for r in rows:
        if integer(r.get('PLAYER_ID'), 'shot PLAYER_ID') != player_id:
            raise DataError('Mixed player shot events.')
        tid = integer(r.get('TEAM_ID'), 'shot TEAM_ID')
        if tid <= 0 or (team_id and tid != team_id):
            raise DataError('Shot event team disagrees with requested stint.')
        game = str(r.get('GAME_ID', '')).zfill(10)
        if len(game) != 10 or not game.isdigit() or not game.startswith(required_prefix + f'{start_year % 100:02d}'):
            raise DataError('Shot game ID season/type differs from the base sample.')
        date = datetime.strptime(str(r.get('GAME_DATE')), '%Y%m%d')
        if date.year not in {start_year, start_year + 1}:
            raise DataError('Shot game date outside season years.')
        event = integer(r.get('GAME_EVENT_ID'), 'shot event ID')
        key = (game, event)
        if event <= 0 or key in seen:
            raise DataError('Duplicate or invalid shot event ID.')
        seen.add(key); games.add(game)
        attempted = integer(r.get('SHOT_ATTEMPTED_FLAG'), 'attempted flag')
        made = integer(r.get('SHOT_MADE_FLAG'), 'made flag')
        if attempted != 1 or made not in (0, 1):
            raise DataError('Expected FGA events with binary made flags.')
        kind = r.get('SHOT_TYPE')
        zone = r.get('SHOT_ZONE_BASIC')
        if kind not in {'2PT Field Goal', '3PT Field Goal'}:
            raise DataError('Unknown shot type or zone; review provider schema.')
        if zone not in ZONES:
            if allow_partial and zone in (None,''):
                missing_zones.append(dict(game_id=game,event_id=event,original_zone=zone))
                zone='Missing Zone'
            else:raise DataError('Unknown shot type or zone; review provider schema.')
        conflict = (zone in {'Restricted Area', 'In The Paint (Non-RA)', 'Mid-Range'} and kind != '2PT Field Goal') or (zone in {'Left Corner 3', 'Right Corner 3', 'Above the Break 3'} and kind != '3PT Field Goal')
        if conflict:
            anomalies.append(dict(game_id=game, event_id=event, original_zone=zone, original_type=kind,
                                  handling='Preserve raw values; count in explicit unresolved zone bucket.'))
            zone = 'Provider Label Conflict'
        x, y = number(r.get('LOC_X'), 'LOC_X',optional=allow_partial), number(r.get('LOC_Y'), 'LOC_Y',optional=allow_partial)
        missing_xy=x is None or y is None
        if (x is not None and not -250 <= x <= 250) or (y is not None and not -52.5 <= y <= 887.5):
            raise DataError('Coordinates outside full-court bounds; do not clip them silently.')
        period = integer(r.get('PERIOD'), 'PERIOD')
        minute, second = integer(r.get('MINUTES_REMAINING'), 'MINUTES_REMAINING'), integer(r.get('SECONDS_REMAINING'), 'SECONDS_REMAINING')
        if period <= 0 or not 0 <= second < 60 or not 0 <= minute <= (12 if period <= 4 else 5):
            raise DataError('Invalid event period/clock.')
        if missing_xy:
            missing_locations.append(dict(game_id=game,event_id=event,game_date=r['GAME_DATE'],
                period=period,clock=f'{minute:02d}:{second:02d}',made=made,three=kind.startswith('3PT'),
                original_x=r.get('LOC_X'),original_y=r.get('LOC_Y'),original_zone=r.get('SHOT_ZONE_BASIC')))
        else:points.append(dict(x=x, y=y, made=made, three=kind.startswith('3PT'), game_id=game, event_id=event))
        event_totals['FGA']+=1;event_totals['FGM']+=made
        event_totals['FG3A']+=int(kind.startswith('3PT'));event_totals['FG3M']+=made*int(kind.startswith('3PT'))
        zones[zone]['fga'] += 1; zones[zone]['fgm'] += made
    observed = event_totals
    for field, value in observed.items():
        if value != integer(base.get(field), 'base.' + field):
            raise DataError(f'Shot coverage differs from base {field}: {value} versus {base.get(field)}.')
    # GP can include games without any FGA. Do not demand one shot in every appearance.
    if len(games) > integer(base.get('GP'), 'base.GP'):
        raise DataError('Shot games exceed base appearances.')
    output = []
    groups = dict(ZONES)
    if anomalies:
        groups['Provider Label Conflict'] = ('UNRESOLVED', '区域/类型标签冲突')
    if missing_zones:groups['Missing Zone']=('MISSING','区域标签缺失')
    for zone, (code, label) in groups.items():
        n, k = zones[zone]['fga'], zones[zone]['fgm']
        output.append(dict(code=code, label=label, fga=n, fgm=k, fg_pct=k/n if n else None,
                           share=n/len(rows), small_sample=n < 30))
    result=dict(status='ok', counts=observed, shot_games=len(games), appearance_games=integer(base['GP'], 'GP'),
                zones=output, points=points, anomalies=anomalies,
                coverage='FGA/FGM/3PA/3PM exactly match base; appearance GP may include zero-FGA games.')
    if allow_partial:
        result.update(location_count=len(points),missing_location_count=len(missing_locations),
            missing_locations=missing_locations,missing_zone_count=len(missing_zones),missing_zones=missing_zones,
            location_coverage=len(points)/len(rows),location_status='partial' if missing_locations else 'complete')
    return result


def register_shot_metrics(context, add, reason):
    add('SHOT_EVENT_FGA', context['counts']['FGA'] if context else None, 'count', ['P_SHOT', 'P_BASE'],
        'Count validated unique FGA events; exact base coverage', reason)
    if not context:
        return
    if 'location_count' in context:
        for mid,value,unit in [('SHOT_LOCATION_FGA',context['location_count'],'count'),
                              ('SHOT_LOCATION_MISSING',context['missing_location_count'],'count'),
                              ('SHOT_LOCATION_COVERAGE',context['location_coverage'],'fraction'),
                              ('SHOT_ZONE_MISSING',context['missing_zone_count'],'count')]:
            add(mid,value,unit,['P_SHOT','P_BASE'],'Retained complete events; valid coordinates and missing fields counted separately','')
    for mid, value in [('SHOT_EVENT_FGM', context['counts']['FGM']), ('SHOT_EVENT_GAMES', context['shot_games']),
                       ('SHOT_ZONE_CONFLICTS', len(context['anomalies']))]:
        add(mid, value, 'count', ['P_SHOT', 'P_BASE'], 'Count from coverage-validated shot events', '')
    for z in context['zones']:
        for suffix, value, unit in [('FGA', z['fga'], 'count'), ('FGM', z['fgm'], 'count'),
                                    ('FG_PCT', z['fg_pct'], 'fraction'), ('SHARE', z['share'], 'fraction')]:
            add('SHOT_' + z['code'] + '_' + suffix, value, unit, ['P_SHOT', 'P_BASE'],
                'Validated NBA SHOT_ZONE_BASIC: ' + z['label'] + '; ' + suffix, 'No attempts in this zone.')


def shot_visuals(analysis, theme):
    ctx = analysis.get('shot_context')
    entries = {}
    note = '真实逐次出手；绿色圆点为命中，红色叉为未中。坐标单位为 0.1 英尺，篮筐为原点；不插值、不按颜色推断能力，远距出手全部保留。'
    for key, title in [('shot_locations', '真实投篮位置：全场出手'), ('shot_zones', '官方区域：命中数 / 出手数')]:
        entries[key] = dict(title=title, status='ok' if ctx else 'missing',
                            metric_ids=['SHOT_EVENT_FGA'], source_ids=['P_SHOT', 'P_BASE'], note=note, svg=None)
    if not ctx:
        return entries
    missing=ctx.get('missing_location_count',0)
    if missing:
        entries['shot_locations']['title']='真实投篮位置：有坐标出手（部分覆盖）'
        entries['shot_locations']['note']=f'赛季事件{ctx["counts"]["FGA"]}次齐全；图上{len(ctx["points"])}次，缺坐标{missing}次不落点。位置筛选分母仅含有坐标事件；区域表仍以赛季全部事件为分母。'
        entries['shot_locations']['metric_ids']+=['SHOT_LOCATION_FGA','SHOT_LOCATION_MISSING','SHOT_LOCATION_COVERAGE']
    prefix = 'SYNTHETIC TEST DATA · ' if analysis['data_kind'] == 'synthetic' else ''
    title = prefix + analysis['sample']['season'] + ' / P_SHOT + P_BASE'
    # Equal scale for both axes. Full court (50 x 94 ft); basket at (0,0), baseline -5.25 ft.
    p = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 650" role="img" aria-label="真实投篮散点图">',
         '<rect width="480" height="650" fill="' + '#F7F9FC' + '"/>',
         '<rect x="105" y="40" width="270" height="507.6" fill="none" stroke="#8793a2"/>',
         '<path d="M105 293.8H375 M196.8 40V142.6H283.2V40 M196.8 547.6V445H283.2V547.6" fill="none" stroke="#8793a2"/>',
         '<circle cx="240" cy="68.35" r="3.24" fill="none" stroke="#8793a2"/>',
         '<circle cx="240" cy="519.25" r="3.24" fill="none" stroke="#8793a2"/>',
         '<circle cx="240" cy="293.8" r="32.4" fill="none" stroke="#8793a2"/>',
         '<path d="M121.2 40V116.95 M358.8 40V116.95 M121.2 116.95A128.25 128.25 0 0 0 358.8 116.95" fill="none" stroke="#8793a2"/>']
    for r in ctx['points']:
        x, y = 240 + r['x'] * .54, 68.35 + r['y'] * .54
        if r['made']:
            p.append(f'<circle cx="{x:.3f}" cy="{y:.3f}" r="1.9" fill="#157d55" opacity=".58"/>')
        else:
            p.append(f'<path d="M{x-1.8:.3f} {y-1.8:.3f}l3.6 3.6m0 -3.6l-3.6 3.6" stroke="#ce3d43" stroke-width=".7" opacity=".5"/>')
    p += [f'<text x="24" y="585" font-size="14" fill="#182334">命中 {sum(p["made"] for p in ctx["points"])} / 出手 {len(ctx["points"])} · 圆点命中 / 叉未中</text>',
          '<text x="24" y="608" font-size="12">'+(f'缺坐标 {missing} 次；赛季全部出手 {ctx["counts"]["FGA"]} 次' if missing else '全场等比例；图上远距出手未被裁切')+'</text>',
          '<text x="24" y="632" font-size="10">' + escape(title) + '</text></svg>']
    entries['shot_locations']['svg'] = ''.join(p)
    if not ctx['points']:entries['shot_locations'].update(status='missing',svg=None,note='全部事件缺坐标；仍保留区域统计，不绘制位置。')
    height = 84 + len(ctx['zones']) * 53
    p = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 {height}" role="img" aria-label="真实投篮区域统计">',
         f'<rect width="480" height="{height}" fill="#F7F9FC"/>']
    ids = []
    for i, z in enumerate(ctx['zones']):
        y = 30 + i * 53
        small = ' · 少样本' if z['small_sample'] else ''
        pct = f'{z["fg_pct"]*100:.1f}%' if z['fg_pct'] is not None else 'N/A'
        p += [f'<text x="20" y="{y}" font-size="12">{z["label"]}</text>',
              f'<text x="460" y="{y}" text-anchor="end" font-size="12">{z["fgm"]}/{z["fga"]} · {pct}{small}</text>',
              f'<rect x="20" y="{y+9}" width="440" height="10" fill="#dce1e8"/>',
              f'<rect x="20" y="{y+9}" width="{440*z["share"]:.4f}" height="10" fill="{theme["primary"]}"/>']
        ids += ['SHOT_' + z['code'] + '_' + s for s in ('FGA', 'FGM', 'SHARE')]
        if z['fg_pct'] is not None:
            ids.append('SHOT_' + z['code'] + '_FG_PCT')
    p += [f'<text x="20" y="{height-45}" font-size="12">条长 = 该区域出手 / 全部出手；不是命中率</text>',
          f'<text x="20" y="{height-24}" font-size="11">少样本：出手少于 30 次（提示阈值，非显著性检验）</text>',
          f'<text x="20" y="{height-6}" font-size="10">' + escape(title) + '</text></svg>']
    entries['shot_zones'].update(svg=''.join(p), metric_ids=ids,
        note='按官方 SHOT_ZONE_BASIC 分组；区域标签缺失与区域/类型冲突各自单列，不修正原值。分母为完整赛季全部事件，数字为命中数/出手数与命中率，条长是出手份额。没有相同口径联盟区域基准，不计算相对联盟热区；少样本提示不代表统计显著性。')
    return entries

