"""Empirical distributions of retained provider statistics, never ability scores."""
from collections import Counter, defaultdict
from copy import deepcopy
from datetime import date
import json
import re

from common import DataError, digest, integer, normalize_name, number
from impact_metrics import SPECS
from player_comparisons import full_table, percentile

MIN_GP, MIN_MINUTES, MIN_N = 20, 500, 8
METHOD = '100 × (严格更低人数 + 0.5 × 同值人数) / N；包含目标球员，保留原表精度；仅为数值分布位置，不代表能力或显著性。'
HISTORY_NOTE = '口径待核验：同赛季、同上游来源的归档数值分布；记录日期不一致，GP/MIN、估计类型及比赛范围未核实，不是同日预测、整季Actual或联盟能力百分位。'
# mid, provider column, label, unit. All axes describe numeric order (higher).
NBA = [
    ('USG_PCT','USG_PCT','使用率','fraction'), ('AST_PCT','AST_PCT','助攻率','fraction'),
    ('NBA_PIE','PIE','PIE 事件贡献份额','fraction'),
    ('ADV_NBA_OREB_PCT','OREB_PCT','进攻篮板率','fraction'),
    ('ADV_NBA_DREB_PCT','DREB_PCT','防守篮板率','fraction'),
    ('ADV_NBA_REB_PCT','REB_PCT','总篮板率','fraction'),
    ('ADV_NBA_AST_RATIO','AST_RATIO','助攻比率','percent'),
    ('ADV_NBA_TOV_PCT','TM_TOV_PCT','失误比率','percent'),
    ('ADV_NBA_PACE','PACE','在场节奏','possessions_per48'),
    ('ONCOURT_OFF_RATING','OFF_RATING','在场球队进攻效率','per100_team'),
    ('ONCOURT_DEF_RATING','DEF_RATING','在场球队防守失分','per100_team'),
    ('ONCOURT_NET_RATING','NET_RATING','在场球队净效率','per100_team')]
BREF_EXTRA = [('PER','per','PER','ratio'),('TS','ts_pct','真实命中率','fraction'),
              ('3PAR','fg3a_per_fga_pct','三分出手占比','fraction'),
              ('FTR','fta_per_fga_pct','罚球出手比','ratio')]+[
    (k.upper(), k, label, 'percent') for k,label in [
        ('orb_pct','进攻篮板率'),('drb_pct','防守篮板率'),('trb_pct','总篮板率'),
        ('ast_pct','助攻率'),('stl_pct','抢断率'),('blk_pct','封盖率'),
        ('tov_pct','失误率'),('usg_pct','使用率')]]


def eligible(row):
    gp, mins = number(row.get('GP')), number(row.get('MIN'))
    if gp < 0 or gp != int(gp) or mins < 0 or mins > gp * 80:
        raise DataError('Invalid GP/total minutes in percentile population')
    return gp >= MIN_GP and mins >= MIN_MINUTES


def value(row, key, unit):
    v = number(row.get(key), key, optional=True)
    if v is not None and unit == 'fraction' and not 0 <= v <= 1:
        raise DataError('Invalid fraction in population: '+key)
    if v is not None and unit == 'percent' and not 0 <= v <= 100:
        raise DataError('Invalid percentage in population: '+key)
    return v


def summarize(mid, label, unit, target, players, key, sids):
    vals = [value(r, key, unit) for r in players]
    valid = [v for v in vals if v is not None]
    v = value(target, key, unit) if target else None
    entry = dict(metric_id=mid, percentile_metric_id='PCTL_'+mid, label=label, unit=unit,
                 target=v, n=len(valid), missing_count=len(vals)-len(valid), source_ids=sids,
                 direction='higher_numeric', percentile=None, status='missing')
    if v is None: entry['reason']='目标球员未进入样本，或该字段缺失。'
    elif len(valid) < MIN_N: entry['reason']='有效样本少于8人，不计算百分位。'
    else:
        entry.update(status='ok', percentile=percentile(v,valid),
                     lower_count=sum(x<v for x in valid), equal_count=sum(x==v for x in valid))
    return entry


def group(family, label, scope, rows, target, specs, sids, raw_n, **extra):
    entries=[summarize(mid,title,unit,target,rows,key,sids) for mid,key,title,unit in specs]
    return dict(family=family,label=label,scope=scope,status='ok',raw_count=raw_n,
                eligible_count=len(rows),entries=entries,source_ids=sids,
                population_keys=[r.get('PLAYER_ID',r.get('provider_player_key',r.get('nba_id'))) for r in rows],**extra)


