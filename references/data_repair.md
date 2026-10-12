# 单表补抓与恢复

失败表可单独补抓，不重抓其他健康表，也不改已有文章。

```text
python <SKILL_DIR>/scripts/repair_data.py --input <旧目录>/data_bundle.json --tables player_scoring --out <新补抓目录>
python <SKILL_DIR>/scripts/repair_data.py --input <旧目录>/data_bundle.json --tables player_shots --player-id <ID> --out <新补抓目录>
python <SKILL_DIR>/scripts/repair_data.py --input <旧目录>/data_bundle.json --tables player_onoff --player-id <ID> --on-off-team-id <实际球队ID> --out <新补抓目录>
python <SKILL_DIR>/scripts/run_analysis.py --input <新补抓目录>/data_bundle.json --player-id <ID> --season <YYYY-YY> --team-id <原效力段或0> --out <新研究目录>
```

不指定 `--tables` 时，只选择输入中已经存在的空表；不会自行开启新的数据类型。已有行的表默认拒绝替换；确需更新时显式 `--replace-existing`，`--refresh` 仅绕过缓存，不等于授权替换已有表。整个输出目录必须新建或为空。拒绝把真实 NBA 数据混入合成样本。

`repair_log.json` 登记原包和结果包摘要、逐表旧/新来源、抓取时间、行摘要和失败原因。未选中的表及来源必须完全不变。失败保留原表及原来源，部分成功也写新包，退出码1提示仍有失败；下一轮从新包继续，只选择失败表。已经成功的旧抓取日期不能改成本次日期。来源、样本或基础快照变化必须重新复算并审阅正文；日志不证明战术结论成立。

使用与普通采集相同的有限重试和24小时缓存。`--offline` 只用缓存，保留原抓取时间并披露过期；与 `--refresh` 不兼容。更换赛季、比赛类型或效力段应新建样本，不拼到旧包。On/Off 和投篮事件会额外核验分钟/出手覆盖，不能用假设适配球队替代真实样本球队。
