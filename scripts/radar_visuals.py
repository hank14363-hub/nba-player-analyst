"""Source-specific percentile radars with polygon-clipped concentric quantile bands and tangential bezel labels."""
from html import escape
from math import isfinite

AXIS_CODES = {
    'USG_PCT': 'USG%',
    'AST_PCT': 'AST%',
    'TS_PCT': 'TS%',
    'EFG_PCT': 'eFG%',
    'AST_TOV': 'AST/TOV',
    'FT_RATE': 'FTr',
    'FG3A_RATE': '3PAr',
    'NBA_PIE': 'PIE',
    'ADV_NBA_OREB_PCT': 'OREB%',
    'ADV_NBA_DREB_PCT': 'DREB%',
    'ADV_NBA_REB_PCT': 'REB%',
    'ADV_NBA_AST_RATIO': 'AST-R',
    'ADV_NBA_TOV_PCT': 'TOV%',
    'ADV_NBA_BALL_SECURITY': '1-TOV%',
    'ONCOURT_OFF_RATING': 'ORTG',
    'ONCOURT_DEF_RATING': 'DRTG',
    'ONCOURT_NET_RATING': 'NET-RTG',
    'IMPACT_BPM': 'BPM',
    'IMPACT_OBPM': 'O-BPM',
    'IMPACT_DBPM': 'D-BPM',
    'IMPACT_VORP': 'VORP',
    'IMPACT_WS': 'WS',
    'IMPACT_WS48': 'WS/48',
    'ADV_BREF_PER': 'PER',
    'ADV_BREF_TS': 'TS%',
    'ADV_BREF_3PAR': '3PAr',
    'ADV_BREF_FTR': 'FTr',
    'ADV_BREF_USG_PCT': 'USG%',
    'ADV_BREF_AST_PCT': 'AST%',
    'ADV_BREF_TRB_PCT': 'TRB%',
    'ADV_BREF_ORB_PCT': 'ORB%',
    'ADV_BREF_DRB_PCT': 'DRB%',
    'ADV_BREF_STL_PCT': 'STL%',
    'ADV_BREF_BLK_PCT': 'BLK%',
    'ADV_BREF_STOCK_PCT': 'STOCK%',
    'ADV_BREF_BALL_SECURITY': '1-TOV%',
    'IMPACT_EPM': 'EPM',
    'IMPACT_O_EPM': 'O-EPM',
    'IMPACT_D_EPM': 'D-EPM',
    'IMPACT_LEBRON': 'LEBRON',
    'IMPACT_O_LEBRON': 'O-LEBRON',
    'IMPACT_D_LEBRON': 'D-LEBRON',
}