def nba_group(bundle, pid):
    base=full_table(bundle,'player_base','P_BASE')
    adv=full_table(bundle,'player_advanced','P_ADV')
    if set(base)!=set(adv): raise DataError('NBA base/advanced ID population differs')
    rows=[]
    for key,b in base.items():
        a=adv[key]
        if b.get('GP')!=a.get('GP') or b.get('TEAM_COUNT')!=a.get('TEAM_COUNT'):
            raise DataError('NBA advanced/base GP or team coverage differs')
        if not eligible(b): continue
        mins=number(a.get('MIN'))
        if abs(mins-b['MIN'])>2 and abs(mins*b['GP']-b['MIN'])>b['GP']*.051+1:
            raise DataError('NBA advanced/base minutes differ')
        r=dict(a)
        from calculate_metrics import counts, safe_ratio
        c=counts(b,'percentile base')
        r['EXACT_TS']=safe_ratio(c['PTS'],2*(c['FGA']+.44*c['FTA'])) if all(c[k] is not None for k in ('PTS','FGA','FTA')) else None
        r['EXACT_EFG']=safe_ratio(c['FGM']+.5*c['FG3M'],c['FGA']) if c['FGM'] is not None and c['FG3M'] is not None else None
        r['EXACT_AST_TOV']=safe_ratio(c['AST'],c['TOV'])
        rows.append(r)
    specs=NBA+ [('TS_PCT','EXACT_TS','真实命中率','fraction'),
                 ('EFG_PCT','EXACT_EFG','有效命中率','fraction'),
                 ('AST_TOV','EXACT_AST_TOV','助攻失误比','ratio')]
    target=next((r for r in rows if r['PLAYER_ID']==pid),None)
    return group('NBA','NBA · 同季合格联盟样本','GP≥20且赛季总分钟≥500；全位置，不另按角色筛选。',
                 rows,target,specs,['P_BASE','P_ADV'],len(base),
                 threshold=dict(gp=MIN_GP,minutes=MIN_MINUTES),excluded_below_threshold=len(base)-len(rows),
                 caveats=['使用率、助攻率和节奏的高值只是职责或环境；防守失分及失误率高值通常并非优势。全部百分位按数值由低到高计算。',
                          '在场效率为球队环境，不是个人攻防评分；TS/eFG和助攻失误比由同一基础总量重算。'])


def bref_group(bundle, dataset):
    rows=dataset['raw_rows']; by=defaultdict(list)
    for r in rows:
        key=r.get('provider_player_key')
        if not key: raise DataError('BREF population missing unique provider key')
        by[key].append(r)
    unique=[]
    for key,stints in by.items():
        aggregate=[r for r in stints if r.get('team_name_abbr')=='TOT' or re.fullmatch(r'[2-9]TM',r.get('team_name_abbr',''))]
        if len(stints)>1:
            if len(aggregate)!=1: raise DataError('BREF duplicate identity without one aggregate row')
            row=aggregate[0]
        else: row=stints[0]
        # The BREF table itself supplies season totals, not inferred MPG.
        if eligible(dict(GP=row.get('games'), MIN=row.get('mp'))): unique.append(row)
    selector=dataset['selector']
    target=next((r for r in unique if all(str(r.get(k))==str(v) for k,v in selector.items())),None)
    specs=[('IMPACT_'+mid,key,mid,unit) for mid,key,unit in SPECS['BREF'][1]]
    specs += [('ADV_BREF_'+mid,key,title,unit) for mid,key,title,unit in BREF_EXTRA]
    return group('BREF','Basketball-Reference · 同季合格样本','GP≥20且提供者总分钟≥500；转会球员仅保留唯一赛季合计行。',
                 unique,target,specs,[dataset['source_id']],len(rows),unique_player_count=len(by),
                 removed_stint_count=len(rows)-len(by),excluded_below_threshold=len(by)-len(unique),
                 threshold=dict(gp=MIN_GP,minutes=MIN_MINUTES),
                 caveats=['BR与NBA的使用率、助攻率等定义及精度不同，分别计算，不混用分母。',
                          'BPM等模型与VORP/WS累计量分别解释；高出勤有利于累计量。失误率等高数值不意味着更优。'])


