#!/usr/bin/env python3
"""Render a team-colored player verdict poster with six auditable chart modules."""
from __future__ import annotations
import argparse
import base64
import hashlib
import html
import json
import sys
from pathlib import Path
from common import SKILL_ROOT, DataError, now_iso, write_json
from book_contract import dictionary, load_context
from poster_contract import POSTER_VERSION, make_template, load_poster
from poster_charts import Charts, T
from render_research_book import safe_url, APP_VERSION
from team_themes import select_theme, css_vars

L = {'synthetic': '合成测试数据 / 非真实 NBA 球员评价',
 'synthetic_note': '球员、球队与统计均为虚构测试样本；队色仅展示排版，不表示该球员效力于对应真实球队。',
 'test_rts': '与合成样本基准相比',
 'rts': '与联盟整体水平相比',
 'pp': '百分点 / rTS',
 'not_score': '得分效率差，不是实力分',
 'sample': '样本',
 'team': '球队环境',
 'gp': '场',
 'regular': '常规赛',
 'playoffs': '季后赛',
 'verdict': '一句话看懂',
 'offense': '进攻分工',
 'defense': '防守判断',
 'hypothesis': '建议尝试的分工',
 'boundary': '按现有资料判断，不是防守评分',
 'evidence': '数据证据',
 'read_chart': '图表解读',
 'strength': '最值得发挥的能力',
 'fit': '需要怎样的队友',
 'risk': '哪些还不能下结论',
 'application': '怎么用好这名球员',
 'tactics': '战术分工与配合',
 'condition': '需要哪些队友配合',
 'tradeoff': '可能遇到什么问题',
 'validation': '接下来重点看什么',
 'gaps_title': '这份报告还没有回答什么',
 'source': '来源',
 'notes': '查看结论依据与数据来源（点击展开）',
 'not_verified': '数字和引用已核对，不等于战术建议已在比赛中验证。',
 'theme_note': '球队配色只用于排版，不是官方标准色，也不证明球员整个赛季都在该队效力。',
 'help': '点击图表下方的来源或结论编号可回溯证据。图片导出请使用 export_poster.py。',
 'limited': '相关资料不完整，暂时无法判断这一项表现。'}

def esc(value): return html.escape(str(value),quote=True)


def metric_html(m):
    if not m or m['status']!='ok':return 'N/A'
    return f'<span data-metric-id="{esc(m["metric_id"])}" data-value="{m["value"]!r}">{esc(m["display"])}</span>'


def portrait_data(run_dir,config):
    if config is None:return None
    root=run_dir.resolve();path=(root/config['path']).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise DataError('Portrait must exist inside the run directory')
    raw=path.read_bytes()
    if len(raw)>5*1024*1024:raise DataError('Portrait exceeds 5 MB; resize it first')
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):mime='image/png'
    elif raw.startswith(b'\xff\xd8\xff'):mime='image/jpeg'
    elif raw.startswith(b'RIFF') and raw[8:12]==b'WEBP':mime='image/webp'
    else:raise DataError('Portrait must be PNG/JPEG/WebP; SVG and arbitrary data URLs are not accepted')
    return 'data:'+mime+';base64,'+base64.b64encode(raw).decode('ascii')


