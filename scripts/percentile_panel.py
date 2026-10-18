"""Accessible, responsive percentile rows; raw statistic remains visible."""
from html import escape


def render(book):
    ctx=book.a.get('percentile_context')
    if not ctx:return ''
    from render_research_book import metric_value, source_links
    body='<section class="advanced-percentiles" id="advanced-percentiles"><header><span class="dimension-kicker">DISTRIBUTION / SAME SOURCE</span><h3>高阶数据，放回样本中看</h3><p>每一条同时显示原始读数与数值百分位。条越长，数值越高；使用率、节奏和球队失分的高值不一定是优势。各来源分别计算，不相加。</p></header>'
    if ctx.get('reason'):body+='<p class="note">'+escape(ctx['reason'])+'</p>'
    radar=book.c.get('percentile_presentation')=='radar'
    if radar:
        from radar_visuals import studio
        body+=studio(book)
    body+='<details class="percentile-method"><summary>百分位怎么算，为什么样本不同</summary><p>'+escape(ctx['method'])+'</p><p>'+escape(ctx.get('boundary',''))+'</p><p>常规赛与季后赛不混用；门槛为本项目的描述性筛选规则，未校准为置信阈值。样本不足或数据缺失时保留空白。</p></details>'
    for g in ctx['groups']:
        if g['status']!='ok':
            body+='<p class="percentile-unavailable"><strong>'+escape(g['label'])+'</strong> · '+escape(g['reason'])+'</p>';continue
        hist=g['family']=='EPM_HISTORICAL'
        collapsed=radar and not hist
        if collapsed:body+='<details class="percentile-full-data"><summary>展开 '+escape(g['family'])+' 全部 '+str(len(g['entries']))+' 项读数与百分位</summary>'
        body+='<section class="percentile-group'+(' percentile-archive' if hist else '')+'"><h4>'+escape(g['label'])+'</h4><p class="percentile-scope">'+escape(g['scope'])+'</p>'
        if hist:
            body+='<p class="percentile-scope">记录范围 '+escape(g['date_min'])+'—'+escape(g['date_max'])+'；目标记录 '+escape(g['target_date'])+'。日期不齐，不能作为同日横向比较。</p>'
        body+='<div class="percentile-column-head" aria-hidden="true"><span>指标 / 原始读数</span><span>数值百分位 · 0—100</span><span>有效样本</span></div><div class="percentile-rows">'
        for e in g['entries']:
            m=book.metrics[e['metric_id']]; p=book.metrics[e['percentile_metric_id']]
            raw=metric_value(m)
            if e['unit']=='percent':raw+='%'
            leader=next((l for l in book.a.get('stat_leader_context',{}).get('leaders',[]) if l['metric_id']==e['metric_id']),None) if radar else None
            badge='<span class="league-leader-badge" title="'+escape(leader['scope'])+'；N='+str(leader['n'])+'">★ '+escape(leader['text'])+'</span>' if leader else ''
            body+='<article class="percentile-row'+(' is-league-leader' if leader else '')+'"><div><span class="percentile-name">'+escape(e['label'])+badge+'</span><strong class="percentile-raw">'+raw+'</strong></div>'
            if e['status']=='ok':
                body+='<div class="percentile-distribution"><div class="percentile-track" aria-hidden="true"><span style="width:'+f"{e['percentile']:.4f}"+'%"></span></div><span class="percentile-result">P'+metric_value(p)+'</span></div>'
            else:body+='<div class="percentile-missing">暂缺 · '+escape(e.get('reason','样本不足'))+'</div>'
            body+='<small>N = '+str(e['n'])+('</small>' if not e['missing_count'] else '<br>字段缺失 '+str(e['missing_count'])+'</small>')+'</article>'
        body+='</div><details class="percentile-audit"><summary>样本筛选与解释边界</summary><p>原表 '+str(g['raw_count'])+' 行；纳入 '+str(g['eligible_count'])+' 名球员。'
        if 'removed_stint_count' in g:body+='去除球队分段 '+str(g['removed_stint_count'])+' 行。'
        if 'excluded_below_threshold' in g:body+='未达门槛 '+str(g['excluded_below_threshold'])+' 人。'
        if g.get('excluded'):body+='未纳入 '+str(len(g['excluded']))+' 条，逐项原因见advanced_percentiles.json。'
        body+='</p>'+''.join('<p>'+escape(c)+'</p>' for c in g.get('caveats',[]))+source_links(g['source_ids'])+'</details></section>'
        if collapsed:body+='</details>'
    cids=[cid for cid,c in book.claims.items() if any(mid.startswith(('PCTL_','STAT_LEADER_')) for mid in c['metric_ids'])]
    body+=book.referenced_claims(cids)
    return body+'</section>'