PROFILES = [
    dict(key='nba',family='NBA',title='职责与效率',subtitle='NBA · 全位置合格样本',
         axes=[('USG_PCT','终结负荷'),('AST_PCT','助攻率'),('TS_PCT','真实命中率'),
               ('AST_TOV','助攻失误比'),('ADV_NBA_OREB_PCT','进攻篮板率'),('ADV_NBA_DREB_PCT','防守篮板率')],
         notes=['使用率描述终结进攻的负荷，高值不自动代表更强。',
                '助攻率描述已实现助攻参与，不等于创造空位的能力。',
                '真实命中率纳入投篮与罚球结果，未调整机会难度。',
                '助攻与失误的总量比值，不能单独衡量传球决策质量。',
                '进攻篮板率受场上分工与位置影响，不是全面能力。',
                '防守篮板率描述篮板结果，不能代表全部防守表现。'],
         boundary='六轴分别描述职责、结果与效率；外圈是较高数值，不合成能力分。'),
    dict(key='bref',family='BREF',title='模型与出勤',subtitle='Basketball-Reference · 全位置合格样本',
         axes=[('IMPACT_BPM','BPM 总值'),('IMPACT_OBPM','OBPM 进攻'),('IMPACT_DBPM','DBPM 防守'),
               ('IMPACT_VORP','VORP'),('IMPACT_WS','Win Shares'),('IMPACT_WS48','WS / 48')],
         notes=['技术统计与球队背景模型的总读数，不是直接测量的因果影响。',
                'BPM 的进攻分量；与总值共享输入，不算独立验证。',
                'BPM 的防守分量，不等同于个人防守能力或对位评分。',
                '替补水平基准的累计读数，受到出勤与分钟影响。',
                '按提供者方法分配的胜利份额，不是个人实测赢球数。',
                '按时间表达的胜利份额；不能与每百回合模型值直接相加。'],
         boundary='比率与累计量各自转为样本百分位；指标共享输入，图形面积没有综合分含义。'),
    dict(key='nba_compass',family='NBA',title='职责与结果罗盘',subtitle='NBA · 10轴同心分位刻度罗盘',
         axes=[('NBA_PIE','PIE 事件份额'),('ONCOURT_OFF_RATING','在场进攻'),('FT_RATE','造罚球率'),
               ('USG_PCT','终结负荷'),('TS_PCT','真实命中率'),('AST_PCT','助攻率'),
               ('ADV_NBA_REB_PCT','总篮板率'),('AST_TOV','助失比'),('ONCOURT_NET_RATING','在场球队净效率'),
               ('ADV_NBA_BALL_SECURITY','失误率补数')],
         notes=['PIE 反映球员在场事件中的综合统计份额，非加权正负值模型。',
                '球员在场期间的球队百回合得分，受队友与轮换搭配影响。',
                '每次运动战出手对应的罚球次数，衡量造杀伤频率。',
                '在场期间由该球员终结回合的比例，体现战术负荷。',
                '综合两分、三分与罚球的真实得分效率。',
                '在场期间队友进球由该球员助攻的比例。',
                '在场期间可争抢篮板中被该球员摘下的比例。',
                '总助攻与总失误的比值，衡量传控稳健度。',
                '在场期间球队百回合净胜分，对应赛场正负走势。',
                '100% 减去失误比率 (1-TOV%)，仅是失误率的补数，不能区分失误类型，受持球与传球职责影响。'],
         boundary='十轴同源展示事件份额、职责、效率与球队环境；高值不一概有利，在场效率不是个人因果影响。'),
    dict(key='bref_compass',family='BREF',title='高阶统计罗盘',subtitle='Basketball-Reference · 11轴同心分位罗盘',
         axes=[('IMPACT_BPM','BPM 总值'),('IMPACT_OBPM','OBPM 进攻分量'),('IMPACT_DBPM','DBPM 防守分量'),
               ('ADV_BREF_FTR','罚球出手比'),('ADV_BREF_USG_PCT','终结负荷'),('ADV_BREF_PER','PER'),
               ('ADV_BREF_TS','真实命中'),('ADV_BREF_AST_PCT','助攻率'),('ADV_BREF_TRB_PCT','总篮板率'),
               ('IMPACT_VORP','VORP 累计量'),('ADV_BREF_BALL_SECURITY','失误率补数')],
         notes=['Basketball-Reference 基于技术统计与球队净胜分的百回合综合估计。',
                'BPM 进攻端分量，反映进攻输出与效率贡献。',
                'BPM 防守端分量，受篮板、抢断、封盖与球队防守背景共同影响。',
                '罚球出手与运动战出手之比，体现冲击内线与博取罚球频率。',
                '进攻回合由该球员终结（出手、罚球或失误）的百分比。',
                'John Hollinger 综合每分钟正面与负面技术统计的效率读数。',
                '纳入两分、三分与罚球后的真实得分效率。',
                '在场时队友运动战进球由其助攻的百分比。',
                '在场期间可争抢总篮板的获取百分比。',
                '相对于替补水准球员的累计不可替代价值。',
                '100% 减去 BR 失误率 (1-TOV%)，只表示该口径的失误比例较低，不表示球权成功率或独立控球能力。'],
         boundary='十一轴为同来源统计画像；模型、效率、职责及累计量分别解释，不合成战力或防守能力评分。')]