class Poster:
    def __init__(self,analysis,claims,book,content,theme,portrait=None):
        self.a,self.book,self.c,self.t=analysis,book,content,theme
        self.claims={c['id']:c for c in claims['claims']}
        self.chart=Charts(analysis,theme);self.charts=self.chart.build();self.metrics=self.chart.m
        self.synthetic=analysis['data_kind']=='synthetic';self.portrait=portrait

    def refs(self,claim_ids=(),source_ids=()):
        return '<div class="refs">'+''.join(f'<a href="#claim-{esc(c)}">{esc(c)}</a>' for c in claim_ids)+''.join(f'<a href="#source-{esc(s)}">[{esc(s)}]</a>' for s in source_ids)+'</div>'

    def hero(self):
        a,c=self.a,self.c
        rts=self.metrics.get('RTS_PP');synthetic=' <small>'+L['synthetic_note']+'</small>' if self.synthetic else ''
        banner='<div class="demo-banner">'+L['synthetic']+synthetic+'</div>' if self.synthetic else ''
        season_type=L['regular'] if a['sample']['season_type']=='Regular Season' else L['playoffs']
        rts_text=f'{rts["value"]:+.2f}' if rts and rts['status']=='ok' else 'N/A'
        if self.portrait:
            aside=f'<img class="portrait" src="{self.portrait}" alt="{esc(a["player"]["name"])}"><div class="portrait-credit">{esc(c["portrait"]["credit"])}</div>'
        else:
            aside='<div class="hero-emblem"><div class="eyebrow">RELATIVE TS</div><div class="hero-number">'+rts_text+'</div><div class="unit">'+L['pp']+'</div><div class="eyebrow">'+(L['test_rts'] if self.synthetic else L['rts'])+'</div></div><div class="portrait-credit">'+L['not_score']+'</div>'
        sample=esc(a['sample']['season'])+' / '+season_type+' / '+L['sample']+' '+metric_html(self.metrics.get('GP'))+' '+L['gp']
        return ('<div class="masthead"><span>PLAYER LAB / EVIDENCE FIRST</span><b>'+esc(self.t['key'])+' PALETTE / v'+APP_VERSION+'</b></div>'+banner+
            '<header class="hero" id="cover"><div class="hero-main"><div class="eyebrow">SCOUTING VERDICT / '+esc(a['sample']['season'])+'</div><div class="player-name">'+esc(a['player']['name'])+'</div><h1>'+esc(c['headline'])+'</h1><p class="deck">'+esc(c['deck'])+'</p><div class="sample-row">'+sample+'<br>'+L['team']+' / '+esc(a['target_team'].get('name') or 'N/A')+'</div></div><div class="hero-aside">'+aside+'</div></header>')

    def kpis(self):
        from core_metrics import select_core
        return '<div class="kpis">'+''.join('<div class="kpi"><div class="kpi-label">'+esc(c['label'])+'</div><strong>'+metric_html(self.metrics.get(c['metric_id']))+'</strong><p class="kpi-note">'+esc(c['note'])+'</p>'+self.refs(source_ids=self.metrics.get(c['metric_id'],{}).get('source_ids',[]))+'</div>' for c in select_core(self.a,self.book))+'</div>'

    def verdict(self):
        c=self.c
        roles=''
        for role,en in (('offense','OFFENSIVE ROLE'),('defense','DEFENSIVE EVIDENCE')):
            r=c['roles'][role]
            roles+='<div class="role"><div class="english">'+en+' / '+L[role]+'</div><strong>'+esc(r['text'])+'</strong><div class="badge">'+L['hypothesis' if role=='offense' else 'boundary']+'</div>'+self.refs(r['claim_ids'])+'</div>'
        return '<section class="verdict"><div class="section-top"><h2>'+L['verdict']+'</h2><div class="english">THE VERDICT</div></div><p class="verdict-main">'+esc(c['verdict']['text'])+'</p>'+self.refs(c['verdict']['claim_ids'])+'<div class="roles">'+roles+'</div></section>'

    def figure(self,key):
        chart=self.charts[key];note=self.c['chart_notes'][key]
        audit=''.join(metric_html(self.metrics[k]) for k in chart['metric_ids'] if k in self.metrics)
        graph=chart['svg'] or '<div class="chart-missing">'+T['missing']+'</div>'
        # In a missing-data module, suppress affirmative editor-written takeaways.
        takeaway=esc(note['takeaway']) if chart['status']=='ok' else L['limited']
        return ('<figure class="chart-card" id="chart-'+key+'"><div class="chart-kicker">'+key.upper().replace('_',' ')+'</div><h3>'+chart['title']+'</h3>'+graph+
                '<p class="takeaway">'+takeaway+'</p><figcaption class="chart-boundary">'+chart['note']+'</figcaption>'+self.refs(note['claim_ids'],chart['source_ids'])+'<div class="hidden-audit">'+audit+'</div></figure>')

    def charts_section(self):
        return '<section class="charts-section"><div class="band"><span class="index">01</span><h2>'+L['evidence']+'</h2><span class="english">READ THE GAME IN DATA</span></div><div class="chart-grid">'+''.join(self.figure(k) for k in self.charts)+'</div></section>'

    def conclusions(self):
        cards=''
        for key,letter in (('strength','A'),('fit','B'),('risk','C')):
            c=self.c[key]
            cards+='<article class="conclusion-card"><div class="letter">'+letter+'</div><h3>'+L[key]+'</h3><p>'+esc(c['text'])+'</p>'+self.refs(c['claim_ids'])+'</article>'
        return '<section class="conclusion"><div class="band"><span class="index">02</span><h2>'+L['application']+'</h2><span class="english">VALUE / FIT / RISK</span></div><div class="conclusion-grid">'+cards+'</div></section>'

    def tactics(self):
        cards=''
        for s in self.book['strategies'][:2]:
            cards+='<article class="tactic"><h3>'+esc(s['title'])+'</h3><p>'+esc(s['action'])+'</p>'
            for label,key in (('condition','conditions'),('tradeoff','tradeoffs'),('validation','validation_plan')):
                cards+='<div class="tactic-label">'+L[label]+'</div><p>'+esc(' '.join(s[key]))+'</p>'
            cards+=self.refs(s['claim_ids'])+'</article>'
        if not cards:
            cards='<div class="gaps">'+L['limited']+'</div>'
        return '<section class="tactics"><div class="band"><span class="index">03</span><h2>'+L['tactics']+'</h2><span class="english">CONDITIONAL, NOT CERTAIN</span></div><div class="tactics-grid">'+cards+'</div></section>'

    def appendix(self):
        out='<details class="evidence" id="evidence"><summary>'+L['notes']+'</summary>'
        for cid,c in self.claims.items():
            out+='<div class="evidence-claim" id="claim-'+esc(cid)+'"><b>'+esc(cid)+' / '+esc(c['kind'])+'</b><p>'+esc(c['report_quote'])+'</p><p>'+esc('; '.join(c.get('caveats',[])))+'</p>'+self.refs(source_ids=c.get('source_ids',[]))+'</div>'
        out+='<h3>METRICS / AUDIT TRAIL</h3><table><thead><tr><th>Metric</th><th>Value</th><th>Formula</th></tr></thead><tbody>'
        for m in self.metrics.values():
            out+='<tr><td>'+esc(m['label'])+'</td><td>'+metric_html(m)+'</td><td>'+esc(m['formula'])+'</td></tr>'
        out+='</tbody></table><h3>SOURCES</h3>'
        for sid,s in self.a['sources'].items():
            url=safe_url(s.get('url'));link='<a href="'+esc(url)+'" target="_blank" rel="noopener noreferrer">'+esc(url)+'</a>' if url else 'N/A'
            out+='<div class="evidence-claim" id="source-'+esc(sid)+'"><b>'+esc(sid)+'</b><br>'+esc(s.get('provider',''))+'<br>'+link+'<br>'+esc(s.get('retrieved_at','N/A'))+'</div>'
        return out+'</details>'

    def render(self):
        from player_comparisons import limitations
        gaps='<br>'.join(esc(v) for v in limitations(self.a))
        footer='<footer class="footer"><div class="english">PLAYER LAB / SOURCES OVER SCORES</div>'+L['theme_note']+'<br>'+L['not_verified']+'<br>'+('SYNTHETIC TEST DATA / NOT REAL NBA ANALYSIS' if self.synthetic else esc(self.a['sample']['season'])+' / '+esc(self.a['sample']['season_type']))+'</footer>'
        body='<main class="poster" id="player-poster">'+self.hero()+self.kpis()+self.verdict()+self.charts_section()+self.conclusions()+self.tactics()+'<section class="known-gaps"><div class="gaps"><b>'+L['gaps_title']+'</b><br>'+gaps+'</div></section>'+footer+'</main>'+self.appendix()+'<div class="screen-help">'+L['help']+'</div>'
        css=(SKILL_ROOT/'assets/player_poster.css').read_text(encoding='utf-8')
        # Only this fixed script runs; it opens the evidence drawer for internal references.
        script="document.addEventListener('click',function(e){const a=e.target.closest('a[href^=\"#\"]');if(a){document.getElementById('evidence').open=true;}});"
        sh=base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()
        csp="default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-"+sh+"'; img-src data:; base-uri 'none'; form-action 'none'"
        return '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="'+csp+'"><meta name="generator" content="NBA Player Analyst '+APP_VERSION+'"><title>'+esc(self.a['player']['name'])+' / PLAYER POSTER</title><style>'+css_vars(self.t)+css+'</style></head><body>'+body+'<script>'+script+'</script></body></html>'


