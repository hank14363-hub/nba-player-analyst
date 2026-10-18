# 中文长文写作任务

对象：MVP Demo Guard；赛季：2024-25；比赛类型：Regular Season。
目标字数：约 2500 字；研究问题：得分、组织、无球、防守和球队分工。
数据类别：synthetic。

先读本目录 analysis.json、evidence.md、sources.json，以及技能 references/evaluation.md、writing_style.md、plain_language.md。
写给看球但不熟悉所有统计术语的读者：先说明球员能做什么，再用关键数据解释。术语首次出现给一句简单释义，图表标题优先写成篮球问题。
完成 report.md 和 claims.json，不把本文件或 report.template.md 当作成稿。

讨论得分、组织、无球、防守以及球队分工。避免“机会转化、主控结论保留、角色迁移”等连续抽象表达，也不要换成“无敌、顶级、完美适配”式夸张评价。
统计数字只取自已核验指标，来源放在相关句子旁。保留事实、推断、观察的区别；说明缺什么资料，不把“未知”说成“能力差”。
有 observations.md 时注明它是用户提供的记录，没有实际看片不能自称观察了录像。
资料不够就缩短相应部分；合成数据在标题下醒目标注“合成测试数据，不是真实NBA结论”，使用虚构姓名。

修改正文后同步更新 claims.json 中的原句。运行 review_language.py 查看表达建议，再运行 validate_report.py 核对数字与来源；人工复核每条结论后，继续生成研究册和结论长图。
