# v0.5 独立现实试用

请求：保留坎宁安 2024-25 常规赛官方已有统计，仅增加真实投篮位置图，为之后个人防守录像研究准备可追溯记录。仅读取 v0.4 data_bundle.json 和本地缓存，不联网、不安装、不修改发布代码。

结果：repair_data.py --tables player_shots --player-id 1630595 --offline 成功，1457 次真实出手、684 次命中、418 次三分出手和149次三分命中完全匹配原基础表，70 场有出手。新包保留所有原表、原来源与原抓取日期，旧有非投篮指标全部未变。保留一条官方区域/类型冲突，未改写原始事件。

生成 evidence_ready 证据包、真实位置和官方区域 SVG、空录像模板和 film_plan.md。录像记录0条，未声称看过录像或给出个人防守能力评分。trial_validation.json 保存复核结果。

需要改善的实际使用问题：

1. input_schema.md 的允许表清单缺少 player_shots/P_SHOT/Events；也未含 player_onoff。虽然单独参考文档给出新增表，但用户照主输入契约可能误以为不支持，应补齐主表清单并链接对应契约。
2. 缺少只导出投篮图的公开 CLI。用户仅要图而不需报告时，研究册渲染需要额外正文/claims/book_content。本试用通过内部 shot_visuals 函数导出，不是面向一般用户的已文档化操作。建议提供独立图表导出命令或研究册渲染器的 --charts-only，并生成引用与口径 manifest。
3. run_analysis.py 接受 --input 与 --shots 同时传入，但导入分支会静默忽略 --shots；--tracking/--on-off-team-id 同理。主 SKILL 已正确指导先 repair，CLI 仍容易给用户“自动补抓成功”的错觉。建议拒绝组合或明确警告导入模式不会取数，并给 repair 命令。

以上未阻止本次按 SKILL 正确流程完成，未发现旧统计遭覆盖或虚构观察。


## 三项修复复核

1. 主输入清单现已包含 player_onoff/P_ONOFF/Totals、player_shots/P_SHOT/Events，并补齐 CSV 和详细契约入口。通过。
2. 分别实际运行 --input 配合 --shots、--tracking、--on-off-team-id，三种都退出码2，说明 import-only，并给出 repair_data.py 下一步；没有生成输出目录或联网。结果保存在 flag_recheck.json。通过。
3. 按 shot_locations.md 新入口运行 render_shot_charts.py，无需 report/claims/book_content 即生成两个可解析 SVG 与 shot_chart_manifest.json；manifest 登记1457/684/418/149、原始来源和1条标签冲突。通过。

首跑旧证据目录被重新计算保护拒绝，原因是试用期间代码新增了投篮指标与中文标签，不是基础数值改变。从现成 data_bundle.json 重新导入到新 evidence-recheck 目录后成功导图到 standalone-charts；没有覆盖旧证据。三项原问题已解决，无新增阻塞。
