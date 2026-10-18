"""Recognize a statistic maximum only against a verified complete league table."""
from collections import defaultdict
import re

from common import DataError, digest, number
from impact_metrics import SPECS
from player_comparisons import full_table


def unique_bref(rows):
    by=defaultdict(list)
    for row in rows:
        if not row.get('provider_player_key'):raise DataError('League leader needs unique BREF identity')
        by[row['provider_player_key']].append(row)
    result=[]
    for rows in by.values():
        if len(rows)==1:result.append(rows[0]);continue
        aggregates=[r for r in rows if r.get('team_name_abbr')=='TOT' or re.fullmatch(r'[2-9]TM',r.get('team_name_abbr',''))]
        if len(aggregates)!=1:raise DataError('League leader: duplicate stints without unique aggregate')
        result.append(aggregates[0])
    return result


def maximum(mid,metric,rows,key,sid,family,scope):
    """Undefined values prevent an all-league claim; no percentile shortcut."""
    values=[number(r.get(key),key,optional=True) for r in rows]
    if len(values)<8 or any(v is None for v in values):return None
    target=metric['value']
    if sum(v>target for v in values) or target not in values:return None
    ties=sum(v==target for v in values)
    return dict(metric_id=mid,label=metric['label'],value=target,rank=1,ties=ties,n=len(values),
                family=family,source_ids=[sid],direction='higher_numeric',scope=scope,
                text='全联盟第1' if ties==1 else '全联盟并列第1',
                boundary='指该来源、该赛季与比赛类型的单项原始数值最大；按原表精度同值并列，不是个人能力排名。')


def context(bundle,pid,team_id,metrics):
    out=dict(status='ok',leaders=[],excluded=[],method='1 + 严格高于目标的人数；完整联盟原表，转会合计去重；按原表精度同值并列。')
    if team_id:
        out.update(status='missing',reason='球队效力段不声明整季联盟第一。');return out
    known={m['metric_id']:m for m in metrics if m['status']=='ok'}
    try:
        base=full_table(bundle,'player_base','P_BASE');adv=full_table(bundle,'player_advanced','P_ADV')
        if set(base)!=set(adv):raise DataError('League leader NBA ID coverage differs')
        if len(base)<8:raise DataError('Full NBA population too small')
        if pid not in adv:raise DataError('Target absent from full NBA population')
        for k,a in adv.items():
            b=base[k]
            if a.get('GP')!=b.get('GP') or a.get('TEAM_COUNT')!=b.get('TEAM_COUNT'):
                raise DataError('League leader NBA sample mismatch')
            minutes=number(a.get('MIN'));total=number(b.get('MIN'));gp=number(b.get('GP'))
            if abs(minutes-total)>2 and abs(minutes*gp-total)>gp*.051+1:
                raise DataError('League leader NBA minutes mismatch')
        from advanced_percentiles import NBA
        for mid,key,_,_ in NBA:
            if mid not in known or mid in ('ONCOURT_DEF_RATING','ADV_NBA_TOV_PCT'):continue
            if number(adv[pid].get(key),optional=True)!=known[mid]['value']:continue
            leader=maximum(mid,known[mid],list(adv.values()),key,'P_ADV','NBA',bundle['season']+' / '+bundle['season_type']+' / 完整联盟原表；不设出勤门槛')
            if leader:out['leaders'].append(leader)
    except DataError as exc:out['excluded'].append(dict(family='NBA',reason=str(exc)))
    for dataset in bundle.get('impact_data',{}).get('datasets',[]):
        if dataset['family']!='BREF':continue
        try:
            s=bundle['sources'][dataset['source_id']];rows=dataset['raw_rows']
            if bundle['season_type']!='Regular Season':raise DataError('BREF leader currently verifies regular-season league pages only')
            table='advanced'
            expected='https://www.basketball-reference.com/leagues/NBA_'+str(int(bundle['season'][:4])+1)+'_advanced.html'
            if (s.get('url')!=expected or s.get('table_id')!=table or s.get('row_count')!=len(rows)
                    or s.get('sha256_rows')!=digest(rows) or s.get('status')!='ok'
                    or s.get('season')!=bundle['season'] or s.get('season_type')!=bundle['season_type']):
                raise DataError('League leader needs retained full NBA BREF competition table')
            rows=unique_bref(rows)
            if len(rows)<8:raise DataError('Full BREF population too small')
            target=[r for r in rows if all(str(r.get(k))==str(v) for k,v in dataset['selector'].items())]
            if len(target)!=1:raise DataError('BREF league leader selector ambiguous')
            for mid,key,_ in SPECS['BREF'][1]:
                mid='IMPACT_'+mid
                if mid not in known or number(target[0].get(key),optional=True)!=known[mid]['value']:continue
                leader=maximum(mid,known[mid],rows,key,dataset['source_id'],'BREF',bundle['season']+' / '+bundle['season_type']+' / BR完整联盟原表；不设出勤门槛')
                if leader:out['leaders'].append(leader)
        except DataError as exc:out['excluded'].append(dict(family='BREF',reason=str(exc)))
    return out


def register(ctx,add,metrics):
    for leader in ctx['leaders']:
        for key,word in [('rank','单项数值名次'),('ties','同值并列人数'),('n','完整联盟人数')]:
            mid='STAT_LEADER_'+leader['metric_id']+'_'+key.upper()
            add(mid,leader[key],'count',leader['source_ids'],ctx['method'])
            metrics[-1]['label']=leader['metric_id']+' · '+word
