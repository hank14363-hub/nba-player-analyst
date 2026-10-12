#!/usr/bin/env python3
"""Render an offline, single-file Chinese research book from audited NBA evidence."""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import math
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from book_contract import BOOK_VERSION, DIMENSION_NAMES, dictionary, load_context, make_template, validate_content
from common import SKILL_ROOT, DataError, now_iso, write_json
from team_themes import select_theme
from book_visuals import visuals
from book_media import load_media, render_media
from book_sources import source_index
from book_shot_explorer import explorer_rows, render_explorer

APP_VERSION = "0.8.1"

L = {'book': '球员研究册',
 'menu': '目录',
 'print': '打印 / 导出 PDF',
 'skip': '跳到正文',
 'back': '返回封面',
 'read': '研究阅读',
 'fact': '统计事实',
 'inference': '战术推断',
 'observation': '观察记录',
 'high': '较高',
 'moderate': '中等',
 'low': '较低',
 'caveat': '这条判断的限制',
 'raw': '原始指标',
 'source': '数据来源',
 'missing': '缺失 / 不作评分',
 'na': '相关资料还不够，暂时不作判断。',
 'synthetic': '合成测试数据，不是真实 NBA 球员结论',
 'synthetic_note': '球员、球队和全部数字均为虚构测试样本；基准仅为测试总体，不是真实联盟均值。',
 'limited': '部分数据缺失，以下只讨论已有资料能支持的内容。',
 'season': '赛季',
 'sample': '样本',
 'team': '适配对象',
 'regular': '常规赛',
 'playoffs': '季后赛',
 'known': '数据能确认的',
 'inferred': '值得尝试的',
 'unknown': '还要再确认的',
 'known_note': '已核对得分、效率和使用率等统计的数值与口径，缺失数据不填零。',
 'inferred_note': '关于持球、无球和队友分工的建议，来自已有表现，但还需要在具体比赛中验证。',
 'unknown_note': '没有录像支持的技术细节，以及他个人到底改善了多少攻防表现，目前不能确定。',
 'proposed': '建议方案，尚待比赛验证',
 'conditions': '需要什么配合',
 'tradeoffs': '可能遇到的问题',
 'validation': '接下来怎么看',
 'action': '具体怎么用',
 'evidence_needed': '还需要哪些资料',
 'decision_rule': '看到什么会改变判断',
 'strategy_link': '查看对应方案',
 'challenge_link': '返回问题',
 'plan_link': '查看验证计划',
 'question': '核心问题',
 'all_metrics': '完整指标表',
 'claims': '结论依据',
 'sources': '数据来源',
 'metric': '指标',
 'value': '数值',
 'basis': '来源 / 口径',
 'confidence': '对这条判断的把握（非球员评分）',
 'collected': '来源记录时间',
 'generated': '研究册生成时间',
 'integrity': '指标已重新计算，引用的数字已核对。战术判断仍需人工检查，不能把程序通过当成实战证明。',
 'ts_title': '得分效率与基准对比',
 'shot_title': '出手结构：三分与两分',
 'player_ts': '球员真实命中率',
 'league_ts': '联盟整体真实命中率',
 'test_ts': '合成样本真实命中率',
 'three': '三分出手占比',
 'two': '两分出手占比',
 'ts_note': '统一赛季与比赛类型；基准使用总得分、总出手和总罚球计算，不是球员 TS 的简单平均。',
 'shot_note': '分母是全部投篮出手；两分占比为 1 减去三分占比。不包含罚球，不是得分占比或球场区域热图。',
 'summary': '核心判断摘要',
 'summary_note': '摘自已核对的正文，不省掉重要条件，也不增加新的能力判断。',
 'mode_core': '主要数据可用',
 'mode_limited': '部分数据缺失',
 'all_teams': '整个赛季样本，可能包含转会前后的比赛',
 'hypothetical': '假设适配对象',
 'no_network': '单文件·离线阅读·无外部字体',
 'keyboard': 'Alt + ↑ / ↓ 切换章节；普通方向键保留滚动。'}
MODULES = [('01', '先说结论', '他最值得发挥什么，哪些还不能确定？先看主要判断，再查数据。'),
 ('02', '得分与出手', '既看得了多少分，也看用了多少机会，以及两分、三分如何分配。'),
 ('03', '组织与无球', '能否帮队友创造机会？球不在手里时，还能怎样参与进攻？'),
 ('04', '防守与球队表现', '先分清个人做了什么、整套阵容做了什么，再讨论防守。'),
 ('05', '还要回答的问题', '把“值得尝试”与“已经证明”分开，找到影响球员分工的关键问题。'),
 ('06', '放进球队怎么用', '写清具体任务、队友配合和可能的问题，不只说“适合这支球队”。'),
 ('07', '接下来重点看什么', '明确还需要什么数据或录像，以及哪些表现会改变当前判断。'),
 ('08', '完整分析', '围绕得分、组织、无球、防守和球队分工，展开说明。'),
 ('09', '数据与来源', '这里保留完整指标、计算口径和引用，方便逐项复核。')]


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def safe_url(value) -> str | None:
    """Only ordinary web links are active. No file, data or javascript navigation."""
    if not isinstance(value, str) or any(ord(c) < 32 for c in value):
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    if parts.scheme.lower() not in {"http", "https"} or not parts.netloc or parts.username or parts.password:
        return None
    return value


def source_links(ids) -> str:
    return " ".join(f'<a class="source-ref" href="#source-{esc(sid)}">[{esc(sid)}]</a>' for sid in ids)


def source_disclosure(ids, sources) -> str:
    notes = []
    for sid in ids:
        source = sources.get(sid, {})
        if source.get('direct_page_verified') is False:
            notes.append(sid + '：索引补充，原页未直接核验')
        if source.get('stale'):
            notes.append(sid + '：过期缓存，保留原抓取时间')
    return '<span class="source-quality">' + esc('；'.join(notes)) + '</span>' if notes else ''


