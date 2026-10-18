> **完整交付包｜2026-10-12**  
> 本包包含 v0.3.1 全部技能源码、模板、规范、测试及合成示范，另加入 `examples/cade-cunningham-2024-25/` 真实历史案例和 `documentation/history/` 早期成果记录。先读 `START_HERE.md`。  
> 本次没有修改运行代码；坎宁安案例采用公开数据导入，不代表 NBA Stats 直连已验证。历史文档仅用于版本回顾，安装与操作以本 README 为准。

# NBA Player Analyst v0.3.1｜表达优化版

保持原有球队配色、图表、数据计算和校验。此次主要调整长文、研究册与结论长图的表达：让看球但不熟悉统计模型的读者也能理解。

## 本次变化

新增 `references/plain_language.md`；重写长文规范、任务模板、图表标题与图注。专业词首次出现先解释，缩写作为辅助。保留数据分母、来源和判断限制，不把“暂时不知道”写成“能力不足”。
更新整套合成示例及其结论原句。示例数值与原始数据没有修改；样例不是现实球员评价。
新增 `scripts/review_language.py`，提供行话、长句、缩写和夸张措辞提示。它不自动改文、不改数字，也不验证篮球判断是否正确。

## 在 Codex 交互框中使用

```text
$nba-player-analyst
按专业但易懂的篮球评论风格，分析指定球员和赛季。
先说清场上作用，再用数据支持；必要术语第一次出现时解释。
图表标题用读者能理解的问题，避免连续使用抽象行话。
保留队色、图表、来源、样本范围和结论限制。
改写后同步claims.json原句，重新生成研究册和长图，并完成检查。
```

已有真实报告要改语言时，先复制到新目录保留原稿。不要直接覆盖数据包；先改正文和编辑性JSON，再重建派生成果。

```text
python <SKILL_DIR>/scripts/review_language.py --run-dir <RUN>
```

结果写入 `language_review.json`。`no_heuristic_warnings`只表示没有命中内置提示，不表示文章已通过专业编辑；`review_suggested`表示有可供人工斟酌的地方。

## 升级

先将旧技能目录移到 `.agents/skills/` 之外备份，再解压完整 `skill.zip`。保留虚拟环境、缓存和已有报告；无需安装新的必需依赖。
版本号只更新技能与渲染器；数据结构仍为0.1.0，研究册为0.2.0，长图为0.3.0，已有报告格式不变。

以下保留原有安装与功能说明。实际测试范围以本包 `TEST_REPORT.md` 为准。

---

## 原有功能：球队主题色与球员结论长图

面向本地 Codex CLI：**数据证据 → 能力矛盾 → 条件性战术建议 → 验证计划 → 中文长文与研究册**。

## v0.3 新增：结论长图与图表解读

保留原有研究册、长文与证据校验。新增 30 套球队灵感配色、球员结论海报、六类带解读的 SVG 图表、可选 PNG 长图与封面导出。

先打开 `examples/demo_output/player_poster.html`。这是合成数据的紫金配色演示，不是真实球员的湖人报告。图表和主题的细则见 `references/player_poster.md`。

### 在 Codex 中调用

```text
$nba-player-analyst
分析2024-25赛季常规赛 Anthony Edwards 的综合实力与森林狼契合。
输出中文长文、球队主题色研究册和球员结论长图，主题 MIN。
完成 poster_content.json，为图表补上篮球解读、来源和判断边界。
保存到 reports/edwards-v3，运行报告、研究册和长图检查。
没有对应数据时不生成排名、雷达图、热区或综合评分。
联网失败时说明原因，不使用演示数据替代真实分析。
```

### 对已完成报告补建长图

```text
python <SKILL_DIR>/scripts/render_player_poster.py --run-dir <RUN> --prepare
```

由 Codex 从已审核的结论撰写 `poster_content.json`，不直接发布空模板，再运行：

