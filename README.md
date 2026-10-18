# NBA Player Analyst

**从可追溯数据到中文分析、交互式研究册与结论长图。**

A Codex skill for evidence-based NBA player research, Chinese reports, interactive HTML research books, and team-themed visual summaries. Missing data and model limitations stay explicit.

[下载公开完整包 v0.8.1](https://github.com/hank14363-hub/nba-player-analyst/releases/download/v0.8.1/nba-player-analyst-v0.8.1.zip) · [Release 说明](https://github.com/hank14363-hub/nba-player-analyst/releases/tag/v0.8.1) · [Skill 执行流程](SKILL.md) · [研究方法与文档](#研究方法与文档)

> **版本说明（2026-10-18）：** 当前仓库核心源码与公开完整包为 **v0.8.1**。后续本地维护已推进至 **v0.8.14**，尚未同步到当前源码及Release。下方使用命令对应公开版本；新版本的EPM导入、六轴雷达与缺失恢复等进展在文末单列。

## 能研究什么

围绕一名球员、一个赛季和明确的比赛类型，解释其竞争特点、使用条件与战术适配。适合球员研究、球探报告和赛季复盘；不用于即时比分或投注建议。

| 研究内容 | 成果与条件 |
|---|---|
| 产量、效率与组织 | 基础、高阶、受助攻和追踪指标共同解读，保留各表覆盖范围 |
| 球队在场表现 | 核验同队On/Off及分钟后作描述性比较，不将差值当个人因果贡献 |
| 真实投篮分布 | 核验完整事件后展示点位、区域和出手频次；支持筛选、点亮回放、暂停调速与正文跳转 |
| 同角色比较 | 用核验后的完整联盟表展示实际值、同组中位数、统计百分位与门槛敏感性 |
| 影响力模型 | 支持BPM、VORP、Win Shares、公开LEBRON转引与带日期的DARKO历史预测，分别解释来源与范围 |
| 图文研究成果 | 中文长文、球队主题离线HTML研究册、结论长图及来源清单；按球员特点选择四项封面指标 |
| 外部观点与录像记录 | 实际查阅的球评文章署名引用；导入真实录像观察及比赛、双时钟、观察者与替代解释 |

缺失留空并说明，不用其他球员、其他赛季或合成数据补齐；不生成任意综合实力分、个人防守评分或能力排名。模型防守分量不等于个人防守能力。

## 选择下载方式

| 内容 | 仓库源码 / Source code ZIP | Release完整包 |
|---|---|---|
| Skill、脚本、方法文档、视觉资源、代理配置 | 包含 | 包含 |
| 完整案例`examples/` | 不包含 | 包含 |
| 测试与夹具`tests/` | 不包含 | 包含 |
| 验证、历史资料和打包清单 | 不包含 | 包含 |

首次使用、浏览完整案例或运行回归，下载 **Release附件`nba-player-analyst-v0.8.1.zip`**。GitHub自动生成的“Source code (zip)”只有核心源码。最新维护成果尚未发布为新的下载附件。

## 快速开始

### 1. 安装

解压后将完整`nba-player-analyst/`放入当前Codex环境识别的个人或项目skills目录，保持`nba-player-analyst/SKILL.md`层级。已有可识别安装时，避免重复安装同名Skill；具体目录以当前Codex配置为准。

使用Python 3.10+，在Skill根目录安装依赖，建议使用项目虚拟环境：

```bash
python -m pip install -r requirements.txt
```

离线指标计算与HTML/SVG渲染使用标准库；联网和第三方页面解析需要对应依赖。PNG/PDF导出可选安装`requirements-print.txt`并配置Chrome/Edge等兼容浏览器。**阅读生成的单文件HTML不需要Python或运行服务。**

### 2. 在Codex中调用

```text
使用 $nba-player-analyst 分析凯德·坎宁安2024–25常规赛。
重点研究持球创造、投篮效率、失误成本和战术适配。
使用可追溯数据，补充可核验的公开影响力指标和署名球评观点。
按球员特点选择四项封面核心数据，生成中文图文长文、交互式研究册、结论长图及来源清单。
明确标注缺失、转引、模型预测和分析推断，将成果写入新目录。
```

更换球员时明确姓名或NBA ID、赛季及常规赛/季后赛。`--team-id`表示球员实际效力段，`--target-team-id`表示拟适配球队；两者不能混用。旧案例只演示流程，不能代替新研究取数。

### 3. 浏览完整包内的案例

解压后用浏览器打开：

```text
examples/cade-cunningham-2024-25-official-v081/research_book.html
```

![坎宁安研究册：整季影响力与带日期的历史预测分开呈现](docs/images/cade-v081-impact.png)

该历史案例保留70场、1,457次真实出手、141个可用指标和41条登记结论。数量描述此案例，不代表其他球员能获得相同覆盖。BPM、LEBRON与DARKO分别解释，来源可跳转核对。

`research_book.html`可离线阅读；编辑正文时保留`report.md`与`charts/`；`claims.json`、`sources.json`用于核对结论和引用；`data_bundle.json`与`raw/`保留可复算输入。`examples/demo_output/`是合成样式测试，不能用于真实球员评价。

## 数据与结论如何衔接

**采集/导入 → 样本与指标核验 → 阅读资料并写作 → 登记结论和引用 → 渲染 → 校验与视觉检查。**

`run_analysis.py`生成证据包和模板，不会自动完成文章、球评阅读或图片搜索。Codex还需完成`report.md`、`claims.json`、`book_content.json`与`poster_content.json`，解释指标的篮球意义与限制，再生成研究册。模板或取数成功不等于成稿。

来源优先采用实际官方响应、合法且可核验的导出、定义明确的公开备用源；保存请求、抓取时间、原始行和摘要。网络故障有限重试，访问受限则停止该途径并记录，不绕过订阅或用其他日期读数替代。

公开v0.8.1的EPM尚未导入，RAPM候选因比赛集合与覆盖待核验而未纳入案例。DARKO是带历史日期的生涯加权预测，不是整季实际贡献；LEBRON公开转引须保留来源链。模型输入可能重叠，方向一致不等于独立验证。统计百分位描述样本位置，出手频次图描述次数，都不是能力评分。

## 可选：命令行工作流

以下命令在公开版Skill根目录运行，输出目录需新建或为空。接口及数据覆盖决定实际可用内容。

```bash
# 官方采集；On/Off必须指定实际样本球队
python scripts/run_analysis.py --player-id 1630595 --season 2024-25 --tracking --shots --on-off-team-id 1610612765 --out runs/cade-online

# 网络故障诊断
python scripts/diagnose_network.py --season 2024-25 --out runs/network-check/network_diagnostic.json

# 完整包内案例的离线复算；比较需显式开启
python scripts/run_analysis.py --input examples/cade-cunningham-2024-25-official-v081/data_bundle.json --player-id 1630595 --season 2024-25 --comparisons --out runs/cade-offline
```

`--input`不联网，不能与`--tracking/--shots/--on-off-team-id`同用；补抓另用`repair_data.py`。`--comparisons`复用核验后的联盟表，不自动补造样本。

公开高阶补数可用`collect_impact.py`。它默认只选BREF；增加LEBRON或DARKO需显式`--providers`，DARKO需`--cutoff`历史日期，身份键与样本规则见 [影响力模型](references/impact_models.md)。公开版主流程不会自动完成后续维护版的默认高阶采集。

内容完成后的渲染与检查：

```bash
python scripts/review_language.py --run-dir runs/cade-offline
python scripts/validate_report.py --run-dir runs/cade-offline
python scripts/render_research_book.py --run-dir runs/cade-offline --theme auto
python scripts/validate_book.py --run-dir runs/cade-offline
python scripts/render_player_poster.py --run-dir runs/cade-offline --theme auto
python scripts/validate_poster.py --run-dir runs/cade-offline
```

PNG导出用`export_poster.py`，可用`--browser-path`指定浏览器；PDF按需要导出并另查分页。修改内容后用相应脚本的`--force`重建，保留原始数据。完整包可运行`python -m unittest discover -s tests -v`；核心源码仓库没有测试目录。

## 后续维护进展：v0.8.14（待同步发布）

下列内容已在本地维护版实现并验证，**当前仓库源码和v0.8.1下载包尚不包含这些新增能力**：

| 维护方向 | 已完成的进展与限制 |
|---|---|
| 历史数据备用源 | deocheng Kaggle与Sumitro/BR独立导入，保留原始行、SHA-256、身份桥接和确定性复算 |
| EPM接入 | 合法Actual离线导入、Kaggle Actual核验、带“口径待核验”备注的历史归档；在线访问审计不代表取得受限数值 |
| 高阶表达 | 默认尝试同源数值百分位，六轴同源雷达；单项第一另核验完整联盟原表，并保留并列与样本人数 |
| 分析完整性 | 默认高阶尝试、模型已采未写检查、署名球评检索记录与图片来源核验；检索阅读由代理实际执行 |
| 配图恢复 | 单张下载失败后继续正常公开替代检索，区分拍摄/上传日期、许可与用途；手机图注排版修复 |
| 投篮缺失恢复 | 完整事件中个别空间字段缺失时保留真实点位与覆盖率；库里案例恢复1,596/1,598次坐标，缺失两次单列 |

本地v0.8.14维护版595项回归通过；公开v0.8.1发布时为285项。两者属于不同版本的验证记录，不能在旧源码上直接复现新测试或新功能。后续发布时需同步脚本、资源、方法文档与版本信息，不能只修改README版本号。

接下来优先核实历史EPM的估计类型与覆盖、补充同口径区域基准、增加真实录像与同角色模型样本。自动录像识别、阵容调整因果模型、校准综合评分与联盟实力排名仍未实现。

## 研究方法与文档

| 主题 | 公开版文档 |
|---|---|
| 数据、导入、补抓 | [来源与访问](references/data_sources.md) · [输入契约](references/input_schema.md) · [单表恢复](references/data_repair.md) |
| 指标与样本 | [指标定义](references/metrics.md) · [追踪和On/Off](references/advanced_data.md) · [同角色比较](references/role_comparisons.md) |
| 投篮图与交互 | [真实位置](references/shot_locations.md) · [交互研究](references/shot_explorer.md) |
| 模型、观点与录像 | [影响力模型](references/impact_models.md) · [球评文章](references/commentary_research.md) · [录像记录](references/film_workflow.md) |
| 呈现与输出 | [研究册](references/research_book.md) · [影像配置](references/editorial_media.md) · [结论长图](references/player_poster.md) |

公开完整包内`documentation/validation_v081.md`记录当时的回归和桌面/窄屏、无脚本、打印检查。离线测试不证明网站当前可访问，结构与数值校验不证明篮球判断或因果关系；语义和视觉仍需实际审阅。公开方法文档对应v0.8.1，后续维护规则以新版本发布时的文档为准。

## 许可与致谢

原创代码与模板采用 [MIT License](LICENSE)。NBA数据、第三方模型、文章与影像遵循各自提供者的条款及授权，仓库许可不替代上游许可。案例资料照保留署名、许可和改动说明，照片轮播不冒充连续比赛录像；球队配色不代表官方认可。详见 [致谢与素材说明](ACKNOWLEDGEMENTS.md)。
