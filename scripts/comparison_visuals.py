"""Paper-toned statistical profile, usage/efficiency context and observed spatial bins."""
from html import escape as esc
from math import sin,cos,pi,floor


def fmt(value,unit):return f'{value*100:.1f}%' if unit=='fraction' else f'{value:.2f}'


def comparison_visuals(analysis,theme):
    ctx=analysis.get('comparison_context',{});entries={'shot_density':dict(title='真实出手频次热区',status='missing',metric_ids=[],source_ids=[],note='完整投篮坐标缺失或未通过覆盖核验；不以合成位置填图。',svg=None)}
    if ctx.get('status')=='ok':
        axes=ctx['axes'];cx,cy,r=240,190,115
        p=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 430" role="img" aria-label="同角色统计百分位画像，不是能力评分">',
           '<rect width="480" height="430" fill="#F6F4EF"/>']
        def xy(i,value):a=-pi/2+i*2*pi/len(axes);return cx+cos(a)*r*value/100,cy+sin(a)*r*value/100
        for level in [25,50,75,100]:
            points=' '.join(f'{x:.2f},{y:.2f}' for x,y in [xy(i,level) for i in range(len(axes))])
            p.append(f'<polygon points="{points}" fill="none" stroke="#d6d5ce"/>')
            p.append(f'<text x="244" y="{cy-level/100*r-3:.2f}" font-size="9" fill="#647080">{level}</text>')
        for i,a in enumerate(axes):
            x,y=xy(i,100);lx,ly=xy(i,128)
            p.append(f'<path d="M{cx} {cy}L{x:.2f} {y:.2f}" stroke="#d6d5ce"/>')
            anchor='start' if lx>cx+10 else ('end' if lx<cx-10 else 'middle')
            p.append(f'<text x="{lx:.2f}" y="{ly:.2f}" text-anchor="{anchor}" font-size="11" fill="#344454">{esc(a["label"])}</text>')
            p.append(f'<text x="{lx:.2f}" y="{ly+16:.2f}" text-anchor="{anchor}" font-size="12" fill="#1e6574">P{a["percentile"]:.1f}</text>')
        pts=' '.join(f'{x:.2f},{y:.2f}' for x,y in [xy(i,a['percentile']) for i,a in enumerate(axes)])
        p.append(f'<polygon points="{pts}" fill="#448696" fill-opacity=".18" stroke="#337988" stroke-width="2"/>')
        for i,a in enumerate(axes):
            x,y=xy(i,a['percentile']);p.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3.5" fill="#337988"><title>{esc(a["label"])}：{fmt(a["target"],a["unit"])}；百分位 {a["percentile"]:.2f}</title></circle>')
        p+=['<text x="24" y="376" font-size="12" fill="#344454">统计画像 · 外圈 = 同角色样本内较高读数</text>',
            '<text x="24" y="397" font-size="11" fill="#5a6573">'+('BR五轴；失误轴反向；不含非受助攻命中与PIE' if ctx.get('adapter') == 'sumitro-v56' else '失误轴反向；自主终结占比是职责描述，不是越高越好')+'</text>',
            f'<text x="24" y="416" font-size="10" fill="#5a6573">N={ctx["cohort_count"]} · 不连加、不算面积分、不作综合排名</text></svg>']
        entries['role_profile']=dict(title='同角色统计画像：优势与代价一起看',status='ok',
            metric_ids=['COHORT_N']+['COHORT_'+a['metric_id']+'_PERCENTILE' for a in axes],
            source_ids=ctx['source_ids'],note=ctx['percentile_formula']+'。'+ctx['boundary'],svg=''.join(p))
        p=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 370" role="img" aria-label="稳定轮换使用率与真实命中率，非能力排名">','<rect width="480" height="370" fill="#F6F4EF"/>']
        rows=ctx['league_players'];lo=min(.10,min(r['USG_PCT'] for r in rows)-.02);hi=max(.40,max(r['USG_PCT'] for r in rows)+.02)
        bot=min(.45,min(r['TS_PCT'] for r in rows)-.02);top=max(.70,max(r['TS_PCT'] for r in rows)+.02)
        def pos(row):return 55+370*(row['USG_PCT']-lo)/(hi-lo),295-240*(row['TS_PCT']-bot)/(top-bot)
        for usg in [.10,.20,.30,.40]:
            x=55+370*(usg-lo)/(hi-lo)
            p.append(f'<path d="M{x:.2f} 55V295" stroke="#dedbd4"/><text x="{x:.2f}" y="315" text-anchor="middle" font-size="10">{usg*100:.0f}%</text>')
        for ts in [.45,.50,.55,.60,.65,.70]:
            if bot<=ts<=top:
                y=295-240*(ts-bot)/(top-bot);p.append(f'<path d="M55 {y:.2f}H425" stroke="#dedbd4"/><text x="45" y="{y+3:.2f}" text-anchor="end" font-size="10">{ts*100:.0f}%</text>')
        cohort_ids={r['player_id'] for r in ctx['players']}
        for row in rows:
            x,y=pos(row);c='#5e8792' if row['player_id'] in cohort_ids else '#b2b7b5'
            p.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{c}" opacity=".65"><title>{esc(row["name"])} · USG {row["USG_PCT"]*100:.1f}% · TS {row["TS_PCT"]*100:.1f}%</title></circle>')
        row=next(r for r in rows if r['player_id']==ctx['target_id']);x,y=pos(row)
        p+=[f'<circle cx="{x:.2f}" cy="{y:.2f}" r="6" fill="#ae4d5b" stroke="#fff" stroke-width="2"/>',f'<text x="{x-10:.2f}" y="{y-12:.2f}" text-anchor="end" font-size="12" fill="#8f3848">本球员</text>',
            '<text x="24" y="27" font-size="12">纵轴：真实命中率 · 横轴：使用率</text>',
            '<text x="55" y="342" font-size="11">灰：稳定轮换；蓝：同角色；红：本球员</text>',
            '<text x="55" y="360" font-size="10">使用率不是持球时长；负荷不自动解释效率差</text></svg>']
        entries['usage_efficiency']=dict(title='高负荷，也要面对效率问题',status='ok',metric_ids=['USG_PCT','TS_PCT','COMPARISON_ELIGIBLE_N'],source_ids=ctx['source_ids'],note='同赛季 GP≥40、总分钟≥1000 的稳定轮换；TS由基础总量统一复算。未调整机会难度，不建立负荷与效率因果关系。',svg=''.join(p))
    if analysis.get('shot_context',{} ) and analysis['shot_context']['points']:
        entries['shot_density']=density(analysis)
    return entries


