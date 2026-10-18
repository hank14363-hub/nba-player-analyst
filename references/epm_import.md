# Actual EPM 离线导入

`scripts/import_epm.py` 读取用户合法取得的 Dunks & Threes **Actual EPM** 文件，不访问网站、不读取订阅脚本。支持 UTF-8 CSV（可带 BOM）或由平面行对象组成的 JSON 数组；未取得真实导出文件时，不宣称已核验官网的当前导出结构。

当前支持一个球员、完整常规赛，与已有 `data_bundle.json` 的姓名、NBA ID、赛季、场次及总分钟匹配。预测 EPM、球队效力段、季后赛、缺少总分钟或缺少 NBA ID 的文件不接入。其他模型和原有来源保留，不静默替换已导入的 EPM。

## 使用流程

1. 准备同赛季、同球员的参考 `data_bundle.json`，其 `P_BASE` 必须有原始行 SHA-256。参考可以是已核验的 NBA 或历史导入总量，不能把同名球员或另一赛季作为身份桥接。
2. 保留下载的原始文件。复制 `assets/epm_import_metadata.template.json` 到项目，填写实际导出信息和准确列名，不为通过校验修改球员读数。
3. 导入到新目录，再以 `run_analysis --input` 生成新的证据包；继续完成正文、claims、研究册和检查。

```text
python <SKILL_DIR>/scripts/import_epm.py --bundle <原证据目录>/data_bundle.json --file <用户导出文件.csv> --metadata <epm_metadata.json> --player-id <NBA_ID> --out <新EPM目录>
python <SKILL_DIR>/scripts/run_analysis.py --input <新EPM目录>/data_bundle.json --player-id <NBA_ID> --season <YYYY-YY> --out <新研究目录>
```

导入器只输出通过校验的数据包及审计，不自动完成球员评价。将 `IMPACT_EPM`、`IMPACT_O_EPM`、`IMPACT_D_EPM` 的解释写入正文并登记 claims。说明攻防分量、与其他证据相符或分歧之处和限制；引用场次或分钟不能代替模型解读。严格内容审查沿用逐模型的 `impact_unwritten` 检查。

## 元数据与字段映射

模板中的 `null` 必须依据实际文件填写；模板本身不能直接导入。

| 字段 | 含义与要求 |
|---|---|
| `estimate_type` | 固定 `actual`；不能给预测文件改标签 |
| `source_url` | `https://dunksandthrees.com/epm/actual`；如果带 season 参数，必须等于目标赛季结束年份 |
| `exported_at` | 用户声明的实际导出时间，ISO 8601，包含时区；不是脚本联网查阅时间 |
| `league` / `season_type` / `sample_scope` | `NBA` / `Regular Season` / `full_season` |
| `season` | 标准 `YYYY-YY`，必须与参考包一致 |
| `season_format` | 原始行用 `YYYY-YY` 时填 `nba`；用结束年份时填 `end_year`；不猜年份含义 |
| `minutes_unit` | 只接受 `total`；不把舍入场均分钟乘以场次构造总分钟 |
| `minutes_decimals` | 实际导出总分钟的精度，整数 0–4；不是放宽校验的开关 |
| `model_version` | 文件或说明提供的版本；未披露时明确写 unknown，不猜修订版本 |
| `columns` | 标准字段 → 文件中真实列名；必须唯一，不自动猜别名 |

标准字段为 `nba_id`、`player_name`、`season`、`games`、`minutes`、`tot`、`off`、`def`。例如原文件采用 `name`、`gp`、`mp` 时，分别映射 `player_name: name`、`games: gp`、`minutes: mp`，并先确认 `mp` 确为总分钟。`nba_id` 必须是 NBA ID，不能将提供者内部 ID 改名冒充。

原行若另有比赛类型或估计类型列，在 `columns` 中加入 `season_type`、`estimate_type`，与元数据交叉核验。当前接口的取值分别为 `Regular Season` 和 `actual`；其他编码需核实后新增受测试的适配规则，不能手改原始行。

## 核验规则

- 数字 NBA ID 与完整姓名同时匹配。姓名只进行 Unicode、大小写和标点规范化，不使用模糊匹配或缩写猜测。
- NBA ID + 赛季必须唯一命中；重复行和分球队记录不能求和、平均或自动择优。其他球员与赛季的原始行保留，但不构成已核验的模型比较样本。
- 场次必须是正整数且与参考值相等。总分钟必须符合声明精度，且与参考值的差不超过该精度的半个舍入单位；例如整数分钟为 0.5 分钟，两位小数为 0.005 分钟。仅允许微小浮点计算误差，不因数据失败调整精度。
- `tot`、`off`、`def` 全部必需且为有限数；允许零与负值，缺失不能补零。要求 `abs(tot - off - def) <= 0.15`，不修改提供者数值凑等式。
- 范围、版本、字段映射、原始行和参考身份/总量参与确定性重算。只改规范化后的数值及其行摘要仍会失败。

## 留存与文件传递

`raw/epm_export.csv`（或 `.json`）保存原文件字节；`raw/epm_metadata.json` 保存原元数据字节；`raw/epm_selection.json` 保存原始行、映射、样本声明和参考身份。文件分别登记 SHA-256，规范化模型行另有 `sha256_rows`。

`epm_import.snapshot` 是复算契约。导入和渲染时，既校验文件摘要，也重新解析原文件并与保留行及元数据比较。`run_analysis --input` 将所有登记的 raw 文件复制到新研究目录；少传原文件、改写原文件或让解析行与原文件不一致都会被拒绝。其他模型的原始快照一起保留。

SHA-256证明文件一致性，不能认证其一定来自提供者、证明版权许可或验证模型正确性。原始授权导出保留在用户项目，未经相应许可不要随公开 Skill 包或仓库分发。

`epm_import_audit.json` 记录离线导入、身份、样本、分钟精度、分量容差及零网络请求。原有在线访问失败记录保留为历史，不代表离线导入失败。新研究册以已核验 EPM 的实际状态更新图表与缺失说明，来源标为“用户离线导出”。

## 发布元数据与真实数据状态

`epm_offline_import_supported=true` 表示支持导入；`epm_value_imported` 表示分发包是否包含已验证的真实 EPM 案例。仅有合成测试时，后者保持 false。用户导入成功的状态以自己研究目录中的数据契约和审计为准，不回写全局发布元数据。

本功能用合成身份与明确标注的合成读数测试导入、拒绝路径、图表和文件传递。尚未获得真实授权导出进行现场验收，不把测试读数用于勒布朗或任何真实球员报告。

## v0.8.9 Kaggle 转引配置

新增独立`source_kind=kaggle_deocheng_v1`配置，经`scripts/import_kaggle_epm.py`生成元数据并复用本导入器。仅接受已审查v1 Actual原始字节，使用`acquired_at`记录Kaggle下载时间，来源标为Kaggle转引；不能将转引文件冒充用户官网导出。历史候选和2025–26真实验收的边界、分钟差异及命令见 [kaggle_epm.md](kaggle_epm.md)。官网直接导出仍未现场验收，前文合成测试说明只适用于该路径。
