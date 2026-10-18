# NBA Player Analyst v0.2.0 验证记录

日期：2026-10-11。环境：Linux、Python 3.13.5、本地 Chromium 与 Playwright。

## 已执行

| 检查 | 结果 |
|---|---|
| 原有测试 + 新研究册测试 | 91 项通过（原有 55 + 新增 36） |
| 合成样例报告验证 | pass；2239 个汉字、17 条结论、26 项登记数值 |
| 合成样例研究册验证 | pass；9 章、214 处锚点链接、2 张 SVG、45 处嵌入指标 |
| 指标一致性 | 从原始 bundle 重算后比较通过 |
| 桌面浏览器检查 | 1440 x 1024；无横向溢出；问题到策略跳转正常 |
| 手机宽度模拟 | 390 x 844；无横向溢出；菜单打开/跳转后收起正常 |
| 资源与脚本 | 观察到的外部网络请求 0；页面 JavaScript 错误 0 |
| 可选 PDF 脚本 | export_pdf.py 实际导出成功；A4、19 页（含正文和完整证据附录） |
| 视觉检查 | 已检查桌面/窄屏截图、PDF 全页缩略图与重点页；修复了孤立页脚与矛盾章节分页 |

新测试覆盖编辑合约、球员/赛季绑定、模板未完成阻止、引用存在性、条件与代价要求、无据不凑卡片、原文保留、图表口径、非有效数值、指标修改、来源修改、文件校验值、路径保护、HTML 注入转义、外部资源拒绝及链接完整性。

## 测试方法与边界

浏览器为容器中的无头 Chromium，不是手机实机。当前环境策略阻止 file:// 导航，因此通过 Playwright set_content 加载同一份自包含 HTML，不修改浏览器管理策略。导出脚本使用同样的内存加载方式并阻止外部请求。

未执行真实 NBA Stats 联网端到端测试。网络单元测试仍使用模拟响应，不表示服务可访问。未在用户的 Codex CLI、Windows、macOS或 WSL 上实测安装、审批与自动写作。

示例使用 MVP Demo Guard、Demo Owls 等虚构名称和合成数据。它演示成果样式、证据追溯与条件性策略，不是真实球员分析或经实赛验证的战术方案。

验证通过仅说明结构、登记数字、引用与文件一致性等检查通过，不能自动证明所有语义、评价与战术推断正确。必须人工复核每一个判断的证据范围。生成文件中的 SHA256 用于检查一致性，不是外部权威认证。

## 复现

```text
python -m unittest discover -s tests -v
python scripts/render_research_book.py --run-dir examples/demo_output --force
python scripts/validate_book.py --run-dir examples/demo_output
python scripts/export_pdf.py --run-dir examples/demo_output --out demo.pdf
```

前三条只需 Python 标准库。PDF 需要可选 Playwright 和 Chromium，也可用浏览器打印。
