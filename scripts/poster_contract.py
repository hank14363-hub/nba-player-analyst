"""Versioned editorial sidecar and derived chart metrics for the player poster."""
from __future__ import annotations
import math
import re
from pathlib import Path
from common import DataError, number
from book_contract import dictionary, load_context, validate_content

POSTER_VERSION='0.3.0'
CHART_IDS=('efficiency','shot_mix','scoring_mix','creation','assisted','team_context')


def make_template(analysis: dict) -> dict:
    return {'schema_version':POSTER_VERSION,'status':'draft','data_kind':analysis['data_kind'],
            'identity':{'player_id':analysis['player']['id'],'season':analysis['sample']['season'],
                        'season_type':analysis['sample']['season_type']},
            'headline':'','deck':'','verdict':{'text':'','claim_ids':[]},
            'roles':{'offense':{'text':'','claim_ids':[]},'defense':{'text':'','claim_ids':[]}},
            'chart_notes':{k:{'takeaway':'','claim_ids':[]} for k in CHART_IDS},
            'strength':{'text':'','claim_ids':[]},'fit':{'text':'','claim_ids':[]},
            'risk':{'text':'','claim_ids':[]},'portrait':None}


def validate_poster(content: dict, analysis: dict, claims: dict) -> list[str]:
    errors=[]
    if not isinstance(content,dict): return ['poster_content must be an object']
    expected=make_template(analysis)
    if content.get('schema_version')!=POSTER_VERSION or content.get('status')!='ready':
        errors.append('Poster must have schema_version=0.3.0 and status=ready')
    for k in ('data_kind','identity'):
        if content.get(k)!=expected[k]: errors.append('Poster '+k+' mismatch')
    known={c['id'] for c in claims['claims']}
    def text(v,label,limit):
        if not isinstance(v,str) or not v.strip() or len(v)>limit:
            errors.append(label+': nonempty concise text required');return
        if re.search(r'\d',v) or any(m in v for m in ('{{','NOT_FINAL','[WRITE')):
            errors.append(label+': do not put numbers or placeholders in editorial prose')
    def block(v,label,limit):
        if not isinstance(v,dict): errors.append(label+': object required');return
        text(v.get('text',v.get('takeaway')),label,limit)
        refs=v.get('claim_ids')
        if not isinstance(refs,list) or not refs or any(not isinstance(x,str) or x not in known for x in refs):
            errors.append(label+': known claim_ids required')
        elif len(refs)!=len(set(refs)): errors.append(label+': duplicate claim_ids')
    text(content.get('headline'),'headline',32);text(content.get('deck'),'deck',110)
    for k in ('verdict','strength','fit','risk'): block(content.get(k),k,120)
    roles=content.get('roles')
    if not isinstance(roles,dict) or set(roles)!={'offense','defense'}: errors.append('Exactly offense/defense role objects required')
    else:
        for k in roles: block(roles[k],'role '+k,28)
    notes=content.get('chart_notes')
    if not isinstance(notes,dict) or set(notes)!=set(CHART_IDS): errors.append('Exactly six chart_notes required')
    else:
        for k,v in notes.items(): block(v,'chart '+k,100)
    p=content.get('portrait')
    if p is not None:
        if not isinstance(p,dict): errors.append('Portrait must be null or an object')
        elif set(p)!={'path','credit','rights_confirmed'} or p.get('rights_confirmed') is not True:
            errors.append('Portrait requires relative path, credit and rights_confirmed=true')
        else:
            if not isinstance(p['credit'],str) or not p['credit'].strip(): errors.append('Portrait credit required')
            name=p['path']
            if not isinstance(name,str) or not name or name.startswith('/') or Path(name).is_absolute() or '..' in Path(name).parts or ':' in name or '\\' in name:
                errors.append('Portrait path must be local relative POSIX path inside the run directory')
    return errors


def load_poster(run_dir: Path, min_chars: int=1200):
    analysis,claims,report,report_check=load_context(run_dir,min_chars)
    book=dictionary(run_dir/'book_content.json')
    content=dictionary(run_dir/'poster_content.json')
    errors=validate_content(book,analysis,claims)+validate_poster(content,analysis,claims)
    if errors: raise DataError('; '.join(errors))
    return analysis,claims,book,content,report_check


def derived_metrics(analysis: dict) -> list[dict]:
    """Only additive presentation metrics; do not mutate the v0.1 evidence schema."""
    metrics={m['metric_id']:m for m in analysis['metrics']}
    out=[]
    def add(mid,label,value,formula,source_ids):
        if value is not None and (not math.isfinite(value) or value<0 or value>1):
            raise DataError('Invalid derived fraction '+mid)
        out.append({'metric_id':mid,'label':label,'value':value,'display':f'{value*100:.1f}%' if value is not None else 'N/A',
                    'unit':'fraction','status':'ok' if value is not None else 'missing','formula':formula,
                    'source_ids':source_ids,'reason':'' if value is not None else 'Required matching-sample input absent'})
    m=metrics.get('FG3A_RATE',{})
    value=1-m['value'] if m.get('status')=='ok' else None
    add('V_FG2A_RATE','\u4e24\u5206\u51fa\u624b\u5360\u6bd4',value,'1-FG3A_RATE',m.get('source_ids',[]))
    r=analysis.get('selected_rows',{}).get('player_base',{})
    values=[number(r.get(k), k, optional=True) for k in ('PTS','FGM','FG3M','FTM')]
    valid=all(isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v) and v>=0 for v in values)
    if valid:
        pts,fgm,fg3m,ftm=values
        if fg3m>fgm or not math.isclose(2*(fgm-fg3m)+3*fg3m+ftm,pts,rel_tol=1e-9,abs_tol=1e-7):
            raise DataError('Scoring composition violates the points identity')
    for mid,label,numerator,formula in (
        ('V_PTS_2P_SHARE','\u4e24\u5206\u5f97\u5206',2*(values[1]-values[2]) if valid else None,'2*(FGM-FG3M)/PTS'),
        ('V_PTS_3P_SHARE','\u4e09\u5206\u5f97\u5206',3*values[2] if valid else None,'3*FG3M/PTS'),
        ('V_PTS_FT_SHARE','\u7f5a\u7403\u5f97\u5206',values[3] if valid else None,'FTM/PTS')):
        add(mid,label,numerator/values[0] if valid and values[0]>0 else None,formula,['P_BASE'])
    m=metrics.get('PCT_AST_3PM',{})
    value=1-m['value'] if m.get('status')=='ok' else None
    add('V_PCT_UAST_3PM','\u4e09\u5206\u547d\u4e2d\u7403\u975e\u53d7\u52a9\u653b\u6bd4\u4f8b',value,'1-PCT_AST_3PM',m.get('source_ids',[]))
    return out
