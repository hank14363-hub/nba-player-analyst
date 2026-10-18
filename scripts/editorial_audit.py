"""Observable completeness signals; never a semantic or basketball truth score."""
from collections import Counter
from common import DataError

GENERIC={'结合任务与机会质量阅读结果。','把结论用于具体分工与回合核验。'}


def audit(content, analysis, claims, bundle=None):
    findings=[]
    def add(code, location, message):
        findings.append(dict(code=code,location=location,message=message))
    if analysis['data_kind']!='synthetic':
        research=content.get('commentary_research',{})
        cards=content.get('commentary_cards',[])
        if not isinstance(research,dict):research={'status':'pending'}
        if not isinstance(cards,list):cards=[]
        if not research and not cards:
            add('commentary_not_attempted','book_content.json','未登记球评检索、原文阅读或明确限制；完整研究应先检索阅读再写作。')
        elif research.get('status')=='pending':
            add('commentary_pending','book_content.json','球评记录仍为待执行，建议查询不代表实际搜索。')
        elif research:
            from commentary_workflow import validate as validate_commentary
            if validate_commentary(research,analysis['sources'],analysis):
                add('commentary_record_invalid','book_content.json','球评阅读记录不完整，需处理结构校验错误。')
            articles=research.get('articles',[])
            read_ids={r.get('source_id') for r in articles if isinstance(r,dict) and r.get('status')=='read'} if isinstance(articles,list) else set()
            used={c.get('source_id') for c in cards if isinstance(c,dict)}
            if read_ids-used:add('commentary_unwritten','book_content.json','已登记阅读的文章未形成观点回应卡；不采用时改记排除理由。')
    context=analysis.get('comparison_context',{})
    percentiles=analysis.get('percentile_context',{})
    if percentiles:
        cited={mid for c in claims.get('claims',[]) for mid in c.get('metric_ids',[])}
        missing=[g['family'] for g in percentiles.get('groups',[]) if any(e['status']=='ok' for e in g['entries']) and not any(e['percentile_metric_id'] in cited for e in g['entries'])]
        if missing:add('percentiles_unwritten','report.md / claims.json','已计算的高阶分布尚无正文解读：'+', '.join(missing)+'；需说明样本与解释边界。')
    impact=analysis.get('impact_context',{}) or {}
    if impact.get('status')=='ok':
        cited={mid for c in claims.get('claims',[]) for mid in c.get('metric_ids',[])}
        missing=[d['family'] for d in impact['datasets'] if not cited.intersection({'IMPACT_'+k for k,v in d['values'].items() if v is not None})]
        if missing:add('impact_unwritten','report.md / claims.json','已接入模型或归档读数尚未登记正文解读：'+', '.join(missing)+'；需解释结果与限制，样本分钟引用不替代模型分析。')
    if not impact and analysis['data_kind']!='synthetic' and analysis['request'].get('impact_policy') not in ('disabled','retained_only') and not (bundle or {}).get('impact_collection'):
        add('impact_not_attempted','data_bundle.json','未保留高阶采集记录或模型数据；需补采或说明离线/导入范围。')
    if context.get('status')=='ok':
        registered=any(any(mid.startswith('COHORT_') for mid in c.get('metric_ids',[])) for c in claims.get('claims',[]))
        if not registered:
            add('comparison_unwritten','report.md / claims.json','比较数据已计算，但没有登记引用同角色指标的解读；图表不是正文结论。')
    elif not context and bundle is not None and analysis['data_kind']!='synthetic':
        from player_comparisons import comparison_context
        try:
            comparison_context(bundle,analysis['player']['id'],analysis['request'].get('team_id',0))
        except DataError:
            pass
        else:
            # An explicit opt-out is intentional scope, not an omission.
            if analysis['request'].get('comparisons') is not False:
                add('comparison_not_enabled','analysis.json / request','已有数据可通过比较核验，但运行未启用比较；可离线补算，无需重新取数。')
    repeated=Counter()
    for d in content.get('dimensions',[]):
        location='dimension-'+str(d.get('dimension'))
        if not d.get('claim_ids'):
            add('dimension_without_claims',location,'该主题没有登记结论；确认是证据缺失还是写作遗漏，不要求补造判断。')
        for index,card in enumerate(d.get('reading_cards',[]),1):
            for field in ('interpretation','application','boundary'):
                value=card.get(field,'').strip()
                if value in GENERIC:
                    add('generic_reading_note',location+'/card-'+str(index)+'/'+field,'解读沿用通用套话，需写明本球员的任务、条件或验证方式。')
                if value:repeated[(field,value)]+=1
    for (field,value),count in repeated.items():
        if count>=3:
            add('repeated_reading_note','reading_cards/'+field,'多个主题重复同一句解读；检查能否改为主题具体说明或移到全局限制。')
    return dict(status='review_required' if findings else 'no_flags',semantic_truth_verified=False,findings=findings)