from radar_geometry import svg, format_ring_tick, RING_LEVELS


def profiles(analysis):
    """Prefer a complete rich profile per family; retain six-axis fallback."""
    metrics={m['metric_id']:m for m in analysis['metrics']}
    groups={g['family']:g for g in analysis.get('percentile_context',{}).get('groups',[])}
    candidates=[]
    for spec in PROFILES:
        group=groups.get(spec['family'],{})
        if group.get('status')!='ok':continue
        entries={e['metric_id']:e for e in group['entries']}
        keys=group.get('population_keys',[]);n=group['eligible_count']
        if n<8 or len(keys)!=n or len(set(keys))!=n:continue
        axes=[]
        for (mid,label),note in zip(spec['axes'],spec['notes']):
            e=entries.get(mid,{});p=metrics.get('PCTL_'+mid,{});raw=metrics.get(mid,{})
            if (e.get('status')!='ok' or e.get('n')!=n or e.get('missing_count')!=0
                or raw.get('status')!='ok' or p.get('status')!='ok'
                or any(not isinstance(v,(int,float)) or isinstance(v,bool) or not isfinite(v)
                       for v in (p.get('value'),raw.get('value'),e.get('percentile'),e.get('target')))
                or not 0<=p['value']<=100
                or abs(p['value']-e['percentile'])>1e-9 or abs(raw['value']-e['target'])>1e-9):
                break
            supplied=e.get('ring_quantiles',{})
            rings={}
            if supplied:
                vals=[supplied.get(str(level)) for level in RING_LEVELS]
                if (all(isinstance(v,(int,float)) and not isinstance(v,bool) and isfinite(v) for v in vals)
                    and all(a<=b for a,b in zip(vals,vals[1:]))):
                    rings={str(level):v for level,v in zip(RING_LEVELS,vals)}
            # No synthetic or real fallback: absent quantiles stay visibly absent.
            display=raw['display']+('%' if raw['unit']=='percent' and not str(raw['display']).endswith('%') else '')
            direction=e.get('polarity_note')
            if not direction:
                from metric_polarity import describe
                direction=describe(mid)['polarity_note']
            axes.append(dict(metric_id=mid,percentile_metric_id=p['metric_id'],label=label,
                code=AXIS_CODES.get(mid,mid),unit=raw.get('unit','ratio'),n=n,raw=raw['value'],
                display=display,percentile=p['value'],ring_quantiles=rings,
                polarity=e.get('polarity','role_neutral'),note=note+' '+direction,source_ids=e['source_ids'],
                leader=next((l for l in analysis.get('stat_leader_context',{}).get('leaders',[])
                             if l['metric_id']==mid),None)))
        if len(axes)==len(spec['axes']):
            candidates.append(dict(spec,n=n,axes=axes,source_ids=group['source_ids'],scope=group['scope'],population_keys=keys))
    result=[]
    for family in ('BREF','NBA'):
        options=[p for p in candidates if p['family']==family]
        if options:result.append(max(options,key=lambda p:len(p['axes'])))
    return result


def radar_entries(analysis,theme):
    result={}
    for p in profiles(analysis):
        ids=[mid for a in p['axes'] for mid in (a['metric_id'],a['percentile_metric_id'],a['percentile_metric_id']+'_N')]
        ids += ['STAT_LEADER_'+a['metric_id']+'_'+k for a in p['axes'] if a.get('leader') for k in ('RANK','TIES','N')]
        result['percentile_'+p['key']+'_radar']=dict(title=p['title']+f" · {len(p['axes'])}轴",
            status='ok',metric_ids=ids,source_ids=p['source_ids'],note=p['scope']+' '+p['boundary'],svg=svg(p,analysis,theme))
    return result


