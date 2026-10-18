"""Offline adapter for deocheng/nba-data-1946-2026. No EPM or shot-coordinate import."""
from __future__ import annotations

import argparse
import csv
import hashlib
import re
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

from common import DataError, digest, integer, normalize_name, number, read_json, validate_bundle, validate_season, write_json

DATASET = 'https://www.kaggle.com/datasets/deocheng/nba-data-1946-2026'
COUNTS = {'GP':'g','MIN':'mp','PTS':'pts','FGM':'fg','FGA':'fga','FG3M':'x3p',
          'FG3A':'x3pa','FTM':'ft','FTA':'fta','OREB':'orb','DREB':'drb','REB':'trb',
          'AST':'ast','TOV':'tov','STL':'stl','BLK':'blk','PF':'pf'}
TEAMS = dict(zip(['ATL','BOS','CLE','NOP','CHI','DAL','DEN','GSW','HOU','LAC','LAL',
                 'MIA','MIL','MIN','BRK','NYK','ORL','IND','PHI','PHO','POR','SAC',
                 'SAS','OKC','TOR','UTA','MEM','WAS','DET','CHO'], range(1610612737,1610612767)))
TEAMS.update(BKN=TEAMS['BRK'],PHX=TEAMS['PHO'],CHA=TEAMS['CHO'])
SHOOTING = {'PCT_AST_2PM':'percent_assisted_x2p_fg','PCT_AST_3PM':'percent_assisted_x3p_fg',
            'AVG_SHOT_DISTANCE_FT':'avg_dist_fga'}
for band in ('0_3','3_10','10_16','16_3p','3p'):
    SHOOTING['PCT_FGA_'+band.upper()]='percent_fga_from_x'+band+'_range'
    SHOOTING['FG_PCT_'+band.upper()]='fg_percent_from_x'+band+'_range'


def unique(rows, context):
    if len(rows)!=1:
        raise DataError(f'{context}: expected one unambiguous row, found {len(rows)}')
    return rows[0]


def select_stint(rows, team_id):
    if team_id:
        return unique([r for r in rows if TEAMS.get(r.get('team'))==team_id], 'Requested team stint')
    totals=[r for r in rows if re.fullmatch(r'TOT|[2-9]TM',r.get('team',''))]
    return unique(totals if totals else rows,'Full-season total (never add team stints)')


def checked_fraction(value, field):
    val=number(value,field,optional=True)
    if val is not None and not 0<=val<=1:
        raise DataError('Fraction outside 0..1: '+field)
    return val


def source(snapshot, table, sid, mode, rows, usage):
    meta=snapshot['files'][table]
    return dict(provider='Basketball Reference via Kaggle / Deo Cheng',url=DATASET,
                retrieved_at=meta['acquired_at'],season=snapshot['season'],season_type='Regular Season',
                per_mode=mode,status='ok',source_type='kaggle_data',adapter='deocheng-v1',
                dataset_version=snapshot['dataset_version'],dataset_snapshot_date=snapshot['snapshot_date'],
                original_csv=table,sha256_csv=meta['sha256'],row_count=len(rows),sha256_rows=digest(rows),
                coverage='selected_player_sample',upstream_url='https://www.basketball-reference.com/',
                raw_file='raw/kaggle_selection.json',sha256_raw=snapshot['snapshot_sha256'],usage=usage)


