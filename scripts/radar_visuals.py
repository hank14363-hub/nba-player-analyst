"""Source-specific percentile radars with a shared complete population on every axis."""
from html import escape
from math import cos, sin, pi, isfinite

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
         boundary='比率与累计量各自转为样本百分位；指标共享输入，图形面积没有综合分含义。')]


def profiles(analysis):
    metrics={m['metric_id']:m for m in analysis['metrics']}
    groups={g['family']:g for g in analysis.get('percentile_context',{}).get('groups',[])}
    result=[]
    for spec in PROFILES:
        group=groups.get(spec['family'],{})
        if group.get('status')!='ok':continue
        entries={e['metric_id']:e for e in group['entries']}
        keys=group.get('population_keys',[])
        n=group['eligible_count']
        if n<8 or len(keys)!=n or len(set(keys))!=n:continue
        axes=[]
        for (mid,label),note in zip(spec['axes'],spec['notes']):
            e=entries.get(mid,{});p=metrics.get('PCTL_'+mid,{});raw=metrics.get(mid,{})
            if (e.get('status')!='ok' or e.get('n')!=n or e.get('missing_count')!=0
                or raw.get('status')!='ok' or p.get('status')!='ok'
                or not isinstance(p.get('value'),(int,float)) or isinstance(p.get('value'),bool)
                or not isfinite(p['value']) or not 0<=p['value']<=100
                or abs(p['value']-e['percentile'])>1e-9 or abs(raw['value']-e['target'])>1e-9):
                break
            axes.append(dict(metric_id=mid,percentile_metric_id=p['metric_id'],label=label,n=n,
                             raw=raw['value'],display=raw['display']+('%' if raw['unit']=='percent' else ''),
                             percentile=p['value'],note=note,source_ids=e['source_ids']))
            axes[-1]['leader']=next((l for l in analysis.get('stat_leader_context',{}).get('leaders',[]) if l['metric_id']==mid),None)
        if len(axes)==len(spec['axes']):
            result.append(dict(spec,n=n,axes=axes,source_ids=group['source_ids'],scope=group['scope'],
                               population_keys=keys))
    return result