def historical_rows(rows, season, upstream):
    """Deterministically select all archived rows from one season/source, no rankings."""
    chosen=[r for r in rows if integer(r.get('season'),'historical season')==int(season[:4])+1 and r.get('source')==upstream]
    out=[]; seen=set()
    for r in chosen:
        pid=integer(r.get('nba_player_id'),'historical NBA ID'); stamp=date.fromisoformat(r['game_dt'])
        if pid<=0 or pid in seen: raise DataError('Historical population duplicate/invalid NBA ID; do not pick latest silently')
        seen.add(pid)
        if not date(int(season[:4]),7,1)<=stamp<=date(int(season[:4])+1,6,30):
            raise DataError('Historical population date outside season year')
        try:
            embedded=json.loads(r['raw'])
            for col,key in [('nba_player_id','player_id'),('season','season'),('epm_tot','tot'),('epm_off','off'),('epm_def','def')]:
                if number(r[col])!=number(embedded[key]): raise DataError('Historical population embedded value differs')
            if r['game_dt']!=embedded['game_dt'] or normalize_name(r['player_name'])!=normalize_name(embedded['player_name']):
                raise DataError('Historical population embedded name/date differs')
        except (KeyError, TypeError, ValueError) as exc: raise DataError('Historical population embedded JSON invalid: '+str(exc)) from exc
        a=dict(nba_id=pid,player_name=r['player_name'],as_of=r['game_dt'],
               tot=number(r['epm_tot']),off=number(r['epm_off']),**{'def':number(r['epm_def'])})
        if abs(a['tot']-a['off']-a['def'])>.15+1e-12: raise DataError('Historical population component mismatch')
        out.append(a)
    return out


def attach_history(bundle, root):
    """Reuse the already retained original CSV. Never fetch a replacement."""
    from import_epm import parse_rows, sha
    from retained_raw import checked_path
    from historical_epm import validate_files
    validate_files(bundle,root)
    snap=bundle['historical_epm_import']['snapshot']; original=snap['files'][0]
    payload=checked_path(root,original['raw_file']).read_bytes()
    if sha(payload)!=original['sha256_raw']: raise DataError('Historical original CSV hash mismatch')
    upstream=snap['raw_row']['source']; season=bundle['season']
    rows=historical_rows(parse_rows(payload,'csv'),season,upstream)
    sid='EXT_PCTL_EPM_HISTORICAL'
    source=deepcopy(bundle['sources']['EXT_IMPACT_EPM_HISTORICAL'])
    source.update(display_title='历史 EPM 归档分布（口径待核验）', raw_file=original['raw_file'],
                  sha256_raw=original['sha256_raw'], raw_artifacts=[],row_count=len(rows),sha256_rows=digest(rows),
                  cutoff=None,usage=HISTORY_NOTE,per_mode='Archived distribution; mixed observation dates')
    source.update(source_kind='deocheng-historical-epm-distribution-v1',date_min=min(r['as_of'] for r in rows),date_max=max(r['as_of'] for r in rows))
    bundle['sources'][sid]=source
    bundle['advanced_percentile_populations']=dict(schema_version='0.1.0',historical_epm=dict(
        season=season,upstream=upstream,source_id=sid,raw_rows=rows,sha256_rows=digest(rows)))
    return bundle


def history_group(bundle, dataset):
    pop=bundle.get('advanced_percentile_populations',{}).get('historical_epm')
    if not pop: raise DataError('仅保留单球员历史读数；需从原CSV准备同赛季、同来源归档分布。')
    snap=bundle['historical_epm_import']['snapshot']
    rows=pop['raw_rows']; source=bundle['sources'].get(pop['source_id'],{})
    if pop['season']!=bundle['season'] or pop['upstream']!=snap['raw_row']['source']:
        raise DataError('Historical population season/source differs')
    if digest(rows)!=pop['sha256_rows'] or source.get('sha256_rows')!=digest(rows) or source.get('row_count')!=len(rows):
        raise DataError('Historical population hash/count differs')
    if source.get('sha256_raw')!=snap['files'][0]['sha256_raw'] or source.get('raw_file')!=snap['files'][0]['raw_file']:
        raise DataError('Historical population original artifact differs')
    ids=[r['nba_id'] for r in rows]
    if len(set(ids))!=len(ids): raise DataError('Duplicate historical population identity')
    target=next((r for r in rows if r['nba_id']==dataset['player_id']),None)
    selected=dataset['raw_rows'][0]
    if not target or any(target[k]!=selected[k] for k in ('nba_id','player_name','as_of','tot','off','def')):
        raise DataError('Historical population target differs from verified single-player selection')
    dates=Counter(r['as_of'] for r in rows)
    return group('EPM_HISTORICAL','历史 EPM · 归档数值分布（口径待核验）',HISTORY_NOTE,
                 rows,target,[('IMPACT_'+mid,key,mid,unit) for mid,key,unit in SPECS['EPM_HISTORICAL'][1]],
                 [dataset['source_id'],pop['source_id']],len(rows),threshold=None,
                 date_min=min(dates),date_max=max(dates),date_counts=dict(sorted(dates.items())),
                 target_date=target['as_of'],caveats=[HISTORY_NOTE,'未按场次或分钟筛选；未排除低出勤球员，不与合格联盟样本横向比较。'])


