# NBA Player Analyst v0.3.0 | 验证记录

日期：2026-10-11。环境：Linux、Python、本地无头 Chromium 与 Playwright。

## 已执行

| 检查 | 结果 |
|---|---|
| 全量单元测试 | 145 项通过：保留原 91 项，新增 54 项 |
| 原合成长文验证 | pass；2239 个汉字、17 条结论、26 项登记数值 |
| 研究册验证 | pass；9 章、2 张 SVG；球队配色不改变数据 |
| 长图验证 | pass；6 张 SVG、70 处证据链接、69 处指标标记 |
| 确定性重算 | 原始数据到指标、派生图表值及 HTML 再渲染一致 |
| 配色测试 | 30 个球队预设及 NEUTRAL 均通过预设文字对比度检查 |
| 浏览器布局 | 12 组：LAL/MIN 长图及 LAL 研究册，各测试 1440/1080/390/360 像素视口 |
| 浏览器结果 | 无横向溢出、无外部资源请求、无页面脚本错误 |
| 交互 | 长图证据抽屉正常展开；研究册手机目录正常展开并在跳转后收起 |
| PNG 导出 | LAL/MIN 演示长图均为 1080 x 3716；封面均为 1080 x 955 |
| 视觉检查 | 已检查配色对照、桌面图表、手机封面与长图底部；修复了封面 PNG 被视口截断的问题 |

新测试覆盖：身份与赛季绑定、草稿阻止发布、结论引用、字数与自由数值检查、配色自动选择与人工覆盖、CSS 注入防护、得分恒等式、出手/得分分母区分、缺失不补零、不裁剪超过百分之百的 TS、头像路径与权限字段、渲染一致性、文件篡改、覆盖保护及旧研究册兼容性。

## 未执行与判断边界

- 没有新增真实 NBA Stats 联网端到端测试。此环境没有安装 nba_api，本次不声称接口可访问。原网络单元测试仍为模拟响应。
- 未在用户的 Codex CLI、Windows、macOS 或 WSL 实机上安装和执行。手机测试是浏览器窄屏模拟，不是手机实机。
- 本次交付 HTML、SVG 与 PNG，没有对新配色版 PDF 进行逐页验证。旧 PDF 导出脚本保留；不沿用 v0.2 的版式验证结论代替新版。
- 全部示例均为合成数据。LAL/MIN 仅用作配色展示，不是真实湖人或森林狼球员报告。
- 自动校验只验证结构、数值与文件一致性，不能证明每一句压缩结论、能力评价或战术适配成立。需要人工检查引用支撑范围与推断用语。
- 头像权限标记是用户的确认，不是软件对图片授权的法律审核。未附带真人头像、球队标志或字体文件。

## 复现命令

```text
python -m unittest discover -s tests -v
python scripts/render_research_book.py --run-dir examples/demo_output --theme LAL --force
python scripts/validate_book.py --run-dir examples/demo_output
python scripts/render_player_poster.py --run-dir examples/demo_output --theme LAL --force
python scripts/validate_poster.py --run-dir examples/demo_output
python scripts/export_poster.py --run-dir examples/demo_output --out /path/to/demo.png
```

前五条仅需 Python 标准库。最后一条需可选 Playwright 与 Chromium。原数据与 claims 保持结构版本 0.1.0，研究册结构保持 0.2.0，长图结构为 0.3.0。
