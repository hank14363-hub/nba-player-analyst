"""Auditable functional cohorts. Descriptive percentiles, never an ability score."""
from statistics import median
from common import DataError, digest, number

TABLES = [('player_base','P_BASE'),('player_advanced','P_ADV'),
          ('player_per100','P_100'),('player_scoring','P_SCORE')]
AXES = [('PTS_PER75','得分产量','per75',1),('AST_PER75','助攻产量','per75',1),
        ('TS_PCT','真实命中率','fraction',1),('AST_TOV','助攻失误比','ratio',1),
        ('PCT_UAST_FGM','非受助攻命中占比','fraction',1),('TOV_PER75','控制失误','per75',-1)]
SOURCE_IDS = ['P_BASE','P_ADV','P_100','P_SCORE']


def full_table(bundle, table, sid):
    rows=bundle['tables'].get(table,[]); s=bundle['sources'].get(sid,{})
    if not rows or s.get('status')!='ok' or s.get('endpoint')!='leaguedashplayerstats':
        raise DataError('Need registered NBA full-league table: '+table)
    p=s.get('parameters',{})
    expected_mode='Per100Possessions' if table=='player_per100' else 'Totals'
    expected_measure={'player_advanced':'Advanced','player_scoring':'Scoring'}.get(table,'Base')
    if p.get('PerMode')!=expected_mode or p.get('MeasureType')!=expected_measure:
        raise DataError('Comparison mode/measure differs: '+table)
    if p.get('Season')!=bundle['season'] or p.get('SeasonType')!=bundle['season_type']:
        raise DataError('Comparison season/type differs: '+table)
    allowed={'LeagueID','MeasureType','PerMode','PaceAdjust','PlusMinus','Rank','Season','SeasonType'}
    for key,value in p.items():
        if key not in allowed and value not in ('',None,0,'0'):
            raise DataError('Filtered comparison source: '+table+'/'+key)
    if s.get('row_count')!=len(rows) or s.get('sha256_rows')!=digest(rows):
        raise DataError('Comparison raw row hash/count differs: '+table)
    ids=[r.get('PLAYER_ID') for r in rows]
    if any(not isinstance(i,int) or i<=0 for i in ids) or len(ids)!=len(set(ids)):
        raise DataError('Duplicate player/stint IDs: '+table+'; aggregate explicitly before comparing')
    return {r['PLAYER_ID']:r for r in rows}


def percentile(value, values, direction=1):
    """Midrank empirical percentile, including target; ties get equal credit."""
    return 100*(sum(direction*x<direction*value for x in values)+.5*sum(x==value for x in values))/len(values)


def choose_profile(row):
    if row['USG_PCT']>=.25 and row['AST_PCT']>=.30:return 'creator'
    if row['OREB_PCT']>=.08 and row['DREB_PCT']>=.18:return 'rebounder'
    if row['FG3A_RATE']>=.45 and row['FG3A']>=200:return 'shooter'
    if row['USG_PCT']>=.25:return 'scorer'
    return 'rotation'


PROFILES = {
    'creator':('高负荷组织核心',lambda r:r['USG_PCT']>=.25 and r['AST_PCT']>=.30,
               'USG≥25% 且 AST%≥30%；不以名气或实际百分位挑人'),
    'rebounder':('篮板职责明显的轮换',lambda r:r['OREB_PCT']>=.08 and r['DREB_PCT']>=.18,
                'OREB%≥8% 且 DREB%≥18%；功能代理，不代表已核验位置'),
    'shooter':('三分职责明显的轮换',lambda r:r['FG3A_RATE']>=.45 and r['FG3A']>=200,
              '三分出手占比≥45% 且三分出手≥200'),
    'scorer':('高使用率终结者',lambda r:r['USG_PCT']>=.25,'USG≥25%'),
    'rotation':('稳定轮换',lambda r:True,'不附加角色阈值，仅描述轮换样本')}


