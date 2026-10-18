# 坎宁安2024—25常规赛 · 官方数据重建案例

先打开research_book.html，再看player_poster.png或report.md。本轮八类图、六处正文配图；长图六类图全部由真实数据生成。来源、原始行、指标、结论清单和检查文件在同目录。此案例不代表当前赛季。

全部统计来自2026-10-12实际访问的NBA Stats完整参数响应。基础计数与旧案例一致，使用率/助攻率和每回合值以官方定义重新计算，不混入第三方估计。Advanced/Scoring返回场均MIN的特例已核验；受助攻分母是命中球。真正On/Off匹配同球队及分钟覆盖，描述球队表现，不是个人因果贡献或防守评分。

新研究册包含8类不同图，正文重复嵌入其中6图以便阅读；重复展示不算新证据。PNG为1080px宽结论长图；book-1440-cover.png、book-390-cover.png及chart-preview.png是浏览预览。研究册为离线单文件，Markdown正文与charts目录一起复制即可保留配图。

复算：使用Skill的run_analysis.py --player-id 1630595 --season 2024-25 --input <本目录>/data_bundle.json --out <新目录>，重新生成证据后再完成成稿与渲染，不手动改数据。校验器确认复算、引用与文件一致性；具体战术建议仍需录像验证。本轮没有新导出PDF。
