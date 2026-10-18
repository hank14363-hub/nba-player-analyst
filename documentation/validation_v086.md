# v0.8.6 默认高阶采集

在线run_analysis现在默认尝试BREF（BPM/VORP/Win Shares）及LEBRON公开转引，并检查匹配赛季历史实际EPM的访问。自动以同赛季官方完整姓名唯一核对BR slug；页面赛季、NBA ID、场次/分钟与模型分量继续校验。任一家族失败不取消基础报告，原因记入impact_collection_audit.json和研究册缺失提示；保存原始响应与摘要。

EPM没有新增已核验数值适配器：受限历史页停止，无受限脚本提取；即使200可访问仍不能把未核验表填进模型。DARKO需显式--impact-cutoff YYYY-MM-DD且日期匹配目标赛季，不用当前预测替代整季回顾。公开适配器不把整季数据套到季后赛或球队效力段。

--no-impact关闭；--input和--offline只读已有模型、不自动联网。补采历史导入包可用独立collect_impact.py到新目录，或按在线主流程重新取数，不覆盖旧成果。

正文审查增加impact_not_attempted、impact_unwritten，每个已接入模型必须登记模型值并解释结果、分歧与限制；引用分钟或仅放图表不算完成。旧案例普通数值复算仍兼容。

## 命令

```text
python <SKILL_DIR>/scripts/run_analysis.py --player-id 2544 --season 2025-26 --tracking --shots --on-off-team-id 1610612747 --out <新目录>
```

不必加--impact。需要历史预测时额外给出本赛季实际要研究的--impact-cutoff日期。采集可能额外增加最多三次提供者请求（指定DARKO则四次），每次使用--timeout限制；不承诺所有来源随时可达。

## 验证

387项回归全部通过，无跳过，新增12项默认采集与失败路径测试。真实旧BREF、LEBRON、DARKO快照回放通过；官方v0.8.1研究册/长图、Skill结构与发布版本检查通过。本轮使用注入响应验证主流程，没有宣称2025–26勒布朗高阶数据已实际联网取得，也未重建他的原研究册。

本机先备份v0.8.5再安装v0.8.6。未发布GitHub，ZIP安装摘要另附。