def comparison_context(bundle, player_id, team_id):
    if bundle.get('sumitro_import'):
        from import_sumitro import comparison_context as sumitro_context
        return sumitro_context(bundle, player_id, team_id)
    if team_id:raise DataError('Full-season comparison cannot be mixed with a filtered team stint')
    maps=[full_table(bundle,t,s) for t,s in TABLES]
    ids=set(maps[0])
    if any(set(m)!=ids for m in maps):raise DataError('Full-table player ID coverage differs')
    players=[];excluded=[]
    for pid in sorted(ids):
        b,a,p,s=[m[pid] for m in maps]
        if b.get('GP',0)<40 or b.get('MIN',0)<1000:continue
        try:
            if any(r.get('GP')!=b['GP'] for r in (a,p,s)):
                raise DataError('GP differs between comparison tables')
            if any(r.get('TEAM_COUNT')!=b.get('TEAM_COUNT') for r in (a,p,s)):
                raise DataError('TEAM_COUNT differs between comparison tables')
            if any(s.get(k)!=b.get(k) for k in ('FGM','FGA')):
                raise DataError('Scoring FGA/FGM differs from base')
            for r in (a,s):
                mins=number(r.get('MIN'),'comparison MIN')
                # Official Advanced/Scoring can return rounded MPG despite Totals.
                if abs(mins-b['MIN'])>2 and abs(mins*b['GP']-b['MIN'])>b['GP']*.051+1:
                    raise DataError('Comparison minutes scope differs')
            v={k:number(a.get(k),k) for k in ['USG_PCT','AST_PCT','OREB_PCT','DREB_PCT','PIE']}
            for k in ['USG_PCT','AST_PCT','OREB_PCT','DREB_PCT']:
                if not 0<=v[k]<=1:raise DataError('Invalid fraction '+k)
            for k in ['PTS','FGA','FTA','AST','TOV','FG3A','FGM','FG3M']:
                v_count=number(b.get(k),k)
                if v_count<0 or v_count!=int(v_count):raise DataError('Invalid season total '+k)
            if b['FGM']>b['FGA'] or b['FG3M']>b['FG3A'] or b['FG3A']>b['FGA']:
                raise DataError('Invalid comparison shooting totals')
            if b['TOV']<=0 or b['FGA']<=0:raise DataError('Zero denominator')
            ts=b['PTS']/(2*(b['FGA']+.44*b['FTA']))
            if abs(number(a.get('TS_PCT'),'TS')-ts)>.002:raise DataError('TS scope mismatch')
            for k in ['PTS','AST','TOV']:
                val=number(p.get(k),'per100 '+k)
                if val<0:raise DataError('Negative per100 '+k)
                v[k+'_PER75']=.75*val
            v.update(TS_PCT=ts,AST_TOV=b['AST']/b['TOV'],FG3A=b['FG3A'],
                     FG3A_RATE=b['FG3A']/b['FGA'],PCT_UAST_FGM=number(s.get('PCT_UAST_FGM'),'UAST'))
            if not 0<=v['PCT_UAST_FGM']<=1 or abs(v['PCT_UAST_FGM']+number(s.get('PCT_AST_FGM'),'AST_FGM')-1)>.015:
                raise DataError('Scoring complement invalid')
            players.append(dict(player_id=pid,name=b['PLAYER_NAME'],team=b['TEAM_ABBREVIATION'],
                                team_count=b.get('TEAM_COUNT'),gp=b['GP'],minutes=b['MIN'],**v))
        except DataError as e:excluded.append(dict(player_id=pid,reason=str(e)))
    # An incomplete eligible population cannot become a "complete cohort" silently.
    if excluded:raise DataError('Incomplete eligible comparison population: '+str(excluded))
    target=next((r for r in players if r['player_id']==player_id),None)
    if not target:raise DataError('Target does not meet GP≥40 and MIN≥1000; do not lower threshold to force a radar')
    profile=choose_profile(target);label,rule,definition=PROFILES[profile]
    cohort=[r for r in players if rule(r)]
    if len(cohort)<8:raise DataError('Role cohort n<8; table-only research needed, no radar')
    axes=[]
    for mid,label_axis,unit,direction in AXES:
        vals=[r[mid] for r in cohort]
        axes.append(dict(metric_id=mid,label=label_axis,unit=unit,direction=direction,
                         target=target[mid],median=median(vals),percentile=percentile(target[mid],vals,direction),n=len(vals)))
    sensitivity=[]
    if profile=='creator':
        for label_s,usg,ast in [('宽口径',.23,.25),('严格使用率',.28,.30)]:
            group=[r for r in players if r['USG_PCT']>=usg and r['AST_PCT']>=ast]
            sensitivity.append(dict(label=label_s,usg=usg,ast=ast,n=len(group),
                axes={mid:percentile(target[mid],[r[mid] for r in group],direction) for mid,_,_,direction in AXES}))
    else:
        group=[r for r in players if r['gp']>=50 and r['minutes']>=1500 and rule(r)]
        if len(group)>=8 and target in group:
            sensitivity.append(dict(label='更高出勤门槛',gp=50,minutes=1500,n=len(group),
                axes={mid:percentile(target[mid],[r[mid] for r in group],d) for mid,_,_,d in AXES}))
    return dict(status='ok',target_id=player_id,profile=profile,label=label,definition=definition,minimum_gp=40,minimum_minutes=1000,
                source_ids=SOURCE_IDS,raw_player_count=len(ids),eligible_count=len(players),cohort_count=len(cohort),
                players=cohort,league_players=players,axes=axes,sensitivity=sensitivity,
                raw_hashes={sid:bundle['sources'][sid]['sha256_rows'] for _,sid in TABLES},
                percentile_formula='100 × (严格更差人数 + 0.5 × 同值人数) / N；包含目标球员；失误轴反向；非能力概率或综合排名',
                boundary='功能型阈值样本，包含后卫、锋线与中锋；未调整职责难度、阵容或对手。最新球队标签不代表全部赛季效力段。')


