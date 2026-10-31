"""Check that photo work reached an actual asset or a documented fallback outcome."""
import argparse,json
from datetime import datetime
from pathlib import Path
import re
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit
from common import read_json

PROTOCOL='0.2.0'
SLOTS={'cover','scoring','creation','defense'}

def original_key(candidate):
    """Deduplicate known original pages; never treat a CDN/size retry as a new source."""
    if candidate.get('asset_key'):
        return str(candidate['asset_key']).strip()
    parts=urlsplit(candidate['page_url'])
    host=(parts.hostname or '').lower().removeprefix('www.')
    path=unquote(parts.path).rstrip('/')
    if host=='flickr.com':
        match=re.match(r'/photos/[^/]+/(\d+)(?:/|$)',path)
        if match:return 'flickr:'+match.group(1)
    if host=='commons.wikimedia.org':
        query=dict(parse_qsl(parts.query))
        title=path.removeprefix('/wiki/') if path.startswith('/wiki/') else query.get('title','')
        if title.startswith('File:'):return 'commons:'+title.replace('_',' ')
    query=[(key,value) for key,value in parse_qsl(parts.query)
           if not key.lower().startswith('utm_') and key.lower() not in {'fbclid','spm','spm_id_from','vd_source'}]
    return urlunsplit((parts.scheme.lower(),host,path,urlencode(sorted(query)),''))

def audit_coverage(record,items,add):
    """Protocol v2: inspect declared use, not a universal picture/search quota."""
    needs=record.get('needs')
    if not isinstance(needs,list) or not needs:
        add('media_needs_missing','新版日志需逐用途记录covered/unavailable/not_needed；不强制每个章节配图。')
        return
    slots=set();used=set()
    for need in needs:
        if not isinstance(need,dict):
            add('media_need_invalid','图片用途记录应为对象。');continue
        slot=need.get('slot');status=need.get('status');mids=need.get('media_ids')
        if not isinstance(slot,str) or slot not in SLOTS or slot in slots or not isinstance(status,str) or status not in {'covered','unavailable','not_needed'} or not need.get('reason'):
            add('media_need_invalid','用途须唯一、状态须已处理，并记录实际理由；pending不是完成。')
            continue
        slots.add(slot)
        if not isinstance(mids,list) or any(not isinstance(mid,str) for mid in mids):
            add('media_need_invalid','media_ids须为实际媒体ID列表。');continue
        if status=='covered':
            if not mids or any(mid not in items or items[mid].get('slot')!=slot for mid in mids):
                add('media_need_unlinked','covered用途必须对应同槽位实际媒体。')
            for mid in mids:
                if mid not in items:continue
                key=items[mid].get('sha256')
                if key in used:add('media_duplicate_asset','不能把同一文件重复填充用途来制造配图覆盖。')
                used.add(key)
        elif mids:
            add('media_need_unlinked','未覆盖或不需要的用途不应挂载采用媒体。')
        if status=='unavailable' and record.get('status')=='complete':
            add('media_complete_with_gap','还有希望采用但无法取得的图片用途，应标limited并保留原因。')
    covered={mid for need in needs if isinstance(need,dict) and need.get('status')=='covered' and isinstance(need.get('media_ids'),list)
             for mid in need.get('media_ids',[]) if isinstance(mid,str)}
    if set(items)-covered:add('media_asset_without_need','实际媒体未关联图片用途及选择理由。')
    adopted={c.get('media_id') for c in record.get('candidates',[]) if isinstance(c,dict) and c.get('decision')=='adopted' and isinstance(c.get('media_id'),str)}
    if set(items)-adopted:add('media_asset_without_adoption','实际媒体缺少原页采用记录。')

def audit_adoption(candidate,item,analysis,add):
    checks=candidate.get('verification',{})
    if not isinstance(checks,dict):checks={}
    environment=checks.get('identity')=='environment_only'
    if checks.get('identity') not in {'verified','environment_only'} or any(checks.get(k)!='verified' for k in ('rights','visual')):
        add('media_verification_incomplete','采用前实际核对身份、权利与画面；下载成功或搜索摘要不能代替。')
    relation=checks.get('season_relation');date=checks.get('date')
    if relation not in {'in_scope','historical','other_event','unknown'} or date not in {'capture_verified','upload_only','unknown'}:
        add('media_date_scope_missing','分别记录拍摄/上传日期状态及与分析赛季的关系。')
    if relation=='in_scope':
        expected='playoffs' if analysis['sample']['season_type']=='Playoffs' else 'regular_season'
        if date!='capture_verified' or checks.get('event_type')!=expected:
            add('media_season_unverified','同赛季比赛素材须核实拍摄日期和比赛类型，不能以球衣或上传日期认定。')
    if environment and item and item.get('slot')=='cover':
        add('media_environment_as_cover','无法确认主体的环境图不能充当球员封面。')
    if item and (relation!='in_scope' or environment):
        disclosure=candidate.get('disclosure')
        if not isinstance(disclosure,str) or not disclosure.strip() or disclosure not in item.get('caption',''):
            add('media_visible_disclosure_missing','历史/其他活动/日期未知/环境图的实际限制须写入可见caption。')

def timestamp(value):
    try:return bool(datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo)
    except (AttributeError,TypeError,ValueError):return False

