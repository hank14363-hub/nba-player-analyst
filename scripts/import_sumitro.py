"""Offline sumitrodatta v56 adapter: BR regular-season totals, profiles and cohorts."""
import argparse
import hashlib
import json
import re
import sys
from copy import deepcopy
from pathlib import Path
from statistics import median

from common import DataError, digest, integer, normalize_name, number, read_json, validate_bundle, validate_season, write_json
from import_kaggle import COUNTS, TEAMS, SHOOTING, checked_fraction, unique, select_stint, read_selected

DATASET='https://www.kaggle.com/datasets/sumitrodatta/nba-aba-baa-stats'
FILES={'totals':'Player Totals.csv','advanced':'Advanced.csv','per100':'Per 100 Poss.csv',
       'shooting':'Player Shooting.csv','pbp':'Player Play By Play.csv','teams':'Team Totals.csv','team_advanced':'Team Summaries.csv'}
PBP={'BR_BAD_PASS_TOV':'bad_pass_turnover','BR_LOST_BALL_TOV':'lost_ball_turnover',
     'BR_SHOOTING_FOUL_DRAWN':'shooting_foul_drawn','BR_OFFENSIVE_FOUL_COMMITTED':'offensive_foul_committed',
     'BR_ASSIST_GENERATED_POINTS':'points_generated_by_assists','BR_AND1':'and1','BR_FGA_BLOCKED':'fga_blocked'}
AXES=[('PTS_PER75','得分产量','per75',1),('AST_PER75','助攻产量','per75',1),
      ('TS_PCT','真实命中率','fraction',1),('AST_TOV','助攻失误比','ratio',1),('TOV_PER75','控制失误','per75',-1)]