def build_bundle(snapshot):
    """Recompute converted tables from retained provider rows, without network access."""
    validate_season(snapshot['season'],'Regular Season')
    if str(snapshot['dataset_version'])!='1':
        raise DataError('Only reviewed dataset version 1 is supported; re-audit changed schemas first')
    pid=integer(snapshot['player_id'],'player_id');key=snapshot['bref_key'];tid=integer(snapshot['team_id'],'team_id')
    if pid<=0 or tid<0 or not re.fullmatch(r'[a-z0-9]+',key):raise DataError('Invalid player identity/team scope')
    end=str(int(snapshot['season'][:4])+1)
    raw=snapshot['inputs']
    rows=[r for r in raw['season'] if r.get('season')==end and r.get('season_type')=='Regular Season' and r.get('lg')=='NBA' and r.get('player_id')==key]
    r=select_stint(rows,tid)
    mappings=[b for b in raw['bridge'] if b.get('br_player_id')==key and b.get('nba_player_id')]
    ids={integer(b['nba_player_id'],'bridge NBA ID') for b in mappings}
    if ids!={pid}:raise DataError('Conflicting or missing numeric NBA/BR identity bridge')
    names=[b for b in raw['bridge'] if b.get('br_player_id')==key and b.get('match_strategy')=='exact_name' and normalize_name(b.get('player_name',''))==normalize_name(r.get('player',''))]
    if not names:raise DataError('An exact-name and numeric-ID bridge is required; abbreviations are insufficient')
    is_total=bool(re.fullmatch(r'TOT|[2-9]TM',r['team']))
    actual_team=0 if is_total else TEAMS.get(r['team'])
    if actual_team is None:raise DataError('Unmapped historical team abbreviation; do not guess an NBA ID')
    base=dict(PLAYER_ID=pid,PLAYER_NAME=r['player'],TEAM_ID=actual_team,TEAM_ABBREVIATION=r['team'])
    base.update({dest:number(r.get(src),src,optional=True) for dest,src in COUNTS.items()})
    from calculate_metrics import counts
    values=counts(base,'Kaggle season totals')
    if any(values[k] is None for k in ('GP','MIN','PTS','FGA','FTA')) or values['GP']<=0 or values['MIN']<=0:
        raise DataError('Required season totals missing or nonpositive')
    advanced={k:base[k] for k in ('PLAYER_ID','PLAYER_NAME','TEAM_ID','GP','MIN')}
    for dst,src in [('USG_PCT','usg_percent'),('AST_PCT','ast_percent'),('OREB_PCT','orb_percent'),('DREB_PCT','drb_percent')]:
        v=number(r.get(src),src,optional=True)
        advanced[dst]=checked_fraction(None if v is None else v/100,src)
    advanced['TS_PCT']=checked_fraction(r.get('ts_percent'),'ts_percent')
    # Provider individual ORtg/DRtg deliberately never map to team-oncourt ratings.
    per100={k:base[k] for k in ('PLAYER_ID','PLAYER_NAME','TEAM_ID','GP')}
    for dst,src in [('PTS','pts_per_100_poss'),('REB','trb_per_100_poss'),('AST','ast_per_100_poss'),('TOV','tov_per_100_poss')]:
        v=number(r.get(src),src,optional=True)
        if v is not None and v<0:raise DataError('Negative per100 value')
        per100[dst]=v
    tables={'player_base':[base],'player_advanced':[advanced],'player_per100':[per100]}
    sources={sid:source(snapshot,'public.fact_player_season_stats.csv',sid,mode,tables[t],
                        'BR season totals/rates via Kaggle; not NBA Stats definitions. No individual ORtg/DRtg mapping.')
             for t,sid,mode in [('player_base','P_BASE','Totals'),('player_advanced','P_ADV','Totals'),('player_per100','P_100','Per100Possessions')]}
    warnings=['Kaggle historical snapshot; BR rate definitions/precision differ from NBA Stats. Single-player import is not a complete league cohort.']
    excluded=[dict(domain='EPM',reason='Estimate type/date/window not verified; 2025 actual unavailable'),
              dict(domain='shot_coordinates',reason='Coordinate system and full shot coverage not verified'),
              dict(domain='team_on_off',reason='Mislabelled opponent-vs-team fields; use player_onoff only'),
              dict(domain='Playoffs',reason='Season-table player identities incomplete; adapter is regular-season-only')]
    shoot=[x for x in raw.get('shooting',[]) if x.get('season')==end and x.get('season_type')=='Regular Season' and x.get('player_id')==key]
    if shoot:
        sr=select_stint(shoot,tid)
        if sr['team']!=r['team'] or number(sr.get('g'),'shooting.g')!=base['GP'] or abs(number(sr.get('mp'),'shooting.mp')-base['MIN'])>1:
            raise DataError('Shooting identity/team/games/minutes differs from season totals')
        scoring={k:base[k] for k in ('PLAYER_ID','PLAYER_NAME','TEAM_ID','GP','MIN','FGM','FGA')}
        for dst,src in SHOOTING.items():
            scoring[dst]=number(sr.get(src),src,optional=True) if dst=='AVG_SHOT_DISTANCE_FT' else checked_fraction(sr.get(src),src)
        if scoring['AVG_SHOT_DISTANCE_FT'] is not None and scoring['AVG_SHOT_DISTANCE_FT']<0:raise DataError('Negative shot distance')
        shares=[scoring['PCT_FGA_'+band] for band in ('0_3','3_10','10_16','16_3P','3P')]
        if all(v is not None for v in shares) and abs(sum(shares)-1)>.006:
            raise DataError('Distance-band attempt shares fail rounded sum-to-one check')
        for band in ('0_3','3_10','10_16','16_3P','3P'):
            if scoring['PCT_FGA_'+band] is None or scoring['PCT_FGA_'+band]<=0:
                scoring['FG_PCT_'+band]=None
        if not base.get('FG3M'):scoring['PCT_AST_3PM']=None
        if base.get('FGM') is None or base.get('FG3M') is None or base['FGM']-base['FG3M']<=0:
            scoring['PCT_AST_2PM']=None
        tables['player_scoring']=[scoring]
        sources['P_SCORE']=source(snapshot,'public.player_shooting.csv','P_SCORE','Totals',[scoring],
            'Assisted shares use made 2P/3P denominators; rounded BR shares. No exact assisted counts or combined FGM share inferred.')
    else:excluded.append(dict(domain='shooting_profile',reason='No matching shooting rows'))
    bundle=dict(schema_version='0.1.0',data_kind='nba',season=snapshot['season'],season_type='Regular Season',
                player_team_id=tid,tables=tables,sources=sources,warnings=warnings)
    # Optional independently sourced team baseline, never constructed from On+Off.
    ref=snapshot.get('reference')
    if ref:
        if ref.get('season')!=snapshot['season'] or ref.get('season_type')!='Regular Season' or ref.get('data_kind')!='nba':
            raise DataError('Reference bundle season/type/kind mismatch')
        teams=ref['tables'].get('team_base',[]);ts=ref['sources'].get('T_BASE',{})
        if ts.get('status')!='ok' or ts.get('coverage')!='full_league' or ts.get('endpoint')!='leaguedashteamstats' or ts.get('sha256_rows')!=digest(teams):
            raise DataError('Reference requires hashed official full-league team totals')
        params=ts.get('parameters',{})
        if params.get('Season')!=snapshot['season'] or params.get('SeasonType')!='Regular Season' or params.get('PerMode')!='Totals' or params.get('MeasureType')!='Base':
            raise DataError('Reference team source parameters mismatch')
        allowed={'Season','SeasonType','PerMode','MeasureType','PaceAdjust','PlusMinus','Rank','LeagueID'}
        if any(v not in ('',None,0,'0') for k,v in params.items() if k not in allowed):raise DataError('Filtered reference team source')
        ids=[integer(t.get('TEAM_ID'),'reference TEAM_ID') for t in teams]
        if len(ids)!=30 or len(set(ids))!=30 or any(i not in TEAMS.values() for i in ids):raise DataError('Reference must contain the complete modern 30-team NBA league')
        tables['team_base']=deepcopy(teams);sources['T_BASE']=deepcopy(ts)
    onrows=[x for x in raw.get('onoff',[]) if x.get('player_id')==key and x.get('season')==end and x.get('season_type')=='Regular Season' and TEAMS.get(x.get('team_id'))==actual_team and x.get('split') in ('On Court','Off Court')]
    if actual_team and ref and onrows:
        converted=[]
        for status in ('On Court','Off Court'):
            row=unique([x for x in onrows if x['split']==status],'On/Off '+status)
            off=number(row.get('off_rtg'),'off_rtg');defense=number(row.get('opp_off_rtg'),'opp_off_rtg')
            net=number(row.get('diff_off_rtg'),'diff_off_rtg',optional=True)
            converted.append(dict(PLAYER_ID=pid,TEAM_ID=actual_team,COURT_STATUS='On' if status=='On Court' else 'Off',
                                  MIN=number(row.get('mp'),'onoff.mp'),OFF_RATING=off,DEF_RATING=defense,NET_RATING=net if net is not None else off-defense))
        tables['player_onoff']=converted
        osrc=source(snapshot,'public.player_onoff.csv','P_ONOFF','Totals',converted,
            'BR grouped team-oncourt rates, rounded; NBA Stats team minutes independently checked. Descriptive, not causal.')
        osrc.update(team_id=actual_team,sample_scope='full_team_season',metric_definition='team_oncourt')
        sources['P_ONOFF']=osrc
        from supplemental_metrics import onoff_context
        try:onoff_context(bundle,base,pid,tid)
        except DataError as exc:
            tables.pop('player_onoff');sources.pop('P_ONOFF')
            excluded.append(dict(domain='player_onoff',reason=str(exc)))
    else:excluded.append(dict(domain='player_onoff',reason='Needs one actual sample team, matching rows and an independent official team-minute reference; never use On+Off as its own baseline'))
    if 'player_onoff' in tables:
        team=next(t for t in tables['team_base'] if t['TEAM_ID']==actual_team)
        sources['P_ONOFF']['minute_check']=dict(on_minutes=converted[0]['MIN'],off_minutes=converted[1]['MIN'],
            player_minutes=base['MIN'],official_team_floor_minutes=team['MIN'],
            on_player_gap=converted[0]['MIN']-base['MIN'],team_coverage_gap=sum(x['MIN'] for x in converted)-team['MIN'],
            tolerance_minutes=2,reference_source_id='T_BASE')
    # Reuse the existing BREF model contract. Team-stint box models stay excluded.
    if not tid and any(r.get(k) not in ('',None) for k in ('bpm','vorp','ws')):
        impact=dict(provider_player_key=key,name_display=r['player'],games=base['GP'],mp=base['MIN'])
        impact.update({k:number(r.get(src),src,optional=True) for k,src in [('bpm','bpm'),('obpm','obpm'),('dbpm','dbpm'),('vorp','vorp'),('ws','ws'),('ows','ows'),('dws','dws'),('ws_per_48','ws_48')]})
        model='BPM 2.0 / BR Win Shares; upstream version inferred from field family, historical implementation unverified'
        sid='EXT_IMPACT_BREF';s=source(snapshot,'public.fact_player_season_stats.csv',sid,'Provider model',[impact],'Kaggle redistribution of BR box models; not primary-site retrieval; no composite or defensive ability score.')
        s.update(source_type='impact_data',model_version=model,cutoff=None,table_id='advanced')
        sources[sid]=s
        bundle['impact_data']=dict(schema_version='0.1.0',datasets=[dict(family='BREF',player_id=pid,player_team_id=0,
            provider_player_key=key,season=snapshot['season'],season_type='Regular Season',estimate_type='retrospective_box',
            model_version=model,cutoff=None,source_id=sid,raw_rows=[impact],selector={'provider_player_key':key},
            caveats=['BR model estimates redistributed via Kaggle; GP and rounded minutes matched to BR totals, not new official validation.',
                     'Defensive component is not individual defensive ability; no averaging into composite ratings.'])],excluded=[])
    bundle['warnings'].extend(x['domain']+': '+x['reason'] for x in excluded)
    return bundle,excluded


