# v0.3.1 — 中文表达优化

- 更新长文规范、术语解释与写作模板，强调先说场上作用，再用数据说明。
- 简化研究册、结论卡和六类图表的标题、标签与解读；保留统计口径。
- 同步重写合成示例与claims原句，不修改原始数据和计算公式。
- 增加非阻断的表达检查，不自动重写，不替代事实核验。
- 保持所有JSON结构版本与现有脚本兼容；不增加必需依赖。

# Changelog

## 0.3.0 - 2026-10-11

- Added 30 high-contrast team-inspired palettes and neutral fallback; theme selection never changes identity or statistics.
- Added a separately versioned player-poster editorial contract and six auditable SVG chart modules.
- Added concise evidence-linked verdict, role/value/fit/risk cards and conditional tactical recommendations.
- Added optional credited, user-authorized local portraits; no athlete portraits or logos are bundled.
- Added poster HTML, standalone SVGs, derived chart metadata, render parity validation and optional PNG/cover export.
- Added palette accents to the existing research book without changing the original data or book schemas.
- Added 54 deterministic unit tests, retaining all 91 earlier tests.
- Did not add live-data verification, percentiles, rankings, shot maps, EPM or synthetic player scores.


## 0.2.0 - 2026-10-11

- Retained the complete 0.1.0 data collector, calculations, import formats, cache, reports and tests.
- Added an independently implemented black-and-white, responsive, self-contained research book.
- Added registered-claim cards, challenges, conditional tactical suggestions, and follow-up evidence plans.
- Added two deterministic SVG charts (TS comparison and field-goal attempt mix), not a player rating.
- Added a separate 0.2.0 editorial contract; original data and claims remain schema 0.1.0.
- Added report-to-book consistency checks, fresh metric recomputation, manifests and HTML security checks.
- Added source-linked extract summary and optional offline Chromium PDF export.
- Added 36 automated regression tests; all 55 original tests retained.
- Added a complete synthetic demonstration and documented browser/PDF QA.
- Did not add or verify live NBA access, film understanding, adjusted impact models or full shot-location charts.

See TEST_REPORT.md for executed tests and remaining limitations.