def svg(profile,analysis,theme):
    """Raw values and exact percentile metric IDs travel with standalone SVG exports."""
    esc=lambda v:escape(str(v),quote=True)
    key=profile['key'];n=len(profile['axes']);cx,cy,r=320,270,148
    color=theme.get('accent','#F0C35C')
    def xy(i,p):
        angle=-pi/2+2*pi*i/n
        return cx+r*p/100*cos(angle),cy+r*p/100*sin(angle)
    def points(level):return ' '.join(f'{x:.3f},{y:.3f}' for x,y in (xy(i,level) for i in range(n)))
    title=profile['title']+' · 数值百分位，非能力评分'
    body=[f'<svg xmlns="http://www.w3.org/2000/svg" class="percentile-radar-svg" viewBox="0 0 640 570" role="group" aria-labelledby="radar-title-{key} radar-desc-{key}">',
          f'<title id="radar-title-{key}">{esc(title)}</title>',
          f'<desc id="radar-desc-{key}">{esc(analysis["player"]["name"])}；{esc(analysis["sample"]["season"])}；N={profile["n"]}。中心0、外圈100，虚线为P50参考线。所有轴使用同一完整纳入样本，不按面积计算得分。</desc>',
          f'<defs><filter id="radar-glow-{key}" x="-40%" y="-40%" width="180%" height="180%"><feGaussianBlur stdDeviation="4"/></filter>',
          f'<radialGradient id="radar-atmosphere-{key}"><stop stop-color="#72512b" stop-opacity=".25"/><stop offset="1" stop-color="#080d14" stop-opacity="0"/></radialGradient>',
          f'<linearGradient id="radar-fill-{key}" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#ffe4a1"/><stop offset="1" stop-color="{esc(color)}"/></linearGradient></defs>',
          '<rect class="radar-chart-bg" width="640" height="570" fill="#0d121a" rx="12"/>',
          f'<ellipse cx="320" cy="270" rx="255" ry="245" fill="url(#radar-atmosphere-{key})"/>',
          '<g aria-hidden="true" fill="none" stroke="#c0a16a"><circle cx="320" cy="270" r="171" stroke-opacity=".13"/><circle cx="320" cy="270" r="179" stroke-opacity=".07" stroke-dasharray="1 9"/></g>']
    for tick in range(72):
        angle=2*pi*tick/72
        inner=172 if tick%6==0 else 176
        body.append(f'<path aria-hidden="true" d="M{cx+inner*cos(angle):.3f} {cy+inner*sin(angle):.3f}L{cx+181*cos(angle):.3f} {cy+181*sin(angle):.3f}" stroke="#c5ad76" stroke-opacity="{.45 if tick%6==0 else .17}"/>')
    for level in (25,50,75,100):
        body.append(f'<polygon points="{points(level)}" fill="none" stroke="'+('#a6b1b9' if level==50 else '#52606a')+f'" stroke-opacity="{.7 if level==50 else .43}" stroke-width="1"'+(' stroke-dasharray="5 6"' if level==50 else '')+'/>')
        body.append(f'<text x="327" y="{cy-r*level/100-4:.3f}" fill="#8f9ca6" font-family="Arial,sans-serif" font-size="10">{level}</text>')
    for i in range(n):
        x,y=xy(i,100);body.append(f'<path d="M{cx} {cy}L{x:.3f} {y:.3f}" stroke="#52606a" stroke-opacity=".4"/>')
    values=' '.join(f'{x:.3f},{y:.3f}' for x,y in (xy(i,a['percentile']) for i,a in enumerate(profile['axes'])))
    body.append(f'<polygon class="radar-bloom" points="{values}" fill="none" stroke="{esc(color)}" stroke-width="7" opacity=".38" filter="url(#radar-glow-{key})"/>')
    body.append(f'<polygon class="radar-shape" points="{values}" fill="url(#radar-fill-{key})" fill-opacity=".20" stroke="#ffdc87" stroke-width="2.8" stroke-linejoin="round"/>')
    body.append('<path aria-hidden="true" d="M313 270H327M320 263V277" stroke="#d2bc8a" stroke-opacity=".5"/>')
    for i,a in enumerate(profile['axes']):
        x,y=xy(i,a['percentile']);lx,ly=xy(i,146)
        anchor='start' if lx>cx+15 else 'end' if lx<cx-15 else 'middle'
        aria=f"{a['label']}，原始值{a['display']}，数值百分位P{a['percentile']:.2f}，N={a['n']}"
        leader=a.get('leader')
        if leader:aria+='，'+leader['text']+'，完整联盟样本'+str(leader['n'])+'人'
        data=f'data-axis-index="{i}" data-axis-label="{esc(a["label"])}" data-axis-raw="{esc(a["display"])}" data-axis-percentile="P{a["percentile"]:.2f}" data-axis-note="{esc(a["note"])}"'
        body.append(f'<g class="radar-axis'+(' is-league-leader' if leader else '')+f'" role="button" tabindex="0" aria-label="{esc(aria)}" {data}><title>{esc(aria)}</title>')
        body.append(f'<circle class="radar-marker-halo" cx="{x:.3f}" cy="{y:.3f}" r="9" fill="none" stroke="{esc(color)}" opacity="0"/>')
        body.append(f'<circle class="radar-marker" cx="{x:.3f}" cy="{y:.3f}" r="3.5" fill="{esc(color)}" stroke="#12191f" stroke-width="2"/>')
        if leader:
            body.append(f'<circle class="radar-leader-orbit" aria-hidden="true" cx="{x:.3f}" cy="{y:.3f}" r="11" fill="#f5d98a" fill-opacity=".12" stroke="#ffe4a1" stroke-opacity=".65"/>')
        body.append(f'<rect x="{lx-5 if anchor=="start" else lx-125 if anchor=="end" else lx-65:.3f}" y="{ly-20:.3f}" width="130" height="65" fill="transparent"/>')
        badge=' <tspan fill="#ffe07a" font-weight="700">★ '+('NO.1' if leader['ties']==1 else '=NO.1')+'</tspan>' if leader else ''
        body.append(f'<text class="radar-axis-label" x="{lx:.3f}" y="{ly-7:.3f}" text-anchor="{anchor}" fill="#d7dce1" font-family="Arial,sans-serif" font-size="14">{esc(a["label"])}{badge}</text>')
        body.append(f'<text class="radar-axis-value" x="{lx:.3f}" y="{ly+21:.3f}" text-anchor="{anchor}" fill="'+('#ffe07a' if leader else '#f5f3ed')+f'" font-family="Arial,sans-serif" font-size="27" font-weight="800" data-metric-id="{a["metric_id"]}" data-value="{a["raw"]}">{esc(a["display"])}</text>')
        body.append(f'<text class="radar-axis-percentile" x="{lx:.3f}" y="{ly+44:.3f}" text-anchor="{anchor}" fill="{esc(color)}" font-family="Arial,sans-serif" font-size="12">P<tspan data-metric-id="{a["percentile_metric_id"]}" data-value="{a["percentile"]}">{a["percentile"]:.2f}</tspan></text></g>')
    body += [f'<text class="radar-svg-footer" x="32" y="538" fill="#8f9ca6" font-family="Arial,sans-serif" font-size="11">{esc(analysis["sample"]["season"])} · {esc(analysis["sample"]["season_type"])} · N={profile["n"]} · {profile["family"]}</text>',
             '<text class="radar-svg-footer" x="32" y="557" fill="#8f9ca6" font-family="Arial,sans-serif" font-size="10">'+('SYNTHETIC TEST DATA · ' if analysis['data_kind']=='synthetic' else '')+'中心0 / 外圈100 · 同来源数值分布 · 不算面积分</text></svg>']
    return ''.join(body)


