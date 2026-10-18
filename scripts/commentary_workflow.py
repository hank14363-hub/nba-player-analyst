"""Research records describe actual human/agent reading, never automatic verification."""
from datetime import datetime
from urllib.parse import urlsplit

def template(analysis):
    name=analysis['player']['name'];season=analysis['sample']['season']
    return dict(schema_version='0.1.0',status='pending',reason='',identity=dict(player_id=analysis['player']['id'],season=season,season_type=analysis['sample']['season_type']),queries=[],articles=[],
                suggested_queries=[f'{name} {season} season analysis role offense defense',f'{name} {season} film breakdown scouting'],
                note='Suggested queries are not completed searches. Record actual tool/time and original-page reading before registering a source.')

def validate(record,sources,analysis=None):
    if not isinstance(record,dict):return ['commentary_research must be an object']
    errors=[]
    if analysis is not None:
        expected=dict(player_id=analysis['player']['id'],season=analysis['sample']['season'],season_type=analysis['sample']['season_type'])
        if record.get('identity')!=expected:errors.append('Commentary research identity/season differs from current report')
    if record.get('schema_version')!='0.1.0':errors.append('Unknown commentary research schema')
    status=record.get('status')
    if status not in ('pending','complete','limited','skipped'):errors.append('Unknown commentary research status')
    if status in ('limited','skipped') and not str(record.get('reason','')).strip():errors.append('Limited/skipped commentary needs a concrete reason')
    def stamp(value):
        try:return datetime.fromisoformat(value.replace('Z','+00:00')).tzinfo is not None
        except (ValueError,TypeError,AttributeError):return False
    queries=record.get('queries');articles=record.get('articles')
    if not isinstance(queries,list) or not all(isinstance(q,dict) for q in queries):return errors+['Commentary queries must be objects']
    if not isinstance(articles,list) or not all(isinstance(a,dict) for a in articles):return errors+['Commentary articles must be objects']
    for q in queries:
        if not all(isinstance(q.get(k),str) and q[k].strip() for k in ('query','tool')) or not stamp(q.get('searched_at')):errors.append('Search record needs query, actual tool and timezone timestamp')
    for a in articles:
        state=a.get('status');url=a.get('url','')
        if not isinstance(url,str) or urlsplit(url).scheme not in ('http','https') or not urlsplit(url).netloc:errors.append('Article needs an HTTP(S) original URL')
        if not stamp(a.get('accessed_at')):errors.append('Article needs timezone access timestamp')
        if state not in ('read','blocked','irrelevant','metadata_missing'):errors.append('Unknown article reading status')
        if not isinstance(a.get('reason'),str) or not a['reason'].strip():errors.append('Article needs reading note or exclusion reason')
        if state=='read':
            s=sources.get(a.get('source_id'),{})
            if s.get('source_type')!='commentary_article' or s.get('status')!='ok' or s.get('direct_page_verified') is not True or s.get('url')!=url:errors.append('Read article must match a directly verified registered source')
            if any(not isinstance(s.get(k),str) or not s[k].strip() for k in ('author','title','published_at','sample_scope','usage')):errors.append('Read article source needs author/title/date/sample scope and usage')
    if status=='complete' and not any(a.get('status')=='read' for a in articles):errors.append('Complete commentary research needs an original article read')
    if status=='limited' and not queries and not articles and record.get('reason') not in ('search_tool_unavailable','user_requested_offline'):
        errors.append('Limited commentary needs attempts, or an explicit tool/offline limitation')
    return errors
