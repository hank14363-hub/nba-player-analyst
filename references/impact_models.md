# 第三方影响力模型与历史预测

`collect_impact.py` 可选采集公开 BRef、nbarapm 转引 LEBRON、DARKO 原站历史页面。默认只采集 BRef，不随普通 NBA 取数自动请求所有提供者。它输出补充后的新 data_bundle.json、原始快照与访问日志；每提供者一次请求，拒绝、限流、非预期结构或超时即记录并停止该来源，不切换代理或绕过订阅。离线复算与渲染不需要 requests/BeautifulSoup。

```text
python <SKILL_DIR>/scripts/collect_impact.py --bundle <已有目录>/data_bundle.json --player-id <ID> --name "<英文姓名>" --bref-key <已核验BRef键> --providers BREF LEBRON DARKO --cutoff <YYYY-MM-DD> --out <新补数目录>
python <SKILL_DIR>/scripts/run_analysis.py --input <新补数目录>/data_bundle.json --player-id <ID> --season <YYYY-YY> --comparisons --out <新研究目录>
```

公开采集器当前只支持完整常规赛；不把转会球队段与整季模型混配。`--cutoff` 必须是目标赛季内的历史日期，既不是抓取日期，也不是用当前值回填的标签。采集失败的来源单列，不能填零；全失败时保留访问日志，停止指标交付。获取成功仍需读方法和样本，完成正文与结论登记后才渲染。

## 各指标回答什么

| 家族 | 估计对象与基准 | 使用边界 |
|---|---|---|
| BPM / OBPM / DBPM | 单赛季技术统计与球队背景；相对平均球员的每百回合点数 | BPM 2.0，不是纯阵容回归；防守分量不确认单防、协防能力 |
| VORP | BPM与出勤结合，使用替补基准 | 不等于实际多赢的场次，不与BPM点数共轴 |
| WS / OWS / DWS | 提供者分配的赛季胜利份额 | 依赖球队结果与统计假设，不是个人造成胜利的因果值 |
| WS/48 | 单位上场时间的模型胜利份额 | 与每百回合点数分开；页面精度三位小数保留 |
| LEBRON | 技术统计先验与运气调整的阵容回归；相对平均球员的攻防点数 | 原站为BBall Index；公开转引必须显示来源链，不能冒充原始导出 |
| DARKO DPM | 历史日期的生涯加权预测，回答下一场预期表现 | 不是该赛季实际贡献；历史重建页若无版本证明，不声称原样复现当年发布模型 |

方法可直接查阅时登记独立 `method_reference`；球员读数来源登记 `impact_data`。原站超时与转引说明可用是两件事，不能写成已核验原站模型全文。模型输入重叠，方向一致不等于独立验证；没有置信区间时不推导统计显著性。模型防守分量可以如实展示，但不改名为个人防守能力评分。禁止相加、平均或任意加权生成综合分/实力名次。

## 数据契约与复算

可选顶层 `data_bundle.impact_data` 不进入官方 TABLES，旧数据包没有此字段时指标与行为保持原样。

```json
{
  "schema_version": "0.1.0",
  "datasets": [{
    "family": "BREF",
    "player_id": 999001,
    "player_team_id": 0,
    "provider_player_key": "verified-provider-key",
    "season": "2024-25",
    "season_type": "Regular Season",
    "estimate_type": "retrospective_box",
    "model_version": "BPM 2.0; provider Win Shares method",
    "cutoff": null,
    "source_id": "EXT_IMPACT_BREF",
    "raw_rows": [],
    "selector": {"provider_player_key": "verified-provider-key"},
    "caveats": ["模型估计，不能当作个人防守能力评分"]
  }],
  "excluded": [{"family": "RAPM", "reason": "比赛范围待核验"}]
}
```

上例只演示结构，空行不可运行，不是真实球员数据。完整可运行实例看 `examples/cade-cunningham-2024-25-official-v081/data_bundle.json`。

每个家族只能一组，selector 必须从原始行唯一选出；不选择重复候选、不叠加转会段。BRef原表按`#advanced`常规赛、`#advanced_post`季后赛分开，转会球员用唯一TOT/2TM/3TM合计，姓名与显式提供者键匹配NBA身份。页面带更高精度排序值时不替换已公布显示精度。BRef自己的AST%/USG%不能覆盖NBA同名字段。

LEBRON按NBA ID和`Season`双重选行，名称复核，分钟与官方总量差不超过点一；转引没有场次时明确缺失。该误差门槛用于暴露范围冲突，不是模型精度证明。BRef场次须一致、整数分钟舍入误差不超过点五一。DARKO验证可见页面的历史日期与赛季，按NBA ID取历史DPM/Off/Def列；忽略同页Now/Since及排名。响应式重复行须读数相同。

来源包含provider/url/带时区retrieved_at/season/season_type/model_version/cutoff/sha256_rows。保存原始快照时使用安全的相对 `raw_file` 与`sha256_raw`；HTTP响应另被解码重序列化时区分响应摘要与保存文件摘要，不能称保存字节完全等同响应。原数据hash、样本、模型与日期都参与确定性复算，生成 `impact_context` 与 `IMPACT_*`指标；渲染重查原始快照摘要，防止仅手改分析JSON。已补数目录被--input导入时复制登记的raw快照，不再请求网络。

攻防分量与总值按来源显示精度核对：BPM/DARKO允许舍入差，LEBRON使用较小误差；不为对齐总值修改提供者数值。缺字段仍missing，禁止填零。

## 仍需核验的来源

EPM目前区分预测与历史实际入口。历史实际页若跳转`subscribe?reason=locked-season`，停止该请求并保留缺失；不能提取受限脚本数据，或用另一年/另一日期的预测替代。

nbarapm公开RAPM返回`Latest_Year`、`Year_Interval`、模型版本、文件名和回合数，但年份一致和返回对象名rs不足以证明拟合只使用常规赛。须核实比赛集合、窗口、正则化设置与覆盖，尤其`_all_`等范围未解释且回合不匹配时，不纳入本赛季模型图。不从文件名反推模型参数，也不挑重复TimeDecay行。保存候选和排除原因供后续核验。

同角色模型比较需要所有纳入球员的同源、同版本、同窗数据；单球员多个模型不构成完整比较样本。优先补原始历史导出、模型版本和不确定性，再考虑同组分布与跨季变化。
