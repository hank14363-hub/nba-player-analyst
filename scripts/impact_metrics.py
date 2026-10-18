"""Validate optional provider-defined impact estimates; never blend model scales."""
from datetime import date, datetime
import re
from common import DataError, digest, integer, number

SPECS = {
    'BREF': ('retrospective_box', [('BPM','bpm','per100_model'),('OBPM','obpm','per100_model'),('DBPM','dbpm','per100_model'),('VORP','vorp','replacement_value'),('WS','ws','win_shares'),('OWS','ows','win_shares'),('DWS','dws','win_shares'),('WS48','ws_per_48','ws_per48')]),
    'LEBRON': ('retrospective_adjusted', [('LEBRON','LEBRON','per100_model'),('O_LEBRON','O-LEBRON','per100_model'),('D_LEBRON','D-LEBRON','per100_model')]),
    'EPM': ('retrospective_adjusted', [('EPM','tot','per100_model'),('O_EPM','off','per100_model'),('D_EPM','def','per100_model')]),
    'EPM_HISTORICAL': ('historical_snapshot_unverified', [('EPM_HIST','tot','provider_epm_points'),('O_EPM_HIST','off','provider_epm_points'),('D_EPM_HIST','def','provider_epm_points')]),
    'DARKO': ('predictive_snapshot', [('DPM','dpm','per100_model'),('O_DPM','o_dpm','per100_model'),('D_DPM','d_dpm','per100_model')]),
}

def normalized_name(value):
    return re.sub(r'[^a-z]', '', str(value).lower())

def impact_context(bundle, player_id, player_name, totals, team_id):
    data = bundle.get('impact_data')
    if data is None:
        return None
    if not isinstance(data,dict) or data.get('schema_version') != '0.1.0':
        raise DataError('impact_data requires schema_version=0.1.0')
    datasets=data.get('datasets')
    if not isinstance(datasets,list) or not datasets:
        raise DataError('impact_data.datasets must be nonempty')
    out=[];seen=set()
    for d in datasets:
        family=d.get('family');spec=SPECS.get(family)
        if spec is None or family in seen:
            raise DataError('Unknown or duplicate impact family')
        seen.add(family)
        if d.get('season') != bundle['season'] or d.get('season_type') != bundle['season_type']:
            raise DataError('Impact season or competition differs from requested sample')
        if integer(d.get('player_id'),'impact player_id') != player_id or integer(d.get('player_team_id',0),'impact team scope') != team_id:
            raise DataError('Impact identity or team-stint scope mismatch')
        if d.get('estimate_type') != spec[0] or not isinstance(d.get('model_version'),str) or not d['model_version'].strip():
            raise DataError('Impact model version/type must be explicit (unknown version allowed as text)')
        sid=d.get('source_id');source=bundle['sources'].get(sid,{})
        rows=d.get('raw_rows')
        if not isinstance(rows,list) or not rows or not all(isinstance(r,dict) for r in rows):
            raise DataError('Impact provider rows required')
        if source.get('status') != 'ok' or source.get('source_type')!='impact_data' or source.get('sha256_rows') != digest(rows):
            raise DataError('Impact raw rows/source hash mismatch')
        if source.get('season') != d['season'] or source.get('season_type') != d['season_type'] or source.get('model_version') != d['model_version'] or source.get('cutoff') != d.get('cutoff'):
            raise DataError('Impact source model/window metadata mismatch')
        for key in ('provider','url','retrieved_at'):
            if not isinstance(source.get(key),str) or not source[key].strip():raise DataError('Impact source lacks '+key)
        try:
            if datetime.fromisoformat(source['retrieved_at'].replace('Z','+00:00')).tzinfo is None:raise ValueError()
        except ValueError as exc:raise DataError('Impact collection time requires timezone') from exc
        selector=d.get('selector')
        if not isinstance(selector,dict) or not selector:raise DataError('Explicit provider row selector required')
        matches=[r for r in rows if all(str(r.get(k))==str(v) for k,v in selector.items())]
        if len(matches)!=1:raise DataError('Impact selector must resolve exactly one row, never sum stints or select duplicates')
        row=matches[0]
        name_key={'BREF':'name_display','LEBRON':'player_name','DARKO':'player_name','EPM':'player_name','EPM_HISTORICAL':'player_name'}[family]
        if family in ('EPM','EPM_HISTORICAL'):
            if family=='EPM':
                from import_epm import validate_import
            else:
                from historical_epm import validate_import
            from common import normalize_name
            validate_import(bundle)
            if normalize_name(row.get(name_key,'')) != normalize_name(player_name):raise DataError('EPM provider exact name mapping mismatch')
        elif normalized_name(row.get(name_key)) != normalized_name(player_name):raise DataError('Impact provider name mapping mismatch')
        if family=='BREF':
            if selector.get('provider_player_key') != d.get('provider_player_key') or not d.get('provider_player_key'):raise DataError('BRef identity mapping required')
            if source.get('table_id') != ('advanced' if bundle['season_type']=='Regular Season' else 'advanced_post'):raise DataError('Wrong BRef competition table')
        else:
            if integer(row.get('nba_id'),'provider nba_id') != player_id:raise DataError('Provider NBA identity mismatch')
        cutoff=d.get('cutoff')
        if family=='EPM_HISTORICAL':
            if row.get('season')!=bundle['season'] or row.get('as_of')!=cutoff or row.get('sample_scope')!='unverified':
                raise DataError('Historical EPM raw scope/date mismatch')
            sample=dict(GP=None,MIN=None,minutes_difference=None,coverage='历史快照；场次、总分钟、估计类型和比赛范围未核验，不作为整季Actual EPM或已验证预测。')
        elif family=='DARKO':
            try:
                stamp=date.fromisoformat(cutoff)
                start=int(bundle['season'][:4]);end=start+1
                if not date(start,7,1)<=stamp<=date(end,6,30):raise ValueError()
            except (TypeError,ValueError) as exc:raise DataError('DARKO requires historical cutoff within target season') from exc
            if str(row.get('as_of'))!=cutoff or str(row.get('season'))!=bundle['season']:
                raise DataError('DARKO raw date/season mismatch; current rating cannot substitute')
            sample=dict(GP=None,MIN=None,minutes_difference=None,coverage='Career-weighted prediction; no single-season minute coverage')
        else:
            if family=='LEBRON' and row.get('Season')!=bundle['season']:raise DataError('LEBRON raw season mismatch')
            if family=='EPM' and (row.get('season')!=bundle['season'] or row.get('season_type')!='Regular Season' or row.get('estimate_type')!='actual' or cutoff is not None):raise DataError('EPM must be a matching Actual full-season estimate')
            gp=number(row.get('games'),optional=family!='EPM') if family in ('BREF','EPM') else None
            mins=number(row.get('mp') if family=='BREF' else row.get('minutes') if family=='EPM' else row.get('Minutes'),'impact minutes')
            tolerance=(.5*10**(-integer(d.get('minutes_decimals'),'EPM minutes precision'))+1e-9) if family=='EPM' else .51 if family=='BREF' else .1
            if gp is not None and gp!=totals['GP']:raise DataError('Impact GP mismatch')
            if abs(mins-totals['MIN'])>tolerance:raise DataError('Impact minute coverage mismatch')
            sample=dict(GP=gp,MIN=mins,minutes_difference=mins-totals['MIN'],coverage='GP and reference total minutes matched at declared export precision' if family=='EPM' else 'Season sample checked against official total; LEBRON games not supplied' if gp is None else 'GP and rounded total minutes matched')
        values={mid:number(row.get(key),family+'.'+key,optional=True) for mid,key,_ in spec[1]}
        if not any(v is not None for v in values.values()):raise DataError('No impact values supplied')
        components={'BREF':('BPM','OBPM','DBPM',.151),'LEBRON':('LEBRON','O_LEBRON','D_LEBRON',.001),'DARKO':('DPM','O_DPM','D_DPM',.151),'EPM':('EPM','O_EPM','D_EPM',.15+1e-12),'EPM_HISTORICAL':('EPM_HIST','O_EPM_HIST','D_EPM_HIST',.15+1e-12)}[family]
        total,off,defense,tol=components
        if all(values[k] is not None for k in (total,off,defense)) and abs(values[total]-values[off]-values[defense])>tol:
            raise DataError('Impact components fail provider rounding tolerance')
        if family=='BREF' and all(values[k] is not None for k in ('WS','OWS','DWS')) and abs(values['WS']-values['OWS']-values['DWS'])>.151:raise DataError('Win Shares components mismatch')
        caveats=d.get('caveats')
        if not isinstance(caveats,list) or not caveats or not all(isinstance(c,str) and c for c in caveats):raise DataError('Impact interpretation caveats required')
        out.append(dict(family=family,estimate_type=d['estimate_type'],model_version=d['model_version'],season=d['season'],season_type=d['season_type'],cutoff=cutoff,source_id=sid,values=values,sample=sample,caveats=caveats,uncertainty='Provider confidence intervals unavailable; signs do not establish statistical significance'))
    excluded=data.get('excluded',[])
    if not isinstance(excluded,list) or not all(isinstance(e,dict) and isinstance(e.get('reason'),str) and e.get('reason') for e in excluded):raise DataError('Invalid excluded impact records')
    return dict(status='ok',datasets=out,excluded=excluded,boundary='Provider-defined model estimates. No averaging, composite score, causal claims or ability ranking.')