def other_model_group(bundle,d):
    family=d['family']; raw=d['raw_rows']; pid=d['player_id']; checked=[]; excluded=[]
    if family=='EPM':
        from import_epm import build_dataset
        snap=bundle['epm_import']['snapshot']
        raw=snap['raw_rows']; cols=snap['metadata']['columns']
        base=full_table(bundle,'player_base','P_BASE'); seen=set()
        from import_epm import row_season
        for row in raw:
            if row_season(row[cols['season']],snap['metadata']['season_format'])!=bundle['season']:continue
            key=integer(row[cols['nba_id']],'Actual population NBA ID')
            if key in seen: raise DataError('Duplicate Actual EPM population ID')
            seen.add(key)
            if key not in base:
                excluded.append(dict(player_id=key,reason='参考联盟样本无此ID'));continue
            if not eligible(base[key]):
                excluded.append(dict(player_id=key,reason='未达到GP/MIN门槛'));continue
            trial=dict(snap,player_id=key,reference_player=base[key])
            try:
                record,_=build_dataset(trial)
                checked.append(record['raw_rows'][0])
            except DataError as exc: excluded.append(dict(player_id=key,reason=str(exc)))
        threshold=dict(gp=MIN_GP,minutes=MIN_MINUTES)
        scope='GP≥20、总分钟≥500且姓名、NBA ID、场次和分钟均匹配参考表的Actual导出子样本；未通过者不纳入。'
    elif family=='LEBRON':
        base=full_table(bundle,'player_base','P_BASE'); seen=set()
        for r in raw:
            if r.get('Season')!=bundle['season']:continue
            key=integer(r.get('nba_id'),'LEBRON population NBA ID')
            if key in seen: raise DataError('Duplicate LEBRON population ID')
            seen.add(key)
            if key not in base or not eligible(base[key]):
                excluded.append(dict(player_id=key,reason='无参考样本或未达GP/MIN门槛'));continue
            if normalize_name(r.get('player_name',''))!=normalize_name(base[key]['PLAYER_NAME']) or abs(number(r.get('Minutes'))-base[key]['MIN'])>.1:
                excluded.append(dict(player_id=key,reason='姓名或总分钟不匹配'));continue
            checked.append(r)
        threshold=dict(gp=MIN_GP,minutes=MIN_MINUTES)
        scope='同季LEBRON转引、参考GP≥20且MIN≥500、姓名/总分钟匹配的样本；不声称覆盖全部球员。'
    else:
        for r in raw:
            if r.get('season')!=bundle['season'] or r.get('as_of')!=d['cutoff']:
                raise DataError('DARKO population season/date differs')
        ids=[integer(r.get('nba_id'),'DARKO population NBA ID') for r in raw]
        if len(set(ids))!=len(ids): raise DataError('Duplicate DARKO population ID')
        checked=raw; threshold=None
        scope='同一历史日期的DARKO页面样本；生涯加权预测，不按单季GP/MIN筛选。'
    target=next((r for r in checked if integer(r.get('nba_id'),'population NBA ID')==pid),None)
    return group(family,family+' · 提供者样本分布',scope,checked,target,
                 [('IMPACT_'+mid,key,mid,unit) for mid,key,unit in SPECS[family][1]],
                 [d['source_id']]+(['P_BASE'] if family!='DARKO' else []),len(raw),threshold=threshold,
                 excluded=excluded,caveats=['模型版本及覆盖限制沿用已登记来源；不合成综合分，不将防守分量改名为个人防守能力。'])


