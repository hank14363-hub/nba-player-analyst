# v0.7 最终小范围复核

最新发布树 SKILL.md 已标 v0.7.0，并直接链接 references/shot_explorer.md 与 commentary_research.md；research_book.md 写明 presentation=integrated 与 reading_cards.chart_key，新增来源署名、文章归属和阶段样本限制可发现。此前版本/文档缺漏已补齐。

使用隔离目录副本重新生成研究册，并以 Chrome / Playwright 在 390 像素手机宽度分别采用减少动画与正常动画验证。当前 HTML 共十个 SVG，折叠“补充数据图”包含得分来源、球队背景两图，打开后可读且无横向溢出；两图均在滚入视口后正常显示。历史影像默认折叠，展开后照片与照片轮播 GIF 加载成功、图注保留二〇二二年技巧挑战赛和非连续录像限制；GIF 默认静态，播放/暂停按钮均有效。得分主题、球评与新增折叠区的主要内容在两种动画设置下均能显示，没有被动效持续隐藏。完整长文起始与上述操作后保持关闭。

已实际查看 supplement-390-reduce.png 与 media-390-reduce.png；固定导航在元素长截图中的覆盖是截屏定位叠加，不将其误判成内容缺失。补充图标注及影像图注均完整。结果详见 final_results.json 和 final_check.py。本次没有重新联网核验文章原页，也没有声称看过比赛录像。