def build(run_dir: Path,theme: str='auto',custom: dict|None=None,force: bool=False,min_chars: int=1200):
    outputs=['player_poster.html','poster_metrics.json','poster_manifest.json']
    if not force and any((run_dir/f).exists() for f in outputs):raise DataError('Poster outputs exist; use --force only for derived outputs')
    analysis,claims,book,content,report_check=load_poster(run_dir,min_chars)
    selected=select_theme(analysis,theme,custom);portrait=portrait_data(run_dir,content['portrait'])
    poster=Poster(analysis,claims,book,content,selected,portrait)
    output=poster.render()
    (run_dir/'player_poster.html').write_text(output,encoding='utf-8')
    chart_dir=run_dir/'poster_charts';chart_dir.mkdir(exist_ok=True)
    chart_names=[]
    for key,chart in poster.charts.items():
        dest=chart_dir/(key+'.svg')
        if chart['svg']:
            dest.write_text(chart['svg'],encoding='utf-8');chart_names.append('poster_charts/'+key+'.svg')
        elif dest.exists() and force:dest.unlink()
    metrics={'schema_version':POSTER_VERSION,'data_kind':analysis['data_kind'],'derived_metrics':poster.chart.derived,
             'charts':{k:{f:v for f,v in c.items() if f!='svg'} for k,c in poster.charts.items()}}
    write_json(run_dir/'poster_metrics.json',metrics)
    inputs=['data_bundle.json','analysis.json','sources.json','report.md','claims.json','book_content.json','poster_content.json']
    if content['portrait']:inputs.append(content['portrait']['path'])
    generated=['player_poster.html','poster_metrics.json']+chart_names
    hashes={n:hashlib.sha256((run_dir/n).read_bytes()).hexdigest() for n in inputs+generated}
    manifest={'poster_version':POSTER_VERSION,'renderer_version':APP_VERSION,'generated_at':now_iso(),'data_kind':analysis['data_kind'],
              'theme':selected,'inputs':inputs,'generated':generated,'sha256':hashes,
              'recomputed_metrics':True,'report_validation':report_check,'manual_semantic_review_required':True}
    write_json(run_dir/'poster_manifest.json',manifest)
    return manifest


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run-dir',required=True,type=Path)
    p.add_argument('--theme',default='auto');p.add_argument('--theme-config',type=Path)
    p.add_argument('--prepare',action='store_true');p.add_argument('--force',action='store_true');p.add_argument('--min-chars',type=int,default=1200)
    args=p.parse_args()
    try:
        if args.min_chars<0:raise DataError('--min-chars must be nonnegative')
        if args.prepare:
            a,*_=load_context(args.run_dir,args.min_chars);dest=args.run_dir/'poster_content.template.json'
            if dest.exists() and not args.force:raise DataError('Draft exists; use --force to replace only the template')
            write_json(dest,make_template(a));print('Draft ready; author poster_content.json before publishing');return 0
        result=build(args.run_dir,args.theme,dictionary(args.theme_config) if args.theme_config else None,args.force,args.min_chars)
        print(json.dumps({'status':'poster_rendered','theme':result['theme']['key'],'files':result['generated']},ensure_ascii=False,indent=2));return 0
    except (DataError,OSError,KeyError,TypeError,ValueError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
