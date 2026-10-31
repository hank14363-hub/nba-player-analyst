# v0.8.17 · 初版研究册缺口修复

2026-10-23。根据线程`$nba-player-analyst 分析MVP赛季威斯布鲁克的赛场表现`的实际结果，补强“数据到成稿”的最后一步。

- 初版已有百分位数据，但研究册未必声明雷达；现在有可用百分位时默认要求`percentile_presentation=radar`，只有明确`bars`才允许条形图。
- 初版缺少配图时容易停在搜索计划；现在要求真实`media_research.json`执行记录、`media_content.json`本地素材和`EXT_MEDIA_`来源，缺失必须写`limited`或用户明确`skipped`。
- 初版球评记录可能停留在建议查询；现在要求直接阅读原文、登记作者/日期/原页，在正文/claims/`commentary_cards`中形成观点回应。
- `validate_book.py --strict-editorial`新增`percentile_radar_missing`，并继续审查图片及球评缺口。

新增3项测试，总计657项回归。未改变统计值、雷达算法、图片许可规则或球评内容；只把遗漏从“可选说明”提升为“可见的成稿检查”。
