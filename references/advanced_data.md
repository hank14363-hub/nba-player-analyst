# v0.4 新数据定义与兼容规则

## NBA MIN 特殊返回

实际核验日期：2026-10-12。leaguedashplayerstats 的 Advanced/Scoring 请求 PerMode=Totals 时，坎宁安 MIN 返回 35.0，而 Base 为赛季总分钟 2451.9966666666664、GP=70。保留原始行。仅在 NBA endpoint 已登记且 GP 相同、MIN×GP 与总分钟符合一位小数舍入容差时接受场均解释；Scoring 的 FGM/FGA 若提供，还需与 Base 一致。不能对未知来源自动假设 MIN 的单位。

## 真正 On/Off

可选 --on-off-team-id 调用 teamplayeronoffsummary，MeasureType=Advanced、PerMode=Totals。解析 PlayersOnCourtTeamPlayerOnOffSummary 与 PlayersOffCourtTeamPlayerOnOffSummary；VS_PLAYER_ID 转为 PLAYER_ID，保留原字段、COURT_STATUS、TEAM_ID 与分钟。

输入表 player_onoff，对应来源 P_ONOFF（per_mode=Totals），必须登记 team_id、sample_scope=full_team_season、metric_definition=team_oncourt。每名球员/球队只允许一行 On、一行 Off；On 分钟匹配球员样本，On+Off 分钟匹配同样本 team_base.MIN（球队场上分钟，不能使用五名球员分钟之和）。容差两分钟只处理来源舍入差异。

新增 ONOFF_ON_OFF_RATING、ONOFF_ON_DEF_RATING、ONOFF_ON_NET_RATING 及 OFF 对应字段；ON_OFF_DIFFERENTIAL=On净效率−Off净效率，ON_OFF_OFF_DIFFERENTIAL=On进攻−Off进攻，ON_OFF_DEF_DIFFERENTIAL=On失分−Off失分。防守差为正表示在场时失分更多，不是防守改善。不能用全队平均代替 Off；未调整对手、队友和比赛情境，差值不是球员个人净贡献。

P_ADV 的 OFF_RATING/DEF_RATING/NET_RATING 只接受已登记 NBA Advanced 接口或明确核验 metric_definition=team_oncourt 的数据。第三方球员回合估计值禁止映射为在场球队表现。

## 追踪指标

来源均为 leaguedashptstats，PerMode=PerGame。TR_CATCH 登记 CATCH_SHOOT_FG_PCT、CATCH_SHOOT_FGA_PER_GAME、CATCH_SHOOT_EFG_PCT；TR_PULL 登记 PULL_UP_FG_PCT、PULL_UP_FGA_PER_GAME、PULL_UP_EFG_PCT；TR_DRIVE 登记 DRIVES_PER_GAME；TR_PASS 登记 POTENTIAL_AST_PER_GAME。

百分比使用提供者原始小数；场均出手数已舍入，不能相除或乘 GP 得到精确百分比或总数。命中率需对应正出手数，无出手时不把提供者零值解释成投射能力差。保留独立 GP，追踪覆盖与 Base 不同则注明差异。

接球与急停的 eFG 可以描述对应机会的结果，但位置、难度、空位程度不相同，不能直接比较为能力等级。这两类也不是全部出手的完整分区。
