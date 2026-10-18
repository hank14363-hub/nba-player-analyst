# Sumitro Datta / Basketball Reference 历史数据接入

使用 [nba-aba-baa-stats](https://www.kaggle.com/datasets/sumitrodatta/nba-aba-baa-stats) 的已核验 v56（发布于2026-04-13），解压 CSV 后离线导入。当前适配器仅支持2014–15起的 NBA 常规赛；历史 BAA、ABA、旧球队和季后赛不在适配范围。CSV season 使用结束年，例如2025对应2024–25；这是历史快照，不是实时取数。

## 导入

```text
python <SKILL_DIR>/scripts/import_sumitro.py --csv-dir <CSV目录> --identity-bundle <同赛季官方data_bundle.json> --player-id 1630595 --bref-key cunnica01 --season 2024-25 --comparisons --out <新导入目录>
python <SKILL_DIR>/scripts/run_analysis.py --input <新导入目录>/data_bundle.json --player-id 1630595 --season 2024-25 --comparisons --out <新证据目录>
```

identity-bundle 必须保留同赛季常规赛 NBA leaguedashplayerstats 的原始 player_base 行与来源摘要，并能核对指定 NBA ID 的完整姓名。BR slug 是第三方身份，不伪装成 NBA ID。输入缺失时先取得对应官方身份表；不要用演示表、随意编号或缩写名代替。离线包内的2024–25官方案例可以验证该赛季的坎宁安、东契奇等身份，不能用于别的赛季。

七个输入表为 Player Totals、Advanced、Per 100 Poss、Player Shooting、Player Play By Play、Team Totals、Team Summaries。Player Totals 必需；其他缺失时不补造。要计算同角色样本，前三个球员表必须提供匹配的全赛季联盟行。原 CSV 摘要与获取时间依据保留在审计文件；raw/sumitro_selection.json 保存所选赛季原始行及身份映射证据。后续分析复制并核对该快照，校验器重新执行转换；不要手改转换后的数值或来源。

## 统计口径

- 转会球员默认选2TM/3TM等整季行，不与球队效力段相加；--team-id 指定效力段。整季影响力估计与全联盟比较不会套到效力段。
- Team Totals.mp 是五名球员分钟之和，除以5成为球队比赛分钟；排除 League Average，完整30队才生成联盟基准。playoffs 是球队标签，不能当季后赛比赛筛选。
- 投篮距离区间及2P/3P受助攻比例保留提供者精度；不从舍入比例反推精确总受助攻命中球。没有坐标，不画位置热区。
- Player Play By Play 是赛季汇总，并非逐回合事件。传球失误173与丢球失误105可独立描述；坎宁安总失误309减两者得到31，只称算术差额，不能编造第三类事件定义。
- BPM、OBPM、DBPM、VORP及Win Shares进入既有BREF模型契约；个人ORtg/DRtg不映射成球队在场评分，DBPM也不是个人防守能力评分。

## BR五轴比较

选择每名球员的整季行，以GP≥40且MIN≥1000确定轮换样本，再用已登记的使用率、助攻率等角色门槛。2024–25原始569名球员，266人符合轮换门槛；坎宁安与东契奇的高负荷组织核心组均为14人。输出完整名单、中位数、百分位及宽/严门槛敏感性。

五轴为每75回合得分、助攻、真实命中率、助攻失误比与反向失误量。BR数据不生成非受助攻总命中占比或NBA PIE。图表明确BR五轴；旧NBA官方六轴维持原契约。百分位描述指定样本，不能综合成能力分或联盟排名。任一符合门槛者关键字段缺失或三表键不一致，则比较缺失，不静默删人。

## 来源边界

Sumitro与deocheng的上游同为Basketball Reference，不能把两套Kaggle一致写成独立证据验证。Kaggle列出的CC0不自动证明上游素材授权。数据变化后重新检查版本和字段；适配器拒绝未经核验的版本。

仍缺EPM、真实On/Off、投篮坐标、追踪数据与季后赛。示例 examples/sumitro-cade-2024-25、sumitro-luka-2024-25、sumitro-luka-lal-2024-25 是 evidence_ready 证据包；不能当作新研究册或最终文章。