def audit(run_dir,analysis):
    findings=[]
    def add(code,message):findings.append(dict(code=code,location='media_research.json',message=message))
    path=run_dir/'media_research.json'
    if not path.exists():
        if analysis.get('request',{}).get('media_research_audit') and analysis['data_kind']!='synthetic':
            add('media_research_missing','未登记图片检索或明确跳过原因；建议查询不代表已执行。')
        return dict(status='review_required' if findings else 'not_required',findings=findings)
    record=read_json(path)
    if not isinstance(record,dict):
        add('media_record_invalid','图片检索日志须为对象。')
        return dict(status='review_required',findings=findings)
    protocol=record.get('schema_version')
    if protocol not in (None,'0.1.0',PROTOCOL):add('media_schema_unsupported','不支持的图片检索日志版本。')
    v2=protocol==PROTOCOL or analysis.get('request',{}).get('media_research_protocol')==PROTOCOL
    if v2 and protocol!=PROTOCOL:add('media_protocol_missing','新研究需使用0.2.0实际检索日志；计划模板不能替代执行记录。')
    identity=dict(player_id=analysis['player']['id'],season=analysis['sample']['season'],season_type=analysis['sample']['season_type'])
    if record.get('identity')!=identity:add('media_identity_mismatch','检索身份与本次研究不一致。')
    status=record.get('status')
    if status not in ('complete','limited','skipped') or not record.get('reason'):
        add('media_record_invalid','需要complete/limited/skipped及本次实际处理说明。')
    if status=='skipped':
        if record.get('scope') not in ('offline','data_only','user_no_images','narrow_scope'):
            add('media_skip_scope_missing','跳过应记录离线、纯数据、用户无需图片或窄范围请求。')
        return dict(status='review_required' if findings else 'pass',findings=findings)
    candidates=record.get('candidates',[]);queries=record.get('queries',[])
    if not isinstance(candidates,list) or not isinstance(queries,list):
        add('media_record_invalid','queries与candidates必须为实际执行记录列表。')
        return dict(status='review_required',findings=findings)
    for q in queries:
        if not isinstance(q,dict) or not q.get('query') or not q.get('tool') or not timestamp(q.get('searched_at')):
            add('media_query_invalid','查询需要实际工具和带时区时间。')
    content=read_json(run_dir/'media_content.json') if (run_dir/'media_content.json').exists() else dict(items=[])
    items={m['id']:m for m in content.get('items',[])};adopted=[]
    urls=set()
    for c in candidates:
        if not isinstance(c,dict) or not c.get('page_url') or not c.get('decision') or not c.get('reason') or not timestamp(c.get('accessed_at')):
            add('media_candidate_invalid','候选需要原页、实际查阅时间、决定和原因。');continue
        try:urls.add(original_key(c))
        except ValueError:add('media_candidate_invalid','候选原页URL无法解析。')
        if v2 and (not isinstance(c['decision'],str) or c['decision'] not in {'adopted','rejected','blocked','not_downloaded','duplicate'}):
            add('media_decision_invalid','候选须有明确采用、排除、受限、未下载或重复状态。')
        if c['decision']=='adopted':
            adopted.append(c)
            item=items.get(c.get('media_id'))
            sid=c.get('source_id');source=analysis['sources'].get(sid,{})
            if not item or sid not in item.get('source_ids',[]):add('media_adoption_unlinked','采用记录没有对应实际媒体和来源。')
            for field in ('credit','license','license_url','media_date','changes'):
                if not source.get(field):add('media_source_incomplete','采用项来源缺少'+field+'；日期未知应明确写未知。')
            if source.get('url')!=c['page_url']:add('media_source_page_mismatch','采用项原页与来源登记不符。')
            if v2:audit_adoption(c,item,analysis,add)
    if v2:
        audit_coverage(record,items,add)
        if status=='limited' and not record.get('stop_reason'):
            add('media_limited_stop_unexplained','部分完成或受限时须记录真实停止原因和剩余缺口。')
    if status=='complete' and not adopted:add('media_complete_without_asset','没有登记并采用可嵌入图片，不能标complete。')
    if not adopted:
        tool_limited=(record.get('limitation')=='search_and_browse_unavailable' and
                      bool(record.get('stop_reason')) and not candidates and not queries)
        search_empty=(record.get('limitation')=='no_relevant_candidates' and bool(queries) and
                      bool(record.get('stop_reason')) and not candidates)
        if tool_limited or search_empty:
            pass # No actual retrieval route: record the limitation, never fabricate attempts.
        elif len(urls)<2:
            add('media_fallback_not_attempted','只有一个失败/排除候选；应继续正常公开检索另一独立素材或来源，不能把一次下载失败写成整体不可用。')
        elif not record.get('stop_reason'):
            add('media_fallback_stop_unexplained','候选均未采用时说明后续检索结果及实际停止原因。')
    if items:
        from book_media import load_media
        load_media(run_dir,analysis)
    return dict(status='review_required' if findings else 'pass',adopted_count=len(adopted),candidate_count=len(candidates),findings=findings)

def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--run-dir',type=Path,required=True)
    args=parser.parse_args()
    a=read_json(args.run_dir/'analysis.json');a['sources'].update(read_json(args.run_dir/'sources.json')['sources'])
    result=audit(args.run_dir,a);print(json.dumps(result,ensure_ascii=False,indent=2))
    return int(result['status']=='review_required')
if __name__=='__main__':raise SystemExit(main())