def award(profile,book):
    """Only registered full-league maxima qualify for a gold leader card."""
    from render_research_book import metric_value
    esc=lambda v:escape(str(v),quote=True)
    result=''
    for axis in profile['axes']:
        leader=axis.get('leader')
        if not leader:continue
        stem='STAT_LEADER_'+axis['metric_id']+'_'
        result+='<aside class="radar-leader-strip radar-award" aria-label="'+esc(axis['label']+' '+leader['text'])+'"><span class="radar-award-rank">'+metric_value(book.metrics[stem+'RANK'])+'</span><div class="radar-award-title"><span class="radar-award-eyebrow">VERIFIED / '+esc(leader['family'])+'</span><strong>'+esc(leader['text'])+'</strong><span class="radar-award-label">'+esc(axis['label'])+'</span></div><div class="radar-award-score">'+metric_value(book.metrics[axis['metric_id']])+'</div><p>'+esc(leader['family'])+'完整联盟原表 '+metric_value(book.metrics[stem+'N'])+' 人核验 · 同值 '+metric_value(book.metrics[stem+'TIES'])+' 人<br>雷达为 '+str(profile['n'])+' 人出勤合格样本；此处是单项数值名次。</p><span class="radar-award-shine" aria-hidden="true"></span></aside>'
    return result


def ring_ladder(axis):
    esc=lambda v:escape(str(v),quote=True)
    rings=axis['ring_quantiles']
    if not rings:return '<span class="rings-missing">环上分位参考值缺失；需从保留原始总体重新计算，不作估填。</span>'
    return ''.join('<span class="'+('is-reached' if axis['percentile']>=level else '')+'"><small>P'+str(level)+'</small><b>'+esc(format_ring_tick(rings[str(level)],axis['unit'],axis['metric_id']))+'</b></span>' for level in RING_LEVELS)


