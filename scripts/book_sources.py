"""Readable source index; keep full original requests behind disclosure controls."""
import html,json
from urllib.parse import urlsplit

CATALOG={
 'P_BASE':('核心球员统计','基础数据','场次、分钟及得分、出手、助攻等总量；效率复算的基础。'),
 'P_ADV':('核心球员统计','进阶与使用率','官方使用率、助攻率和球队在场背景；不是个人能力评分。'),
 'P_100':('核心球员统计','每百回合数据','统一回合尺度后换算为每75回合，保留原始舍入。'),
 'P_SCORE':('核心球员统计','受助攻命中结构','分母是投篮命中数，不是全部出手或接球投篮。'),
 'P_SHOT':('投篮位置','完整投篮事件','真实坐标与官方区域；出手、命中和三分覆盖已与基础表核对。'),
 'TR_CATCH':('追踪与出手方式','接球投篮','场均出手及投篮结果，使用追踪表自身覆盖场次。'),
 'TR_PULL':('追踪与出手方式','持球急停','场均出手及投篮结果；不与不同难度样本直接比较能力。'),
 'TR_PASS':('追踪与出手方式','传球与潜在助攻','机会数量不等于机会质量或阅读防守能力。'),
 'TR_DRIVE':('追踪与出手方式','突破参与','描述进攻方式；次数不证明每次都突破防守。'),
 'T_BASE':('球队与在场背景','球队基础与联盟基准','完整联盟球队总量用于加权计算联盟真实命中率。'),
 'T_ADV':('球队与在场背景','球队进阶背景','球队进攻、防守失分与节奏；不替代球员不在场样本。'),
 'P_ONOFF':('球队与在场背景','同球队在场 / 不在场','同赛季On与Off比较，核验分钟覆盖；描述性而非因果贡献。'),
}
GROUPS=['核心球员统计','投篮位置','追踪与出手方式','球队与在场背景','高阶影响力与方法','球评文章','赛场影像','其他补充']
MODES={'Totals':'赛季总量','PerGame':'场均口径','Per100Possessions':'每百回合','Events':'逐次事件'}
def esc(value):return html.escape(str(value),quote=True)
def web(value):
    if not isinstance(value,str) or any(ord(c)<32 for c in value):return None
    try:p=urlsplit(value)
    except ValueError:return None
    return value if p.scheme in {'http','https'} and p.netloc and not p.username and not p.password else None
def link(url,label):
    clean=web(url)
    return '<a href="'+esc(clean)+'" target="_blank" rel="noopener noreferrer">'+esc(label)+' ↗</a>' if clean else '<span>'+esc(label)+'</span>'