def inline(text: str, sources: dict) -> str:
    value = esc(text)
    value = re.sub(r"`([^`]+)`", r"<code>\1</code>", value)
    value = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", value)
    def ref(match):
        sid = html.unescape(match.group(1))
        return source_links([sid]) if sid in sources else match.group(0)
    return re.sub(r"\[([A-Za-z][A-Za-z0-9_]*)\](?![:(])", ref, value)


def markdown_body(markdown: str, sources: dict, charts: dict | None = None) -> str:
    """Small safe Markdown subset; never permits raw HTML, scripts or auto-fetch images."""
    result, buffer = [], []
    in_code = False
    code = []
    def flush():
        if buffer:
            result.append('<p>' + inline(" ".join(buffer), sources) + '</p>')
            buffer.clear()
    for line in markdown.splitlines():
        image = re.fullmatch(r'!\[(.*)\]\(charts/([a-z_]+\.svg)\)', line.strip())
        if not in_code and image and charts is not None and image.group(2) in charts:
            flush()
            result.append('<figure class="figure article-chart">' + charts[image.group(2)] + '<figcaption>' + inline(image.group(1), sources) + '</figcaption></figure>')
            continue
        if line.startswith('```'):
            flush()
            if in_code:
                result.append('<pre><code>' + esc('\n'.join(code)) + '</code></pre>')
                code.clear()
            in_code = not in_code
            continue
        if in_code:
            code.append(line)
            continue
        if re.match(r"^\[[A-Za-z][A-Za-z0-9_]*\]:\s", line):
            flush()
            continue
        if not line.strip():
            flush()
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        if heading:
            flush()
            level = 3 if len(heading.group(1)) <= 2 else 4
            cls = ' class="article-title"' if len(heading.group(1)) == 1 else ''
            result.append(f'<h{level}{cls}>' + inline(heading.group(2), sources) + f'</h{level}>')
        elif line.startswith('>'):
            flush()
            result.append('<blockquote>' + inline(line.lstrip('> ').strip(), sources) + '</blockquote>')
        elif line.startswith(('- ', '* ')):
            flush()
            result.append('<ul><li>' + inline(line[2:], sources) + '</li></ul>')
        else:
            buffer.append(line.strip())
    flush()
    if in_code:
        result.append('<pre><code>' + esc('\n'.join(code)) + '</code></pre>')
    return '\n'.join(result)


def metric_label(metric: dict, synthetic: bool) -> str:
    if synthetic and metric['metric_id'] == 'LEAGUE_TS_PCT':
        return L['test_ts']
    if synthetic and metric['metric_id'] == 'RTS_PP':
        return 'rTS (' + L['test_ts'] + ')'
    return metric['label']


def metric_value(metric: dict | None) -> str:
    if not metric or metric['status'] != 'ok':
        return '<span class="note">N/A</span>'
    return f'<span data-metric-id="{esc(metric["metric_id"])}" data-value="{esc(repr(metric["value"]))}">{esc(metric["display"])}</span>'


def bars_svg(rows: list[tuple[str, float]], title: str) -> str:
    """Zero-baseline fraction bars, dynamically extending beyond 100% when necessary."""
    maximum = max(1.0, math.ceil(max(v for _, v in rows) * 4) / 4)
    width, x0, chart_w, height = 720, 205, 420, 65 + 75 * len(rows)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">',
             f'<title>{esc(title)}</title>']
    for i in range(5):
        x = x0 + chart_w * i / 4
        parts.append(f'<line x1="{x:g}" y1="23" x2="{x:g}" y2="{height-35}" stroke="#e1e1e1"/>')
        parts.append(f'<text x="{x:g}" y="{height-10}" font-family="Arial,sans-serif" font-size="12" text-anchor="middle" fill="#666">{maximum*i*25:g}%</text>')
    for i, (label, value) in enumerate(rows):
        y = 47 + i * 75
        fill = '#1a1a1a' if i == 0 else '#b7b7b7'
        parts.append(f'<text x="0" y="{y+5}" font-family="sans-serif" font-size="15">{esc(label)}</text>')
        parts.append(f'<rect x="{x0}" y="{y-10}" width="{chart_w*value/maximum:.3f}" height="18" fill="{fill}"/>')
        parts.append(f'<text x="707" y="{y+5}" font-family="Arial,sans-serif" font-size="17" text-anchor="end">{value*100:.1f}%</text>')
    parts.append('</svg>')
    return ''.join(parts)