def validate_import(bundle):
    data=bundle.get('kaggle_import')
    if data is None:return
    snapshot=data.get('snapshot')
    if not isinstance(snapshot,dict) or data.get('schema_version')!='0.1.0':raise DataError('Invalid Kaggle import contract')
    original={k:v for k,v in snapshot.items() if k!='snapshot_sha256'}
    payload=(__import__('json').dumps(original,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
    if hashlib.sha256(payload).hexdigest()!=snapshot.get('snapshot_sha256'):
        raise DataError('Kaggle retained selection checksum mismatch')
    expected,_=build_bundle(snapshot)
    for key in ('season','season_type','player_team_id','data_kind'):
        if bundle.get(key)!=expected.get(key):raise DataError('Kaggle sample differs: '+key)
    for section in ('tables','sources'):
        for key,value in expected[section].items():
            if digest(bundle.get(section,{}).get(key))!=digest(value):
                raise DataError('Kaggle conversion differs from retained raw selection: '+section+'/'+key)
    if expected.get('impact_data'):
        actual=[d for d in bundle.get('impact_data',{}).get('datasets',[]) if d.get('family')=='BREF']
        if digest(actual)!=digest(expected['impact_data']['datasets']):raise DataError('Kaggle BREF estimates changed')


def read_selected(directory, filename, predicate, required=True):
    path=directory/filename
    if not path.is_file():
        if required:raise DataError('Missing CSV: '+filename)
        return [],None
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1024*1024),b''):h.update(block)
    with path.open(encoding='utf-8-sig',newline='') as f:
        rows=[r for r in csv.DictReader(f) if predicate(r)]
    return rows,dict(sha256=h.hexdigest(),acquired_at=datetime.fromtimestamp(path.stat().st_mtime,timezone.utc).isoformat(),
                     acquisition_time_basis='Local CSV mtime; not original upstream scrape time')


