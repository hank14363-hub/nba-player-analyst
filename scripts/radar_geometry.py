"""Offline SVG compass: one honest percentile scale and traceable ring values."""
from html import escape
from math import cos,sin,pi,isfinite
import json

RING_LEVELS=(5,18,32,46,60,75,90)
CENTER=(500,490)
INNER,OUTER=50,330


def format_ring_tick(value,unit,mid=''):
    if not isinstance(value,(int,float)) or isinstance(value,bool) or not isfinite(value):return ''
    if unit=='fraction':return f'{value*100:.1f}%'
    if unit=='percent':return f'{value:.1f}%'
    if unit in ('per100_model','per100_team') and ('NET' in mid or 'BPM' in mid or 'EPM' in mid):
        return f'{value:+.1f}'
    if mid.endswith('WS48'):return f'{value:.3f}'
    return f'{value:.1f}' if abs(value)>=10 else f'{value:.2f}'


def svg(profile,analysis,theme):
    esc=lambda v:escape(str(v),quote=True)
    key=profile['key'];n=len(profile['axes']);cx,cy=CENTER
    def radius(p):return INNER+(OUTER-INNER)*p/100
    def xy(i,r):
        angle=-pi/2+2*pi*i/n
        return cx+r*cos(angle),cy+r*sin(angle)
    def points(level):return ' '.join(f'{x:.3f},{y:.3f}' for x,y in (xy(i,radius(level)) for i in range(n)))
    values=' '.join(f'{x:.3f},{y:.3f}' for i,a in enumerate(profile['axes']) for x,y in [xy(i,radius(a['percentile']))])
    rings_ready=all(a['ring_quantiles'] for a in profile['axes'])
    desc=(f'{analysis["player"]["name"]}；{analysis["sample"]["season"]}；同来源完整纳入样本N={profile["n"]}。'
          '内缘P0，外缘P100，中心无数据；半径在两缘间按数值百分位线性定位。P50虚线是参考，不是原值均值。不计算面积分。'
          +('环上为原始总体的线性插值分位参考值。' if rings_ready else '环上真实分位参考值缺失，不作估填。'))
    body=[f'<svg xmlns="http://www.w3.org/2000/svg" class="percentile-radar-svg" viewBox="0 0 1000 980" role="group" aria-labelledby="radar-title-{key} radar-desc-{key}">',
          f'<title id="radar-title-{key}">{esc(profile["title"])} · {n}轴数值百分位，非能力评分</title>',
          f'<desc id="radar-desc-{key}">{esc(desc)}</desc>',
          '<rect width="1000" height="980" fill="#0c1219" rx="8"/>',
          f'<defs><clipPath id="radar-clip-{key}"><polygon points="{values}"/></clipPath>',
          f'<filter id="radar-glow-{key}" x="-30%" y="-30%" width="160%" height="160%"><feGaussianBlur stdDeviation="5"/></filter>',
          f'<radialGradient id="radar-glass-{key}"><stop stop-color="#f3f7fc" stop-opacity=".05"/><stop offset="1" stop-color="#fff" stop-opacity=".22"/></radialGradient></defs>']
    # Alternate fills use the exact same radial function as the polygon/ticks.
    edges=(100,82.5,67.5,53,39,25,11.5)
    for i,edge in enumerate(edges):
        body.append(f'<circle cx="{cx}" cy="{cy}" r="{radius(edge):.3f}" fill="'+('#171f29' if i%2==0 else '#232d39')+'" stroke="#bac9d7" stroke-opacity=".12"/>')
    body.append(f'<g class="radar-lit" clip-path="url(#radar-clip-{key})">')
    for i,edge in enumerate(edges):
        body.append(f'<circle cx="{cx}" cy="{cy}" r="{radius(edge):.3f}" fill="'+('#68727e' if i%2==0 else '#838d98')+'" fill-opacity=".9"/>')
    body.append(f'<circle cx="{cx}" cy="{cy}" r="{OUTER}" fill="url(#radar-glass-{key})"/></g>')
    for level in (0,50,100):
        body.append(f'<circle class="radar-grid" data-level="{level}" cx="{cx}" cy="{cy}" r="{radius(level)}" fill="none" stroke="#d4e0eb" stroke-opacity="{.65 if level==50 else .25}" stroke-dasharray="'+('4 7' if level==50 else '1 0')+'"/>')
    for tick in range(120):
        ang=2*pi*tick/120;r1=OUTER+8;r2=OUTER+(15 if tick%5==0 else 11)
        body.append(f'<path aria-hidden="true" d="M{cx+r1*cos(ang):.2f} {cy+r1*sin(ang):.2f}L{cx+r2*cos(ang):.2f} {cy+r2*sin(ang):.2f}" stroke="#bacad9" stroke-opacity="{.6 if tick%5==0 else .25}"/>')
    for i in range(n):
        x0,y0=xy(i,INNER);x1,y1=xy(i,OUTER)
        body.append(f'<path d="M{x0:.3f} {y0:.3f}L{x1:.3f} {y1:.3f}" stroke="#d4e0ee" stroke-opacity=".16"/>')
    body.append(f'<polygon class="radar-bloom" points="{values}" fill="none" stroke="#fff" stroke-width="8" opacity=".55" filter="url(#radar-glow-{key})" stroke-linejoin="round"/>')
    body.append(f'<polygon class="radar-shape" points="{values}" fill="#fff" fill-opacity=".05" stroke="#f7fbff" stroke-width="2.8" stroke-linejoin="round"/>')
    for i,a in enumerate(profile['axes']):
        rotation=(360*i/n+90)%180-90
        for level in RING_LEVELS:
            q=a['ring_quantiles'].get(str(level))
            text=format_ring_tick(q,a['unit'],a['metric_id'])
            if not text:continue
            x,y=xy(i,radius(level))
            body.append(f'<text class="radar-ring-tick" data-axis-index="{i}" data-level="{level}" data-quantile-value="{q}" x="{x:.3f}" y="{y:.3f}" text-anchor="middle" dominant-baseline="central" transform="rotate({rotation:.3f} {x:.3f} {y:.3f})" fill="#eef3f8" fill-opacity="{.95 if a["percentile"]>=level else .55}" font-family="Arial,Microsoft YaHei,sans-serif" font-size="{11 if level==5 else 14}" font-weight="{700 if a["percentile"]>=level else 400}">{esc(text)}</text>')
    body.append(f'<circle cx="{cx}" cy="{cy}" r="{INNER-1}" fill="#111a24" stroke="#7a8999" stroke-opacity=".35"/><text x="{cx}" y="{cy-4}" fill="#c6d3df" font-family="Arial,sans-serif" font-size="14" text-anchor="middle">P0</text><text x="{cx}" y="{cy+17}" fill="#8192a4" font-family="Microsoft YaHei,sans-serif" font-size="11" text-anchor="middle">中心无数据</text>')
    for i,a in enumerate(profile['axes']):
        x,y=xy(i,radius(a['percentile']));lx,ly=xy(i,405)
        rotation=(360*i/n+90)%180-90
        leader=a['leader'];full=''
        if leader:full='，'+leader['text']+'，完整联盟样本'+str(leader['n'])+'人'
        aria=f"{a['label']} {a['code']}，原始值{a['display']}，数值百分位P{a['percentile']:.2f}，N={a['n']}"+full
        ladder=[dict(level=q,display=format_ring_tick(a['ring_quantiles'].get(str(q)),a['unit'],a['metric_id'])) for q in RING_LEVELS] if a['ring_quantiles'] else []
        attrs=f'data-axis-index="{i}" data-axis-label="{esc(a["label"]+" · "+a["code"])}" data-axis-raw="{esc(a["display"])}" data-axis-percentile="P{a["percentile"]:.2f}" data-axis-note="{esc(a["note"])}" data-axis-rings="{esc(json.dumps(ladder,ensure_ascii=False))}"'
        body.append(f'<g class="radar-axis'+(' is-league-leader' if leader else '')+f'" tabindex="0" role="button" aria-label="{esc(aria)}" {attrs}><title>{esc(aria)}</title>')
        body.append(f'<circle class="radar-marker-halo" cx="{x:.3f}" cy="{y:.3f}" r="12" fill="none" stroke="#f3d58d" opacity="0"/><circle class="radar-marker" cx="{x:.3f}" cy="{y:.3f}" r="4" fill="'+('#ffe09a' if leader else '#f7fbff')+'" stroke="#111a24" stroke-width="2"/>')
        body.append(f'<g class="radar-axis-header" transform="translate({lx:.3f} {ly:.3f}) rotate({rotation:.3f})"><rect x="-110" y="-48" width="220" height="105" fill="transparent"/>')
        body.append(f'<text class="radar-axis-label" x="0" y="-26" text-anchor="middle" font-family="Microsoft YaHei,Arial,sans-serif" font-size="19" font-weight="700" fill="#d7e0e8">{esc(a["label"])}</text>')
        body.append(f'<text class="radar-axis-code" x="0" y="0" text-anchor="middle" font-family="Arial,sans-serif" font-size="25" font-style="italic" font-weight="900" fill="#fff">{esc(a["code"])}</text>')
        body.append(f'<text class="radar-axis-value" x="0" y="27" text-anchor="middle" font-family="Arial,sans-serif" font-size="23" font-weight="700" fill="'+('#ffe09a' if leader else '#f2f6fa')+f'" data-metric-id="{a["metric_id"]}" data-value="{a["raw"]}">{esc(a["display"])}</text>')
        body.append(f'<text class="radar-axis-percentile" x="0" y="49" text-anchor="middle" font-family="Arial,sans-serif" font-size="16" fill="#b9c8d8">P<tspan data-metric-id="{a["percentile_metric_id"]}" data-value="{a["percentile"]}">{a["percentile"]:.2f}</tspan></text>')
        if leader:body.append('<text class="radar-axis-badge" x="0" y="-50" text-anchor="middle" font-family="Arial,sans-serif" font-size="16" font-weight="700" fill="#ffe09a">★ '+('NO.1' if leader['ties']==1 else '=NO.1')+'</text>')
        body.append('</g></g>')
    footer=('SYNTHETIC TEST DATA · ' if analysis['data_kind']=='synthetic' else '')+f'{analysis["sample"]["season"]} · {profile["family"]} · N={profile["n"]} · 内缘P0 / 外缘P100 · 非能力分'
    body.append(f'<text x="500" y="961" fill="#9caebf" font-family="Arial,Microsoft YaHei,sans-serif" font-size="13" text-anchor="middle">{esc(footer)}</text></svg>')
    return ''.join(body)