def studio(book):
    from render_research_book import metric_value,source_links
    available=profiles(book.a)
    if not available:return '<aside class="note">统计画像暂缺：所有轴必须同来源、共用同一完整纳入样本；缺失不补零。下方保留各项有效读数。</aside>'
    esc=lambda v:escape(str(v),quote=True)
    body='<section class="radar-studio" id="percentile-radar"><div class="radar-heading"><div><span class="dimension-kicker">SEASON SIGNATURE / V1.00</span><h4>一个赛季，多维罗盘</h4></div><div class="radar-actions"><button type="button" class="radar-zoom" aria-pressed="false">放大罗盘</button><button type="button" class="radar-ring-toggle" aria-pressed="true">环上刻度：开</button><button type="button" class="radar-download">导出 SVG</button><button type="button" class="radar-replay">重播 ↗</button></div></div><div class="radar-tabs" role="tablist" aria-label="同来源统计画像">'
    default=next((p['key'] for p in available if any(a['leader'] for a in p['axes'])),available[0]['key'])
    for p in available:
        selected=p['key']==default
        body+=f'<button type="button" role="tab" id="radar-tab-{p["key"]}" aria-controls="radar-panel-{p["key"]}" aria-selected="{str(selected).lower()}" tabindex="{0 if selected else -1}">'+esc(p['family'])+f' · {len(p["axes"])}轴 '+esc(p['title'])+'</button>'
    body+='</div><div class="radar-deck"><span class="radar-light-sweep" aria-hidden="true"></span>'
    photo=next((m for m in book.media_items if m['slot']=='cover' and m['kind']=='photo'),None)
    body+='<figure class="radar-portrait">'
    if photo:body+='<img src="'+photo['data_url']+'" alt="'+esc(photo['alt'])+'" loading="lazy" decoding="async">'
    body+='<span class="radar-name-outline" aria-hidden="true">'+esc(book.a['player']['name'].upper())+'</span><div class="radar-season">'+esc(book.a['sample']['season'])+'<span>'+('常规赛' if book.a['sample']['season_type']=='Regular Season' else '季后赛')+'</span></div><figcaption><span class="radar-player-kicker">PLAYER / SEASON</span><strong>'+esc(book.a['player']['name'])+'</strong><div class="radar-player-sample">'
    for mid,label in [('GP','场'),('MIN','分钟')]:
        m=book.metrics.get(mid)
        if m and m['status']=='ok':body+='<span>'+metric_value(m)+'<small>'+label+'</small></span>'
    body+='</div><p>原值 · 数值百分位 · 同源样本<br>分别阅读，不合成总分。</p></figcaption></figure><div class="radar-panels">'
    for p in available:
        key=p['key'];chart='percentile_'+key+'_radar';e=book.visual_entries[chart]
        book.charts[chart+'.svg']=e['svg']
        chosen=next((a for a in p['axes'] if a['leader']),p['axes'][0]);index=p['axes'].index(chosen)
        body+=f'<section class="radar-panel" id="radar-panel-{key}" role="tabpanel" aria-labelledby="radar-tab-{key}" data-initial-axis="{index}"><header><div><p class="radar-panel-source">'+esc(p['subtitle'])+'</p><h5>'+esc(p['title'])+'</h5></div><span class="radar-sample-badge">同源样本<strong>'+str(p['n'])+'</strong></span></header><div class="radar-legend"><span><i></i>球员轮廓</span><span><i class="baseline"></i>P50 参考</span><span>外缘 P100 · 中心无数据</span></div><div class="radar-chart-viewport" tabindex="0" aria-label="可横向滚动的统计罗盘">'+e['svg']+'</div>'
        body+='<div class="radar-focus" role="status" aria-live="polite" aria-atomic="true"><div><span class="radar-focus-label">'+esc(chosen['label'])+'</span><strong class="radar-focus-raw">'+esc(chosen['display'])+'</strong><b class="radar-focus-percentile">P'+f"{chosen['percentile']:.2f}"+'</b></div><p class="radar-focus-note">'+esc(chosen['note'])+'</p><div class="radar-focus-rings" aria-label="当前轴分位参考值">'+ring_ladder(chosen)+'</div></div><div class="radar-awards">'+award(p,book)+'</div>'
        body+='<details class="radar-axis-details"><summary>逐轴读数与分位参考表 · '+str(len(p['axes']))+'项</summary><div class="radar-table-wrap" tabindex="0" aria-label="可横向滚动的逐轴分位表"><table><thead><tr><th>指标</th><th>原值</th><th>数值百分位</th>'+''.join('<th>P'+str(level)+'</th>' for level in RING_LEVELS)+'</tr></thead><tbody>'
        for i,a in enumerate(p['axes']):
            body+='<tr><th scope="row"><button type="button" class="radar-table-axis" data-axis-index="'+str(i)+'">'+esc(a['label'])+' <small>'+esc(a['code'])+'</small></button></th><td>'+metric_value(book.metrics[a['metric_id']])+'</td><td>'+metric_value(book.metrics[a['percentile_metric_id']])+'</td>'+''.join('<td>'+esc(format_ring_tick(a['ring_quantiles'].get(str(level)),a['unit'],a['metric_id']) or 'N/A')+'</td>' for level in RING_LEVELS)+'</tr>'
        body+='</tbody></table></div></details><p class="radar-gesture">点选轴或表格查看解释；方向键切换轴，Home / End 到首尾。</p><p class="radar-boundary">'+esc(p['scope']+' '+p['boundary'])+'</p>'+source_links(p['source_ids'])+'</section>'
    body+='</div></div><div class="radar-footnotes"><p>内缘为P0，外缘为P100，中间按百分位线性定位；中心圆盘没有数据。环上数值由同季合格样本的原值排序后线性插值得到，与球员的中秩百分位是两种计算。P50不是原值均值；不同来源不比较面积，高数值不一概代表优势。</p>'
    if photo:
        credit=' · '.join(book.a['sources'][sid]['credit']+' / '+book.a['sources'][sid]['license'] for sid in photo['source_ids'])
        body+='<p>'+esc(photo['caption']+' '+credit)+' '+source_links(photo['source_ids'])+'</p>'
    return body+'</div></section>'