def run(args):
    if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):raise DataError('Choose a new/empty output directory')
    validate_season(args.season,args.season_type)
    if args.season_type!='Regular Season':raise DataError('Kaggle adapter supports regular season only; playoff identities require repair')
    if int(args.season[:4])<2014:raise DataError('Adapter currently supports modern NBA seasons from 2014-15; historical teams require a separately verified map')
    directory=args.csv_dir
    if (directory/'csv').is_dir():directory=directory/'csv'
    end=str(int(args.season[:4])+1);inputs={};files={}
    for dest,name,required in [('season','public.fact_player_season_stats.csv',True),('shooting','public.player_shooting.csv',False),
                               ('onoff','public.player_onoff.csv',False),('bridge','public.player_id_bridge.csv',True)]:
        predicate=(lambda r:r.get('br_player_id')==args.bref_key) if dest=='bridge' else (lambda r:r.get('player_id')==args.bref_key and r.get('season')==end and r.get('season_type')=='Regular Season')
        selected,meta=read_selected(directory,name,predicate,required)
        inputs[dest]=selected
        if meta:files[name]=meta
    ref=read_json(args.reference_bundle) if args.reference_bundle else None
    if ref:
        ref={k:deepcopy(ref[k]) for k in ('season','season_type','data_kind','tables','sources')}
        ref['tables']={'team_base':ref['tables'].get('team_base',[])}
        ref['sources']={'T_BASE':ref['sources'].get('T_BASE',{})}
    snapshot=dict(schema_version='0.1.0',dataset_url=DATASET,dataset_version=args.dataset_version,
                  snapshot_date=args.snapshot_date,season=args.season,player_id=args.player_id,bref_key=args.bref_key,
                  team_id=args.team_id,inputs=inputs,files=files,reference=ref)
    payload=(__import__('json').dumps(snapshot,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')
    snapshot['snapshot_sha256']=hashlib.sha256(payload).hexdigest()
    bundle,excluded=build_bundle(snapshot)
    bundle['kaggle_import']=dict(schema_version='0.1.0',snapshot=snapshot)
    validate_bundle(bundle,args.season,'Regular Season',args.team_id)
    from calculate_metrics import analyze
    analysis=analyze(bundle,dict(player_id=args.player_id,season=args.season,season_type='Regular Season',team_id=args.team_id))
    args.out.mkdir(parents=True,exist_ok=True);(args.out/'raw').mkdir()
    (args.out/'raw/kaggle_selection.json').write_bytes(payload)
    write_json(args.out/'data_bundle.json',bundle)
    write_json(args.out/'kaggle_import_audit.json',dict(status='ok',dataset_url=DATASET,dataset_version=args.dataset_version,
        snapshot_date=args.snapshot_date,player=analysis['player'],sample=analysis['sample'],files=files,excluded=excluded,
        metrics_available=sum(m['status']=='ok' for m in analysis['metrics']),
        raw_selection_note='Filtered original CSV rows retained; full CSV SHA256 recorded. Selected JSON is not a byte-for-byte copy of full source CSV.'))
    return args.out


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--csv-dir',required=True,type=Path);p.add_argument('--player-id',required=True,type=int)
    p.add_argument('--bref-key',required=True);p.add_argument('--season',required=True)
    p.add_argument('--season-type',default='Regular Season',choices=['Regular Season','Playoffs'])
    p.add_argument('--team-id',default=0,type=int);p.add_argument('--dataset-version',default=1,type=int)
    p.add_argument('--snapshot-date',required=True,help='Uploader-declared export date, YYYY-MM-DD; not current date')
    p.add_argument('--reference-bundle',type=Path,help='Optional matching official team baseline; required for validated On/Off')
    p.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    try:
        datetime.strptime(args.snapshot_date,'%Y-%m-%d')
        print(run(args));return 0
    except (DataError,OSError,ValueError,KeyError) as exc:
        print('ERROR: '+str(exc),file=sys.stderr);return 2


if __name__=='__main__':raise SystemExit(main())
