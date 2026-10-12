"""Optional public impact collectors. One request/provider; no access-limit workaround."""
import argparse, hashlib, json, sys
from pathlib import Path
from urllib.parse import quote
from common import DataError, digest, now_iso, read_json, write_json

def parse_bref(payload, table_id='advanced'):
    from bs4 import BeautifulSoup
    soup=BeautifulSoup(payload,'html.parser');table=soup.find('table',id=table_id)
    if table is None:raise DataError('BRef requested competition table absent')
    rows=[]
    for tr in table.select('tbody tr'):
        name=tr.find(attrs={'data-stat':'name_display'})
        if name is None or not name.get('data-append-csv'):continue
        row={c.get('data-stat'):c.get_text(' ',strip=True) for c in tr.find_all(['td','th']) if c.get('data-stat')}
        row['provider_player_key']=name['data-append-csv'];rows.append(row)
    if not rows:raise DataError('Empty BRef table')
    return rows

def parse_darko(payload,cutoff,season):
    from bs4 import BeautifulSoup
    import re
    from datetime import date
    soup=BeautifulSoup(payload,'html.parser');text=soup.get_text(' ',strip=True)
    expected=date.fromisoformat(cutoff).strftime('%B %d, %Y').replace(' 0',' ')
    if 'DARKO as of '+expected not in text or season+' season' not in text:raise DataError('DARKO did not return requested historical date/season')
    rows=[];seen=set()
    for a in soup.select('a.player-link[href]'):
        match=re.fullmatch(r'/player/(\d+)\?asof='+re.escape(cutoff),a['href'])
        tr=a.find_parent('tr')
        if not match or tr is None:continue
        pid=int(match[1])
        name=a.select_one('.player-text > span')
        row=dict(nba_id=pid,player_name=name.get_text(' ',strip=True) if name else '',as_of=cutoff,season=season)
        for key,css in [('dpm','dpm'),('o_dpm','o-dpm'),('d_dpm','d-dpm')]:
            cell=tr.select_one('.leaderboard-cell--'+css)
            figure=cell.select_one('.dpm-figure') if cell else None
            row[key]=(figure or cell).get_text(' ',strip=True) if cell else None
        twins=[r for r in rows if r['nba_id']==pid]
        if twins and twins[0]!=row:raise DataError('Conflicting duplicate DARKO rows')
        if not twins:rows.append(row)
        seen.add(pid)
    if not rows:raise DataError('DARKO historical visible rows absent')
    return rows

