"""Interpret numeric order without reversing percentiles or inferring ability."""

PROTOCOL='0.2.0'
LOWER={'ADV_NBA_TOV_PCT','ADV_BREF_TOV_PCT','ONCOURT_DEF_RATING'}
NEUTRAL={'USG_PCT','AST_PCT','ADV_NBA_PACE','ADV_NBA_AST_RATIO',
         'ADV_NBA_OREB_PCT','ADV_NBA_DREB_PCT','ADV_NBA_REB_PCT',
         'ADV_BREF_3PAR','ADV_BREF_FTR','ADV_BREF_USG_PCT','ADV_BREF_AST_PCT',
         'ADV_BREF_ORB_PCT','ADV_BREF_DRB_PCT','ADV_BREF_TRB_PCT',
         'ADV_BREF_STL_PCT','ADV_BREF_BLK_PCT'}
HIGHER={'TS_PCT','EFG_PCT','AST_TOV','NBA_PIE','ONCOURT_OFF_RATING','ONCOURT_NET_RATING',
        'ADV_BREF_PER','ADV_BREF_TS','ADV_NBA_BALL_SECURITY','ADV_BREF_BALL_SECURITY'}


def describe(mid):
    if mid in LOWER:
        note='数值越高通常越不利；高数值百分位不是优势。'
        if mid=='ONCOURT_DEF_RATING':note+='这是在场球队失分，不是个人防守评分。'
        else:note+='解释失误时仍需考虑持球职责与传球风险。'
        return dict(polarity='lower_better',polarity_note=note)
    if mid in NEUTRAL:
        return dict(polarity='role_neutral',polarity_note='描述职责、机会、风格或环境；数值较高不自动代表能力更强。')
    if mid in HIGHER or (mid.startswith('IMPACT_') and not mid.endswith('_HIST')):
        note='在指标定义及样本条件下通常较高有利；不等于独立的个人能力或因果效果。'
        if mid.startswith('IMPACT_'):note+='模型/累计量限制仍保留，累计量受出勤影响。'
        return dict(polarity='higher_better',polarity_note=note)
    return dict(polarity='role_neutral',polarity_note='仅说明原始数值分布；解释方向需结合口径，不能按条长评定能力。')


def acknowledge(claim, entries):
    """Check declared direction for sensitive cited percentiles; not semantic proof."""
    problems=[]
    declarations=claim.get('percentile_interpretations',[])
    if not isinstance(declarations,list):return ['方向说明应为percentile_interpretations列表。']
    declared={}
    for row in declarations:
        if not isinstance(row,dict) or not isinstance(row.get('metric_id'),str):
            problems.append('方向说明需关联实际百分位指标。');continue
        mid=row['metric_id']
        if mid in declared:problems.append('同一百分位方向说明重复。')
        declared[mid]=row
    for mid in claim.get('metric_ids',[]):
        entry=entries.get(mid)
        if not entry:continue
        row=declared.get(mid)
        sensitive=entry.get('polarity') in {'lower_better','role_neutral'}
        if not row:
            if sensitive:problems.append(mid+'需要明确数值方向和解释边界。')
            continue
        if row.get('polarity')!=entry['polarity']:
            problems.append(mid+'的方向声明与登记指标相反或不符。')
        disclosure=row.get('disclosure')
        if not isinstance(disclosure,str) or not disclosure.strip() or disclosure not in claim.get('report_quote',''):
            problems.append(mid+'的方向说明须原文出现在正文结论中。')
    for mid in declared:
        if mid not in claim.get('metric_ids',[]) or mid not in entries:
            problems.append('方向说明引用未登记或本结论未采用的百分位：'+mid)
    return problems
