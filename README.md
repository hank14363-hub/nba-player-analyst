# NBA Player Analyst v0.8.14

用可追溯数据研究NBA球员单赛季表现与战术适配，生成中文图文长文、球队主题HTML研究册和结论长图。统计缺失、模型限制与来源范围在结果中明确保留。

An evidence-based NBA player research skill for single-season analysis, tactical fit, advanced impact metrics, and interactive Chinese research books. Missing data and source limitations remain visible.

## 获取完整 Skill

- 当前源码版本：**v0.8.14**，入口为根目录的 [SKILL.md](SKILL.md)。
- [源码 ZIP](https://github.com/hank14363-hub/nba-player-analyst/archive/refs/heads/main.zip)：解压后将文件夹命名为 `nba-player-analyst`，再按下方说明安装。
- [Release 下载](https://github.com/hank14363-hub/nba-player-analyst/releases)：下载前核对标签；旧版 Release 不会随主分支自动更新。
- 完整目录包含脚本、资源、测试、文档和历史案例；不能只安装 `SKILL.md`。

## 快速开始

将完整`nba-player-analyst`文件夹放入Codex可发现的skills目录，确保`SKILL.md`位于文件夹根层。直接提出：

> 使用 $nba-player-analyst 分析斯蒂芬·库里2015–16常规赛，重点研究投射、组织与球队适配，生成图文研究册。

需要指定球员、赛季与常规赛/季后赛；转会球队段和假设适配球队分开设置。采集结果受来源与网络可用性影响，不能保证所有数据都有值。

脚本证据包入口（将`<SKILL_DIR>`替换为本文件所在目录）：

```text
python -m pip install -r <SKILL_DIR>/requirements.txt
python <SKILL_DIR>/scripts/run_analysis.py --player-id <NBA_ID> --season <YYYY-YY> --tracking --shots --out <新目录>
```

有匹配数据包时可离线导入：

```text
python <SKILL_DIR>/scripts/run_analysis.py --input <数据包目录>/data_bundle.json --player-id <NBA_ID> --season <YYYY-YY> --out <新目录>
```

Python 3.10+；离线计算与HTML/SVG只用标准库，联网依赖安装到项目环境。PNG/PDF另需可选Playwright与浏览器，见`requirements-print.txt`。`--input`不联网，补抓缺表另用`repair_data.py`。

## 当前功能与执行方式

| 功能 | 当前方式与边界 |
|---|---|
| 基础、高阶、追踪与On/Off | 官方接口或核验后的导入数据；追踪和投篮用`--tracking/--shots`，On/Off需实际样本球队ID |
| 影响力模型 | 在线默认尝试BREF、LEBRON及历史Actual EPM访问审计；DARKO需明确历史日期；拒绝访问时保留缺失 |
| Actual EPM | 合法离线导出或已核验Kaggle Actual表独立导入；核对身份、赛季、GP、总分钟与分量 |
| 历史EPM | 可显式导入归档表，保留原日期与“口径待核验”；不替代整季Actual或已验证预测 |
| 同角色比较与数值百分位 | 默认尝试已有同源匹配样本；缺失不补零，不合成能力分 |
| 雷达与单项第一特效 | 雷达须六轴同源、同一样本；第一须另核验完整联盟原表，注明并列及人数 |
| 投篮位置、区域与交互 | 完整事件总量须匹配；空间字段部分缺失时保留真实点位、覆盖率及缺失明细 |
| 四项封面指标 | 按球员鲜明特点选择，逐项关联登记指标与正文依据 |
| 球评文章与配图 | 代理实际检索、阅读和核验；脚本不会自动搜索文章或图片；记录来源、许可、日期及限制 |
| 录像观察 | 导入已观看并登记的结构化记录；不自动观看或识别录像 |

用`--no-impact`、`--no-comparisons`、`--no-advanced-percentiles`按研究范围关闭相应尝试。`--offline`仅读缓存，保留实际抓取时间。默认完整研究包含文章与图片检索；纯数据、离线或窄范围任务可如实记录跳过。

## 从证据包到完整成果

脚本先生成`analysis.json`、`metrics.csv`、`sources.json`、`evidence.md`、`writing_brief.md`及模板。随后由代理完成：

1. 查阅证据和所需球评/图片原页，保留实际记录。
2. 撰写`report.md`与`claims.json`，解释已接入高阶模型、比较和百分位。
3. 完成`book_content.json`、`poster_content.json`；采用图片时增加媒体文件、`media_content.json`与`media_research.json`。
4. 渲染、严格校验，并实际检查桌面/手机呈现。

```text
python <SKILL_DIR>/scripts/validate_report.py --run-dir <目录>
python <SKILL_DIR>/scripts/render_research_book.py --run-dir <目录> --theme auto
python <SKILL_DIR>/scripts/validate_book.py --run-dir <目录> --strict-editorial
python <SKILL_DIR>/scripts/render_player_poster.py --run-dir <目录> --theme auto
python <SKILL_DIR>/scripts/validate_poster.py --run-dir <目录>
```

`research_book.html`为内嵌图像与交互的离线单文件；正文配图阅读需保留`report.md`及`charts/`。模板、取数成功和结构检查通过均不代表篮球判断已获证明。PDF按需要导出；修改后用`--force`重建派生文件。

## 文档导航

| 需要了解 | 入口 |
|---|---|
| 代理完整执行流程 | [SKILL.md](SKILL.md) |
| 官方取数、备用来源与网络故障 | [data_sources.md](references/data_sources.md)、[data_repair.md](references/data_repair.md) |
| Kaggle与Sumitro导入 | [kaggle_import.md](references/kaggle_import.md)、[sumitro_import.md](references/sumitro_import.md) |
| 影响力、Actual/历史EPM | [impact_models.md](references/impact_models.md)、[epm_import.md](references/epm_import.md)、[kaggle_epm.md](references/kaggle_epm.md) |
| 比较、百分位和雷达 | [role_comparisons.md](references/role_comparisons.md)、[advanced_percentiles.md](references/advanced_percentiles.md) |
| 投篮图和交互 | [shot_locations.md](references/shot_locations.md)、[shot_explorer.md](references/shot_explorer.md) |
| 球评与图片检索 | [commentary_research.md](references/commentary_research.md)、[image_research.md](references/image_research.md) |
| 研究册、媒体和结论长图 | [research_book.md](references/research_book.md)、[editorial_media.md](references/editorial_media.md)、[player_poster.md](references/player_poster.md) |
| 版本、测试与后续方向 | [CHANGELOG.md](CHANGELOG.md)、[TEST_REPORT.md](TEST_REPORT.md)、[development_roadmap.md](references/development_roadmap.md) |

## 目录与案例

```text
nba-player-analyst/
├── SKILL.md / README.md       执行入口与使用说明
├── agents/                   Codex发现与界面元数据
├── scripts/                  采集、导入、计算、渲染、检查
├── references/               按任务选读的方法、契约与配置
├── assets/                   HTML/CSS/JS与文字标签
├── tests/                    回归测试
├── examples/                 真实历史案例与明确标记的合成样式测试
├── documentation/            版本验证、打包记录和历史快照
└── PACKAGE_INFO.json / FILE_HASHES.json  发布信息与文件摘要
```

| 案例 | 用途 |
|---|---|
| [官方高阶案例](examples/cade-cunningham-2024-25-official-v081/research_book.html) | BREF、LEBRON转引、历史DARKO；完整来源与研究册 |
| [比较与投篮案例](examples/cade-cunningham-2024-25-official-v08/research_book.html) | 同角色比较、门槛敏感性、频次图与个性化封面 |
| [图文与球评案例](examples/cade-cunningham-2024-25-official-v07/research_book.html) | 图文重组、真实事件筛选、署名球评回应 |
| `examples/kaggle-*`、`examples/sumitro-*` | 备用来源的导入证据包，并非都含完成的文章 |
| `examples/demo_output/` | 合成样式测试，不可用于真实球员评价 |

较早案例保留原路径；[CHANGELOG.md](CHANGELOG.md)记录各阶段功能。最近库里配图/空间缺失修复与勒布朗雷达的现场案例位于用户项目，未随Skill打包；验证边界见 [v0.8.14记录](documentation/validation_v0814.md)。旧请求保留确定性复算，新选项不自动改写旧文稿。

## 版本与验证

当前发布版本为**v0.8.14**；数据/claims结构为0.1.0，研究册内容为0.2.0，长图内容为0.3.0。运行`check_release.py`核对，不能把发布版本写进旧数据结构字段。

现有595项回归及最新媒体/投篮修复验证见 [TEST_REPORT.md](TEST_REPORT.md)；维护与摘要核验见 [PACKAGE_VALIDATION.md](PACKAGE_VALIDATION.md)。2026-10-18本轮仅整理文档，保留算法、脚本、资源与案例路径。

`epm_value_imported=false`表示分发包没有真实EPM案例；Kaggle真实导入现场验证另有标志。官网直接导出验收、Kaggle转引验收和历史归档口径是不同状态，不能据一个标志笼统判断所有EPM都可用或不可用。

## 研究册预览

以下为随包保留的 v0.8.1 历史案例截图；不代表全部 v0.8.14 新功能。

![坎宁安研究册历史案例预览](docs/images/cade-v081-impact.png)

## 许可与来源

代码采用 [MIT License](LICENSE)。图片、转引统计与其他第三方内容按各自来源和许可处理；保留案例中的署名、许可链接、日期与限制，不因仓库采用 MIT 而改变其许可。