def dataset(family,rows,access,player_id,name,season,key=None,cutoff=None):
    sid='EXT_IMPACT_'+family
    model={'BREF':'BPM 2.0; provider Win Shares method','LEBRON':'LEBRON; revision not specified in relay','DARKO':'DARKO DPM; historical page model revision unspecified'}[family]
    kind={'BREF':'retrospective_box','LEBRON':'retrospective_adjusted','DARKO':'predictive_snapshot'}[family]
    if family=='BREF':selector={'provider_player_key':key}
    elif family=='LEBRON':selector={'nba_id':str(player_id),'Season':season}
    else:selector={'nba_id':player_id,'as_of':cutoff}
    if family=='BREF':
        matches=[r for r in rows if r['provider_player_key']==key]
        if len(matches)>1:
            totals=[r for r in matches if r.get('team_name_abbr')=='TOT' or r.get('team_name_abbr','').endswith('TM')]
            if len(totals)!=1:raise DataError('BRef needs one aggregate row, never combine team stints')
            selector['team_name_abbr']=totals[0]['team_name_abbr']
    caveats={
     'BREF':['整季技术统计模型；BPM零点为联盟平均，VORP使用替补基准；防守分量不能确认单防能力。','BRef助攻率、使用率定义不同，不覆盖NBA官方指标；保留页面公布精度。'],
     'LEBRON':['BBall Index 指标经nbarapm公开转引；原站导出与模型版本未随转引提供，方法需独立核验。','分钟需与官方样本核验；转引未提供场次和置信区间，不导入提供者排名。'],
     'DARKO':['指定日期的生涯加权预测，不是整季实际表现；历史页面如今取得，不保证模型版本等同当年发布版本。','只取历史DPM/Off/Def列，忽略Now与Since列；舍入可能导致分量之和与总值相差一位小数。']
    }[family]
    source=dict(provider={'BREF':'Basketball-Reference','LEBRON':'BBall Index via nbarapm public relay','DARKO':'DARKO (Kostya Medvedovsky)'}[family],url=access['url'],retrieved_at=access['retrieved_at'],status='ok',source_type='impact_data',season=season,season_type='Regular Season',per_mode='Provider model',sha256_rows=digest(rows),row_count=len(rows),sha256_raw=access['sha256'],raw_file=access.get('raw_file'),display_title={'BREF':'BPM / VORP / Win Shares 整季原表','LEBRON':'LEBRON 整季公开转引','DARKO':'DARKO 历史预测快照'}[family],usage='；'.join(caveats),cutoff=cutoff,model_version=model)
    if family=='BREF':source['table_id']='advanced'
    return dict(family=family,player_id=player_id,player_team_id=0,provider_player_key=key,season=season,season_type='Regular Season',estimate_type=kind,model_version=model,cutoff=cutoff,source_id=sid,raw_rows=rows,selector=selector,caveats=caveats),source

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--player-id',type=int,required=True);p.add_argument('--name',required=True)
    p.add_argument('--bref-key');p.add_argument('--cutoff');p.add_argument('--providers',nargs='+',choices=['BREF','LEBRON','DARKO'],default=['BREF'])
    p.add_argument('--out',type=Path,required=True);p.add_argument('--timeout',type=float,default=25)
    args=p.parse_args()
    try:
        import requests
        bundle=read_json(args.bundle);season=bundle['season']
        if bundle['season_type']!='Regular Season' or bundle.get('player_team_id',0)!=0:raise DataError('Public collector supports full regular seasons only')
        if 'BREF' in args.providers and not args.bref_key:raise DataError('--bref-key required, verify provider identity first')
        if 'DARKO' in args.providers and not args.cutoff:raise DataError('--cutoff required for DARKO')
        if args.out.exists() and any(args.out.iterdir()):raise DataError('Choose a new empty output directory')
        args.out.mkdir(parents=True,exist_ok=True);(args.out/'raw').mkdir(exist_ok=True)
        urls={'BREF':f'https://www.basketball-reference.com/leagues/NBA_{int(season[:4])+1}_advanced.html','LEBRON':'https://nbarapm.com/search/lebron?allow_empty=1&player_name='+quote(args.name),'DARKO':'https://www.darko.app/?asof='+str(args.cutoff)}
        records=[];datasets=[];excluded=[]
        for family in args.providers:
            access=dict(family=family,url=urls[family],retrieved_at=now_iso())
            try:
                r=requests.get(urls[family],timeout=args.timeout);access.update(status=r.status_code,final_url=r.url)
                if r.status_code!=200:raise DataError('HTTP '+str(r.status_code)+'; stopped')
                payload=r.content;access['sha256']=hashlib.sha256(payload).hexdigest()
                access['raw_file']='raw/impact_'+family.lower()+('.json' if family=='LEBRON' else '.html')
                (args.out/access['raw_file']).write_bytes(payload)
                rows=parse_bref(payload) if family=='BREF' else (json.loads(payload) if family=='LEBRON' else parse_darko(payload,args.cutoff,season))
                d,s=dataset(family,rows,access,args.player_id,args.name,season,args.bref_key,args.cutoff if family=='DARKO' else None)
                bundle['sources'][d['source_id']]=s;datasets.append(d)
            except (requests.RequestException,ValueError,DataError) as exc:
                access['error']=str(exc);excluded.append(dict(family=family,reason=str(exc)))
            records.append(access)
        write_json(args.out/'impact_access_audit.json',dict(requests=records,excluded=excluded))
        if not datasets:raise DataError('No usable impact dataset; audit saved')
        bundle['impact_data']=dict(schema_version='0.1.0',datasets=datasets,excluded=excluded)
        from calculate_metrics import analyze
        analyze(bundle,dict(player_id=args.player_id,player=None,season=season,season_type='Regular Season',team_id=0))
        write_json(args.out/'data_bundle.json',bundle)
        print(json.dumps(dict(status='validated_bundle',out=str(args.out.resolve()),families=[d['family'] for d in datasets]),ensure_ascii=False))
        return 0
    except (DataError,OSError,ImportError) as exc:
        print(str(exc),file=sys.stderr);return 2

if __name__=='__main__':raise SystemExit(main())
