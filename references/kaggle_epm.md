# Kaggle deocheng v1：历史 EPM 读取与 Actual 单球员导入

已在2026-10-17检查公开Kaggle元数据，并下载两张完整EPM表；当前版本仍为1，快照2026-08-18。无需下载6.33GB全库，使用`csv/public.player_epm.csv`（约32MB）和`csv/public.player_epm_actual.csv`（约1.3MB）。支持离线重放，不自动联网下载。

## 两张表的区别

| 文件 | 已核验的覆盖 | 本适配器用途 |
|---|---|---|
| `player_epm.csv` | 13,255行，season=2002–2026；12,653行标为`player/eskills`，602行标为`epm` | 默认读取候选；显式`--import-historical`可接入独立归档指标与强制备注 |
| `player_epm_actual.csv` | 602行，仅season=2026，即2025–26；标为`epm/actual` | 通过单球员核验后登记Actual EPM及攻防分量 |

历史候选缺少场次和总分钟，部分日期落在季后赛期间，2026还存在不同来源的重复球员赛季记录。不能据列名把它们认定为整季常规赛Actual，也不能直接认定为已验证的历史预测。`n`和`n_rapm`不是该球员场次或回合数。不平均重复行，不把历史候选复制进Actual表，不改年份填补空缺。

## 命令

```text
python <SKILL_DIR>/scripts/import_kaggle_epm.py --csv-dir <CSV目录> --player-id <NBA_ID> --season 2017-18 --out <新候选目录>
python <SKILL_DIR>/scripts/import_kaggle_epm.py --csv-dir <CSV目录> --player-id <NBA_ID> --season 2025-26 --import-actual --bundle <同球员同季参考data_bundle.json> --acquired-at <实际Kaggle下载时间，含时区> --out <新核验目录>
python <SKILL_DIR>/scripts/run_analysis.py --input <新核验目录>/imported/data_bundle.json --player-id <NBA_ID> --season 2025-26 --out <新研究目录>
```

`--csv-dir`接受CSV目录或含`csv/`子目录的根目录。只读模式不需要参考包。导入模式不能复用含其他球员专属影响力模型的参考包；官方完整联盟基础原表可复用，但准备球员参考包时应明确记录对其他球员模型的排除，不能更改基础数据或来源摘要。

Actual模式缺行或核验失败，输出`kaggle_epm_read_audit.json`及原因，以非零退出码结束；原始历史候选仍可阅读，不会生成已接入EPM的数据包。通过后，`imported/`含原文件字节、映射元数据、原始选中行和SHA-256，并沿用`import_epm`的确定性重算与文件传递。

## 核验与边界

只接受已检查v1两张CSV的固定SHA-256；新版本或不同字节需重新审查。固定摘要证明与已检查快照一致，不证明模型正确或上游授权。Actual选中行另核对内嵌`raw`JSON的ID、姓名、赛季、场次、总分钟、攻防值和类型/范围码。

Actual的`seasontype=2`与`scope_id=0`原样保留；未取得独立类型码说明，按匹配同季常规赛参考GP/MIN限定本次单球员用途并披露此限制。总分钟使用原值，容差为序列化小数位对应的半单位，至少按两位小数检查，不能通过整数外观或手动降低精度放宽校验。拒绝用场均分钟乘场次或四舍五入原始值。分量容差仍为0.15，其他身份和比赛范围规则不放宽。

实测奎克利2025–26：70场，Actual总分钟2231.31，官方2231.3083333333334，差约0.001667，符合两位小数容差0.005；EPM=2.257、进攻2.1676、防守0.0894035，分量差约-0.0000035。勒布朗同季Actual分钟1989.48，官方1989.055，差0.425，大于0.005，拒绝导入。不能为了接入勒布朗放宽容差。

来源明确显示`Dunks & Threes → Kaggle / deocheng v1`，保留Kaggle链接、上游Actual链接、版本、快照日期与真实下载时间。`scraped_at`缺时区，只作为原始字符串保存，不冒充可核验的官网导出时间。官网模型修订版本未知，不导入排名或宣称统计显著性。

Kaggle页面标示Apache2.0，第三方声明不能独立证明上游内容授权；原CSV和真实导入案例仅保留用户项目，不默认加入Skill分发包。官网直接导出验收状态仍与Kaggle转引验收分开。

## v0.8.10 历史快照导入

用户需要将历史EPM读数放入结果时，显式使用：

```text
python <SKILL_DIR>/scripts/import_kaggle_epm.py --csv-dir <CSV目录> --player-id <NBA_ID> --season 2017-18 --import-historical --bundle <同球员同季data_bundle.json> --acquired-at <实际Kaggle下载时间，含时区> --out <新历史EPM目录>
python <SKILL_DIR>/scripts/run_analysis.py --input <新历史EPM目录>/imported/data_bundle.json --player-id <NBA_ID> --season 2017-18 --out <新研究目录>
```

`--import-historical`与`--import-actual`互斥。基础参考范围目前仍是完整常规赛，但历史来源自身的比赛范围明确为`unverified`，不能因为附在常规赛报告中就改称常规赛Actual。历史表有多行时必须用`--source`和/或`--snapshot-date`唯一指定原始来源/日期；即使读数相同也不自动去重。原始日期不自动解读成模型发布日期或预测截止日。

独立家族`EPM_HISTORICAL`、类型`historical_snapshot_unverified`，指标`IMPACT_EPM_HIST`/`IMPACT_O_EPM_HIST`/`IMPACT_D_EPM_HIST`保留原表点数，单位记为`provider_epm_points`。GP/MIN保持null，不借用n、n_rapm或参考表填充。与Actual并存时各自保留来源与校验契约，不互相覆盖；Actual缺失仍明确显示。

生成结果必须就近标注：**历史 EPM 快照（口径待核验）**；原始记录日期；Dunks & Threes经Kaggle转引；估计类型、比赛范围、模型版本及场次/分钟未核实。仅用于补充阅读，不能据此确定常规赛攻防能力、作为独立验证或排名。引用这些指标的正文claims必须带“口径待核验”及caveats，缺备注会被validate_report拒绝。图表单独进入历史快照区，不混入整季回顾或已验证历史预测图。

`historical_epm_import`保存选中原始行及参考身份契约，`raw/historical_epm_export.csv`保留完整原CSV，另存metadata/selection及SHA-256。导入、复算、渲染与补抓传递均检查原文件；去掉备注或修改规范化结果将与确定性重算冲突。SHA-256只核验文件和转换一致，不核验模型或授权。

实测勒布朗2017–18记录：2018-06-08，原来源player/eskills，总值6.5729、进攻6.34402、防守0.228924。新研究册保留这些读数和备注；核心常规赛评价继续使用已有可核验证据。
