# 数据证据包（不是最终长文）: Cade Cunningham

分析样本: 2024-25 / Regular Season
GP=70; MIN=2452
数据覆盖模式: core

## 已登记指标

| ID | Metric | Value | Sources |
|---|---|---:|---|
| GP | 出场场数 | 70 | [P_BASE] |
| MIN | 总出场分钟 | 2452.00 | [P_BASE] |
| FGA | 投篮出手总数 | 1457 | [P_BASE] |
| FG3A | 三分出手总数 | 418 | [P_BASE] |
| FTA | 罚球出手总数 | 370 | [P_BASE] |
| PTS_PER_GAME | 场均得分 | 26.14 | [P_BASE] |
| MIN_PER_GAME | 场均分钟 | 35.03 | [P_BASE] |
| REB_PER_GAME | 场均篮板 | 6.07 | [P_BASE] |
| AST_PER_GAME | 场均助攻 | 9.11 | [P_BASE] |
| TOV_PER_GAME | 场均失误 | 4.41 | [P_BASE] |
| STL_PER_GAME | 场均抢断 | 1.01 | [P_BASE] |
| BLK_PER_GAME | 场均封盖 | 0.76 | [P_BASE] |
| PF_PER_GAME | 场均犯规 | 2.79 | [P_BASE] |
| TS_PCT | 真实命中率 | 56.5% | [P_BASE] |
| EFG_PCT | 有效命中率 | 52.1% | [P_BASE] |
| FG3_PCT | 三分命中率 | 35.6% | [P_BASE] |
| FG3A_RATE | 三分出手占比 | 28.7% | [P_BASE] |
| FT_RATE | 罚球出手比（FTA/FGA） | 0.25 | [P_BASE] |
| AST_TOV | 助攻失误比 | 2.06 | [P_BASE] |
| LEAGUE_TS_PCT | 联盟整体真实命中率 | 57.6% | [T_BASE] |
| RTS_PP | 相对联盟TS（百分点） | -1.13 pp | [P_BASE] [T_BASE] |
| USG_PCT | 使用率（来源值） | 33.2% | [P_ADV] |
| AST_PCT | 助攻率（来源值） | 42.4% | [P_ADV] |
| ONCOURT_OFF_RATING | 在场时球队进攻效率 | N/A | [P_ADV] |
| ONCOURT_DEF_RATING | 在场时球队防守效率 | N/A | [P_ADV] |
| ONCOURT_NET_RATING | 在场时球队净效率 | N/A | [P_ADV] |
| PTS_PER75 | 每75回合得分 | 26.92 | [P_100] |
| REB_PER75 | 每75回合篮板 | 6.23 | [P_100] |
| AST_PER75 | 每75回合助攻 | 9.38 | [P_100] |
| TOV_PER75 | 每75回合失误 | 4.57 | [P_100] |
| PCT_AST_FGM | 命中球受助攻比例 | N/A | [P_SCORE] |
| PCT_UAST_FGM | 命中球非受助攻比例 | N/A | [P_SCORE] |
| PCT_AST_3PM | 三分命中球受助攻比例 | N/A | [P_SCORE] |
| TEAM_OFF_RATING | 目标球队进攻效率 | 115.00 | [T_ADV] |
| TEAM_DEF_RATING | 目标球队防守效率 | 113.10 | [T_ADV] |
| TEAM_NET_RATING | 目标球队净效率 | 1.90 | [T_ADV] |
| TEAM_PACE | 目标球队节奏 | 99.80 | [T_ADV] |
| TEAM_AST_PCT | 目标球队助攻率 | 61.8% | [T_ADV] |
| TEAM_FG3A_RATE | 目标球队三分出手占比 | 39.4% | [T_BASE] |
| ON_OFF_DIFFERENTIAL | 真实在场/不在场差值（未实现） | N/A |  |
| DEFENSIVE_ABILITY_SCORE | 个人防守评分（不生成） | N/A |  |

## 样本限制与缺失

- NBA Stats direct access failed in this runtime; this is a curated public-table import, NOT an nba_api live end-to-end success.
- RealGM supplies totals and estimates. USG/AST and team ratings use RealGM definitions, not NBA Stats tracking or exact on-court possession counts.
- P_100 is the complete 2024-25 Cade row returned in the Basketball-Reference search index. Direct page access returned 403. Rounded source values; supplemental only, not a primary inference basis.
- No verified assisted-shot, tracking, individual on-court, shot-location or film dataset; do not infer those capabilities.
- All season statistics refer only to 2024-25 regular season; no 2025-26 data or playoff data included.
- Player sample is full-season, not a team stint. TEAM_ID may label a latest team; do not assume all minutes were played for that team or that team context is a causal effect.
- ONCOURT_OFF_RATING: player_advanced.OFF_RATING missing or unverified; not inferred from box-score totals.
- ONCOURT_DEF_RATING: player_advanced.DEF_RATING missing or unverified; not inferred from box-score totals.
- ONCOURT_NET_RATING: player_advanced.NET_RATING missing or unverified; not inferred from box-score totals.
- PCT_AST_FGM: player_scoring.PCT_AST_FGM missing or unverified; not inferred from box-score totals.
- PCT_UAST_FGM: player_scoring.PCT_UAST_FGM missing or unverified; not inferred from box-score totals.
- PCT_AST_3PM: player_scoring.PCT_AST_3PM missing or unverified; not inferred from box-score totals.
- ON_OFF_DIFFERENTIAL: No off-court/lineup dataset in v0.1. On-court ratings are NOT on/off.
- DEFENSIVE_ABILITY_SCORE: No validated individual defensive model; never derive this from steals, blocks, or on-court defensive rating.

## 来源记录

[P_BASE]: https://basketball.realgm.com/player/Cade-Cunningham/Summary/124839 "RealGM public season totals | 2026-10-12T01:27:27.372889+00:00 | Totals"
[P_ADV]: https://basketball.realgm.com/player/Cade-Cunningham/Summary/124839 "RealGM advanced estimates | 2026-10-12T01:27:27.372889+00:00 | Totals"
[P_100]: https://www.basketball-reference.com/leagues/NBA_2025_per_poss.html "Basketball-Reference complete indexed player row | 2026-10-12T01:27:27.372889+00:00 | Per100Possessions"
[T_BASE]: https://basketball.realgm.com/nba/team-stats/2025/Totals/Team_Totals/Regular_Season "RealGM full-league team totals | 2026-10-12T01:27:27.372889+00:00 | Totals"
[T_ADV]: https://basketball.realgm.com/nba/team-stats/2025/Advanced_Stats/Team_Totals/Regular_Season "RealGM team advanced estimates | 2026-10-12T01:27:27.372889+00:00 | Totals"
[EXT_AWARD]: https://www.nba.com/news/2024-25-all-nba-teams-announced "NBA / Detroit Pistons official public publication | 2026-10-12T01:27:27.372889+00:00 | notes"
[EXT_SEASON]: https://www.nba.com/pistons/news/cade-cunningham-named-2024-25-kia-all-nba-third-team "NBA / Detroit Pistons official public publication | 2026-10-12T01:27:27.372889+00:00 | notes"
[EXT_FIT]: https://www.nba.com/pistons/news/pistons-3-key-vets-keep-showing-up-and-knocking-down-triples "NBA / Detroit Pistons official public publication | 2026-10-12T01:27:27.372889+00:00 | notes"
[EXT_PREVIEW]: https://www.nba.com/news/2024-25-season-preview-det "NBA / Detroit Pistons official public publication | 2026-10-12T01:27:27.372889+00:00 | notes"
