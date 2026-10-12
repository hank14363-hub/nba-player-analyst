# 指标定义与计算限制

所有自算指标用未四舍五入的赛季总计；展示时再格式化。raw value 使用小数比例，RTS_PP 例外使用百分点。

| ID | 公式 / 来源 | 必要限制 |
|---|---|---|
| TS_PCT | PTS / [2 × (FGA + 0.44 × FTA)] | 0.44 为统计近似，不是逐回合精确消耗；极小样本可能超过100% |
| EFG_PCT | (FGM + 0.5 × FG3M) / FGA | 只修正三分价值，不包含罚球 |
| FG3_PCT | FG3M / FG3A | 同时报告出手数 |
| FG3A_RATE | FG3A / FGA | 三分出手占比，不是三分得分占比 |
| FT_RATE | FTA / FGA | 本项目明确定义为罚球出手比，不是 FTM/FGA |
| AST_TOV | AST / TOV | TOV=0 时为缺失，不生成无穷大，不直接代表组织能力 |
| LEAGUE_TS_PCT | Σ球队PTS / [2 × (Σ球队FGA + 0.44 × Σ球队FTA)] | 完整同赛季同类型联盟球队总计，不平均球员TS |
| RTS_PP | 100 × (TS_PCT - LEAGUE_TS_PCT) | 单位：百分点，而非相对百分比增幅 |
| USG_PCT / AST_PCT | 直接读取已核验来源的高阶字段 | 不从个人赛季基础表伪造或套用不一致估计公式 |
| PTS/REB/AST/TOV_PER75 | 来源每100回合计数 × 0.75 | 不按每36分钟估算，不乘百分比或球队效率 |
| PCT_AST_FGM | 来源：全部命中球中受助攻比例 | 分母不是出手数 |
| PCT_UAST_FGM | 来源：全部命中球中非受助攻比例 | 不是单打占比或进攻创造分值 |
| PCT_AST_3PM | 来源：三分命中球受助攻比例 | 不是接球三分命中率 |
| ONCOURT_*RATING | 来源：球员在场时球队每100回合效率 | 不是个人创造/失分，绝不是 on/off 差值 |
| TEAM_*RATING / TEAM_PACE / TEAM_AST_PCT | 来源：目标球队高阶表 | 只能描述球队环境，不能单独识别战术体系 |
| TEAM_FG3A_RATE | 目标球队 FG3A/FGA | 不等于真实空间牵制水平 |

GP 与 MIN 总样本、FGA/FG3A/FTA 出手量和基础场均同时输出。球队资料和球员资料不混用单位。

## 校验

检查非负计数、整数总计、命中数不大于出手数、三分不大于总投篮、PTS=2×FGM+FG3M+FTM。缺失字段不拿0补齐。AST/TOV等分母为0时输出 null 与原因。

检查球员高阶/得分构成的 GP、MIN 与基础表匹配；NBA Advanced/Scoring 的 MIN 场均特例见 advanced_data.md。每100回合表 GP 与基础表一致；追踪表覆盖差异另行标记，而不强行改造成同样场数。

官方 TS_PCT 与本项目复算相差超过0.2个百分点时警告，检查样本或计算口径，不覆盖差异。此阈值是排查提示，不是统计显著性检验。

导入比例大于1时不会自动除100“修好”，因为这可能隐藏单位错误。USG%等字段缺失时不编造。

## 暂无的数据

v0.4 的 ON_OFF_DIFFERENTIAL 在匹配 On/Off 数据存在且核验通过时生成；否则为 missing。来源与公式见 advanced_data.md。DEFENSIVE_ABILITY_SCORE 仍保留为 missing，不把团队失分或抢断封盖变成个人评分。

来源术语参考：https://www.nba.com/stats/help/glossary 。自定义的 rTS 命名、输出单位、质量阈值、评分限制属于本项目设计，不应称作 NBA 官方评分标准。