def radar_entries(analysis,theme):
    result={}
    for p in profiles(analysis):
        ids=[mid for a in p['axes'] for mid in (a['metric_id'],a['percentile_metric_id'],a['percentile_metric_id']+'_N')]
        ids += ['STAT_LEADER_'+a['metric_id']+'_'+k for a in p['axes'] if a.get('leader') for k in ('RANK','TIES','N')]
        result['percentile_'+p['key']+'_radar']=dict(title=p['title']+' · 六轴统计画像',status='ok',
            metric_ids=ids,source_ids=p['source_ids'],note=p['scope']+' '+p['boundary'],svg=svg(p,analysis,theme))
    return result


def award(profile,book):
    """A prominent single-stat callout using only registered full-league results."""
    from render_research_book import metric_value
    esc=lambda v:escape(str(v),quote=True)
    result=''
    for axis in profile['axes']:
        leader=axis.get('leader')
        if not leader:continue
        stem='STAT_LEADER_'+axis['metric_id']+'_'
        result+='<aside class="radar-leader-strip radar-award" aria-label="'+esc(axis['label']+' '+leader['text'])+'"><span class="radar-award-rank">'+metric_value(book.metrics[stem+'RANK'])+'</span><div class="radar-award-title"><span class="radar-award-eyebrow">LEAGUE LEADER / '+esc(leader['family'])+'</span><strong>'+esc(leader['text'])+'</strong><span class="radar-award-label">'+esc(axis['label'])+'</span></div><div class="radar-award-score">'+metric_value(book.metrics[axis['metric_id']])+'</div><p>'+esc(leader['family'])+'完整联盟原表 '+metric_value(book.metrics[stem+'N'])+' 人核验 · 同值 '+metric_value(book.metrics[stem+'TIES'])+' 人<br>雷达为 '+str(profile['n'])+' 人出勤合格样本；此处是单项数值名次。</p><span class="radar-award-shine" aria-hidden="true"></span></aside>'
    return result


