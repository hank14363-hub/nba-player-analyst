# 中文长文写作任务

对象：{{PLAYER}}；赛季：{{SEASON}}；比赛类型：{{SEASON_TYPE}}。
目标字数：约 {{WORDS}} 字；研究问题：{{QUESTION}}。
数据类别：{{DATA_KIND}}。

先读本目录 analysis.json、evidence.md、sources.json，以及技能 references/evaluation.md、writing_style.md、plain_language.md。
写给看球但不熟悉所有统计术语的读者：先说明球员能做什么，再用关键数据解释。术语首次出现给一句简单释义，图表标题优先写成篮球问题。
完成 report.md 和 claims.json，不把本文件或 report.template.md 当作成稿。

讨论得分、组织、无球、防守以及球队分工。避免“机会转化、主控结论保留、角色迁移”等连续抽象表达，也不要换成“无敌、顶级、完美适配”式夸张评价。
统计数字只取自已核验指标，来源放在相关句子旁。保留事实、推断、观察的区别；说明缺什么资料，不把“未知”说成“能力差”。
有 observations.md 时注明它是用户提供的记录，没有实际看片不能自称观察了录像。
资料不够就缩短相应部分；合成数据在标题下醒目标注“合成测试数据，不是真实NBA结论”，使用虚构姓名。

修改正文后同步更新 claims.json 中的原句。运行 review_language.py 查看表达建议，再运行 validate_report.py 核对数字与来源；人工复核每条结论后，继续生成研究册和结论长图。

比较成功时，正文至少解释本球员的实际值、同角色中位数和角色门槛敏感性，并登记相应COHORT_指标；未启用和核验失败分开说明。
每个reading_card写明本主题能支持的判断、具体使用条件与尚缺的证据，避免用“结合任务与机会质量阅读结果”“把结论用于具体分工与回合核验”代替球员分析；通用限制放全局，不在所有卡片重复。
完成研究册后运行validate_book.py --strict-editorial，处理editorial_audit提示。该审查只识别明显遗漏，仍需人工核对结论；资料不足的主题保留缺失。

高阶数据检查impact_collection_audit.json和impact_context。每个已接入模型都解释结果及分歧，并在正文/claims登记IMPACT_模型指标；模型样本分钟引用不替代分析。缺失时说明访问、日期、身份或样本原因，不套用其他球员/赛季。

完整研究默认先做球评检索阅读：读references/commentary_research.md，以commentary_research.template.json为记录草稿，建议查询不算已搜索。使用可用搜索/浏览工具直接阅读署名原文，将实际记录写入book_content.commentary_research；采用观点登记正文、claims和commentary_cards，写清作者观点、本研究回应及验证问题。无工具/受限时记录真实限制，不能用摘要代替全文。
