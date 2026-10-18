# NBA Player Analyst｜完整交付包

本包以 **v0.3.1 表达优化版**为唯一可安装的技能，合并此前已完成的功能、示范成果和凯德·坎宁安真实历史案例。无需分别安装 v0.1、v0.2 或 v0.3。本次仅整理交付，不修改数据计算与采集代码，也不新增实时数据。

## 先看什么

| 用途 | 文件或目录 |
|---|---|
| 安装与使用 | `README.md` |
| 技能入口与完整工作流程 | `SKILL.md` |
| 坎宁安结论长图 | `examples/cade-cunningham-2024-25/player_poster.png` |
| 坎宁安交互研究册 | `examples/cade-cunningham-2024-25/research_book.html` |
| 坎宁安 PDF 研究册 | `examples/cade-cunningham-2024-25/research_book.pdf` |
| 坎宁安中文长文 | `examples/cade-cunningham-2024-25/report.md` |
| 坎宁安数据、来源与限制 | `examples/cade-cunningham-2024-25/README.md` |
| 最新合成样式示范 | `examples/demo_output/` |
| 早期版本说明与样式记录 | `documentation/history/` |
| 本次打包核验 | `PACKAGE_VALIDATION.md` |

## 包含哪些能力

数据采集与缓存、离线 JSON/CSV 导入、高阶指标计算、球员实力与战术适配分析规范、中文长文写作、专业术语的通俗解释、球队风格配色、HTML 研究册、带篮球解读的图表、球员结论长图、可选 PNG/PDF 导出，以及数值、引用和成果一致性检查。

`Python` 负责采集、计算和生成展示成果；完整文章及战术分析由 Codex 按技能指令撰写。仅运行数据脚本，不等于文章已完成。

## 安装时注意

按 `README.md` 安装。解压后的 `nba-player-analyst` 文件夹放入项目 `.agents/skills/`，目录应为 `.agents/skills/nba-player-analyst/SKILL.md`，不要额外嵌套一层。

已有旧版时先移到技能扫描目录之外备份，再替换；保留虚拟环境、缓存和已有报告。历史说明仅供查看，不另建同名技能。

代码、模板和参考规范保持 v0.3.1；本次新增的案例与历史资料不改变既有数据结构版本。安装依赖和运行命令以根目录 `README.md` 为准，不以历史目录中的旧说明为准。

## 本地离线复核坎宁安

在项目根目录运行，并将 `python` 替换成项目虚拟环境的解释器：

```text
python .agents/skills/nba-player-analyst/scripts/run_analysis.py --player "Cade Cunningham" --season 2024-25 --input .agents/skills/nba-player-analyst/examples/cade-cunningham-2024-25/data_bundle.json --out reports/cade-recheck
```

该命令复跑数据阶段，不重新取数，也不会自动重写文章。完整案例中保留了文章、结论清单、研究册编辑内容、长图编辑内容和导出成果。每次使用新的输出目录，避免覆盖旧成果。

## 样本与验证边界

坎宁安案例仅覆盖 **2024—25 赛季常规赛**。核心数据由公开赛季表整理导入，不是 NBA Stats 接口直连成功的证明；每75回合补充数据另有索引访问及舍入限制，详见案例说明。不能将这份历史报告当成实时实力结论。

`examples/demo_output/` 与历史样式中的虚构球员使用合成测试数据，不能用于真实球员评价。

本次重新运行了160项离线回归测试，并检查两份案例的报告、研究册与长图一致性。没有新增在线接口、本地 Codex 或浏览器排版实测。包内既有视觉检查记录保留原来的日期与范围。

未打包 Python 虚拟环境、浏览器程序、字体文件或账户凭据。可选导出依赖需按说明在本地准备。