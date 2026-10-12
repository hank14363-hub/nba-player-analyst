# NBA Player Analyst v0.8.1

生成有来源的中文NBA球员分析、图文研究册和球队主题结论长图。新增单表补抓、真实投篮位置/区域图和结构化录像记录；保留官方联网诊断、真实On/Off、追踪指标、正文SVG嵌图与来源质量披露；保留历史功能和样式。主流程见 SKILL.md。

## 安装与运行环境

本次已安装到用户 ~/.codex/skills/nba-player-analyst。分发包可解压到自己的Codex用户skills目录，以 $nba-player-analyst 调用；新会话可重新发现技能。不要解压到系统目录或覆盖无关技能。

离线计算、HTML/SVG与回归仅需Python 3.10+标准库。联网依赖 requirements.txt；可选PNG/PDF依赖 requirements-print.txt 与兼容Chromium。使用项目虚拟环境或Codex提供的Python，依赖安装到项目环境，不捆绑此机器运行时，不更改系统代理。

```text
python -m pip install -r <SKILL_DIR>/requirements.txt
python <SKILL_DIR>/scripts/diagnose_network.py --season 2024-25 --out <新目录>/network_diagnostic.json
python <SKILL_DIR>/scripts/run_analysis.py --player-id 1630595 --season 2024-25 --tracking --shots --on-off-team-id 1610612765 --out <新目录>
```

此命令只生成证据包；Codex继续完成report.md、claims.json、book_content.json和poster_content.json，并运行渲染与检查。不能交付模板冒充文章。

## 浏览成果

- examples/cade-cunningham-2024-25-official-v08/research_book.html：完整功能样本与统计百分位、门槛敏感性、真实频次热区、PIE与EPM访问边界、个性化四项封面；保留此前球场交互和正文往返。方法见references/role_comparisons.md。

- examples/cade-cunningham-2024-25-official-v073/research_book.html：半场聚焦／完整全场、圆点／叉形、邻近候选、区域解读与正文样本往返。配置reading_cards.shot_zone见references/shot_explorer.md，shot-research-preview.png提供图文联动预览。

- examples/cade-cunningham-2024-25-official-v072/research_book.html：参考视频视觉的透视球场舞台、发光点、装饰光弧、累计计数与进度；保留平面图切换与真实事件。配套shot-stage-preview.gif和style_reference.json。

- examples/cade-cunningham-2024-25-official-v071/research_book.html：完整球场点位动效、点击定位圆环、可暂停调速的逐次点亮；配套shot-animation-preview.gif与动效验证记录。

- examples/cade-cunningham-2024-25-official-v07/research_book.html：13个图文主题、真实投篮筛选、三位署名球评对读及5,134字完整长文；配套研究笔记、可编辑解读、截图与最新长图。

- examples/cade-cunningham-2024-25-official-v061/research_book.html：18张分析卡、新增2801字解读和紧凑指标条；扩展文本见同目录研究解读补充.md。

- examples/cade-cunningham-2024-25-official-v06/research_book.html：视觉升级案例，浅色图表、2张资料照、1组可控照片GIF、4474字正文与分组来源索引。
- examples/cade-cunningham-2024-25-official-v05/：上一轮10类图、8处正文配图和补抓案例。
- examples/cade-cunningham-2024-25-official-v04/：上一轮官方案例，8类图、6处正文配图。
- 同目录player_poster.png与player_poster.html：6类图全部有数据的结论长图。
- examples/cade-cunningham-2024-25/：原第三方导入数据，用新版重建HTML；仍保留缺失。
- examples/demo_output/：合成样式测试，不能套用到真实球星。
- documentation/history/v0.3.1/examples/：原案例、原PNG/PDF/HTML的未经改写快照；其他history目录保留更早版本。

单文件HTML可离线打开；report.md与charts文件夹一起复制即可阅读正文配图。官方案例的data_bundle.json保留全部实际行与来源；--input导入该文件到新目录可重算。历史保存的analysis若因新版字段说明不匹配而拒绝，重新从原data_bundle.json导入，不手改统计。

## 导出和测试

```text
python <SKILL_DIR>/scripts/render_research_book.py --run-dir <目录>
python <SKILL_DIR>/scripts/validate_book.py --run-dir <目录>
python <SKILL_DIR>/scripts/render_player_poster.py --run-dir <目录>
python <SKILL_DIR>/scripts/validate_poster.py --run-dir <目录>
python <SKILL_DIR>/scripts/export_poster.py --run-dir <目录> --browser-path <已安装Chrome或Edge路径>
python -m unittest discover -s <SKILL_DIR>/tests -v
```

PNG/PDF导出不自动安装浏览器。PDF仅按用户需要生成并另做分页检查。修改后用--force重建派生文件，原始数据与正文不覆盖。

新版检查结果见 documentation/validation_v081.md。真实取数成功不代表所有环境永久可达，结构与数值检查不代表因果判断或战术建议被证明。真实投篮图与录像记录校验已实现；自动录像识别、阵容调整模型、能力排名与个人防守评分尚未实现。下一步见 references/development_roadmap.md。

## 新增入口

```text
python <SKILL_DIR>/scripts/repair_data.py --input <旧数据包> --tables player_shots --player-id <ID> --out <新补抓目录>
python <SKILL_DIR>/scripts/run_analysis.py --input <新补抓目录>/data_bundle.json --player-id <ID> --season <YYYY-YY> --out <新证据目录>
python <SKILL_DIR>/scripts/render_shot_charts.py --run-dir <证据目录> --out <新图目录>
```

--input 不联网；与 --shots/--tracking/--on-off-team-id 同用会明确报错，避免误以为补抓已发生。完整采集时用 --shots。真实录像记录完成后加 --film 导入；仅有模板不代表已有观察。入口详见 references/data_repair.md、shot_locations.md、film_workflow.md。

研究册影像和动效通过 references/editorial_media.md 配置；单文件HTML已内嵌素材，离线也能播放GIF。授权/拍摄年份和数据来源分别登记。新版测试见 documentation/validation_v081.md。

图文重组及交互说明见references/shot_explorer.md；球评文章研究与署名归属见references/commentary_research.md。作者观点不是本研究录像观察，阶段数字不能替代整季数据。


可选 --comparisons 复用完整全联盟表，核验样本后生成描述性比较；不会自动增加NBA取数或抓取受限EPM。统计百分位不是能力或综合排名。book_content.core_metrics 支持四项登记过指标和正文依据的个性化封面；结论长图共用。


v0.8.1新增公开高阶影响力补数与可复算模型契约；方法与命令见references/impact_models.md。最新案例examples/cade-cunningham-2024-25-official-v081/，含整季BPM/VORP/WS、LEBRON转引与历史DARKO预测、原始快照及排除记录。285项回归；全部此前案例与样式保留。
