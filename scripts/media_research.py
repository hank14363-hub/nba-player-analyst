"""Check that photo work reached an actual asset or a documented fallback outcome."""
import argparse,json
from datetime import datetime
from pathlib import Path
from common import read_json

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
        urls.add(c['page_url'])
        if c['decision']=='adopted':
            adopted.append(c)
            item=items.get(c.get('media_id'))
            sid=c.get('source_id');source=analysis['sources'].get(sid,{})
            if not item or sid not in item.get('source_ids',[]):add('media_adoption_unlinked','采用记录没有对应实际媒体和来源。')
            for field in ('credit','license','license_url','media_date','changes'):
                if not source.get(field):add('media_source_incomplete','采用项来源缺少'+field+'；日期未知应明确写未知。')
            if source.get('url')!=c['page_url']:add('media_source_page_mismatch','采用项原页与来源登记不符。')
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