```text
python <SKILL_DIR>/scripts/render_research_book.py --run-dir <RUN> --theme MIN --force
python <SKILL_DIR>/scripts/render_player_poster.py --run-dir <RUN> --theme MIN
python <SKILL_DIR>/scripts/validate_poster.py --run-dir <RUN>
```

默认 `--theme auto`，也可指定 LAL / MIN / BOS 等代码。未知球队使用 NEUTRAL。配色不是官方标准色或球员队籍证明。

### PNG 导出（可选）

先在项目虚拟环境安装可选依赖：

```text
python -m pip install -r <SKILL_DIR>/requirements-print.txt
python -m playwright install chromium
python <SKILL_DIR>/scripts/export_poster.py --run-dir <RUN> --out <RUN>/player_poster.png
```

将 `python` 替换为项目虚拟环境解释器。可用 `--browser-path` 指定已安装的 Chromium。导出同时生成 `player_poster-cover.png`，保留样本声明。目前版式支持手机阅读，不自动剪成社交平台九宫格。

HTML 与 SVG 不需要这些可选依赖。相对效率、得分来源与阵容环境不会被混成一个实力分数。

## 研究册与既有功能

保留 v0.1 的采集、计算、缓存、导入和报告核验。新增球队主题色排版的单文件 HTML、侧栏目录、手机折叠菜单、问题到策略的跳转、证据回链、内嵌 SVG 图表与 A4 打印样式。

**示范成果：**打开 `examples/demo_output/research_book.html`。全部示例数字均为合成测试数据，不是真实 NBA 球员。本版并未补充真实 NBA 接口的联网实测。

HTML 生成仅用 Python 标准库，不需 Node.js、前端构建、CDN、外部字体或新增 API key。单独运行 Python 不会自动写作；Codex 负责 `report.md`、`claims.json`、`book_content.json` 和 `poster_content.json`。

## 已安装 v0.1 / v0.2：升级方法

先把旧 `.agents/skills/nba-player-analyst/` 移到 `.agents/skills` **以外**备份，不要在技能扫描目录中保留两个同名 SKILL.md。将新 skill.zip 解压到 `.agents/skills/`，重启 Codex。保留现有 `.venv`、缓存和 reports。
数据/claims 结构保持 0.1.0，研究册结构为 0.2.0，旧合格报告可直接补建研究册。

## 在 Codex 交互输入框使用

```text
$nba-player-analyst
分析2024-25赛季常规赛 Anthony Edwards 的综合实力与森林狼战术适配。
先核验真实数据，再生成约2500字中文长文、球队主题色交互研究册和摘要。
保存到新目录 reports/edwards-2024-25-v2。完成 claims.json、book_content.json、报告与研究册验证。
不要停在提纲或数据包；联网失败就说明失败，不使用示范数据冒充真实分析。
```

## 手动重建已完成的示范研究册

在项目根目录中，将下面 `python` 换成项目虚拟环境解释器：

```text
python .agents/skills/nba-player-analyst/scripts/render_research_book.py --run-dir .agents/skills/nba-player-analyst/examples/demo_output --force
python .agents/skills/nba-player-analyst/scripts/validate_book.py --run-dir .agents/skills/nba-player-analyst/examples/demo_output
python -m unittest discover -s .agents/skills/nba-player-analyst/tests -v
```

这是重建随包测试样例的例外；日常研究输出放在项目录 reports 中，不放在技能目录。
对已有真实报告先用 `--prepare` 生成编辑模板，由 Codex 完成 book_content.json 后再渲染。不使用演示卡片替代真实结论。

## 新增输出