class Book:
    def __init__(self, analysis: dict, claims: dict, content: dict, report: str, theme: dict | None = None, media: list | None = None, shot_rows: list | None = None):
        self.a, self.c, self.report = analysis, content, report
        self.theme = theme
        self.claims = {c['id']: c for c in claims['claims']}
        self.metrics = {m['metric_id']: m for m in analysis['metrics']}
        self.synthetic = analysis['data_kind'] == 'synthetic'
        self.media_items = media or []
        self.shot_rows = shot_rows or []
        self.integrated = content.get('presentation') == 'integrated'
        self.claim_locations = {}
        if self.integrated:
            for d in content['dimensions']:
                for n, card in enumerate(d.get('reading_cards', []), 1):
                    for cid in card['claim_ids']:
                        self.claim_locations.setdefault(cid, ('reading-'+d['dimension']+'-'+str(n),card['title']))
        self.charts: dict[str, str] = {}
        self.visual_entries = visuals(analysis, theme or select_theme(analysis, 'auto'))

    def media(self, slot: str) -> str:
        return ''.join(render_media(item, self.a['sources']) for item in self.media_items if item['slot'] == slot)

    def chart(self, key: str) -> str:
        entry = self.visual_entries[key]
        name = key + '.svg'
        if entry['status'] != 'ok':
            return '<div class="empty"><strong>' + esc(entry['title']) + '</strong><p>缺少匹配样本或可靠定义，暂不绘图；下一步补充对应来源。</p></div>'
        self.charts[name] = entry['svg']
        return '<figure class="figure"><h3>' + esc(entry['title']) + '</h3>' + entry['svg'] + '<figcaption>' + esc(entry['note']) + ' ' + source_links(entry['source_ids']) + source_disclosure(entry['source_ids'], self.a['sources']) + '</figcaption></figure>'

    def quote(self, cid: str, compact: bool = False) -> str:
        c = self.claims[cid]
        text = '<div class="claim' + (' compact-claim' if compact else '') + '"><span class="tag ' + c['kind'] + '">' + L[c['kind']] + '</span>'
        text += '<p>' + esc(c['report_quote']) + '</p><div class="refs">'
        text += source_links(c['source_ids']) + f' <a href="#claim-{esc(cid)}">{esc(cid)} / {L["caveat"]}</a></div></div>'
        return text

    def shot_link(self, card: dict, target: str) -> str:
        if not self.shot_rows or not card.get('shot_zone'):
            return ''
        code = card['shot_zone']
        label = {'MID':'查看中距离样本','3PT':'查看三分样本','2PT':'查看两分样本'}.get(code,'查看对应出手样本')
        return '<a class="shot-text-link" href="#shot-explorer" data-shot-zone="'+esc(code)+'" data-shot-return="'+esc(target)+'" data-shot-title="'+esc(card['title'])+'">'+label+' →</a>'

    def linked_article(self, article: str) -> str:
        result = markdown_body(article,self.a['sources'])
        if not self.shot_rows:
            return result
        cards = [(cid,card) for d in self.c['dimensions'] for card in d.get('reading_cards',[]) if card.get('shot_zone') for cid in card['claim_ids']]
        clean = lambda text: re.sub(r'\s+','',re.sub(r'\[[A-Za-z][A-Za-z0-9_]*\]','',text))
        used = set()
        def paragraph(match):
            plain = clean(html.unescape(re.sub(r'<[^>]+>','',match.group(1))))
            for cid,card in cards:
                quote = clean(self.claims[cid]['report_quote'])
                if cid not in used and quote and quote in plain:
                    used.add(cid)
                    target='article-shot-'+cid
                    return '<p id="'+esc(target)+'">'+match.group(1)+'</p><div class="article-shot-path">'+self.shot_link(card,target)+'</div>'
            return match.group(0)
        return re.sub(r'<p>(.*?)</p>',paragraph,result,flags=re.S)

    def dimension(self, name: str) -> str:
        d = next(d for d in self.c['dimensions'] if d['dimension'] == name)
        body = '<section class="dimension" id="dimension-' + esc(name) + '"><header class="dimension-head"><span class="dimension-kicker">' + esc(DIMENSION_NAMES[name]) + ' / 研究解读</span><h3>' + esc(d['headline']) + '</h3>'
        if d.get('deck'):
            body += '<p class="dimension-deck">' + esc(d['deck']) + '</p>'
        body += '</header>'
        if d.get('key_metric_ids') and not self.integrated:
            body += '<div class="dimension-metrics">'
            for mid in d['key_metric_ids']:
                m = self.metrics[mid]
                body += '<div class="dimension-metric"><div class="dimension-metric-label">' + esc(metric_label(m, self.synthetic)) + '</div><div class="dimension-metric-value">' + metric_value(m) + '</div><div class="dimension-metric-source">' + source_links(m['source_ids']) + '</div></div>'
            body += '</div>'
        body += '<div class="reading-grid' + (' story-grid' if self.integrated else '') + '">'
        if d.get('reading_cards'):
            for n, card in enumerate(d['reading_cards'], 1):
                body += '<article class="reading-card" id="reading-' + esc(name) + '-' + str(n) + '"><header class="reading-card-head"><span class="reading-number">' + f'{n:02d}' + '</span><h4>' + esc(card['title']) + '</h4></header>'
                if self.integrated and card.get('chart_key'):
                    body += '<div class="story-pair"><div class="story-visual">' + self.chart(card['chart_key']) + '</div><div class="story-text">'
                body += '<div class="reading-evidence">' + ''.join(self.quote(cid, compact=True) for cid in card['claim_ids']) + '</div><dl class="reading-notes">'
                for field, label in [('interpretation', '如何理解'), ('application', '如何使用'), ('boundary', '判断边界')]:
                    body += '<div class="reading-note reading-' + field + '"><dt>' + label + '</dt><dd>' + esc(card[field]) + '</dd></div>'
                body += '</dl>'
                body += self.shot_link(card,'reading-'+name+'-'+str(n))
                if self.integrated and card.get('chart_key'):
                    body += '</div></div>'
                body += '</article>'
        else:
            for cid in d['claim_ids']:
                c = self.claims[cid]
                body += '<article class="reading-card">' + self.quote(cid, compact=True)
                if c.get('caveats'):
                    body += '<div class="reading-boundary"><strong>判断边界</strong><p>' + esc('；'.join(c['caveats'])) + '</p></div>'
                body += '</article>'
            if not d['claim_ids']:
                body += '<p class="empty">' + L['na'] + '</p>'
        return body + '</div></section>'

    def cover(self) -> str:
        a = self.a
        season_type = L['regular'] if a['sample']['season_type'] == 'Regular Season' else L['playoffs']
        banner = '<div class="disclosure synthetic-banner"><strong>' + L['synthetic'] + '</strong><br>' + L['synthetic_note'] + '</div>' if self.synthetic else ''
        if a['quality']['mode'] == 'limited':
            banner += '<div class="disclosure limited">' + L['limited'] + '</div>'
        kpis = []
        from core_metrics import select_core
        for core in select_core(a,self.c):
            mid,label=core['metric_id'],core['label']
            m = self.metrics.get(mid)
            sources = source_links(m['source_ids']) if m and m['status'] == 'ok' else L['missing']
            if m and m['status'] == 'ok':
                sources += source_disclosure(m['source_ids'], a['sources'])
            kpis.append(f'<div class="kpi"><div class="kpi-label">{esc(label)}</div><div class="kpi-value">{metric_value(m)}</div><p class="core-note">{esc(core["note"])}</p><div class="kpi-foot">{sources}</div>'+self.referenced_claims(core.get('claim_ids',[]))+'</div>')
        return ('<header class="cover" id="cover"><div class="cover-meta"><span>NBA PLAYER RESEARCH / FIELD NOTES</span><span>EDITION ' + APP_VERSION + '</span></div>'
                '<div class="cover-hero"><div class="cover-body"><div class="eyebrow">' + esc(a['sample']['season']) + ' / ' + esc(a['sample']['season_type']).upper() + '</div>'
                '<div class="player-name">' + esc(a['player']['name']) + '</div><h1>' + esc(self.c['title']) + '</h1>'
                '<p class="subtitle">' + esc(self.c['subtitle']) + '</p><span class="tag">' + season_type + '</span><span class="tag">' + L['mode_' + a['quality']['mode']] + '</span>' + banner + '</div>' + self.media('cover') + '</div>'
                '<div><div class="kpis">' + ''.join(kpis) + '</div><div class="cover-bottom"><span>' + L['no_network'] + '</span><span>DATA / CONTEXT / ROLE / EVIDENCE</span></div></div></header>')

    def overview(self) -> str:
        a = self.a
        scope = L['all_teams'] if not a['sample']['player_team_id'] else 'TEAM_ID ' + str(a['sample']['player_team_id'])
        data = '<div class="overview-details">' + esc(a['sample']['season']) + ' / ' + esc(a['sample']['season_type'])
        data += ' &nbsp; | &nbsp; GP ' + metric_value(self.metrics['GP']) + ' &nbsp; | &nbsp; MIN ' + metric_value(self.metrics['MIN'])
        data += '<br>' + L['sample'] + ': ' + esc(scope) + '<br>' + L['team'] + ': ' + esc(a['target_team'].get('name') or 'N/A')
        if a['target_team']['hypothetical']:
            data += ' (' + L['hypothetical'] + ')'
        data += '</div>'
        cards = '<div class="three-col">' + ''.join('<div class="panel"><h3>' + L[k] + '</h3><p class="small">' + L[k+'_note'] + '</p></div>' for k in ('known','inferred','unknown')) + '</div>'
        if self.integrated:
            return data + cards + '<div class="overview-paths">' + ''.join(self.claim_link(cid) for cid in self.c['executive_claim_ids']) + '</div><p class="note">核心数字见封面；详细证据与解释放在对应主题，避免重复堆放统计。</p>'
        return data + cards + '<div class="overview-claims">' + ''.join(self.quote(cid) for cid in self.c['executive_claim_ids']) + '</div>'

    def claim_link(self, cid: str) -> str:
        target,title=self.claim_locations.get(cid, ('claim-'+cid,'查看结论依据'))
        return '<a class="claim-jump" href="#'+esc(target)+'">'+esc(cid)+' · '+esc(title)+' &rarr;</a>'

    def referenced_claims(self, ids: list) -> str:
        return '<div class="claim-paths">'+''.join(self.claim_link(cid) for cid in ids)+'</div>' if self.integrated else ''.join(self.quote(cid) for cid in ids)

    def scoring(self) -> str:
        if self.integrated:
            entry=self.visual_entries['shot_locations']
            explorer=render_explorer(self.shot_rows,entry['svg']) if self.shot_rows and entry['svg'] else '<p class="empty">完整事件缺失，无法提供投篮筛选；不以部分样本替代整季。</p>'
            return self.dimension('scoring') + '<div class="density-reading" id="density-reading">'+self.chart('shot_density')+'<p class="note"><a href="#shot-explorer">进入逐次出手，核对热区中的具体事件 &rarr;</a></p></div>' + explorer
        return self.media('scoring') + '<div class="chart-grid">' + self.chart('efficiency') + self.chart('shot_mix') + self.chart('scoring_mix') + '</div><div class="spatial-grid">' + self.chart('shot_locations') + self.chart('shot_zones') + self.chart('shot_density') + '</div>' + self.dimension('scoring')

    def challenges(self) -> str:
        cards = []
        for c in self.c['challenges']:
            links = [f'<a href="#strategy-{esc(s["id"])}">{L["strategy_link"]} {esc(s["id"])} &rarr;</a>' for s in self.c['strategies'] if c['id'] in s['challenge_ids']]
            links.append('<a href="#module-07">' + L['plan_link'] + ' &rarr;</a>')
            cards.append(f'<article class="challenge" id="challenge-{esc(c["id"])}"><div class="card-label">CHALLENGE / {esc(c["id"])}</div><h3>{esc(c["title"])}</h3>' + self.referenced_claims(c['claim_ids']) + '<p class="question"><strong>' + L['question'] + ': </strong>' + esc(c['question']) + '</p><div class="crosslinks">' + ''.join(links) + '</div></article>')
        return ''.join(cards) or '<p class="empty">' + L['na'] + '</p>'

    def strategies(self) -> str:
        cards = []
        for s in self.c['strategies']:
            body = f'<article class="strategy" id="strategy-{esc(s["id"])}"><div class="card-label">PROPOSED ROLE / {esc(s["id"])}</div><h3>{esc(s["title"])}</h3><span class="tag">{L["proposed"]}</span>'
            body += '<div class="strategy-action"><strong>' + L['action'] + '</strong><br>' + esc(s['action']) + '</div>'
            body += self.referenced_claims(s['claim_ids']) + '<dl>'
            for key in ('conditions','tradeoffs','validation_plan'):
                label = L['validation'] if key == 'validation_plan' else L[key]
                body += '<dt>' + label + '</dt><dd><ul>' + ''.join('<li>' + esc(v) + '</li>' for v in s[key]) + '</ul></dd>'
            body += '</dl><div class="evidence-chips">' + ''.join(f'<a href="#challenge-{esc(qid)}">&larr; {L["challenge_link"]} {esc(qid)}</a>' for qid in s['challenge_ids']) + '</div></article>'
            cards.append(body)
        return ''.join(cards) or '<p class="empty">' + L['na'] + '</p>'

    def plans(self) -> str:
        cards = []
        for n, a in enumerate(self.c['next_actions'], 1):
            body = f'<article class="action" id="action-{n}"><div class="card-label">NEXT EVIDENCE / {n:02d}</div><h3>{esc(a["question"])}</h3><div class="action-grid">'
            for key in ('evidence_needed','decision_rule'):
                body += '<div class="label">' + L[key] + '</div><div>' + esc(a[key]) + '</div>'
            body += '</div><div class="evidence-chips">' + ''.join(f'<a href="#challenge-{esc(qid)}">{esc(qid)}</a>' for qid in a['challenge_ids']) + '</div></article>'
            cards.append(body)
        return ''.join(cards)

    def appendix(self) -> str:
        from player_comparisons import limitations
        parts = ['<div class="appendix"><p class="note">' + L['integrity'] + '</p><h3>来源索引</h3>' + source_index(self.a) + '<details class="audit-section" id="audit-metrics"><summary><strong>' + L['all_metrics'] + '</strong><span>展开查看数值与计算口径</span></summary><div class="table-wrap"><table><colgroup><col style="width:43%"><col style="width:18%"><col style="width:39%"></colgroup><thead><tr><th>' + L['metric'] + '</th><th>' + L['value'] + '</th><th>' + L['basis'] + '</th></tr></thead><tbody>']
        parts.insert(0,'<aside class="evidence-boundaries"><h3>现有证据与尚待补齐的部分</h3><ul>'+''.join('<li>'+esc(v)+'</li>' for v in limitations(self.a))+'</ul></aside>')
        if self.integrated:
            parts.insert(0,'<details class="supporting-figures"><summary><strong>补充数据图</strong><span>得分来源与球队整体背景；不重复主题区主图</span></summary><div class="spatial-grid">'+self.chart('scoring_mix')+self.chart('team_context')+'</div></details>')
        for m in self.a['metrics']:
            formula = m.get('reason') if m['status'] != 'ok' else m.get('formula', '')
            parts.append('<tr><td>' + esc(metric_label(m,self.synthetic)) + '<br><code>' + esc(m['metric_id']) + '</code></td><td class="num">' + metric_value(m) + '</td><td>' + source_links(m['source_ids']) + '<br><code>' + esc(formula) + '</code></td></tr>')
        parts.append('</tbody></table></div></details>')
        parts.append('<h3>' + L['claims'] + '</h3>')
        for cid,c in self.claims.items():
            parts.append(f'<details id="claim-{esc(cid)}"><summary><strong>{esc(cid)} / {L[c["kind"]]}</strong> &mdash; {esc(c["report_quote"])}</summary><div class="detail-body"><p>' + L['confidence'] + ': ' + L[c['confidence']] + '</p><p>' + source_links(c['source_ids']) + '</p><p><code>' + esc(', '.join(c['metric_ids'])) + '</code></p><ul>' + ''.join('<li>' + esc(v) + '</li>' for v in c.get('caveats',[])) + '</ul></div></details>')
        parts.append('</div>')
        return ''.join(parts)

    def render(self) -> str:
        if self.integrated:
            self.charts={key+'.svg':entry['svg'] for key,entry in self.visual_entries.items() if entry['status']=='ok'}
            contents=[self.overview(),self.scoring(),self.comparisons()+self.dimension('creation')+self.dimension('off_ball'),self.impacts()+self.dimension('defense')+self.dimension('tactical_fit'),self.challenges(),self.strategies(),self.plans()]
            article=re.sub(r'^!\[.*\]\(charts/[a-z_]+\.svg\)\s*$', '', self.report, flags=re.M)
            contents += [self.commentary() + '<details class="full-article" id="full-article"><summary><strong>展开完整分析长文</strong><span>保留完整论证与统计引用；主题区已展示图表</span></summary><div class="article">'+self.linked_article(article)+'</div></details>',self.appendix()]
        else:
            contents = [self.overview(), self.scoring(), self.media('creation') + '<div class="chart-grid">' + self.chart('creation') + self.chart('assisted') + self.chart('tracking') + '</div>' + self.dimension('creation') + self.dimension('off_ball'), self.impacts() + self.media('defense') + '<div class="spatial-grid">' + self.chart('team_context') + self.chart('onoff') + '</div>' + self.dimension('defense') + self.dimension('tactical_fit'), self.challenges(), self.strategies(), self.plans()]
            if self.a.get('comparison_context'):
                contents[2]=self.comparisons()+contents[2]
            contents += ['<div class="article">' + markdown_body(self.report,self.a['sources'],self.charts) + '</div>', self.appendix()]
        if self.theme:
            replacements = {'#1a1a1a': self.theme['primary'], '#b7b7b7': '#A7AFBC'}
            for old,new in replacements.items():
                contents = [v.replace(old,new) for v in contents]
                self.charts = {k:v.replace(old,new) for k,v in self.charts.items()}
        navigation = '<nav id="toc" aria-label="' + L['menu'] + '"><div class="wordmark">NBA PLAYER<br>RESEARCH BOOK</div><div class="version">LOCAL CODEX / ' + APP_VERSION + '</div><a href="#cover"><span>00</span>' + L['book'] + '</a>'
        navigation += ''.join(f'<a href="#module-{number}"><span>{number}</span>{title}</a>' for number,title,_ in MODULES)
        navigation += '<div class="tools"><button id="print-button" type="button">' + L['print'] + '</button><p>' + L['keyboard'] + '</p></div></nav>'
        modules=[(number,'球评对读与长文' if number=='08' and self.integrated else title,deck) for number,title,deck in MODULES]
        if self.integrated:
            navigation=navigation.replace('完整分析','球评对读与长文')
        sections = []
        for (number,title,deck), content in zip(modules,contents):
            sections.append(f'<section class="module" id="module-{number}"><header class="module-head"><div class="module-num">{number}</div><div><h2>{title}</h2><p class="module-deck">{deck}</p></div></header>{content}</section>')
        body = '<div class="reading-progress" aria-hidden="true"><span id="reading-progress-bar"></span></div><a class="skip" href="#module-01">' + L['skip'] + '</a><button class="mobile-toggle" id="menu-toggle" aria-controls="toc" aria-expanded="false">' + L['menu'] + ' / NBA PLAYER RESEARCH</button>' + navigation + '<main id="main"><div class="inner">' + self.cover() + ''.join(sections)
        body += '<footer class="footer">NBA PLAYER ANALYST / ' + APP_VERSION + '<br>' + L['generated'] + ': ' + esc(now_iso()) + '</footer></div></main><a class="book-back" href="#cover">' + L['back'] + ' &uarr;</a>'
        root = SKILL_ROOT / 'assets'
        script = (root/'book_shot_stage.js').read_text(encoding='utf-8') + '\n' + (root/'book_shot_research.js').read_text(encoding='utf-8') + '\n' + (root/'research_book.js').read_text(encoding='utf-8')
        replacements = {'TITLE':esc(self.a['player']['name'] + ' | ' + self.c['title']), 'CSS':(root/'research_book.css').read_text(encoding='utf-8'), 'BODY':body, 'JS':script, 'SCRIPT_HASH':base64.b64encode(hashlib.sha256(script.encode()).digest()).decode()}
        if self.theme:
            theme_css = (root/'research_book_theme.css').read_text(encoding='utf-8')
            theme_vars = ':root{--book-primary:'+self.theme['primary']+';--book-on-primary:'+self.theme['on_primary']+';--book-accent:'+self.theme['accent']+';--book-on-accent:'+self.theme['on_accent']+';}'
            replacements['CSS'] += theme_vars + theme_css
        replacements['CSS'] += (root/'research_book_editorial.css').read_text(encoding='utf-8')
        replacements['CSS'] += (root/'book_comparisons.css').read_text(encoding='utf-8')
        replacements['CSS'] += (root/'book_impact.css').read_text(encoding='utf-8')
        template = (root/'research_book_template.html').read_text(encoding='utf-8')
        return re.sub(r'\{\{([A-Z_]+)\}\}',lambda m: replacements[m.group(1)],template)

    def comparisons(self) -> str:
        from comparison_visuals import fmt
        c=self.a.get('comparison_context',{})
        if c.get('status')!='ok':
            return '<aside class="note">同角色比较尚未通过核验：'+esc(c.get('reason','未启用完整样本比较'))+'</aside>'
        body='<section class="role-comparison" id="role-comparison"><header><span class="dimension-kicker">ROLE / TRADEOFF / SENSITIVITY</span><h3>与承担类似任务的人放在一起看</h3><p>从 '+str(c['raw_player_count'])+' 名球员的整季原始表开始，先选出 '+str(c['eligible_count'])+' 名 GP≥'+str(c['minimum_gp'])+'、总分钟≥'+str(c['minimum_minutes'])+' 的稳定轮换，再按角色阈值纳入 '+str(c['cohort_count'])+' 人（包含本球员）。角色为 '+esc(c['label'])+'：'+esc(c['definition'])+'。</p><p class="note">'+esc(c['boundary'])+'</p></header><div class="comparison-charts">'+self.chart('role_profile')+self.chart('usage_efficiency')+'</div>'
        body+=self.referenced_claims([cid for cid,claim in self.claims.items() if any(mid.startswith('COHORT_') for mid in claim['metric_ids'])])
        body+='<div class="table-wrap"><table class="cohort-axis-table"><thead><tr><th>维度</th><th>本球员</th><th>同角色中位数</th><th>统计百分位</th></tr></thead><tbody>'
        for a in c['axes']:
            body+='<tr><th>'+esc(a['label'])+(' ↓' if a['direction']==-1 else '')+'</th><td>'+fmt(a['target'],a['unit'])+'</td><td>'+fmt(a['median'],a['unit'])+'</td><td>P'+f'{a["percentile"]:.1f}'+'</td></tr>'
        body+='</tbody></table></div><p class="note">'+esc(c['percentile_formula'])+'。自主终结占比仅描述职责；高值不自动表示更强。</p>'
        if c['sensitivity']:
            body+='<details class="cohort-sensitivity"><summary>换一组纳入门槛，结论是否改变？</summary><div class="table-wrap"><table><thead><tr><th>样本规则</th><th>N</th>'+''.join('<th>'+esc(a['label'])+'</th>' for a in c['axes'])+'</tr></thead><tbody>'
            for s in c['sensitivity']:
                rule=('USG≥'+f'{s["usg"]*100:.0f}'+'%、AST%≥'+f'{s["ast"]*100:.0f}'+'%') if 'usg' in s else 'GP≥'+str(s['gp'])+'、MIN≥'+str(s['minutes'])
                body+='<tr><th>'+esc(s['label']+' · '+rule)+'</th><td>'+str(s['n'])+'</td>'+''.join('<td>P'+f'{s["axes"][a["metric_id"]]:.1f}'+'</td>' for a in c['axes'])+'</tr>'
            body+='</tbody></table></div><p class="note">阈值是研究规则，不是联盟官方角色分类；百分位变化由样本改变引起。</p></details>'
        body+='<details class="cohort-roster"><summary>查看完整纳入名单与原始读数（按姓名排序）</summary><div class="table-wrap"><table><thead><tr><th>球员 / 来源球队标签</th><th>GP</th><th>分钟</th><th>USG%</th><th>AST%</th><th>PTS/75</th><th>AST/75</th><th>TS%</th><th>AST:TOV</th><th>非受助攻命中</th><th>TOV/75</th><th>PIE</th></tr></thead><tbody>'
        for r in sorted(c['players'],key=lambda r:r['name'].casefold()):
            highlight=' class="target-player"' if r['player_id']==self.a['player']['id'] else ''
            body+='<tr'+highlight+'><th>'+esc(r['name'])+'<br><small>'+esc(r['team'])+' · '+str(r['team_count'])+'队</small></th><td>'+str(r['gp'])+'</td><td>'+f'{r["minutes"]:.1f}'+'</td>'
            for mid,unit in [('USG_PCT','fraction'),('AST_PCT','fraction'),('PTS_PER75','per75'),('AST_PER75','per75'),('TS_PCT','fraction'),('AST_TOV','ratio'),('PCT_UAST_FGM','fraction'),('TOV_PER75','per75'),('PIE','fraction')]:body+='<td>'+fmt(r[mid],unit)+'</td>'
            body+='</tr>'
        pie=self.metrics.get('NBA_PIE');med=self.metrics.get('COHORT_PIE_MEDIAN')
        body+='</tbody></table></div></details><aside class="impact-context"><h4>影响力证据：再多一条线索，仍需分清定义</h4><p>NBA PIE '+metric_value(pie)+'，同角色中位数 '+metric_value(med)+'。PIE 汇总技术统计事件贡献份额，受角色和场上环境影响，不能当作调整过队友、对手后的每百回合净贡献，也不能替代 EPM。</p><p>球队 On/Off 只作描述性背景。第三方模型按各自口径见后续影响力证据区；个人防守判断仍需专项证据。</p>'+source_links(['P_ADV'])+'</aside></section>'
        return body

    def impacts(self) -> str:
        ctx=self.a.get('impact_context',{})
        if ctx.get('status')!='ok':return ''
        body='<section class="impact-research" id="impact-research"><header><span class="dimension-kicker">IMPACT / MODEL / TIME</span><h3>高阶影响力：把模型与样本一起读</h3><p>模型估计补充角色与效率分析。整季回顾描述这一季的表现，日期快照预测当时之后的表现；即使都以每百回合点数表示，也不能相加或直接作为实力排名。</p><span class="impact-scope">整季回顾</span><span class="impact-scope predictive">历史日期预测</span></header><div class="impact-columns">'+(self.chart('impact_retrospective') if 'impact_retrospective' in self.visual_entries else '')+('<div>'+self.chart('impact_predictive')+'<aside class="impact-reading-note"><h4>日期快照怎样补充整季回顾</h4><p>预测使用截至历史日期的信息，回答下一场的预期表现。整季回顾回答这一季的表现估计，二者方向相近也不等于完全独立的验证。</p><p>复核时先确认日期与模型版本，再看分歧来自时间、角色变化还是方法；防守符号需要结合不确定性与回合证据解释。</p></aside></div>' if 'impact_predictive' in self.visual_entries else '')+'</div>'
        body+='<div class="impact-quantities">'
        for mid,title,note in [('IMPACT_VORP','VORP · 出勤与替补基准','将BPM与出勤结合，基准为替补水平；不是直接赢球数。'),('IMPACT_WS','Win Shares · 整季分配','提供者用技术统计与球队表现分配的胜利份额；不是实测个人创造的胜场。'),('IMPACT_WS48','WS/48 · 时间尺度','按每四十八分钟表达模型份额；不能与每百回合点数混画或合成。')]:
            m=self.metrics.get(mid)
            if m and m['status']=='ok':body+='<article class="impact-quantity"><h4>'+title+'</h4><div class="impact-number">'+metric_value(m)+'</div><p>'+note+'</p>'+source_links(m['source_ids'])+'</article>'
        body+='</div>'+self.referenced_claims([cid for cid,c in self.claims.items() if any(mid.startswith('IMPACT_') for mid in c['metric_ids'])])
        body+='<details class="impact-verification"><summary>模型定义、样本核验与不确定性</summary><div class="detail-body">'
        for d in ctx['datasets']:
            scope=d['cutoff']+' 历史预测' if d['estimate_type']=='predictive_snapshot' else d['season']+(' 常规赛回顾' if d['season_type']=='Regular Season' else ' 季后赛回顾')
            sample=d['sample'];coverage='生涯加权预测；不声称与单季分钟完全对应。'
            if sample['MIN'] is not None:coverage='提供者分钟 '+f"{sample['MIN']:.2f}"+'；与官方总分钟差 '+f"{sample['minutes_difference']:+.3f}"+' 分钟。'+('场次 '+str(int(sample['GP']))+'。' if sample['GP'] is not None else '转引未提供场次。')
            body+='<h4>'+esc(d['family'])+' · '+esc(scope)+'</h4><p>'+esc(d['model_version'])+'</p><p>'+esc(coverage)+'</p><ul>'+''.join('<li>'+esc(v)+'</li>' for v in d['caveats'])+'</ul>'+source_links([d['source_id']])
        body+='<p>BPM是技术统计与球队背景模型；LEBRON按转引站说明结合技术统计先验和运气调整的阵容回归；DARKO持续更新生涯信息，预测下一场。模型输入部分重叠，一致方向不构成完全独立的验证。均未取得置信区间，防守分量的正负不能解释为显著优劣。</p>'+source_links([sid for sid in ['EXT_METHOD_BPM_METHOD','EXT_METHOD_RAPM_CADE','EXT_METHOD_DARKO_ABOUT'] if sid in self.a['sources']])+'</div></details><aside class="impact-missing"><h4>仍未纳入的指标</h4>'
        for e in ctx['excluded']:body+='<p><strong>'+esc(e['family'])+'</strong> · '+esc(e['reason'])+'</p>'
        return body+'</aside></section>'

    def commentary(self) -> str:
        cards=self.c.get('commentary_cards',[])
        if not cards:return '<p class="note">未登记可核验球评文章；以下保留完整研究长文。</p>'
        body='<div class="commentary-intro"><h3>把外部观点变成可检验的问题</h3><p>下面是对署名文章的中文概括与本研究的回应，不是原文翻译或独立录像观察。作者使用的阶段样本与本册完整常规赛统计分开；多个作者来自同一媒体，也不构成独立共识。</p></div><div class="commentary-grid">'
        for card in cards:
            s=self.a['sources'][card['source_id']]
            body+='<article class="commentary-card"><header><span class="dimension-kicker">外部球评 / '+esc(s['published_at'][:10])+'</span><h4>'+esc(card['title'])+'</h4><p class="commentary-byline">'+esc(s['author'])+' · '+esc(s['provider'])+'</p></header><dl>'
            for field,label in [('view','作者侧重'),('response','本研究回应'),('question','下一步检验')]:
                body+='<dt>'+label+'</dt><dd>'+esc(card[field])+'</dd>'
            body+='</dl>'+source_links([card['source_id']])+self.referenced_claims(card['claim_ids'])+'</article>'
        return body+'</div><details class="historical-media"><summary><strong>历史赛场资料影像</strong><span>人物展示；不作为本赛季战术证据</span></summary>'+self.media('scoring')+self.media('creation')+'</details>'


