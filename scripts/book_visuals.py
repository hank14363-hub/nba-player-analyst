"""Reuse audited poster charts in the book, plus genuine On/Off and tracking comparisons."""
from poster_charts import Charts, start, text, point_bar, T
from shot_charts import shot_visuals
from poster_charts import soft
from comparison_visuals import comparison_visuals
import re


def visuals(analysis, theme):
    # The research book has a paper background. Poster palettes remain independent.
    theme = dict(theme, panel='#F6F4EF', background='#FBFAF7', text='#263444',
                 muted='#5A6573', accent=theme['primary'], grid='#DDD9D2')
    entries = Charts(analysis, theme).build()
    m = {r['metric_id']: r for r in analysis['metrics']}
    def add(key, title, ids, note, rows, maximum):
        values = [m.get(k, {}) for k in ids]
        ok = all(r.get('status') == 'ok' for r in values)
        p = None
        if ok:
            p = start(title, theme)
            for i, (label, mid) in enumerate(rows):
                v = m[mid]['value']; y = 38 + i * 51
                display = m[mid]['display']
                p += [text(22, y, label, 14, theme['muted']), text(458, y, display, 22, theme['accent'], 'end', 700)]
                point_bar(p, 22, y + 10, 436, v, maximum, theme['accent'])
            p += [text(22, 249, '0 至 ' + str(maximum) + ('%' if key == 'tracking' else ' / 每百回合'), 11, theme['muted'])]
            p += [text(22, 268, analysis['sample']['season'] + ' / ' + analysis['sample']['season_type'], 10, theme['muted'])]
            sources = ' / '.join(sorted({sid for row in values for sid in row.get('source_ids', [])}))
            footer = ('SYNTHETIC TEST DATA / ' if analysis['data_kind'] == 'synthetic' else 'DESCRIPTIVE STATISTICS / ') + sources
            p += [text(22, 281, footer, 9, theme['muted'])]
            p += ['</svg>']
        entries[key] = {'title': title, 'metric_ids': ids, 'source_ids': sorted({s for r in values for s in r.get('source_ids', [])}),
                        'status': 'ok' if ok else 'missing', 'note': note, 'svg': ''.join(p) if p else None}
    ids = ['ONOFF_ON_OFF_RATING', 'ONOFF_OFF_OFF_RATING', 'ONOFF_ON_DEF_RATING', 'ONOFF_OFF_DEF_RATING']
    maximum = max([140] + [m[k]['value'] for k in ids if m.get(k, {}).get('status') == 'ok'])
    add('onoff', '同一球队：在场与不在场', ids,
        '在场与不在场均覆盖同赛季球队样本；进攻值高更好，防守失分值低更好。未调整队友、对手和替补配置，不是个人因果贡献或防守评分。',
        [('在场 · 每百回合得分', ids[0]), ('不在场 · 每百回合得分', ids[1]), ('在场 · 每百回合失分', ids[2]), ('不在场 · 每百回合失分', ids[3])], maximum)
    # The eFG fractions remain raw metric values; scale is 0..1 and caption says 0..100%.
    ids = ['CATCH_SHOOT_EFG_PCT', 'PULL_UP_EFG_PCT']
    maximum = max([1] + [m[k]['value'] for k in ids if m.get(k, {}).get('status') == 'ok'])
    add('tracking', '接球投篮与持球急停：有效命中率', ids,
        '有效命中率给三分命中增加权重。使用官方追踪百分比，不用四舍五入的场均命中数反推；两类出手位置、难度和样本不同，不据此判定哪类能力更强。覆盖场次见指标表。',
        [('接球投篮 eFG', ids[0]), ('持球急停 eFG', ids[1])], maximum)
    if entries['tracking']['svg']:
        entries['tracking']['svg'] = entries['tracking']['svg'].replace('0 至 ' + str(maximum) + '%', '0 至 ' + f'{maximum * 100:g}' + '%')
    entries.update(shot_visuals(analysis, theme))
    entries.update(comparison_visuals(analysis, theme))
    replacements = {'#F3F5F8': theme['text'], '#303846': '#E1DFD8',
                    soft(theme['primary']): '#496780', '#C2CCD7': '#596B70', '#F7F9FC': theme['panel'],
                    'DESCRIPTIVE STATISTICS / NOT A PLAYER RANK': '描述性统计 · 并非球员排名',
                    'DESCRIPTIVE STATISTICS / ': '描述性统计 / '}
    for entry in entries.values():
        if entry['svg']:
            for old, new in replacements.items():
                entry['svg'] = entry['svg'].replace(old, new)
            entry['svg'] = re.sub(r'(<rect\b[^>]*\bheight="14"[^>]*)(/>)', r'\1 class="chart-bar"\2', entry['svg'])
    from impact_visuals import impact_visuals
    entries.update(impact_visuals(analysis))
    return entries