def register_comparisons(ctx, add, metrics):
    source_ids = ctx.get('source_ids', SOURCE_IDS)
    add('COMPARISON_RAW_N',ctx['raw_player_count'],'count',source_ids,'Unique BR slugs in three matched league tables' if ctx.get('adapter') == 'sumitro-v56' else 'Unique IDs in four fully matched league tables')
    add('COHORT_N',ctx['cohort_count'],'count',source_ids,'GP>=40, MIN>=1000; '+ctx['definition'])
    add('COMPARISON_ELIGIBLE_N',ctx['eligible_count'],'count',source_ids,'Full league eligible players before role filters')
    for axis in ctx['axes']:
        mid=axis['metric_id']
        add('COHORT_'+mid+'_MEDIAN',axis['median'],axis['unit'],source_ids,'Median of explicitly enumerated functional cohort')
        metrics[-1]['label']=axis['label']+' · 同角色中位数'
        add('COHORT_'+mid+'_PERCENTILE',axis['percentile'],'percentile',source_ids,ctx['percentile_formula'])
        metrics[-1]['label']=axis['label']+' · 同角色统计百分位'
    target=next(r for r in ctx['players'] if r['player_id']==ctx['target_id'])
    if 'PIE' in target:
        add('NBA_PIE',target['PIE'],'fraction',['P_ADV'],'NBA Advanced.PIE; box-score event share, not adjusted causal impact')
        add('COHORT_PIE_MEDIAN',median(r['PIE'] for r in ctx['players']),'fraction',source_ids,'Median NBA PIE of the explicit functional cohort')
    for i,s in enumerate(ctx['sensitivity']):
        add('COHORT_SENS_'+str(i)+'_N',s['n'],'count',source_ids,'Sensitivity cohort: '+s['label'])
        for mid,value in s['axes'].items():
            add('COHORT_SENS_'+str(i)+'_'+mid,value,'percentile',source_ids,ctx['percentile_formula']+' / '+s['label'])


def limitations(analysis):
    out=[]
    c=analysis.get('comparison_context',{})
    if c.get('status')=='ok':out.append('已提供同角色统计画像；百分位依赖纳入规则，不能合成为能力分或联盟实力排名。')
    else:out.append('同角色比较暂缺：'+c.get('reason','尚未核验全联盟完整比较样本')+'。')
    if (analysis.get('shot_context') or {}).get('points'):
        out.append('已核验投篮坐标并可绘制频次热区；'+('仅覆盖有坐标事件，缺失次数与覆盖率单列；' if analysis['shot_context'].get('missing_location_count') else '')+'尚无同口径联盟区域基准，不做相对效率热区。')
    else:out.append('完整投篮坐标未通过覆盖核验，不绘制投篮频次热区。')
    if analysis.get('impact_context',{}).get('status') == 'ok':
        has_epm=any(d['family']=='EPM' for d in analysis['impact_context']['datasets'])
        has_history=any(d['family']=='EPM_HISTORICAL' for d in analysis['impact_context']['datasets'])
        if has_history:
            out.append('已接入历史EPM快照（口径待核验），仅作补充读数；整季回顾、日期预测与历史快照分开，防守分量不是个人防守能力评分；'+('Actual EPM另已通过离线导入核验，范围未核验的RAPM仍缺失。' if has_epm else '整季Actual EPM与范围未核验的RAPM仍缺失。'))
        else:
            out.append('已接入提供者影响力模型；整季回顾与日期预测分开，防守分量不是个人防守能力评分；'+('Actual EPM已通过离线导入核验，范围未核验的RAPM仍缺失。' if has_epm else 'EPM与范围未核验的RAPM仍缺失。'))
    else:
        out.append('尚未接入同赛季可核验的 EPM；PIE 为技术统计事件份额，On/Off 为球队描述性差值，均不替代调整影响力或个人防守评分。')
    return out
