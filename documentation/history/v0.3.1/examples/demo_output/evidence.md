# 数据证据包（不是最终长文）: MVP Demo Guard

分析样本: 2024-25 / Regular Season
GP=60; MIN=1800
数据覆盖模式: core

> 合成测试数据，不是真实NBA球员或比赛数据；仅验证程序流程，不可用于真实实力结论。

## 已登记指标

| ID | Metric | Value | Sources |
|---|---|---:|---|
| GP | 出场场数 | 60 | [P_BASE] |
| MIN | 总出场分钟 | 1800.00 | [P_BASE] |
| FGA | 投篮出手总数 | 1000 | [P_BASE] |
| FG3A | 三分出手总数 | 450 | [P_BASE] |
| FTA | 罚球出手总数 | 300 | [P_BASE] |
| PTS_PER_GAME | 场均得分 | 23.33 | [P_BASE] |
| MIN_PER_GAME | 场均分钟 | 30.00 | [P_BASE] |
| REB_PER_GAME | 场均篮板 | 5.00 | [P_BASE] |
| AST_PER_GAME | 场均助攻 | 5.00 | [P_BASE] |
| TOV_PER_GAME | 场均失误 | 2.50 | [P_BASE] |
| STL_PER_GAME | 场均抢断 | 1.33 | [P_BASE] |
| BLK_PER_GAME | 场均封盖 | 0.50 | [P_BASE] |
| PF_PER_GAME | 场均犯规 | 2.00 | [P_BASE] |
| TS_PCT | 真实命中率 | 61.8% | [P_BASE] |
| EFG_PCT | 有效命中率 | 57.0% | [P_BASE] |
| FG3_PCT | 三分命中率 | 40.0% | [P_BASE] |
| FG3A_RATE | 三分出手占比 | 45.0% | [P_BASE] |
| FT_RATE | 罚球出手比（FTA/FGA） | 0.30 | [P_BASE] |
| AST_TOV | 助攻失误比 | 2.00 | [P_BASE] |
| LEAGUE_TS_PCT | 联盟整体真实命中率 | 55.1% | [T_BASE] |
| RTS_PP | 相对联盟TS（百分点） | +6.76 pp | [P_BASE] [T_BASE] |
| USG_PCT | 使用率（来源值） | 28.0% | [P_ADV] |
| AST_PCT | 助攻率（来源值） | 23.0% | [P_ADV] |
| ONCOURT_OFF_RATING | 在场时球队进攻效率 | 118.00 | [P_ADV] |
| ONCOURT_DEF_RATING | 在场时球队防守效率 | 112.00 | [P_ADV] |
| ONCOURT_NET_RATING | 在场时球队净效率 | 6.00 | [P_ADV] |
| PTS_PER75 | 每75回合得分 | 30.00 | [P_100] |
| REB_PER75 | 每75回合篮板 | 6.43 | [P_100] |
| AST_PER75 | 每75回合助攻 | 6.43 | [P_100] |
| TOV_PER75 | 每75回合失误 | 3.21 | [P_100] |
| PCT_AST_FGM | 命中球受助攻比例 | 45.0% | [P_SCORE] |
| PCT_UAST_FGM | 命中球非受助攻比例 | 55.0% | [P_SCORE] |
| PCT_AST_3PM | 三分命中球受助攻比例 | 60.0% | [P_SCORE] |
| TEAM_OFF_RATING | 目标球队进攻效率 | 115.00 | [T_ADV] |
| TEAM_DEF_RATING | 目标球队防守效率 | 111.00 | [T_ADV] |
| TEAM_NET_RATING | 目标球队净效率 | 4.00 | [T_ADV] |
| TEAM_PACE | 目标球队节奏 | 98.00 | [T_ADV] |
| TEAM_AST_PCT | 目标球队助攻率 | 62.0% | [T_ADV] |
| TEAM_FG3A_RATE | 目标球队三分出手占比 | 36.5% | [T_BASE] |
| ON_OFF_DIFFERENTIAL | 真实在场/不在场差值（未实现） | N/A |  |
| DEFENSIVE_ABILITY_SCORE | 个人防守评分（不生成） | N/A |  |

## 样本限制与缺失

- SYNTHETIC TEST DATA ONLY: not an NBA player, not real NBA statistics, not publishable analysis.
- SYNTHETIC TWO-TEAM TEST UNIVERSE. All players, teams and numbers are invented for software tests.
- Player sample is full-season, not a team stint. TEAM_ID may label a latest team; do not assume all minutes were played for that team or that team context is a causal effect.
- ON_OFF_DIFFERENTIAL: No off-court/lineup dataset in v0.1. On-court ratings are NOT on/off.
- DEFENSIVE_ABILITY_SCORE: No validated individual defensive model; never derive this from steals, blocks, or on-court defensive rating.

## 来源记录

[P_BASE]: synthetic://nba-player-analyst/player_base "SYNTHETIC UNIT-TEST FIXTURE; NOT NBA DATA | 2026-10-11T00:00:00+00:00 | Totals"
[P_ADV]: synthetic://nba-player-analyst/player_advanced "SYNTHETIC UNIT-TEST FIXTURE; NOT NBA DATA | 2026-10-11T00:00:00+00:00 | Totals"
[P_100]: synthetic://nba-player-analyst/player_per100 "SYNTHETIC UNIT-TEST FIXTURE; NOT NBA DATA | 2026-10-11T00:00:00+00:00 | Per100Possessions"
[P_SCORE]: synthetic://nba-player-analyst/player_scoring "SYNTHETIC UNIT-TEST FIXTURE; NOT NBA DATA | 2026-10-11T00:00:00+00:00 | Totals"
[T_BASE]: synthetic://nba-player-analyst/team_base "SYNTHETIC UNIT-TEST FIXTURE; NOT NBA DATA | 2026-10-11T00:00:00+00:00 | Totals"
[T_ADV]: synthetic://nba-player-analyst/team_advanced "SYNTHETIC UNIT-TEST FIXTURE; NOT NBA DATA | 2026-10-11T00:00:00+00:00 | Totals"