def studio(book):
    from render_research_book import metric_value,source_links
    available=profiles(book.a)
    if not available:
        return '<aside class="note">六轴画像暂缺：需要同来源、同一完整纳入样本的六项有效指标；缺失字段不补零。下方仍保留各项读数。</aside>'
    esc=lambda v:escape(str(v),quote=True)
    body='<section class="radar-studio" id="percentile-radar"><div class="radar-heading"><div><span class="dimension-kicker">SEASON SIGNATURE / PLAYER PROFILE</span><h4>一个赛季，六个侧面</h4></div><button type="button" class="radar-replay">重播入场 <span aria-hidden="true">↗</span></button></div><div class="radar-tabs" role="tablist" aria-label="统计画像来源">'
    default=next((p['key'] for p in available if any(a.get('leader') for a in p['axes'])),available[0]['key'])
    for i,p in enumerate(available):
        selected=p['key']==default
        body+=f'<button type="button" role="tab" id="radar-tab-{p["key"]}" aria-controls="radar-panel-{p["key"]}" aria-selected="{str(selected).lower()}" tabindex="{0 if selected else -1}"><span>{i+1:02d}</span> '+esc(p['family'])+' · '+esc(p['title'])+'</button>'
    body+='</div><div class="radar-deck"><span class="radar-light-sweep" aria-hidden="true"></span>'
    photo=next((m for m in book.media_items if m['slot']=='cover' and m['kind']=='photo'),None)
    body+='<figure class="radar-portrait">'
    if photo:body+='<img src="'+photo['data_url']+'" alt="'+esc(photo['alt'])+'" loading="lazy" decoding="async">'
    body+='<span class="radar-name-outline" aria-hidden="true">'+esc(book.a['player']['name'].upper())+'</span>'
    body+='<div class="radar-season">'+esc(book.a['sample']['season'])+'<span>'+('常规赛' if book.a['sample']['season_type']=='Regular Season' else '季后赛')+'</span></div><figcaption><span class="radar-player-kicker">SEASON PROFILE</span><strong>'+esc(book.a['player']['name'])+'</strong><div class="radar-player-sample">'
    for mid,label in [('GP','场'),('MIN','分钟')]:
        metric=book.metrics.get(mid)
        if metric and metric['status']=='ok':body+='<span>'+metric_value(metric)+'<small>'+label+'</small></span>'
    body+='</div><p>职责、效率与模型读数<br>分别看，不合成评分。</p></figcaption></figure><div class="radar-panels">'
    for p in available:
        key=p['key'];chart='percentile_'+key+'_radar';e=book.visual_entries[chart]
        book.charts[chart+'.svg']=e['svg']
        a=next((a for a in p['axes'] if a.get('leader')),p['axes'][0])
        body+=f'<section class="radar-panel" id="radar-panel-{key}" role="tabpanel" aria-labelledby="radar-tab-{key}"><header><div><p class="radar-panel-source">'+esc(p['subtitle'])+'</p><h5>'+esc(p['title'])+'</h5></div><span class="radar-sample-badge">画像样本 <strong>'+str(p['n'])+'</strong></span></header>'+award(p,book)+'<div class="radar-legend"><span><i></i>本球员</span><span><i class="radar-legend-baseline"></i>P50参考线</span><span>中心0 · 外圈100</span></div>'+e['svg']
        body+='<div class="radar-focus" role="status" aria-live="polite" aria-atomic="true"><div><span class="radar-focus-label">'+esc(a['label'])+'</span><strong class="radar-focus-raw">'+esc(a['display'])+'</strong><b class="radar-focus-percentile">P'+f"{a['percentile']:.2f}"+'</b></div><p class="radar-focus-note">'+esc(a['note'])+'</p></div><p class="radar-gesture">点击或用键盘选择任一轴，查看指标含义。</p><p class="radar-boundary">'+esc(p['boundary'])+'</p>'+source_links(p['source_ids'])+'</section>'
    body+='</div></div><div class="radar-footnotes"><p>雷达仅选六项便于阅读；完整指标保留在下方。P50是百分位刻度参考线，不是原始值均值；不同来源的图不作面积比较。</p>'
    if photo:
        credits=' · '.join(book.a['sources'][sid]['credit']+' / '+book.a['sources'][sid]['license'] for sid in photo['source_ids'])
        body+='<p>'+esc(photo['caption'])+' '+esc(credits)+' '+source_links(photo['source_ids'])+'</p>'
    return body+'</div></section>'
