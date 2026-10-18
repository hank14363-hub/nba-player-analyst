"""Bounded public impact collection; failures never erase official base evidence."""
from copy import deepcopy
import hashlib
import json
from urllib.parse import quote
from common import DataError, normalize_name, now_iso
from calculate_metrics import counts
from collect_impact import parse_bref, parse_darko, validate_provider_rows, dataset, ProviderError
from impact_metrics import impact_context

def collect(bundle,pid,name,timeout=20,cutoff=None,get=None):
    result=deepcopy(bundle);records=[];blobs={};accepted=[];excluded=[]
    if bundle['data_kind']=='synthetic' or bundle['season_type']!='Regular Season' or bundle.get('player_team_id',0):
        audit=dict(status='scope_excluded',requests=[],reason='Public adapters support full regular seasons only; no stint or playoff proxy.')
        result['impact_collection']=audit;return result,audit,blobs
    if get is None:
        try:
            import requests
            get=requests.get
        except ImportError:
            audit=dict(status='dependency_missing',requests=[],reason='Install project requirements.txt for public impact collection.')
            result['impact_collection']=audit;return result,audit,blobs
    season=bundle['season'];year=int(season[:4])+1
    urls={'BREF':f'https://www.basketball-reference.com/leagues/NBA_{year}_advanced.html',
          'LEBRON':'https://nbarapm.com/search/lebron?allow_empty=1&player_name='+quote(name),
          'EPM':f'https://dunksandthrees.com/epm/actual?season={year}'}
    if cutoff:urls['DARKO']='https://www.darko.app/?asof='+cutoff
    base=next(r for r in bundle['tables']['player_base'] if r['PLAYER_ID']==pid)
    totals=counts(base,'impact reference totals')
    for family,url in urls.items():
        rec=dict(family=family,url=url,retrieved_at=now_iso())
        try:
            response=get(url,timeout=timeout);rec.update(http_status=response.status_code,final_url=response.url)
            if response.status_code in (401,403) or any(v in response.url for v in ('/subscribe','/login')):
                raise ProviderError('access_restricted','Historical/provider access restricted; no workaround attempted')
            if response.status_code!=200:raise ProviderError('http_error','HTTP '+str(response.status_code))
            payload=response.content;path='raw/default_impact_'+family.lower()+('.json' if family=='LEBRON' else '.html')
            rec.update(raw_file=path,sha256=hashlib.sha256(payload).hexdigest());blobs[path]=payload
            if family=='EPM':raise ProviderError('unverified_schema','Actual EPM online values not parsed; use import_epm.py with an authorized offline Actual export')
            rows=parse_bref(payload) if family=='BREF' else json.loads(payload) if family=='LEBRON' else parse_darko(payload,cutoff,season)
            if family in ('BREF','DARKO'):validate_provider_rows(family,rows)
            key=None
            if family=='BREF':
                from bs4 import BeautifulSoup
                page=BeautifulSoup(payload,'html.parser')
                heading=' '.join(node.get_text(' ',strip=True) for node in (page.title,page.h1) if node)
                if season not in heading:raise ProviderError('sample_unavailable','BRef page heading does not confirm requested season')
                keys={r['provider_player_key'] for r in rows if normalize_name(r.get('name_display',''))==normalize_name(name)}
                if len(keys)!=1:raise ProviderError('identity_unverified','Cannot uniquely map official full name to BR slug')
                key=next(iter(keys))
            d,s=dataset(family,rows,rec,pid,name,season,key,cutoff if family=='DARKO' else None)
            trial=deepcopy(result);trial['sources'][d['source_id']]=s
            trial['impact_data']=dict(schema_version='0.1.0',datasets=[d],excluded=[])
            impact_context(trial,pid,name,totals,0)  # Per-family identity, season, MIN and model validation.
            accepted.append(d);result['sources'][d['source_id']]=s;rec['status']='validated'
        except Exception as exc:
            # Optional collection failures are recorded, not substituted or fatal to base analysis.
            rec.update(status='excluded',category=getattr(exc,'category','transport_or_data_error'),reason=str(exc))
            excluded.append(dict(family=family,reason=rec['reason']))
        records.append(rec)
    if accepted:result['impact_data']=dict(schema_version='0.1.0',datasets=accepted,excluded=excluded)
    audit=dict(status='partial' if accepted and excluded else 'validated' if accepted else 'unavailable',requests=records,
               reason='DARKO skipped without explicit --impact-cutoff; predictive snapshot never substitutes for season actuals.' if not cutoff else '',validated_families=[d['family'] for d in accepted])
    result['impact_collection']=audit
    result.setdefault('warnings',[]).extend('Impact '+e['family']+': '+e['reason'] for e in excluded)
    return result,audit,blobs
