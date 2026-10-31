# NBA Player Analyst v1.0.0 · V1.00

用可追溯数据研究NBA球员单赛季表现与战术适配，生成中文图文长文、离线HTML研究册和结论长图。保留原始证据、可复算指标、来源与结论依据，明确缺失和模型限制。

An evidence-based NBA player research skill for single-season analysis, tactical fit, advanced statistics, and interactive research books. V1.00 adds same-source percentile compasses with traceable quantile scales and accessible controls.

## 下载 V1.00

- [完整 Skill ZIP](https://github.com/hank14363-hub/nba-player-analyst/releases/download/v1.0.0/nba-player-analyst-v1.0.0-full.zip)：约108 MB，含完整源码、测试与历史案例。
- [轻量运行包](https://github.com/hank14363-hub/nba-player-analyst/releases/download/v1.0.0/nba-player-analyst-v1.0.0-runtime.zip)：约7.8 MB，含全部运行代码、方法文档与当前案例。
- [校验摘要](https://github.com/hank14363-hub/nba-player-analyst/releases/download/v1.0.0/SHA256SUMS.txt) · [版本说明](https://github.com/hank14363-hub/nba-player-analyst/releases/tag/v1.0.0) · [主分支源码 ZIP](https://github.com/hank14363-hub/nba-player-analyst/archive/refs/heads/main.zip)

下载后保留整个`nba-player-analyst`文件夹结构。选择主分支源码ZIP时，将解压文件夹重命名为`nba-player-analyst`。


## V1.00：进阶统计罗盘

- **同心圆画像**：优先BR十一轴与NBA十轴，分来源切换；扩展字段不齐时退回同源六轴。
- **环上分位参考**：七层数值从保留的同季合格总体排序并线性插值，和球员的中秩百分位分别计算；不抄示例值或补造总体。
- **广播风格呈现**：明暗圆环、发光轮廓、切线中文名/代码/原值/P值、已登记球员照片与经独立核验的单项第一高亮。
- **可读的交互**：点轴解释、逐轴参考表、刻度开关、有限动效重播、键盘操作、独立SVG导出；兼顾手机、减少动画、无脚本与打印。
- **兼容旧成果**：旧协议复算保持不变；迁移工具在新目录重放证据，核对原有指标不变，再增加新刻度。

外圈表示更高的**数值百分位**，不合成能力分。职责、环境、模型和累计量分别解释。内缘P0、外缘P100，中心盘没有数据；完整方法见 [罗盘说明](references/radar_compass.md)。

[打开库里2015–16完整研究册](examples/curry-2015-16-v100/research_book.html#percentile-radar) · [BR十一轴SVG](examples/curry-2015-16-v100/charts/percentile_bref_compass_radar.svg) · [NBA十轴SVG](examples/curry-2015-16-v100/charts/percentile_nba_compass_radar.svg)

随包案例为保留证据重放，包含真实配图、已阅读球评及来源限制，不代表本次重新联网取数。旧案例保留原路径；历史案例和tests只在完整包提供。

## 罗盘预览

![库里2015–16高阶统计罗盘](docs/images/curry-v100-compass.png)

真实保留样本重放：BR十一轴、350名同季合格球员；原值、中秩百分位与插值参考刻度分别展示，图形面积不代表综合分。下载ZIP后，在本地打开`examples/curry-2015-16-v100/research_book.html`体验来源切换、解释卡与缩放。

## 使用

将整个`nba-player-analyst`文件夹放入Codex可发现的skills目录，根层须有`SKILL.md`。在对话中提出：

> 使用 $nba-player-analyst 分析斯蒂芬·库里2015–16常规赛，重点研究投射、组织与球队适配，生成图文研究册。

指定球员、赛季、常规赛/季后赛及研究重点。完整执行流程见 [SKILL.md](SKILL.md)。Python 3.10+；离线计算和HTML/SVG使用标准库，联网依赖安装到项目环境。PNG/PDF导出另需可选Playwright与浏览器。

```text
python -m pip install -r <SKILL_DIR>/requirements.txt
python <SKILL_DIR>/scripts/run_analysis.py --player-id <NBA_ID> --season <YYYY-YY> --tracking --shots --out <新目录>
```

有匹配数据包时离线导入：

```text
python <SKILL_DIR>/scripts/run_analysis.py --input <旧目录>/data_bundle.json --player-id <NBA_ID> --season <YYYY-YY> --out <新目录>
```

脚本生成证据包和待填模板；代理还需实际阅读资料、撰写正文、登记claims、选择配图并完成编辑内容。模板或取数成功不等于完整分析。`--input`不联网；缺表通过`repair_data.py`在新目录补采。来源可用性随网络与权限变化，不保证每个指标都有值。

## 数据与分析范围

| 功能 | 当前方式与边界 |
|---|---|
| 基础、高阶、追踪、On/Off | 官方接口或核验导入；追踪/投篮显式开启；On/Off需实际样本球队ID，在场效率不等于个人因果影响 |
| BREF、LEBRON、DARKO | 在线默认尝试前两者；DARKO需要明确历史日期；单人模型不冒充联盟分布 |
| Actual EPM | 合法离线导出或已核验Kaggle Actual表独立导入，检查身份、赛季、GP、总分钟和分量 |
| 历史EPM | 保留原日期、Kaggle转引和“口径待核验”；不是整季Actual、同日预测或能力雷达 |
| Kaggle / Sumitro | 适配器保留原始文件/行和哈希，核验身份桥接与统计定义；不是通用任意CSV读取器 |
| 同角色比较与百分位 | 默认尝试已有同源匹配总体；逐项保留N、门槛、缺失和方向，不混源合成评分 |
| 投篮图 | 完整事件须匹配FGA/FGM/3PA/3PM；只画真实可用坐标，明确覆盖率和未定位事件 |
| 四项封面指标 | 按球员特点选择登记指标，并关联正文结论 |
| 球评文章 | 代理实际搜索、阅读署名原文、登记采用/排除并回应观点；脚本不自动阅读网页 |
| 图片与GIF | 分层检索、原页/身份/日期/许可核验、本地文件审查与图注；无可靠素材时明确limited/skipped |
| 录像观察 | 导入真实观看并登记的结构化记录；不把图片或作者看片冒充本研究观察 |

按研究范围使用`--no-impact`、`--no-comparisons`或`--no-advanced-percentiles`。`--offline`仅读缓存并保留实际抓取时间。未接入的指标不补零、不用另一球员或演示数据替代。

## 成稿与校验

完成`report.md`、`claims.json`、`book_content.json`和`poster_content.json`；采用影像时还需媒体文件、来源与研究日志。默认完整研究的配图、雷达、球评都要实际落地或如实记录限制。

```text
python <SKILL_DIR>/scripts/validate_report.py --run-dir <目录>
python <SKILL_DIR>/scripts/render_research_book.py --run-dir <目录> --theme auto
python <SKILL_DIR>/scripts/validate_book.py --run-dir <目录> --strict-editorial
python <SKILL_DIR>/scripts/render_player_poster.py --run-dir <目录> --theme auto
python <SKILL_DIR>/scripts/validate_poster.py --run-dir <目录>
```

`research_book.html`内嵌图像与交互，离线可读；正文Markdown需保留`charts/`。修改内容后用`--force`重建派生文件，再检查桌面、手机、图注和来源跳转。自动检查证明结构、数字与重放一致性，不证明因果或篮球判断。

升级已完成的百分位研究册：

```text
python <SKILL_DIR>/scripts/upgrade_radar.py --run-dir <旧成稿目录> --out <不存在的新目录>
```

该工具先验证旧成稿和原始文件，拒绝覆盖与旧指标改变；保留正文、球评、照片及抓取日期。新请求保存`radar_protocol=1.0.0`，数据/claims、book、poster结构版本各自独立。

## 文档入口

| 需要了解 | 文档 |
|---|---|
| 完整执行流程 | [SKILL.md](SKILL.md) |
| 来源、定义与补数 | [数据源](references/data_sources.md)、[指标](references/metrics.md)、[缺失修复](references/data_repair.md) |
| 导入 | [标准输入](references/input_schema.md)、[Kaggle](references/kaggle_import.md)、[Sumitro](references/sumitro_import.md) |
| 影响力与EPM | [模型说明](references/impact_models.md)、[Actual导入](references/epm_import.md)、[Kaggle历史EPM](references/kaggle_epm.md) |
| 比较与罗盘 | [同角色比较](references/role_comparisons.md)、[百分位](references/advanced_percentiles.md)、[V1.00罗盘](references/radar_compass.md) |
| 文章、图片与研究册 | [球评](references/commentary_research.md)、[图片检索](references/image_research.md)、[研究册](references/research_book.md)、[成稿检查](references/research_completion.md) |
| 发布与验证 | [版本记录](CHANGELOG.md)、[测试记录](TEST_REPORT.md)、[V1.00验证](documentation/validation_v100.md)、[分发检查](PACKAGE_VALIDATION.md) |
| 后续扩展 | [发展路径](references/development_roadmap.md)及罗盘说明末节 |

## 分发与维护

```text
python -m unittest discover -s <SKILL_DIR>/tests -v
python <SKILL_DIR>/scripts/check_release.py
python <SKILL_DIR>/scripts/package_skill.py --profile full --out <Skill目录之外的新ZIP路径>
python <SKILL_DIR>/scripts/package_skill.py --profile runtime --out <Skill目录之外的另一新ZIP路径>
```

**full**包含运行代码、方法文档、当前及历史案例和回归测试；**runtime**包含相同运行代码、方法文档、当前真实案例与合成结构示例，省略旧案例和tests。归档附`DISTRIBUTION.json`和逐文件SHA-256，运行包中的历史路径需要完整包。安装保留整个文件夹结构，不需要上传缓存、Python环境或凭证。

本版674项离线回归通过，并对真实库里、詹姆斯案例进行图表/交互检查，范围见验证记录。接口、许可、模型解释和来源覆盖的实际限制继续在结果中保留。

## 许可与来源

代码采用 [MIT License](LICENSE)。图片、统计数据和其他第三方内容按各自来源与许可处理；案例保留署名、许可链接、日期及用途限制，仓库的MIT许可不改变第三方内容的许可。
