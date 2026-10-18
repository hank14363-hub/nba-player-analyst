# Kaggle 历史常规赛离线适配

仅在使用 [deocheng/nba-data-1946-2026](https://www.kaggle.com/datasets/deocheng/nba-data-1946-2026) 时读取。本适配器已核对版本 1 的字段；这是截至 2026-08-18 的历史快照，不是实时服务。新版本需要重新检查 schema 与语义，不直接复用版本标签。

## 输入与身份

从 Kaggle 下载或使用现有文件，保留原始 CSV。只需四张表，不必下载整个 6.33 GB 数据库：

- 必需：`public.fact_player_season_stats.csv`、`public.player_id_bridge.csv`。
- 投篮结构可选：`public.player_shooting.csv`。
- 描述性 On/Off 可选：`public.player_onoff.csv`。

`--csv-dir` 接受包含这些文件的目录，或包含 `csv/` 子目录的解压根目录。适配器完全离线，不自动下载、不使用登录凭证。

明确 NBA 数字 ID、BR slug、赛季及上传者快照日期。桥接表必须有一致数字 ID 和完整姓名对应；仅姓氏、简称或多个冲突 ID 均不接受。`season=2025` 转为 `2024-25`。当前仅支持 2014-15 起的现代 NBA 常规赛；ABA、BAA、季后赛和历史球队映射需另行核验。

```bash
python scripts/import_kaggle.py --csv-dir <CSV目录> --player-id 1630595 --bref-key cunnica01 --season 2024-25 --snapshot-date 2026-08-18 --out <新导入目录>
python scripts/run_analysis.py --input <新导入目录>/data_bundle.json --player-id 1630595 --season 2024-25 --out <新证据目录>
```

不筛球队时仅选择唯一 TOT/2TM/3TM 等合计行；没有合计且有多个球队段时拒绝加总。`--team-id` 可明确选择一个球队段，后续分析必须使用相同 `--team-id`。球队段不导入整季 BREF 影响力模型。

## 可接入的内容

基础计数按总量处理，并检查得分恒等式、计数整数和投篮上下界。BR USG%、AST% 等除以 100 转为小数，但仍明确属于 BR 口径，不覆盖已有 NBA Stats 原表；该适配器生成独立数据包。BR 的个人 ORtg/DRtg 不映射为球队在场效率。

BPM、OBPM、DBPM、VORP、WS、OWS、DWS、WS/48 复用现有 BREF 模型契约，注明经 Kaggle 转引和历史模型版本未独立证实。

投篮结构仅导入两分/三分命中受助攻比例、平均距离、五个距离段的出手占比和命中率。分母与提供者三位小数精度保留；不反推精确受助攻次数，不拼造整体受助攻率。无正出手时的距离段命中率保持缺失，零不能替代缺失。

新增指标包括 `PCT_AST_2PM`、`AVG_SHOT_DISTANCE_FT`、`PCT_FGA_0_3` / `FG_PCT_0_3` 等。它们进入 evidence.md、metrics.csv 和结论登记；不会自动生成未经设计的新雷达或投篮热区。

## On/Off 的独立核验

只有 `player_onoff` 的 On Court / Off Court 真分组可用。`team_on_off` 已发现把在场球队/对手数据放入 On/Off 列的情况，不能作为不在场数据。

为避免 On+Off 自证覆盖，需要提供**同赛季常规赛、已保存来源与摘要的官方完整联盟球队基础表**作为独立分钟基准：

```bash
python scripts/import_kaggle.py --csv-dir <CSV目录> --player-id 1630595 --bref-key cunnica01 --season 2024-25 --snapshot-date 2026-08-18 --reference-bundle <已核验官方data_bundle.json> --out <新导入目录>
```

校验官方来源参数、30 个不同球队、行摘要、实际球队、在场分钟与球员分钟，以及 On+Off 与球队场上分钟。复用现有两分钟舍入容差，并在审计中记录实际差异。没有独立基准、转会合计不对应唯一球队或分钟不匹配时，只排除 On/Off，基础证据仍可使用。不能使用季后赛/过滤后的球队表或五人累计分钟作基准。

不新抓官方数据；参考包保留原采集时间。官方球队总量可提供联盟基准，但 Kaggle 单球员导入不构成完整同角色比较样本；`--comparisons` 不会将它伪装成官方完整联盟表。

## 可追溯性与输出

导入输出 `data_bundle.json`、`kaggle_import_audit.json` 和 `raw/kaggle_selection.json`。保存原 CSV SHA256、选中原始行、版本、上传者快照日期、文件本地取得时间依据与排除记录。文件 mtime 仅用于本地取得时间，不能当作上游抓取时间；移动/复制使其失真时，应重新核实时间并如实披露。

`kaggle_selection.json` 是所选行和参考元数据的 JSON 快照，不是原 CSV 字节副本。导入、复算和研究册检查会核验快照及重算转换；移动包时保留邻接 `raw/` 目录。原始完整 CSV 应另行保存，以便重新审计。

本基础适配器不导入EPM、原始投篮坐标、阵容和逐回合表。EPM独立读取与单球员Actual导入见 [kaggle_epm.md](kaggle_epm.md)。尤其 `player_epm_actual` 只有 season=2026，不能补 2024-25 实际 EPM；坐标不能依文档直接映射到 NBA LOC_X/LOC_Y。缺失与排除原因在审计和证据中可见。

当前例子是导入和复算验证，不是新写好的完整球员研究册。仍需按主 Skill 完成正文、结论登记与图文内容，再渲染和检查。

历史EPM可用独立`import_kaggle_epm.py --import-historical`接入带备注归档读数，仍不能补为2024–25 Actual；命令与限制见[kaggle_epm.md](kaggle_epm.md)。
