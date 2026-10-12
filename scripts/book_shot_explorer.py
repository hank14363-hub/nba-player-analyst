"""Offline filters over coverage-validated shot events; retain type/zone conflicts."""
import re
from html import escape
from common import DataError
from shot_charts import ZONES

def explorer_rows(bundle, analysis):
    context=analysis.get('shot_context')
    if not context:
        return []
    raw={(str(r['GAME_ID']).zfill(10),int(r['GAME_EVENT_ID'])):r for r in bundle['tables'].get('player_shots',[])}
    rows=[]
    for point in context['points']:
        key=(point['game_id'],point['event_id'])
        if key not in raw:raise DataError('Explorer event missing from original rows')
        r=raw[key]
        zone=r['SHOT_ZONE_BASIC'];kind=r['SHOT_TYPE']
        conflict=(zone in {'Restricted Area','In The Paint (Non-RA)','Mid-Range'} and kind!='2PT Field Goal') or (zone in {'Left Corner 3','Right Corner 3','Above the Break 3'} and kind!='3PT Field Goal')
        code,label=('UNRESOLVED','区域/类型标签冲突') if conflict else ZONES[zone]
        if r['LOC_X']!=point['x'] or r['LOC_Y']!=point['y'] or int(r['SHOT_MADE_FLAG'])!=point['made'] or kind.startswith('3PT')!=point['three']:
            raise DataError('Explorer data differs from validated coordinates/outcome/type')
        date=str(r['GAME_DATE']);date=date[:4]+'-'+date[4:6]+'-'+date[6:]
        rows.append(dict(point,zone=code,label=label,date=date,period=r['PERIOD'],clock=f"{int(r['MINUTES_REMAINING']):02d}:{int(r['SECONDS_REMAINING']):02d}",original_zone=zone,original_type=kind))
    if len(raw)!=len(rows):raise DataError('Explorer raw coverage mismatch')
    return rows