def register_impact(ctx,add,metrics):
    if ctx is None:return
    for d in ctx['datasets']:
        for mid,key,unit in SPECS[d['family']][1]:
            add('IMPACT_'+mid,d['values'][mid],unit,[d['source_id']],d['family']+'.'+key+' / '+d['estimate_type'],'Provider field unavailable; never zero-filled')
            metrics[-1]['label']=mid+' · 提供者模型估计'
            if d['family']=='EPM_HISTORICAL':
                metrics[-1].update(label=mid+' · 历史 EPM 快照（口径待核验）',
                                   verification_status='archived_reading_only_scope_unverified',
                                   snapshot_date=d['cutoff'], caveats=list(d['caveats']))
            if d['values'][mid] is not None:
                metrics[-1]['display'] = (f"{d['values'][mid]:+.2f}" if unit in ('per100_model','provider_epm_points') else f"{d['values'][mid]:.3f}" if unit=='ws_per48' else f"{d['values'][mid]:.1f}")
        sample=d['sample']
        if d['family']=='BREF':
            add('IMPACT_BREF_GP',sample['GP'],'count',[d['source_id']],'Provider sample games')
            add('IMPACT_BREF_MIN',sample['MIN'],'minutes',[d['source_id']],'Provider rounded minutes')
        if d['family']=='LEBRON':
            add('IMPACT_LEBRON_MIN',sample['MIN'],'minutes',[d['source_id']],'Provider relay minutes')
            add('IMPACT_LEBRON_MIN_GAP_SECONDS',abs(sample['minutes_difference'])*60,'seconds',[d['source_id'],'P_BASE'],'abs(provider minutes - official minutes) * 60')
        if d['family']=='EPM':
            add('IMPACT_EPM_GP',sample['GP'],'count',[d['source_id']],'Provider export games matched to reference totals')
            add('IMPACT_EPM_MIN',sample['MIN'],'minutes',[d['source_id']],'Provider export total minutes at declared precision')