def source_index(analysis):
    grouped={g:[] for g in GROUPS}
    for sid,s in analysis['sources'].items():
        image=s.get('source_type')=='illustrative_media'
        article=s.get('source_type')=='commentary_article'
        method=s.get('source_type')=='method_reference'
        group,title,purpose=CATALOG.get(sid,('赛场影像' if image else '其他补充',s.get('display_title',s.get('title','补充资料')),
                    '历史赛场影像，用于人物展示；不作为本赛季战术证据。' if image else '补充资料，需结合原始出处解释。'))
        if article:group,purpose='球评文章',s.get('usage','署名球评观点，保留原文范围；不替代本研究统计或录像观察。')
        if method:purpose=s.get('usage','指标方法与访问范围核验；不代表已取得球员指标值。')
        impact=s.get('source_type')=='impact_data'
        if impact or (method and (sid.startswith('EXT_METHOD_') or 'EPM' in sid)):
            group='高阶影响力与方法'
            purpose=s.get('usage',purpose)
        ok=s.get('status','ok')=='ok'
        stamp=s.get('retrieved_at','未记录')
        scope=('拍摄 '+s.get('media_date','日期未核实')) if image else s.get('season',analysis['sample']['season'])+' · '+ ('常规赛' if s.get('season_type')=='Regular Season' else s.get('season_type',''))+' · '+MODES.get(s.get('per_mode'),s.get('per_mode',''))
        if article:scope=s.get('author','')+' · 发表 '+s.get('published_at','')[:10]
        if method:scope='模型定义与访问核验 · 本条不提供指标值'
        if impact and s.get('cutoff'):scope=s['cutoff']+' · 历史预测快照'
        search=' '.join([sid,title,purpose,group,s.get('provider',''),'照片 图片 gif 影像' if image else '数据 统计'])
        if article:search+=' 球评 文章 '+s.get('author','')
        status='影像素材' if image else ('官方数据' if s.get('endpoint') else '已登记')
        if impact:status='提供者模型 · 转引' if 'relay' in s.get('provider','') else '提供者模型 · 原站'
        if impact and s.get('adapter')=='dunksandthrees-actual-offline-v1':status='提供者模型 · 用户离线导出'
        if impact and s.get('source_kind')=='kaggle_deocheng_v1':status='提供者模型 · Kaggle转引'
        if impact and s.get('source_kind')=='deocheng-historical-epm-v1':
            status='历史快照 · 口径待核验'
            scope=s.get('cutoff','日期缺失')+' · 原始记录日期 · 比赛范围待核验'
        if impact and s.get('source_kind')=='deocheng-historical-epm-distribution-v1':
            status='归档分布 · 口径待核验'
            scope=s['date_min']+'—'+s['date_max']+' · 不同记录日期 · Kaggle转引'
        if article:status='署名文章'
        if method:status='口径与访问核验'
        if not ok:status='资料缺失'
        body='<details class="source source-card" id="source-'+esc(sid)+'" data-source-search="'+esc(search.lower())+'"><summary><span class="source-id">'+esc(sid)+'</span><span class="source-name">'+esc(title)+'</span><span class="source-state">'+status+'</span><span class="source-scope">'+esc(scope)+'</span></summary><div class="source-detail"><p class="source-purpose">'+esc(purpose)+'</p>'
        body+='<dl class="source-meta"><dt>提供者</dt><dd>'+esc(s.get('provider','未记录'))+'</dd><dt>查阅时间</dt><dd>'+esc(stamp.replace('T',' '))+'</dd>'
        if s.get('row_count') is not None:body+='<dt>原始行数</dt><dd>'+esc(s['row_count'])+'（来源表覆盖，非球员出场数）</dd>'
        if s.get('acquisition_time_basis'):body+='<dt>时间依据</dt><dd>'+esc(s['acquisition_time_basis'])+'</dd>'
        if image:
            body+='<dt>摄影 / 授权</dt><dd>'+esc(s.get('credit',''))+' · '+link(s.get('license_url'),s.get('license',''))+'</dd><dt>编辑处理</dt><dd>'+esc(s.get('changes','未改动'))+'</dd>'
        if article:
            body+='<dt>原文标题</dt><dd>'+esc(s.get('title',''))+'</dd><dt>作者 / 发表</dt><dd>'+esc(s.get('author',''))+' · '+esc(s.get('published_at',''))+'</dd><dt>样本边界</dt><dd>'+esc(s.get('sample_scope',''))+'</dd><dt>核验范围</dt><dd>直接查阅文章正文；未据此声称独立观看嵌入影片。</dd>'
        if not ok:body+='<dt>缺失原因</dt><dd>'+esc(s.get('reason','对应资料尚未取得'))+'</dd>'
        elif method and s.get('reason'):body+='<dt>使用限制</dt><dd>'+esc(s['reason'])+'</dd>'
        if s.get('stale'):body+='<dt>缓存状态</dt><dd>已过期；保留原抓取时间</dd>'
        if s.get('direct_page_verified') is False:body+='<dt>核验范围</dt><dd>索引补充，原页未直接核验</dd>'
        body+='</dl><div class="source-actions">'+link(s.get('url'),'查看图片原页' if image else '查看原始来源')+'</div>'
        if s.get('media_items'):
            body+='<ul class="media-source-list">'+''.join('<li>'+link(m.get('url'),m.get('title','素材原页'))+'</li>' for m in s['media_items'])+'</ul>'
        if s.get('parameters') or s.get('sha256_rows'):
            body+='<details class="source-technical"><summary>完整请求与数据摘要</summary><div class="detail-body">'
            if s.get('endpoint'):body+='<p>接口：<code>'+esc(s['endpoint'])+'</code></p>'
            if s.get('sha256_rows'):body+='<p>SHA256：<code>'+esc(s['sha256_rows'])+'</code></p>'
            if s.get('parameters'):body+='<pre>'+esc(json.dumps(s['parameters'],ensure_ascii=False,indent=2))+'</pre>'
            body+='</div></details>'
        body+='</div></details>'
        grouped[group].append(body)
    result='<div class="source-directory"><label class="source-search-label" for="source-search">查找来源</label><input id="source-search" type="search" placeholder="输入基础、投篮、在场、BPM、DARKO、图片或来源 ID" autocomplete="off"><p class="note" id="source-count" role="status">按研究问题分组；点击来源卡查看口径、查阅时间及原始链接。</p>'
    for group in GROUPS:
        if grouped[group]:result+='<section class="source-group"><h4>'+group+'</h4>'+''.join(grouped[group])+'</section>'
    return result+'</div>'
