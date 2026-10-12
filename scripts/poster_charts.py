"""Accessible deterministic SVG charts; no inferred scores, ranks, or shot coordinates."""
from __future__ import annotations
import html
import math
from common import DataError
from poster_contract import derived_metrics

T = {'efficiency': '得分效率与基准相比如何',
 'shot_mix': '更常投两分，还是三分',
 'scoring_mix': '得分从哪里来',
 'creation': '得分、助攻与失误',
 'assisted': '投进的球，有多少来自助攻',
 'team_context': '他在场时，球队表现怎样',
 'missing': '缺少所需数据，暂不绘图',
 'player': '球员',
 'league': '联盟整体水平',
 'test': '合成样本基准',
 'three': '三分',
 'two': '两分',
 'ft': '罚球',
 'assisted_label': '受助攻',
 'unassisted': '非受助攻',
 'all_makes': '全部投篮命中',
 'three_makes': '三分球命中',
 'ts_note': 'TS综合考虑两分、三分和罚球。rTS是球员与同赛季、同比赛类型基准的TS差，单位为百分点，不是实力分。',
 'shot_note': '占比只算投篮出手，不含罚球。三分命中率只看三分出手；这张图不表示出手位置或难度。',
 'score_note': '按总得分分成两分、三分和罚球：分别用命中数乘以对应分值。四舍五入后合计可能略有偏差；不表示单打、挡拆等打法占比。',
 'creation_note': '统一换算为每75回合，来自同样本的每100回合数据。得分、助攻、失误各看各的，不相加评分；助攻多也不一定代表组织能力强。',
 'assisted_note': '这里只看已经投进的球。没有记助攻不等于单打；记了助攻，也不代表统计了全部接球投篮。',
 'context_note': '并列展示球员在场时和目标球队整体的每百回合得分、失分。两组样本不同，不能相减当成个人贡献；这里没有在场与不在场对比。'}

def esc(value): return html.escape(str(value),quote=True)


def text(x,y,value,size=16,fill='#F3F5F8',anchor='start',weight=400):
    return f'<text x="{x:g}" y="{y:g}" font-family="Arial,Noto Sans CJK SC,Microsoft YaHei,sans-serif" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" fill="{fill}">{esc(value)}</text>'


def start(title,theme,height=285):
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 480 {height}" role="img" aria-label="{esc(title)}">',
            '<title>'+esc(title)+'</title>',f'<rect width="480" height="{height}" fill="{theme["panel"]}"/>']


def soft(primary):
    vals=[int(primary[i:i+2],16) for i in (1,3,5)]
    return '#'+''.join(f'{round(v*.5+255*.5):02X}' for v in vals)


def point_bar(parts,x,y,w,v,maxvalue,color):
    if not math.isfinite(v) or v<0 or maxvalue<=0: raise DataError('Invalid bar value')
    parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="14" rx="2" fill="#303846"/>')
    parts.append(f'<rect x="{x}" y="{y}" width="{w*v/maxvalue:.3f}" height="14" rx="2" fill="{color}"/>')