def context(bundle,pid,team_id,metrics):
    groups=[]
    if team_id: return dict(status='missing',reason='球队效力段不与整季联盟分布混用。',groups=[],method=METHOD)
    try: groups.append(nba_group(bundle,pid))
    except DataError as exc: groups.append(dict(family='NBA',label='NBA 高阶统计',status='missing',reason=str(exc),entries=[]))
    datasets=bundle.get('impact_data',{}).get('datasets',[])
    for d in datasets:
        try:
            source=bundle['sources'][d['source_id']]
            if source.get('row_count')!=len(d['raw_rows']): raise DataError('Provider population row count differs')
            if d['family'] in ('BREF','LEBRON','DARKO') and not supported_original(d,source):
                raise DataError('尚无支持重放的完整提供者原表；单球员读数不构成联盟样本。')
            g=bref_group(bundle,d) if d['family']=='BREF' else history_group(bundle,d) if d['family']=='EPM_HISTORICAL' else other_model_group(bundle,d)
            groups.append(g)
        except DataError as exc: groups.append(dict(family=d['family'],label=d['family'],status='missing',reason=str(exc),entries=[]))
    for family in ('BREF','LEBRON','EPM','DARKO'):
        if not any(g['family']==family for g in groups):
            groups.append(dict(family=family,label=family,status='missing',reason='本次未取得可核验的同季/同日模型及完整提供者样本。',entries=[]))
    if bundle['tables'].get('player_onoff'):
        groups.append(dict(family='ONOFF',label='球队 On/Off',status='missing',reason='当前保留的是单队在场/不在场表，缺少同口径全联盟球员比较样本，不计算联盟百分位。',entries=[]))
    # Never silently compare an independently registered target against another value.
    known={m['metric_id']:m for m in metrics}
    for g in groups:
        for e in g['entries']:
            m=known.get(e['metric_id'])
            if m and e['target'] is not None and (m['status']!='ok' or abs(m['value']-e['target'])>1e-9):
                e.update(status='missing',percentile=None,reason='目标字段与已登记指标不一致，不混用定义。')
    return dict(status='ok' if any(e['status']=='ok' for g in groups for e in g['entries']) else 'missing',
                method=METHOD,groups=groups,minimum_n=MIN_N,
                boundary='全位置数值分布与同角色画像分开。使用率、节奏、失误和球队失分的高百分位并非优势；不反向包装成能力分。')


def register(ctx,add,metrics):
    known={m['metric_id'] for m in metrics}
    for g in ctx['groups']:
        for e in g['entries']:
            mid=e['metric_id']
            if mid not in known:
                add(mid,e['target'],e['unit'],e['source_ids'],g['family']+' retained provider field','Provider target unavailable')
                metrics[-1]['label']=g['family']+' · '+e['label'];known.add(mid)
            add(e['percentile_metric_id'],e['percentile'],'percentile',e['source_ids'],METHOD,e.get('reason',''))
            metrics[-1].update(label=e['label']+' · 数值百分位',population_n=e['n'],population_family=g['family'])
            if g['family']=='EPM_HISTORICAL':
                metrics[-1].update(label=e['label']+' · 归档百分位（口径待核验）',caveats=g['caveats'],
                                   snapshot_date=g['target_date'],verification_status='archived_distribution_mixed_dates_scope_unverified')
            add(e['percentile_metric_id']+'_N',e['n'],'count',e['source_ids'],'Valid numeric values in the explicitly retained population')
            metrics[-1]['label']=e['label']+' · 百分位有效样本人数'


def verify_files(bundle,root):
    """Replay populations against retained original bytes, not a newly self-hashed subset."""
    from retained_raw import checked_path
    from import_epm import sha,parse_rows
    for d in bundle.get('impact_data',{}).get('datasets',[]):
        family=d['family'];s=bundle['sources'][d['source_id']]
        if family not in ('BREF','LEBRON','DARKO'):continue
        if not supported_original(d,s):continue
        payload=checked_path(root,s['raw_file']).read_bytes()
        if sha(payload)!=s['sha256_raw']: raise DataError('Percentile original file SHA differs')
        if family=='BREF':
            from collect_impact import parse_bref
            rows=parse_bref(payload,s['table_id'])
        elif family=='DARKO':
            from collect_impact import parse_darko
            rows=parse_darko(payload,d['cutoff'],d['season'])
        else:rows=json.loads(payload)
        if digest(rows)!=digest(d['raw_rows']): raise DataError('Percentile provider rows differ from original file: '+family)
    pop=bundle.get('advanced_percentile_populations',{}).get('historical_epm')
    if pop:
        s=bundle['sources'][pop['source_id']]
        payload=checked_path(root,s['raw_file']).read_bytes()
        if sha(payload)!=s['sha256_raw']: raise DataError('Historical percentile original SHA differs')
        rows=historical_rows(parse_rows(payload,'csv'),pop['season'],pop['upstream'])
        if digest(rows)!=digest(pop['raw_rows']): raise DataError('Historical percentile subset differs from original CSV')


def supported_original(dataset,source):
    path=source.get('raw_file','')
    if dataset['family']=='BREF':
        return path.endswith('.html') and source.get('table_id') in ('advanced','advanced_post')
    if dataset['family']=='LEBRON':return path.endswith('.json')
    if dataset['family']=='DARKO':return path.endswith('.html')
    return False