| 文件 | 用途 |
|---|---|
| research_book.html | 自包含交互研究册，含长文和证据附录 |
| summary.md | 从已登记原句提取的带来源摘要 |
| charts/*.svg | TS 对比与两分/三分出手构成（有数据才生成） |
| book_content.json | Codex 撰写的矛盾、策略、行动及结论关联 |
| book_manifest.json | 输入与输出文件校验值、版本和生成范围 |
| book_validation.json | 结构、链接、文件一致性与指标检查 |

图表不代替实力评分；出手构成不是得分占比或投篮热区图。每条策略都是有条件的建议，不是自动观看比赛得出的结论。

## 可选 PDF

在本地浏览器打开 HTML，使用页面打印按钮或 Ctrl+P，选择 A4。也可以安装可选依赖后使用脚本：

```text
python -m pip install -r .agents/skills/nba-player-analyst/requirements-print.txt
python -m playwright install chromium
python .agents/skills/nba-player-analyst/scripts/export_pdf.py --run-dir reports/edwards-2024-25-v2
```

已有 Chromium/Chrome 可通过 `--browser-path` 指定。依赖和浏览器下载需联网和正常授权，导出本身不访问外部站点。不需 PDF 时可完全跳过此项。字体与浏览器可影响分页，发布前应检查每页。

视觉与输入规范见 `references/research_book.md`，测试范围见 `TEST_REPORT.md`，参考来源见 `ACKNOWLEDGEMENTS.md`。

---

# 安装、数据与长文基础流程


面向本地 Codex CLI 的 NBA 球员综合分析技能：公开统计采集 → 高阶指标 → 证据约束的实力/战术判断 → 中文长文。

**重要：这是“本地数据脚本 + Codex 分析写作”的 Skill，不是单独运行 Python 就会自动生成专业长文的独立产品。** Python 输出证据包，Codex 按 SKILL.md 继续完成 report.md 与 claims.json。本技能不单独调用模型 API，不需要另填 OpenAI API key；Codex 自身的正常登录/用量规则仍适用。

## 当前交付状态

已实现在线适配器、缓存、离线 JSON/CSV 导入、确定性计算、中文写作指令与报告检查器。构建环境无法联网安装 nba_api，因此真实 NBA 接口没有完成端到端实测。不能将离线测试通过描述为在线取数通过。具体运行结果见 TEST_REPORT.md。

示例中的 MVP Demo Guard、Demo Owls 和 Demo Foxes 都是虚构测试对象；所有示例数字均是合成数据。

## 1. 安装到项目（推荐）

将 skill.zip 解压到项目 `.agents/skills/`，最终结构应是：

```text
你的项目/
  .agents/
    skills/
      nba-player-analyst/
        SKILL.md
        agents/openai.yaml
        scripts/
        references/
        assets/
        examples/
        tests/
        README.md
        requirements.txt
  .venv/                       # 自行在项目创建
  .nba-player-analyst/cache/    # 首次在线采集后生成
  reports/                     # 分析结果，不写回技能目录
```

注意不要多套一层 `skill/nba-player-analyst/`。Codex 本地技能也支持用户级 `$HOME/.agents/skills/`，两种位置选一种即可，避免同名技能重复出现。

启动 Codex 后在其交互输入框使用 `/skills` 检查，或输入 `$nba-player-analyst` 直接调用。新技能未出现时重启 Codex。

官方说明：https://learn.chatgpt.com/docs/build-skills （核对日期：2026-10-11）。

## 2. 准备 Python（3.10 或更新版本）

以下命令都在项目根目录执行。无需激活虚拟环境，直接调用其中的解释器即可，避免 Windows 执行策略问题。

### Windows PowerShell

下载 skill.zip 并放入项目根目录后：

```powershell
New-Item -ItemType Directory -Force .agents/skills | Out-Null
Expand-Archive -Path ./skill.zip -DestinationPath ./.agents/skills
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r .agents/skills/nba-player-analyst/requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s .agents/skills/nba-player-analyst/tests -v
```

先确认 `py -3 --version` 至少 3.10。如没有 `py`，可用已安装的 `python` 创建环境。不使用 `Expand-Archive -Force` 覆盖已有技能；升级前先备份。

### macOS / Linux / WSL

```bash
mkdir -p .agents/skills
unzip skill.zip -d .agents/skills
python3 -m venv .venv
.venv/bin/python -m pip install -r .agents/skills/nba-player-analyst/requirements.txt
.venv/bin/python -m unittest discover -s .agents/skills/nba-player-analyst/tests -v
```

如果 Codex 在 WSL 中运行，虚拟环境也应建在 WSL 项目内，不混用 Windows 的 `.venv/Scripts/python.exe`。

`nba_api==1.11.4` 是按已查阅上游源码固定的版本，不代表 NBA 服务端永不变更。依赖安装需联网。离线测试可跳过安装依赖；本版计算层不直接依赖 pandas 或 matplotlib，缩小 MVP 的运行依赖。

## 3. 首次完整调用：让 Codex 执行并写完文章

在项目中运行 `codex`，然后将下面的文字输入 Codex 的交互框，**不是输入 PowerShell/Bash**：

```text
$nba-player-analyst
分析2024-25赛季常规赛 Anthony Edwards（爱德华兹）的综合实力，重点讨论持球得分、外线投射、组织局限、防守证据与森林狼的战术适配，输出约2500字中文篮球长文。
使用当前项目的Python虚拟环境，先运行技能脚本获取和核验真实数据；然后完成report.md、metrics.csv、sources.json、claims.json及validation.json。不要停在生成数据包或文章提纲。如果联网失败，明确报告失败，不使用演示数据冒充真实分析。
```

仅需要自然语言调用。网络或写入需要审批时，按 Codex 提示授权这次必要操作，不关闭全部安全限制。

## 4. 手动运行数据阶段

Windows 示例：

```powershell
.\.venv\Scripts\python.exe .agents/skills/nba-player-analyst/scripts/run_analysis.py --player "Anthony Edwards" --season 2024-25 --out reports/edwards-2024-25
```

macOS/Linux 将解释器替换为 `.venv/bin/python`。

常用参数：

| 参数 | 含义 |
|---|---|
| `--player` / `--player-id` | 姓名或 NBA ID；同名必须消歧 |
| `--season 2024-25` | 必填，不静默猜最新赛季 |
| `--season-type "Playoffs"` | 季后赛；默认常规赛，二者分开 |
| `--team-id ID` | 仅该球员在这支球队的样本，影响球员各表 |
| `--target-team-id ID` | 同赛季适配对象，不改变原球员样本 |
| `--tracking` | 尝试接球投篮、持球跳投、传球、突破四组追踪数据 |
| `--input PATH` | JSON bundle 或带 metadata.json 的 CSV 目录；不联网 |
| `--offline` | 只读已有缓存，过期缓存显式标记 |
| `--refresh` | 跳过缓存，重新获取；不与 input/offline 混用 |
| `--notes PATH` | 导入 UTF-8 观察笔记，不自动宣称已看片 |
| `--out PATH` | 新的空目录；不覆盖已有报告 |
| `--timeout 20 --retries 2` | 每次网络请求超时与有限重试 |

默认缓存有效期为 24 小时，使用 `--cache-ttl-hours` 调整。在线抓取失败不会偷偷退回过期缓存；希望使用旧缓存需显式 `--offline`。缓存保留原始抓取日期。

默认请求六组核心数据：球员基础、高阶、每100回合、得分构成，球队基础和高阶。追踪数据是可选扩展。第一次网络失败时，`player_base` 失败即停止；其他可选表失败则输出受限证据包。

## 5. 不联网的可复现演示

```powershell
.\.venv\Scripts\python.exe .agents/skills/nba-player-analyst/scripts/run_analysis.py --player "MVP Demo Guard" --season 2024-25 --input .agents/skills/nba-player-analyst/examples/demo_bundle.json --out reports/demo
```

它只验证采集后的计算和输出过程，不证明在线接口或真实球员分析已经验证。随后可在 Codex 内要求：

```text
$nba-player-analyst
读取reports/demo中的证据，完成一篇明确标注“合成测试数据”的中文示范文章及claims.json，并运行报告验证器。不要改用真实球员姓名。
```

真实 CSV 导入格式见 `references/input_schema.md`。本版不直接读取任意 XLSX 或截图，也不猜测表头与百分比单位。

## 6. 结果文件

数据脚本输出：

| 文件 | 内容 |
|---|---|
| data_bundle.json | 原始数据行、样本和来源，可离线复跑 |
| analysis.json | 已核验指标、原始数值、选中行、证据边界与缺失原因 |
| metrics.csv | 中文标签的数据表，UTF-8 BOM |
| sources.json | 接口、参数、抓取时间、单位、缓存状态、行数据校验值 |
| evidence.md | 供 Codex 阅读的证据表 |
| writing_brief.md | 此次中文写作任务 |
| report.template.md | 结构参考，不是成稿 |
| claims.template.json | 空证据清单模板，不是成品 |

Codex 继续输出：report.md、claims.json；验证器写出 validation.json。原始数据与最终文章分开保存，便于复核。

```text
python <技能目录>/scripts/validate_report.py --run-dir reports/edwards-2024-25
```

验证通过仅表示结构、登记的数字与引用 ID 等检查通过，不代表语义自动获得真实性保证。必须人工核对所有数字、引用、推断及观察。

## 7. 已实现与未实现

已实现 TS%、eFG%、三分出手占比、FTA/FGA、AST/TOV、同赛季同类型联盟加权 TS%、rTS（百分点）、来源提供的 USG%/AST%、每100回合到每75回合换算、球队节奏/效率/助攻率/三分出手占比，以及有据可查的命中球受助攻比例。

实力评价和战术适配由 Codex 按 references 中的证据规则撰写，不输出自动“88分”式评分。没有追踪和录像时，无球/防守判断必须收缩。

追踪接口已提供可选采集与样本检查，但 当前数据层不将全部追踪字段自动登记成正式指标。其定量引用需要补充定义、计算映射和测试；避免将不同赛季追踪字段直接当作稳定模式。

暂未实现：自动看片、按区域投篮图、逐回合阵容调整、真正 on/off、EPM/BPM/RAPM、多球员排序、跨赛季/对手强弱调整与季前赛分析。

## 8. 常见问题

**提示输出目录非空：** 改一个新的 `--out`，不要删掉原文章来强行复跑。

**API 超时：** 确认本地可访问 NBA Stats，必要时减少重试并用合法导出的 CSV/JSON。不要绕过网站访问控制，不保证任意网络都能直连。

**rTS 为缺失：** 需要完整、未按球队过滤的联盟球队总计及 full_league 声明。不能只用一两支真实球队或球员平均 TS 代替联盟基准。

**高级表被排除：** GP/MIN、比赛类型、百分比单位可能不一致。重新抓取或修正真实元数据，不能改数字只为通过检查。

**名字未找到：** 使用完整英文名或 ID；内置中文别名仅覆盖少量常用姓名，可按规则扩展别名文件。

**文章没有生成：** 单独运行 Python 只到 evidence_ready。需要让 Codex 继续执行 SKILL.md 的写作和审核步骤。

## 开发与维护

```text
python -m unittest discover -s <技能目录>/tests -v
python <技能目录>/scripts/run_analysis.py --help
```

先更新数据定义与测试，再扩展指标或接入新来源；不要先要求模型填满更多栏目。来源文档见 `references/data_sources.md`。

## 随包写作演示

`examples/demo_output/report.md` 是一篇已完成的中文合成示范文章，旁边保留 analysis.json、metrics.csv、sources.json、claims.json 与 validation.json。它展示文章结构、引用和结论清单，不是实际 NBA 数据报告。离线测试和已知限制见 `TEST_REPORT.md`。