class Charts:
    def __init__(self,analysis,theme):
        self.a,self.t=analysis,theme
        self.derived=derived_metrics(analysis)
        self.m={m['metric_id']:m for m in analysis['metrics']+self.derived}
        self.entries={}

    def values(self,ids):
        rows=[self.m.get(k,{}) for k in ids]
        if any(m.get('status')!='ok' for m in rows): return None
        if any(isinstance(m['value'],bool) or not isinstance(m['value'],(int,float)) or not math.isfinite(m['value']) for m in rows):
            raise DataError('Nonfinite or invalid chart metric')
        return [m['value'] for m in rows]

    def register(self,key,ids,note,svg=None):
        values=self.values(ids)
        if svg:
            footer=('SYNTHETIC TEST DATA / NOT REAL NBA ANALYSIS' if self.a['data_kind']=='synthetic' else 'DESCRIPTIVE STATISTICS / NOT A PLAYER RANK')
            sources=' / '.join(sorted({s for k in ids for s in self.m.get(k,{}).get('source_ids',[])}))
            svg=svg.replace('</svg>',text(22,263,footer,9,self.t['muted'])+text(22,279,self.a['sample']['season']+' / '+self.a['sample']['season_type']+' / '+sources,9,self.t['muted'])+'</svg>')
        self.entries[key]={'title':T[key],'metric_ids':ids,'status':'ok' if values is not None else 'missing',
                           'source_ids':sorted({s for k in ids for s in self.m.get(k,{}).get('source_ids',[])}),
                           'note':T[note], 'svg':svg if values is not None else None}

    def build(self):
        t=self.t; accent=t['accent']; secondary=soft(t['primary']);muted=t['muted']
        # 1: Exact endpoints on a zero-based, common TS scale; no gauge-as-score.
        ids=['TS_PCT','LEAGUE_TS_PCT','RTS_PP'];v=self.values(ids);p=None
        if v is not None:
            p=start(T['efficiency'],t)
            p += [text(22,50,f'{v[2]:+.2f}',46,accent,weight=800),text(222,46,'百分点 / rTS',16,muted),
                  text(22,80,'真实命中率 TS：综合两分、三分和罚球',13,muted)]
            maxval=max(1,math.ceil(max(v[:2])*4)/4)
            for i,(label,value,color) in enumerate(((T['player'],v[0],accent),(T['test'] if self.a['data_kind']=='synthetic' else T['league'],v[1],secondary))):
                y=123+i*55
                p += [text(22,y,label,15),text(458,y,f'{value*100:.1f}%',21,color,'end',700)]
                point_bar(p,22,y+13,436,value,maxval,color)
            p += [text(22,238,'0%',12,muted),text(458,238,f'{maxval*100:g}%',12,muted,'end'),'</svg>']
        self.register('efficiency',ids,'ts_note',''.join(p) if p else None)
        # 2: Attempt shares, distinct from scoring shares.
        ids=['FG3A_RATE','V_FG2A_RATE','FG3_PCT'];v=self.values(ids);p=None
        if v is not None:
            p=start(T['shot_mix'],t)
            p += [text(22,39,'三分出手占比',15,muted),text(22,86,f'{v[0]*100:.1f}%',40,accent,weight=800)]
            x=22;w=436
            for rate,color in ((v[0],accent),(v[1],secondary)):
                p.append(f'<rect x="{x:.3f}" y="107" width="{w*rate:.3f}" height="33" fill="{color}"/>'); x+=w*rate
            p += [text(22,165,T['three']+f' {v[0]*100:.1f}%',15,accent),text(458,165,T['two']+f' {v[1]*100:.1f}%',15,secondary,'end'),
                  text(22,219,'三分命中率',17,muted),text(458,222,f'{v[2]*100:.1f}%',29,t['text'],'end',700),'</svg>']
        self.register('shot_mix',ids,'shot_note',''.join(p) if p else None)
        # 3: Scoring mix with an actual sum-to-one denominator.
        ids=['V_PTS_2P_SHARE','V_PTS_3P_SHARE','V_PTS_FT_SHARE'];v=self.values(ids);p=None
        if v is not None:
            if not math.isclose(sum(v),1,abs_tol=1e-9): raise DataError('Scoring share sum is not one')
            p=start(T['scoring_mix'],t)
            r=78;circ=2*math.pi*r;offset=0;colors=[accent,secondary,'#C2CCD7'];labels=[T['two'],T['three'],T['ft']]
            p.append(f'<circle cx="124" cy="128" r="{r}" fill="none" stroke="#303846" stroke-width="32"/>')
            for value,color in zip(v,colors):
                length=value*circ
                p.append(f'<circle cx="124" cy="128" r="{r}" fill="none" stroke="{color}" stroke-width="32" stroke-dasharray="{length:.5f} {circ-length:.5f}" stroke-dashoffset="{-offset:.5f}" transform="rotate(-90 124 128)"/>');offset+=length
            p += [text(124,126,'得分',29,t['text'],'middle',800),text(124,150,'来源',13,muted,'middle')]
            for i,(label,val,color) in enumerate(zip(labels,v,colors)):
                y=69+i*60
                p.append(f'<rect x="250" y="{y-12}" width="9" height="9" fill="{color}"/>')
                p += [text(272,y,label,16),text(458,y+24,f'{val*100:.1f}%',27,color,'end',700)]
            p.append('</svg>')
        self.register('scoring_mix',ids,'score_note',''.join(p) if p else None)
        # 4: Common numerical scale, separate event meanings, not a composite score.
        ids=['PTS_PER75','AST_PER75','TOV_PER75'];v=self.values(ids);p=None
        if v is not None:
            p=start(T['creation'],t);maximum=max(5,math.ceil(max(v)/5)*5)
            for i,(name,value,color) in enumerate(zip(('得分 / 75回合','助攻 / 75回合','失误 / 75回合'),v,(accent,secondary,'#C2CCD7'))):
                y=36+i*65
                p += [text(22,y,name,15,muted),text(458,y+2,f'{value:.2f}',23,color,'end',700)]
                point_bar(p,22,y+15,436,value,maximum,color)
            p += [text(22,239,'0',12,muted),text(458,239,f'{maximum:g}',12,muted,'end'),'</svg>']
        self.register('creation',ids,'creation_note',''.join(p) if p else None)
        # 5: Share of made shots only; never silently relabel as play type.
        ids=['PCT_AST_FGM','PCT_UAST_FGM','PCT_AST_3PM','V_PCT_UAST_3PM'];v=self.values(ids);p=None
        if v is not None:
            if any(not math.isclose(v[i]+v[i+1],1,abs_tol=.015) for i in (0,2)): raise DataError('Assisted shares do not sum to one')
            p=start(T['assisted'],t)
            for i,label in enumerate((T['all_makes'],T['three_makes'])):
                a,u=v[i*2:i*2+2];y=36+i*90
                p.append(text(22,y,label,16))
                p += [f'<rect x="22" y="{y+14}" width="{436*a:.3f}" height="25" fill="{accent}"/>',f'<rect x="{22+436*a:.3f}" y="{y+14}" width="{436*u:.3f}" height="25" fill="{secondary}"/>',
                      text(22,y+62,f'{a*100:.1f}%',17,accent),text(458,y+62,f'{u*100:.1f}%',17,secondary,'end')]
            p += [text(22,240,T['assisted_label'],14,accent),text(458,240,T['unassisted'],14,secondary,'end'),'</svg>']
        self.register('assisted',ids,'assisted_note',''.join(p) if p else None)
        # 6: Context only. Do NOT subtract team rating from on-court rating.
        ids=['ONCOURT_OFF_RATING','ONCOURT_DEF_RATING','TEAM_OFF_RATING','TEAM_DEF_RATING'];v=self.values(ids);p=None
        if v is not None:
            p=start(T['team_context'],t);maximum=max(140,math.ceil(max(v)/20)*20)
            for i,(label,a,b) in enumerate((('进攻：每百回合得分',v[0],v[2]),('防守：每百回合失分',v[1],v[3]))):
                y=34+i*99
                p += [text(22,y,label,17,muted),text(340,y,f'{a:.1f}',23,accent,'end',700),text(458,y,f'{b:.1f}',23,secondary,'end',700)]
                point_bar(p,22,y+13,436,a,maximum,accent);point_bar(p,22,y+35,436,b,maximum,secondary)
            p += [text(22,230,'\u5728\u573a\u65f6\u7403\u961f',13,accent),text(190,230,'\u76ee\u6807\u7403\u961f\u6574\u4f53',13,secondary),text(458,230,f'0-{maximum:g} / 每百回合',12,muted,'end'),'</svg>']
        self.register('team_context',ids,'context_note',''.join(p) if p else None)
        return self.entries