def render_explorer(rows, svg):
    if not rows:return ''
    esc=lambda v:escape(str(v),quote=True)
    points=iter(enumerate(rows))
    def mark(match):
        index,r=next(points)
        attrs={k:r[k] for k in ('game_id','event_id','zone','made','three','date','period','clock','x','y','original_zone','original_type')}
        attrs.update(beat=index%12,svg_x=f"{240+r['x']*.54:.3f}",svg_y=f"{68.35+r['y']*.54:.3f}")
        text=r['date']+' · '+r['game_id']+' · 事件'+str(r['event_id'])+' · '+r['label']+' · '+('命中' if r['made'] else '未中')
        glyph=re.sub(r'^<(circle|path)\b',r'<\1 class="shot-glyph"',match.group(0))
        return '<g class="shot-event" '+ ' '.join('data-'+k.replace('_','-')+'="'+esc(int(v) if isinstance(v,bool) else v)+'"' for k,v in attrs.items())+'><title>'+esc(text)+'</title>'+glyph+'</g>'
    pattern=r'<circle\b[^>]*r="1\.9"[^>]*/>|<path\b[^>]*stroke="#ce3d43"[^>]*/>'
    svg,n=re.subn(pattern,mark,svg)
    if n!=len(rows):raise DataError('Explorer SVG does not cover original point set')
    svg=svg.replace('命中 '+str(sum(r['made'] for r in rows))+' / 出手 '+str(len(rows))+' · 圆点命中 / 叉未中','圆点命中 / 叉未中 · 筛选统计见上方')
    # Zoom the canvas margins, never the data or the court scale. All validated
    # coordinates fit the complete 50 x 94 ft court, including backcourt shots.
    svg=svg.replace('viewBox="0 0 480 650"','viewBox="88 23 304 542"')
    svg=re.sub(r'<text\b[^>]*>.*?</text>','',svg)
    svg=svg.replace('<rect x="105" y="40" width="270" height="507.6" fill="none"',
                    '<rect class="court-floor" x="105" y="40" width="270" height="507.6" fill="#f0e9dc"')
    # One overlay serves every event; no constantly looping animation per point.
    svg=svg.replace('</svg>','<g class="shot-focus" hidden aria-hidden="true"><circle class="shot-focus-ring" cx="0" cy="0" r="9" fill="none" stroke-width="1.1"/><circle class="shot-focus-core" cx="0" cy="0" r="4.5" fill="none" stroke-width="1.1"/></g></svg>')
    zones={r['zone']:r['label'] for r in rows}
    zone_options=''.join('<option value="'+esc(k)+'">'+esc(v)+'</option>' for k,v in zones.items())
    games={r['game_id']:r['date'] for r in rows}
    game_options=''.join('<option value="'+esc(k)+'">'+esc(v)+' · '+esc(k)+'</option>' for k,v in sorted(games.items(),key=lambda kv:(kv[1],kv[0])))
    fgm=sum(r['made'] for r in rows)
    return '''<section class="shot-explorer" id="shot-explorer"><header class="explorer-head"><span class="dimension-kicker">逐次事件 / 交互研究</span><h3>把出手选择放回具体比赛</h3><p>先选比赛与区域，再查看命中或未中位置。筛选不会改变原始赛季统计；命中率始终使用所选比赛与区域的全部出手作分母。</p></header><div class="shot-controls" hidden>
<label>比赛<select id="shot-game"><option value="all">全部有出手的比赛</option>'''+game_options+'''</select></label><label>区域<select id="shot-zone"><option value="all">全部区域</option><option value="2PT">全部两分（按官方类型）</option><option value="3PT">全部三分（按官方类型）</option>'''+zone_options+'''</select></label><label>显示位置<select id="shot-outcome"><option value="all">命中与未中</option><option value="1">只看命中</option><option value="0">只看未中</option></select></label><button id="shot-reset" type="button">重置筛选</button></div>
<div class="explorer-stats" aria-live="polite"><div><span>样本出手</span><strong id="shot-fga">'''+str(len(rows))+'''</strong></div><div><span>样本命中</span><strong id="shot-fgm">'''+str(fgm)+'''</strong></div><div><span>样本命中率</span><strong id="shot-pct">'''+f'{fgm/len(rows)*100:.1f}%'+'''</strong></div><div><span>图上事件</span><strong id="shot-visible">'''+str(len(rows))+'''</strong></div></div><p class="note" id="shot-scope" role="status">完整赛季全部出手；命中率不是球员能力评分。</p>
<div class="shot-playback" hidden><div class="shot-playback-actions"><button id="shot-play" type="button" aria-pressed="false">逐次点亮</button><button id="shot-stop" type="button" disabled>恢复总览</button><label>速度<select id="shot-speed"><option value="700">1×</option><option value="240" selected>3×</option><option value="90">8×</option></select></label><span id="shot-play-progress" role="status">等待回放</span></div><p>按比赛日期、节次和比赛时钟依次点亮当前筛选中的出手；点位动效仅表示事件顺序，播放间隔经过压缩。建议先选单场比赛。</p></div>
<div class="explorer-layout"><figure class="explorer-court"><div class="shot-view-switch" hidden><div class="shot-view-buttons" role="group" aria-label="投篮图视图"><button type="button" data-shot-view="stage" aria-pressed="true">球场舞台</button><button type="button" data-shot-view="flat" aria-pressed="false">平面图</button></div><label>视域<select id="shot-extent"><option value="focus">进攻半场聚焦</option><option value="full">完整全场</option></select></label><label><input type="checkbox" id="shot-lights" checked>汇聚光效</label></div><div class="shot-stage" hidden><header class="stage-hud"><div><span class="stage-kicker">SHOT DISTRIBUTION / 逐次出手</span><h4 class="stage-player"></h4></div><div class="stage-score"><span class="stage-count-label">筛选事件</span><strong class="stage-count"></strong></div></header><div class="stage-progress"><span class="stage-progress-fill"></span></div><div class="stage-meta"><span class="stage-event-label">点击点位或列表，查看单次出手</span><span><i class="stage-made"></i>命中 <i class="stage-missed">×</i>未中</span></div><canvas class="shot-stage-canvas" role="img" aria-label="投篮事件透视图"></canvas><p class="stage-coverage" role="status"></p><p class="stage-caption">光弧仅作位置到篮筐的视觉连线，非真实飞行轨迹；半场聚焦只改变视域，完整全场可切换；视窗外事件仍保留于列表与统计。</p></div><div class="shot-flat"><div class="shot-legend"><span><i class="legend-made"></i>命中</span><span><i class="legend-missed">×</i>未中</span><span>点击点位查看详情</span></div>'''+svg+'''</div><figcaption>平面图保留完整全场；舞台可切换进攻半场和全场，后场与远距出手不从样本中删除。坐标单位为0.1英尺；原始标签冲突单列，不重写为正常区域。 <a class="source-ref" href="#source-P_SHOT">[P_SHOT]</a></figcaption></figure><aside class="shot-reading" hidden aria-label="筛选样本解读"><span class="dimension-kicker">样本与判断 / 联动阅读</span><h4>这组出手说明什么</h4><p id="shot-context" class="note"></p><a id="shot-return" hidden>返回正文判断 ↑</a><p id="shot-reading-summary" aria-live="polite"></p><p id="shot-reading-boundary" class="note"></p><div class="shot-region-head"><h5>区域结构</h5><button type="button" id="shot-all-zones">全部区域</button></div><p class="note">下表使用所选比赛的全部出手，点击区域聚焦。结果显示与球场视域不改变下表分母。</p><div class="shot-region-table-wrap"><table class="shot-region-table"><thead><tr><th scope="col">区域</th><th scope="col">出手</th><th scope="col">占比</th><th scope="col">命中率</th></tr></thead><tbody id="shot-region-body"></tbody></table></div><p class="note">占比分母为所选比赛全部出手；命中率分母为各区域全部出手。† 少于三十次，只作描述。 <a class="source-ref" href="#source-P_SHOT">[P_SHOT]</a></p><div class="shot-related" id="shot-related"></div></aside><div class="explorer-events" hidden><div class="shot-event-summary"><h4>定位到单次出手</h4><p class="note">点击图中事件或下方列表，查看比赛、节次与剩余时钟。邻近与重叠点可展开候选事件，也可用列表定位；时钟不是录像播放时间。</p><div class="shot-candidates" hidden><strong id="shot-candidate-title"></strong><p class="note">点位邻近不代表同一战术；选择具体比赛与事件查看。</p><div id="shot-candidate-list"></div><div class="shot-pagination"><button type="button" id="shot-candidate-prev">上一组</button><span id="shot-candidate-page"></span><button type="button" id="shot-candidate-next">下一组</button></div><button type="button" id="shot-candidate-close">收起候选</button></div><div id="shot-detail" class="shot-detail">请选择一个事件。</div></div><div class="shot-event-browser"><div id="shot-event-list"></div><div class="shot-pagination"><button id="shot-prev" type="button">上一页</button><span id="shot-page"></span><button id="shot-next" type="button">下一页</button></div></div></div></div><noscript><p class="note">脚本关闭：展示完整赛季静态位置；筛选与逐次定位需要启用脚本。完整统计及来源仍可阅读。</p></noscript></section>'''