def density(analysis):
    ctx=analysis['shot_context'];bins={};off=0
    # 5ft cells, exact observed counts; no kernel interpolation or FG% color.
    for p in ctx['points']:
        if p['y']>417.5:off+=1;continue
        key=(min(9,floor((p['x']+250)/50)),min(9,floor((p['y']+52.5)/50)))
        b=bins.setdefault(key,dict(fga=0,fgm=0));b['fga']+=1;b['fgm']+=p['made']
    maximum=max((b['fga'] for b in bins.values()),default=0)
    p=['<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 530" role="img" aria-label="真实出手频次网格热区，颜色不是命中率或能力">','<rect width="480" height="530" fill="#F6F4EF"/>']
    for (ix,iy),b in bins.items():
        x=40+40*ix;y=35+40*iy
        p.append(f'<rect x="{x}" y="{y}" width="40" height="{min(40,411-y)}" fill="#356c7b" fill-opacity="{.12+.78*b["fga"]/maximum:.4f}"><title>横向 {ix*5-25} 至 {(ix+1)*5-25} ft；纵向 {iy*5-5.25} 至 {min((iy+1)*5-5.25,41.75)} ft；出手 {b["fga"]}，命中 {b["fgm"]}</title></rect>')
        if b['fga']>=5:p.append(f'<text x="{x+20}" y="{y+23}" text-anchor="middle" font-size="11" fill="{"#fff" if b["fga"]/maximum>.45 else "#304553"}">{b["fga"]}</text>')
    p+=['<g fill="none" stroke="#9b9b91" stroke-width="1.3"><rect x="40" y="35" width="400" height="376"/><path d="M176 35V187H304V35 M64 35V149 M416 35V149 M64 149A190 190 0 0 0 416 149"/><circle cx="240" cy="77" r="4.8"/><path d="M208 66H272"/></g>',
        '<text x="40" y="440" font-size="13" fill="#304553">颜色越深 = 出手次数越多；不是命中率</text>',
        f'<text x="40" y="462" font-size="12">5 × 5 英尺网格 · 最大格 {maximum} 次 · 不平滑插值</text>',
        f'<text x="40" y="482" font-size="11">近端半场 {len(ctx["points"])-off} / 全部 {len(ctx["points"])}；视窗外 {off} 次</text>',
        '<text x="40" y="501" font-size="11">'+(f'另有 {ctx["missing_location_count"]} 次缺坐标，不计入网格' if ctx.get('missing_location_count') else '全部事件仍在交互球场；标签冲突保留原坐标')+'</text>',
        '<text x="40" y="520" font-size="10">P_SHOT + P_BASE · 悬停格子查看准确出手 / 命中数</text></svg>']
    return dict(title='真实出手频次热区：球从哪里出手'+('（有坐标样本）' if ctx.get('missing_location_count') else ''),status='ok',metric_ids=['SHOT_EVENT_FGA'],source_ids=['P_SHOT','P_BASE'],note='每格精确计数，颜色线性对应频次；边界半开区间、最后一格含球场边界。半场外事件另计并保留在交互球场。'+(f'仅含{len(ctx["points"])}次有坐标事件；缺坐标{ctx["missing_location_count"]}次，赛季总数{ctx["counts"]["FGA"]}次。' if ctx.get('missing_location_count') else '')+'不提供联盟相对效率或投射能力热区。',svg=''.join(p))