def build_summary(analysis: dict, claims: dict, content: dict) -> str:
    by_id = {c['id']:c for c in claims['claims']}
    result = ['# ' + analysis['player']['name'] + ' | ' + L['summary'], '', analysis['sample']['season'] + ' / ' + analysis['sample']['season_type'], '']
    if analysis['data_kind'] == 'synthetic':
        result.extend(['> ' + L['synthetic'], ''])
    used, caveats = set(), set()
    for cid in content['summary_claim_ids']:
        c = by_id[cid]
        result.extend([c['report_quote'] + ' ' + ''.join('[' + sid + ']' for sid in c['source_ids']), ''])
        used.update(c['source_ids'])
        caveats.update(c.get('caveats',[]))
    result.extend(['## ' + L['caveat'], ''] + sorted(caveats) + ['', L['summary_note'], ''])
    for sid in sorted(used):
        source = analysis['sources'][sid]
        result.append(f'[{sid}]: {source.get("url", "N/A")} "{source.get("provider", "")}"')
    return '\n'.join(result) + '\n'


def build(run_dir: Path, force: bool = False, min_chars: int = 1200, theme: str = 'auto', custom: dict | None = None) -> dict:
    outputs = ['research_book.html','summary.md','book_manifest.json']
    if not force and (any((run_dir / name).exists() for name in outputs) or (run_dir/'charts').exists()):
        raise DataError('Book outputs already exist; use --force only to explicitly replace these derived presentation files')
    analysis, claims, report, report_check = load_context(run_dir,min_chars)
    content = dictionary(run_dir/'book_content.json')
    errors = validate_content(content,analysis,claims)
    if errors:
        raise DataError('Book content validation failed: ' + '; '.join(errors))
    selected_theme = select_theme(analysis,theme,custom)
    media, media_files = load_media(run_dir, analysis)
    shots=explorer_rows(dictionary(run_dir/'data_bundle.json'),analysis) if content.get('presentation')=='integrated' else []
    book = Book(analysis,claims,content,report,selected_theme,media,shots)
    result = book.render()
    (run_dir/'research_book.html').write_text(result,encoding='utf-8')
    (run_dir/'summary.md').write_text(build_summary(analysis,claims,content),encoding='utf-8')
    chart_dir = run_dir/'charts'
    chart_dir.mkdir(exist_ok=True)
    for name in (key + '.svg' for key in book.visual_entries):
        path = chart_dir/name
        if name in book.charts:
            path.write_text(book.charts[name],encoding='utf-8')
        elif path.exists() and force:
            path.unlink()
    inputs = ['data_bundle.json','analysis.json','sources.json','report.md','claims.json','book_content.json'] + media_files
    generated = ['research_book.html','summary.md'] + ['charts/'+name for name in book.charts]
    hashes = {name:hashlib.sha256((run_dir/name).read_bytes()).hexdigest() for name in inputs+generated}
    manifest = {'book_version':BOOK_VERSION,'app_version':APP_VERSION,'theme':selected_theme,'generated_at':now_iso(),'data_kind':analysis['data_kind'], 'status':'rendered_pending_book_check','recomputed_metrics':True,'report_validation':report_check,'charts':list(book.charts),'chart_evidence':{k:{f:e[f] for f in ('status','metric_ids','source_ids','note')} for k,e in book.visual_entries.items()},'sha256':hashes,'manual_review_required':True}
    write_json(run_dir/'book_manifest.json',manifest)
    return manifest


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run-dir',type=Path,required=True)
    p.add_argument('--force',action='store_true',help='Explicitly replace derived book/summary/chart outputs; never changes data/report/claims')
    p.add_argument('--prepare',action='store_true',help='Create book_content.template.json only; this is not a finished report')
    p.add_argument('--min-chars',type=int,default=1200)
    p.add_argument('--theme',default='auto',help='Editorial team palette; does not change player/team sample')
    p.add_argument('--theme-config',type=Path,help='Optional JSON with primary and accent hex colors')
    args = p.parse_args()
    try:
        if args.min_chars < 0:
            raise DataError('--min-chars must be nonnegative')
        if args.prepare:
            destination = args.run_dir/'book_content.template.json'
            if destination.exists() and not args.force:
                raise DataError('Template already exists. Do not overwrite authored content')
            write_json(destination,make_template(dictionary(args.run_dir/'analysis.json')))
            print('TEMPLATE ONLY: author book_content.json, then run without --prepare')
        else:
            manifest = build(args.run_dir,args.force,args.min_chars,args.theme,dictionary(args.theme_config) if args.theme_config else None)
            print(json.dumps({'status':manifest['status'],'book':str((args.run_dir/'research_book.html').resolve()),'charts':manifest['charts'],'next':'Run validate_book.py, then inspect desktop/mobile/print layout. Validation is not a semantic truth guarantee.'},ensure_ascii=False,indent=2))
        return 0
    except (DataError,OSError,UnicodeError,KeyError,TypeError,ValueError) as exc:
        print('ERROR: ' + str(exc),file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
