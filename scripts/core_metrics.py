"""Role-aware cover metrics; editorial choices must refer to registered evidence."""
PRESETS={
 'creator':[('AST_PCT','组织覆盖 · AST%','在场期间队友命中球的助攻占比；不衡量机会质量'),
            ('PCT_UAST_FGM','自主终结结构','非受助攻命中 / 全部命中；分母不是出手'),
            ('DRIVES_PER_GAME','突破参与 / 场','官方追踪的场均突破次数；次数不证明突破成功'),
            ('PTS_PER75','得分产量 / 75回合','每百回合数据乘以四分之三；保留来源舍入')],
 'shooter':[('FG3_PCT','三分命中率','命中 / 三分出手；结合出手样本阅读'),
            ('FG3A_RATE','三分出手占比','三分出手 / 全部出手'),
            ('CATCH_SHOOT_EFG_PCT','接球投篮 eFG','官方追踪；不等于受助攻命中率'),
            ('TS_PCT','真实命中率','综合投篮和罚球结果')],
 'rebounder':[('OREB_PCT','前场篮板率','官方机会份额，不等于卡位能力'),
              ('DREB_PCT','后场篮板率','官方机会份额，受阵容影响'),
              ('REB_PER75','篮板产量 / 75回合','回合尺度产量'),
              ('TS_PCT','终结效率 · TS%','需结合机会来源与样本')],
 'scorer':[('PTS_PER75','得分产量 / 75回合','统一回合尺度'),
           ('PCT_UAST_FGM','自主终结结构','非受助攻命中 / 全部命中'),
           ('FT_RATE','罚球出手比','罚球出手 / 投篮出手'),
           ('TS_PCT','真实命中率','结果效率，不衡量难度')],
 'rotation':[('PTS_PER75','得分产量 / 75回合','统一回合尺度'),
             ('AST_PER75','助攻产量 / 75回合','结果产量，不等于阅读能力'),
             ('REB_PER75','篮板产量 / 75回合','结果产量，受角色影响'),
             ('TS_PCT','真实命中率','综合投篮和罚球结果')]}


def select_core(analysis, content=None):
    m={r['metric_id']:r for r in analysis['metrics']}
    if content and content.get('core_metrics'):
        return content['core_metrics']
    def v(k):return m.get(k,{}).get('value') if m.get(k,{}).get('status')=='ok' else None
    profile=analysis.get('comparison_context',{}).get('profile')
    if profile not in PRESETS:
        if v('USG_PCT') is not None and v('AST_PCT') is not None and v('USG_PCT')>=.25 and v('AST_PCT')>=.30:profile='creator'
        elif v('OREB_PCT') is not None and v('DREB_PCT') is not None and v('OREB_PCT')>=.08 and v('DREB_PCT')>=.18:profile='rebounder'
        elif v('FG3A_RATE') is not None and v('FG3A') is not None and v('FG3A_RATE')>=.45 and v('FG3A')>=200:profile='shooter'
        elif v('USG_PCT') is not None and v('USG_PCT')>=.25:profile='scorer'
        else:profile='rotation'
    choices=PRESETS[profile]+PRESETS['rotation']+[('GP','出场样本','样本信息，不是优势指标'),('MIN_PER_GAME','场均分钟','职责描述，不是能力评分')]
    out=[];seen=set()
    for mid,label,note in choices:
        if mid not in seen and m.get(mid,{}).get('status')=='ok':
            out.append(dict(metric_id=mid,label=label,note=note,claim_ids=[]));seen.add(mid)
        if len(out)==4:break
    # Very thin imports retain explicit N/A cards rather than inserting invented stats.
    for mid,label,note in PRESETS['rotation']:
        if len(out)==4:break
        if mid not in seen:out.append(dict(metric_id=mid,label=label,note=note,claim_ids=[]));seen.add(mid)
    return out
