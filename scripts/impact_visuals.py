"""Model components on shared units, with retrospective and predictive panels apart."""
import html, math

def impact_visuals(analysis):
    ctx=analysis.get('impact_context',{});metrics={m['metric_id']:m for m in analysis['metrics']};entries={}
    for key,title,predictive in [('impact_retrospective','整季回顾：进攻与防守分量',False),('impact_predictive','历史预测：DARKO 日期快照',True)]:
        groups=[];ids=[];sources=[]
        for d in ctx.get('datasets',[]):
            if (d['estimate_type']=='predictive_snapshot')!=predictive:continue
            names={'BREF':('BPM','OBPM','DBPM'),'LEBRON':('LEBRON','O_LEBRON','D_LEBRON'),'DARKO':('DPM','O_DPM','D_DPM')}[d['family']]
            mids=['IMPACT_'+v for v in names]
            if any(metrics[m]['status']!='ok' for m in mids):continue
            groups.append((d,mids));ids+=mids;sources.append(d['source_id'])
        if not groups:continue
        vals=[metrics[mid]['value'] for mid in ids];lo=min(-1,math.floor(min(vals)));hi=max(2,math.ceil(max(vals)))
        def x(v):return 128+295*(v-lo)/(hi-lo)
        height=108+len(groups)*150
        esc=lambda v:html.escape(str(v),quote=True)
        p=[f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 {height}" role="img" aria-label="{esc(title)}"><rect width="480" height="{height}" fill="#F6F4EF"/>',f'<text x="24" y="27" font-size="15" font-weight="700" fill="#263444">{esc(title)}</text>', '<text x="24" y="48" font-size="12" fill="#5A6573">每百回合模型点数 · 零点为平均 · 不取平均分</text>']
        for tick in range(lo,hi+1):
            p.append(f'<path d="M{x(tick):.2f} 71V{height-53}" stroke="'+('#8e98a1' if tick==0 else '#DDD9D2')+f'"/><text x="{x(tick):.2f}" y="{height-34}" text-anchor="middle" font-size="12" fill="#5A6573">{tick:+d}</text>')
        for i,(d,mids) in enumerate(groups):
            y=85+i*150;label=d['family'] if d['family']!='BREF' else 'BPM 2.0'
            scope=d['cutoff']+' · 预测' if predictive else d['season']+' · 回顾'
            p.append(f'<text x="24" y="{y}" font-size="13" font-weight="700" fill="#263444">{esc(label)}</text><text x="154" y="{y}" font-size="12" fill="#5A6573">{esc(scope)}</text>')
            for j,mid in enumerate(mids):
                m=metrics[mid];value=m['value'];yy=y+27+j*29;color=['#2e6477','#426f87','#946f59'][j]
                p.append(f'<text x="34" y="{yy+4}" font-size="12" fill="#344454">'+['总值','进攻分量','防守分量'][j]+f'</text><path d="M{x(0):.2f} {yy}H{x(value):.2f}" stroke="{color}" stroke-width="6" stroke-linecap="round"/><circle cx="{x(value):.2f}" cy="{yy}" r="4" fill="{color}"><title>{esc(mid)} {value:+.3f}</title></circle><text x="461" y="{yy+4}" text-anchor="end" font-size="12" fill="#263444" data-metric-id="{mid}" data-value="{value}">{value:+.1f}</text>')
        p.append(f'<text x="24" y="{height-12}" font-size="12" fill="#5A6573">'+('生涯加权预测；当日历史值与整季实际表现不同' if predictive else '模型输入重叠；防守分量不等于个人防守能力')+'</text></svg>')
        entries[key]=dict(title=title,status='ok',metric_ids=ids,source_ids=sources,note='单位相同但估计对象与方法不同，不比较点数大小作为能力名次。舍入可使总值与分量和略有不同。',svg=''.join(p))
    return entries
