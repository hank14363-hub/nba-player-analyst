# 真实投篮位置与区域统计（v0.5）

在线加 `--shots`，或用 `repair_data.py --tables player_shots --player-id <ID>` 为旧 NBA 数据包补抓。`ShotChartDetail` 必须请求 `ContextMeasure=FGA`，默认得分事件不能覆盖未中球。结果集名是 `Shot_Chart_Detail`。完整请求、抓取时间、原始行和 SHA256 都保留。

只需要位置图时，无需先写整篇文章：`python <SKILL_DIR>/scripts/render_shot_charts.py --run-dir <证据包目录> --out <新图目录>`。命令重新核验数据，导出两张 SVG 与来源/异常 manifest；完整研究册仍按正常写作流程生成。

`player_shots` / `P_SHOT` 是逐次事件表，`per_mode=Events`。来源需登记 `player_id`、`player_team_id`（0 表示全赛季）、`context_measure=FGA`、`coordinate_units=tenths_of_foot`。各事件保留 GAME_ID、GAME_EVENT_ID、PLAYER_ID、TEAM_ID、GAME_DATE、PERIOD、MINUTES_REMAINING、SECONDS_REMAINING、SHOT_TYPE、SHOT_ZONE_BASIC、SHOT_ATTEMPTED_FLAG、SHOT_MADE_FLAG、LOC_X、LOC_Y；导入不能凭空构造这些字段。

脚本核验球员、效力段、赛季/比赛类型、唯一比赛+事件 ID、坐标范围，以及事件 FGA/FGM/FG3A/FG3M 与基础表完全一致。样本不完整则拒绝整季位置图。出手比赛数不可超过 GP，但球员可能有零出手场次，因此不强制二者相等。来源限制了日期、单场或其他分段时，不接受为完整赛季样本。

坐标原点是进攻篮筐，单位 0.1 英尺。SVG 采用等比例全场：横坐标 `240 + LOC_X × 0.54`、纵坐标 `68.35 + LOC_Y × 0.54`；底线在 LOC_Y=-52.5，全场上界 887.5。所有远距出手保留；命中圆点、未中叉号。它是实际事件散点，不是平滑热区或出手难度模型。

区域按官方 SHOT_ZONE_BASIC 分组。区域标签与两/三分类型冲突时，原始行不改，派生统计单列“区域/类型标签冲突”；analysis.shot_context.anomalies 保存定位与原标签。区域命中率分母是该区域出手，条长是该区域出手/全部出手。零出手命中率为 N/A；出手少于30次标“少样本”，这是阅读提示，不是显著性门槛。不能用少量底角出手推断稳定的左右侧能力差异。

图名 `shot_locations`、`shot_zones` 可嵌正文。区域指标 ID 为 SHOT_<RA/PAINT/MID/LC3/RC3/ATB3/BACK/UNRESOLVED>_<FGA/FGM/FG_PCT/SHARE>；UNRESOLVED 仅在有冲突时存在。没有匹配的联盟区域基准时，不输出区域相对联盟值、排名或能力颜色。