def payload(snapshot):
    return (json.dumps({k:v for k,v in snapshot.items() if k!='snapshot_sha256'},ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')


def src(s,kind,mode,rows,usage):
    meta=s['files'][FILES[kind]]
    return dict(provider='Basketball Reference via Kaggle / Sumitro Datta',url=DATASET,
        retrieved_at=meta['acquired_at'],season=s['season'],season_type='Regular Season',per_mode=mode,status='ok',
        source_type='kaggle_data',adapter='sumitro-v56',dataset_version=56,dataset_snapshot_date=s['snapshot_date'],
        original_csv=FILES[kind],sha256_csv=meta['sha256'],row_count=len(rows),sha256_rows=digest(rows),
        upstream_url='https://www.basketball-reference.com/',raw_file='raw/sumitro_selection.json',
        sha256_raw=s['snapshot_sha256'],usage=usage)


def rows_for(s,kind):
    year=str(int(s['season'][:4])+1)
    return [r for r in s['inputs'].get(kind,[]) if r.get('season')==year and r.get('lg')=='NBA']


def keymap(rows):
    out={}
    for r in rows:
        key=(r.get('player_id'),r.get('team'))
        if not key[0] or key[0] in ('NA','N/A') or key in out:raise DataError('Missing/duplicate BR player-team key')
        out[key]=r
    return out


def convert(raw,adv,per,shoot,pid):
    from calculate_metrics import counts
    team=raw['team'];tid=0 if re.fullmatch(r'TOT|[2-9]TM',team) else TEAMS.get(team)
    if tid is None:raise DataError('Unmapped modern NBA team: '+team)
    b=dict(PLAYER_ID=pid,PLAYER_NAME=raw['player'],TEAM_ID=tid,TEAM_ABBREVIATION=team)
    b.update({k:number(raw.get(v),v,optional=True) for k,v in COUNTS.items()});counts(b,'Sumitro totals')
    if any(b[k] is None for k in ('GP','MIN','PTS','FGA','FTA')):raise DataError('Required totals unavailable')
    def matched(r):
        if (r['player_id'],r['team'])!=(raw['player_id'],raw['team']) or normalize_name(r['player'])!=normalize_name(raw['player']):raise DataError('Cross-table identity mismatch')
        if number(r.get('g'),'g')!=b['GP'] or number(r.get('mp'),'mp')!=b['MIN']:raise DataError('Cross-table GP/MIN mismatch')
    a={k:b[k] for k in ('PLAYER_ID','PLAYER_NAME','TEAM_ID','GP','MIN')}
    if adv:
        matched(adv)
        for dest,key in [('USG_PCT','usg_percent'),('AST_PCT','ast_percent'),('OREB_PCT','orb_percent'),('DREB_PCT','drb_percent')]:
            n=number(adv.get(key),key,optional=True);a[dest]=checked_fraction(None if n is None else n/100,key)
        a['TS_PCT']=checked_fraction(adv.get('ts_percent'),'TS')
    p={k:b[k] for k in ('PLAYER_ID','PLAYER_NAME','TEAM_ID','GP')}
    if per:
        matched(per)
        for dest,key in [('PTS','pts_per_100_poss'),('AST','ast_per_100_poss'),('REB','trb_per_100_poss'),('TOV','tov_per_100_poss')]:
            p[dest]=number(per.get(key),key,optional=True)
            if p[dest] is not None and p[dest]<0:raise DataError('Negative per100 statistic')
    score=None
    if shoot:
        matched(shoot);score={k:b[k] for k in ('PLAYER_ID','PLAYER_NAME','TEAM_ID','GP','MIN','FGM','FGA')}
        for dest,key in SHOOTING.items():score[dest]=number(shoot.get(key),key,optional=True) if dest=='AVG_SHOT_DISTANCE_FT' else checked_fraction(shoot.get(key),key)
        shares=[score['PCT_FGA_'+k] for k in ('0_3','3_10','10_16','16_3P','3P')]
        if all(x is not None for x in shares) and abs(sum(shares)-1)>.006:raise DataError('Shooting shares do not sum to one within rounding')
        if score['AVG_SHOT_DISTANCE_FT'] is not None and score['AVG_SHOT_DISTANCE_FT']<0:raise DataError('Negative distance')
        for band in ('0_3','3_10','10_16','16_3P','3P'):
            if not score['PCT_FGA_'+band]:score['FG_PCT_'+band]=None
        if not b['FG3M']:score['PCT_AST_3PM']=None
        if b['FGM'] is None or b['FG3M'] is None or b['FGM']-b['FG3M']<=0:score['PCT_AST_2PM']=None
    return b,a,p,score


def build(s):
    validate_season(s['season'],'Regular Season')
    if s['dataset_version']!=56 or int(s['season'][:4])<2014:raise DataError('Reviewed v56 modern regular seasons only (2014-15 onward)')
    if s['dataset_url']!=DATASET:raise DataError('Wrong Sumitro dataset')
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',s['snapshot_date']):raise DataError('Snapshot date needs YYYY-MM-DD')
    target=s['bref_key'];pid=integer(s['player_id'],'NBA ID');tid=integer(s['team_id'],'team scope')
    if pid<=0 or tid<0:raise DataError('Invalid IDs')
    maps={k:keymap(rows_for(s,k)) for k in ('totals','advanced','per100','shooting','pbp')}
    raw=select_stint([r for r in maps['totals'].values() if r['player_id']==target],tid);key=(target,raw['team'])
    identity=s['identity'];refrows=identity['rows'];refsource=identity['source']
    if identity.get('data_kind')!='nba' or refsource.get('status')!='ok' or refsource.get('endpoint')!='leaguedashplayerstats' or refsource.get('sha256_rows')!=digest(refrows):raise DataError('Identity needs retained hashed official player rows')
    if refsource.get('season')!=s['season'] or refsource.get('season_type')!='Regular Season':raise DataError('Identity reference season/type differs')
    names={normalize_name(r['PLAYER_NAME']) for r in refrows if integer(r['PLAYER_ID'],'identity PLAYER_ID')==pid}
    if names!={normalize_name(raw['player'])}:raise DataError('NBA ID does not match target BR full name')
    b,a,p,score=convert(raw,maps['advanced'].get(key),maps['per100'].get(key),maps['shooting'].get(key),pid)
    tables={'player_base':[b]};sources={'P_BASE':src(s,'totals','Totals',[b],'BR totals; selected player sample; original source is Kaggle, not NBA Stats.')}
    for name,sid,kind,mode,row in [('player_advanced','P_ADV','advanced','Totals',a),('player_per100','P_100','per100','Per100Possessions',p),('player_scoring','P_SCORE','shooting','Totals',score)]:
        if maps[kind].get(key) and row:
            tables[name]=[row];sources[sid]=src(s,kind,mode,[row],'BR definitions and rounding; individual ORtg/DRtg omitted; assisted shares use made 2P/3P denominators.')
    excluded=[dict(domain='EPM / shot coordinates / Playoffs / tracking / On-Off',reason='These required raw tables are absent; no proxies or zero fill')]
    warnings=['Sumitro v56 historical BR regular-season snapshot; shares upstream with deocheng, not independent corroboration.']
    bundle=dict(schema_version='0.1.0',data_kind='nba',season=s['season'],season_type='Regular Season',player_team_id=tid,tables=tables,sources=sources,warnings=warnings)
    teams=rows_for(s,'teams');real=[r for r in teams if r.get('abbreviation') in TEAMS]
    if teams:
        ids=[TEAMS[r['abbreviation']] for r in real]
        if len(ids)!=30 or len(set(ids))!=30:raise DataError('Team baseline lacks complete modern 30-team coverage')
        converted=[]
        from calculate_metrics import counts
        for r in real:
            t=dict(TEAM_ID=TEAMS[r['abbreviation']],TEAM_NAME=r['team'])
            t.update({k:number(r.get(v),v,optional=True) for k,v in COUNTS.items()})
            if t['MIN'] is None or t['MIN']<=0:raise DataError('Missing team five-player minutes')
            t['MIN']/=5;counts(t,'BR team season totals')
            if t['GP']<=0 or not 48<=t['MIN']/t['GP']<=65:raise DataError('Team minutes fail documented five-player conversion')
            converted.append(t)
        tables['team_base']=converted;sources['T_BASE']=src(s,'teams','Totals',converted,'30 actual teams; League Average excluded; BR five-player minute totals divided by five. playoffs column is a team label, not competition type.')
        sources['T_BASE'].update(coverage='full_league',minute_conversion='original mp / 5',league_average_rows_excluded=len(teams)-len(real))
        trs=rows_for(s,'team_advanced');selected=[r for r in trs if r.get('abbreviation') in TEAMS]
        if selected:
            if {r['abbreviation'] for r in selected}!={r['abbreviation'] for r in real} or len(selected)!=30:raise DataError('Team summary coverage differs')
            out=[]
            for r in selected:
                row=dict(TEAM_ID=TEAMS[r['abbreviation']],GP=number(r['w'],'w')+number(r['l'],'l'))
                for dest,field in [('OFF_RATING','o_rtg'),('DEF_RATING','d_rtg'),('NET_RATING','n_rtg'),('PACE','pace')]:row[dest]=number(r.get(field),field,optional=True)
                out.append(row)
            tables['team_advanced']=out;sources['T_ADV']=src(s,'team_advanced','Totals',out,'BR team-level season summaries, not individual oncourt effects.')
    pr=maps['pbp'].get(key)
    if pr:
        if normalize_name(pr['player'])!=normalize_name(raw['player']):raise DataError('PBP name differs')
        if number(pr.get('g'),'pbp.g')!=b['GP'] or number(pr.get('mp'),'pbp.mp')!=b['MIN']:raise DataError('PBP summary sample differs')
        vals={mid:number(pr.get(field),field,optional=True) for mid,field in PBP.items()}
        if any(v is not None and (v<0 or v!=int(v)) for v in vals.values()):raise DataError('PBP totals must be nonnegative integers')
        v1,v2=vals['BR_BAD_PASS_TOV'],vals['BR_LOST_BALL_TOV']
        remaining=None if b['TOV'] is None or v1 is None or v2 is None else b['TOV']-v1-v2
        if remaining is not None and remaining<0:raise DataError('Two turnover counts exceed total')
        vals['BR_TOV_TWO_TYPE_RESIDUAL']=remaining;bundle['sumitro_pbp']=vals
        sources['EXT_BR_PBP']=src(s,'pbp','Totals',[pr],'Season summaries, not original event logs; turnover residual is arithmetic, not a verified third event taxonomy. No On/Off reconstructed.')
    adv=maps['advanced'].get(key)
    if adv and not tid and any(number(adv.get(k),k,optional=True) is not None for k in ('bpm','vorp','ws')):
        row=dict(provider_player_key=target,name_display=raw['player'],games=b['GP'],mp=b['MIN'])
        row.update({dest:number(adv.get(k),k,optional=True) for dest,k in [('bpm','bpm'),('obpm','obpm'),('dbpm','dbpm'),('vorp','vorp'),('ws','ws'),('ows','ows'),('dws','dws'),('ws_per_48','ws_48')]})
        model='BR BPM 2.0 / Win Shares; historical implementation version unverified'
        sources['EXT_IMPACT_BREF']=src(s,'advanced','Provider model',[row],'BR model estimates redistributed by Sumitro; no new primary-site verification.')
        sources['EXT_IMPACT_BREF'].update(source_type='impact_data',model_version=model,cutoff=None,table_id='advanced')
        bundle['impact_data']=dict(schema_version='0.1.0',datasets=[dict(family='BREF',player_id=pid,player_team_id=0,provider_player_key=target,season=s['season'],season_type='Regular Season',estimate_type='retrospective_box',model_version=model,cutoff=None,source_id='EXT_IMPACT_BREF',raw_rows=[row],selector={'provider_player_key':target},caveats=['BR model via Kaggle; GP and rounded MIN matched to source totals.', 'Defense component is not individual defensive ability.'])],excluded=[])
    warnings.extend(x['reason'] for x in excluded)
    return bundle,excluded


def validate_import(bundle):
    contract=bundle.get('sumitro_import')
    if contract is None:return
    if contract.get('schema_version')!='0.1.0':raise DataError('Unknown Sumitro import schema')
    s=contract['snapshot']
    if hashlib.sha256(payload(s)).hexdigest()!=s.get('snapshot_sha256'):raise DataError('Sumitro retained snapshot checksum mismatch')
    expected,_=build(s)
    for k in ('season','season_type','player_team_id','data_kind','sumitro_pbp'):
        if digest(bundle.get(k))!=digest(expected.get(k)):raise DataError('Sumitro sample/summary changed: '+k)
    for section in ('tables','sources'):
        for k,v in expected[section].items():
            if digest(bundle.get(section,{}).get(k))!=digest(v):raise DataError('Sumitro converted value/source changed: '+k)
    if expected.get('impact_data'):
        actual=[x for x in bundle.get('impact_data',{}).get('datasets',[]) if x.get('family')=='BREF']
        if digest(actual)!=digest(expected['impact_data']['datasets']):raise DataError('Sumitro BREF model changed')


def register_pbp(bundle,add):
    for mid,value in bundle.get('sumitro_pbp',{}).items():
        add(mid,value,'count',['EXT_BR_PBP'],'BR provider season summary; residual = total TOV - bad pass - lost ball','Provider field missing')


def comparison_context(bundle,pid,tid):
    if tid:raise DataError('BR cohort compares full seasons only')
    s=bundle['sumitro_import']['snapshot'];raw={k:keymap(rows_for(s,k)) for k in ('totals','advanced','per100')}
    if set(raw['totals'])!=set(raw['advanced']) or set(raw['totals'])!=set(raw['per100']):raise DataError('BR league table keys differ; no silent population removal')
    by={}
    for r in raw['totals'].values():by.setdefault(r['player_id'],[]).append(r)
    players=[]
    from player_comparisons import choose_profile,PROFILES,percentile
    for slug,rs in sorted(by.items()):
        r=select_stint(rs,0);k=(slug,r['team']);adv=raw['advanced'][k];per=raw['per100'][k]
        if number(r.get('g'),'cohort GP')<40 or number(r.get('mp'),'cohort MIN')<1000:continue
        b,a,p,_=convert(r,adv,per,None,slug)
        if b['GP']<40 or b['MIN']<1000:continue
        if b['FGA']<=0 or not b['TOV']:raise DataError('Eligible BR cohort denominator unavailable')
        ts=b['PTS']/(2*(b['FGA']+.44*b['FTA']))
        if a.get('TS_PCT') is None or abs(a['TS_PCT']-ts)>.002:raise DataError('Eligible BR TS scope mismatch')
        vals={field:number(a.get(field),field) for field in ('USG_PCT','AST_PCT','OREB_PCT','DREB_PCT')}
        vals.update(TS_PCT=ts,AST_TOV=b['AST']/b['TOV'],FG3A=b['FG3A'],FG3A_RATE=b['FG3A']/b['FGA'])
        for field in ('PTS','AST','TOV'):vals[field+'_PER75']=.75*number(p.get(field),'per100 '+field)
        players.append(dict(player_id=slug,provider_player_key=slug,name=r['player'],team=r['team'],gp=b['GP'],minutes=b['MIN'],**vals))
    target=next((r for r in players if r['player_id']==s['bref_key']),None)
    if target is None:raise DataError('Target does not meet fixed BR cohort thresholds')
    profile=choose_profile(target);label,rule,definition=PROFILES[profile];cohort=[r for r in players if rule(r)]
    if len(cohort)<8:raise DataError('BR role sample n<8; no percentile chart')
    axes=[dict(metric_id=mid,label=label,unit=unit,direction=d,target=target[mid],median=median(r[mid] for r in cohort),percentile=percentile(target[mid],[r[mid] for r in cohort],d),n=len(cohort)) for mid,label,unit,d in AXES]
    sensitivity=[]
    rules=[('宽口径',lambda r:r['USG_PCT']>=.23 and r['AST_PCT']>=.25),('严格使用率',lambda r:r['USG_PCT']>=.28 and r['AST_PCT']>=.30)] if profile=='creator' else [('更高出勤门槛',lambda r:r['gp']>=50 and r['minutes']>=1500 and rule(r))]
    for label,rule in rules:
        group=[r for r in players if rule(r)]
        if len(group)>=8 and target in group:sensitivity.append(dict(label=label,n=len(group),axes={mid:percentile(target[mid],[r[mid] for r in group],d) for mid,_,_,d in AXES}))
    return dict(status='ok',adapter='sumitro-v56',identity_namespace='Basketball Reference slug; not NBA ID',target_id=s['bref_key'],nba_target_id=pid,profile=profile,label=PROFILES[profile][0],definition=definition,minimum_gp=40,minimum_minutes=1000,source_ids=['P_BASE','P_ADV','P_100'],raw_player_count=len(by),eligible_count=len(players),cohort_count=len(cohort),players=cohort,league_players=players,axes=axes,sensitivity=sensitivity,raw_hashes={k:s['files'][FILES[k]]['sha256'] for k in ('totals','advanced','per100')},percentile_formula='Midrank empirical percentile includes target and tied values; TOV axis reversed',boundary='BR-specific five-axis descriptive cohort. No unassisted-FGM proxy, NBA PIE, overall ability score or independent-source claim.')


def run(args):
    validate_season(args.season,args.season_type)
    if args.season_type!='Regular Season':raise DataError('Dataset has regular season only')
    if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):raise DataError('Choose new/empty output')
    inputs={};files={};year=str(int(args.season[:4])+1)
    for kind,name in FILES.items():
        rows,meta=read_selected(args.csv_dir,name,lambda r:r.get('season')==year and r.get('lg')=='NBA',required=kind=='totals')
        inputs[kind]=rows
        if meta:files[name]=meta
    ref=read_json(args.identity_bundle);identity=dict(data_kind=ref.get('data_kind'),rows=ref['tables']['player_base'],source=ref['sources']['P_BASE'])
    s=dict(schema_version='0.1.0',dataset_url=DATASET,dataset_version=args.dataset_version,snapshot_date=args.snapshot_date,season=args.season,player_id=args.player_id,bref_key=args.bref_key,team_id=args.team_id,inputs=inputs,files=files,identity=identity)
    original=payload(s);s['snapshot_sha256']=hashlib.sha256(original).hexdigest()
    b,excluded=build(s);b['sumitro_import']=dict(schema_version='0.1.0',snapshot=s)
    validate_bundle(b,args.season,'Regular Season',args.team_id)
    from calculate_metrics import analyze
    a=analyze(b,dict(player_id=args.player_id,season=args.season,season_type='Regular Season',team_id=args.team_id,comparisons=args.comparisons))
    args.out.mkdir(parents=True,exist_ok=True);(args.out/'raw').mkdir();(args.out/'raw/sumitro_selection.json').write_bytes(original)
    write_json(args.out/'data_bundle.json',b)
    write_json(args.out/'sumitro_import_audit.json',dict(status='ok',dataset_url=DATASET,dataset_version=56,snapshot_date=args.snapshot_date,player=a['player'],sample=a['sample'],metrics_available=a['quality']['metrics_available'],excluded=excluded,comparison=a.get('comparison_context',{}),files=files,raw_note='Selected source rows retained; full CSV hashes recorded. Identity mapping uses supplied official player rows; BR cohort keys are not NBA IDs.'))
    return args.out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('csv-dir','identity-bundle','out'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--player-id',type=int,required=True);p.add_argument('--bref-key',required=True);p.add_argument('--season',required=True)
    p.add_argument('--season-type',default='Regular Season',choices=['Regular Season','Playoffs']);p.add_argument('--team-id',type=int,default=0)
    p.add_argument('--dataset-version',type=int,default=56);p.add_argument('--snapshot-date',default='2026-04-13')
    p.add_argument('--comparisons',action='store_true');args=p.parse_args()
    try:print(run(args));return 0
    except (DataError,OSError,ValueError,KeyError) as exc:print('ERROR: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
