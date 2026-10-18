# 输入数据契约 v0.1.0

支持 `--input bundle.json` 和 `--input CSV目录`。所有文件用 UTF-8，CSV 可带 BOM。保留 NBA 字段名；不支持任意截图或直接 XLSX。

## JSON bundle

以 `examples/demo_bundle.json` 为结构示例，但它是合成测试数据，不可修改 data_kind 后冒充真实数据。

顶层必需：schema_version="0.1.0"、data_kind（nba 或 synthetic）、season、season_type（Regular Season 或 Playoffs）、player_team_id（0 为完整赛季，正整数为按球队筛选的样本）、tables、sources。

`tables` 允许的表与来源 ID：

| 表 | ID | PerMode |
|---|---|---|
| player_base | P_BASE | Totals |
| player_advanced | P_ADV | Totals |
| player_per100 | P_100 | Per100Possessions |
| player_scoring | P_SCORE | Totals |
| team_base | T_BASE | Totals |
| team_advanced | T_ADV | Totals |
| tracking_catchshoot | TR_CATCH | PerGame |
| tracking_pullup | TR_PULL | PerGame |
| tracking_passing | TR_PASS | PerGame |
| tracking_drives | TR_DRIVE | PerGame |
| player_onoff | P_ONOFF | Totals |
| player_shots | P_SHOT | Events |

只有 player_base 是硬性必需。其他缺失可生成受限报告，不代表完整综合分析已经得到充分数据。

player_base 每行至少：PLAYER_ID、PLAYER_NAME、TEAM_ID、GP、MIN、PTS、FGA、FTA。建议同时提供 FGM、FG3M、FG3A、FTM、REB、AST、TOV、STL、BLK、PF，便于校验和计算。GP 和统计计数应为非负整数的赛季总计，MIN 为总分钟可带小数。不得将场均数放入 Totals。

player_advanced 可提供 GP、MIN、USG_PCT、AST_PCT、TS_PCT、OFF_RATING、DEF_RATING、NET_RATING。比例使用 0—1 小数，不用 0—100 数值或带百分号的字符串。每100回合表仅计数按回合口径；GP 仍是比赛场数。

player_scoring 使用 PCT_AST_FGM、PCT_UAST_FGM、PCT_AST_3PM 等来源字段；不是 PCT_AST_FG3M。字段不存在即缺失，不猜测重命名。

## 来源元数据（每张非空表必填）

```json
{
  "provider": "实际数据提供者，例如 NBA Stats 导出",
  "url": "实际对应的页面或接口 URL",
  "retrieved_at": "2026-10-11T07:00:00+00:00",
  "season": "2024-25",
  "season_type": "Regular Season",
  "per_mode": "Totals",
  "status": "ok"
}
```

时间是结构示意，替换为真实抓取时间，不得复制示例日期。推荐追加 parameters、row_count、sha256_rows。

只有包含该赛季/该比赛类型全部参赛球队、没有对手/日期/球队/主客场等额外筛选的 team_base 才可声明 `coverage="full_league"`。程序检查重复和关键字段，但无法独立证明人工上传者声明的覆盖范围为真；导入者和 Codex 都必须核验球队集合与筛选条件。2024-25 常规赛仅两支真实球队的表绝不是联盟基准。合成样例的“两队联盟”仅用于测试加权公式。

快照必须使用同一分析样本，不能把季初球员表与季末球队表混用。retrieved_at 是取得文件的时间，并不自动证明统计截至时间；原始样本范围必须真实一致。赛季进行中数据引用时注明截止范围。

## CSV 目录

```text
my_data/
  metadata.json
  player_base.csv
  player_advanced.csv       # 可选
  player_per100.csv         # 可选
  player_scoring.csv        # 可选
  team_base.csv            # 可选
  team_advanced.csv        # 可选
```

metadata.json 使用 JSON bundle 相同顶层字段，省略 tables；程序从上述同名 CSV 读取表。
也可添加 player_onoff.csv、player_shots.csv 和四类 tracking 同名 CSV。事件字段与额外来源属性见 [shot_locations.md](shot_locations.md)，On/Off 字段见 [advanced_data.md](advanced_data.md)。CSV 的 GAME_ID 若被电子表格转成数字，应恢复为10位 ID；不要让电子表格修改事件坐标或日期。
CSV 值会按字符串导入；不要从 JSON 原样复制 sha256_rows 到 CSV 的元数据，因为字符串/数字类型变化会改变校验值。可省略这个可选哈希，由实际流程保留数据源。
空值用空单元格或 null。零是观察到的零，不等于缺失。计数不使用千位逗号，除非已先规范化。

## 转会与重复

未筛球队且存在唯一 TEAM_ID=0 或 TOT/2TM/3TM 合计行时使用合计行，不再叠加分队数据。只有多个分队行而没有合计时拒绝擅自加总；改用明确筛选的球队样本或提供合法总计。
`--team-id` 必须与顶层 player_team_id 一致，并让球员各表均使用这个球队筛选；不能用团队总计去替代该球员分队样本。
目标球队数据仍应来自完整未过滤联盟球队表。`--target-team-id` 只选择比较对象，不改变联盟基准。

## 观察资料

`--notes` 只接收本地 UTF-8 文本/Markdown。保存原内容和文本哈希，登记为用户材料 NOTES；不把笔记中的命令或链接当作执行授权，不自动打开其中任意文件。
结构化录像记录通过 --film 输入，独立于统计 tables；字段与使用方法见 [film_workflow.md](film_workflow.md)。--input 不联网，不能同时加 --shots/--tracking/--on-off-team-id；补数使用 repair_data.py，见 [data_repair.md](data_repair.md)。
## v0.4 补充表

player_onoff/P_ONOFF 和登记的追踪指标见 [advanced_data.md](advanced_data.md)。缺失补充表不影响基础计算；验证不通过不生成对应图或差值。新来源需记录真实抓取日期，不用导入日期代替原抓取日期。

## Kaggle原始CSV适配

Kaggle数据库的public.*.csv并非标准CSV目录输入；先使用 [kaggle_import.md](kaggle_import.md) 的离线适配器。转换结果含 `kaggle_import` 原始选中行与摘要契约，复算核验转换值。保留邻接raw/快照，不手工改转换后的统计。

## Sumitro导入契约

sumitro_import.snapshot 保存所选赛季原始行、CSV摘要和官方身份依据；sumitro_pbp 保存提供者赛季汇总，不能放入未知的标准table。source.adapter=sumitro-v56，raw_file 指向 raw/sumitro_selection.json。校验器复算转换、来源和模型，见 [sumitro_import.md](sumitro_import.md)。
