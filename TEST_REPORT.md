# 测试记录 · v1.0.0 · V1.00

2026-10-31：674项标准库离线回归通过；发布标签检查与skill-creator的quick_validate通过。本轮说明与机器记录见 [validation_v100.md](documentation/validation_v100.md)。

- 新增14项有效行为检查：分位插值、旧协议兼容、补数的总体重算与原始行不变、未知协议拒绝、同源完整画像与六轴回退、缺失/非法刻度不估填、刻度与轮廓共享坐标、迁移覆盖/路径/证据/指标改变拒绝。旧几何检查更新为公开的环形线性尺度。
- 原有660项覆盖官方/导入数据、身份/分钟、模型与EPM边界、原始哈希回放、比较、投篮缺失、claims、配图/球评记录、成稿门槛和分发。
- 真实库里2015–16：BR十一轴、NBA十轴各350人，原有238个登记条目不变，新增后共246项、245项有效。
- 真实詹姆斯2017–18：两组各353人，原有230项不变，新增后238项；历史EPM继续单列口径待核验，不混入罗盘。
- 两例均通过严格研究册、长图校验与PNG重建。Edge无头浏览器在1920/1440/390/320px验证全图/放大、页签、逐轴卡、表格、刻度、SVG下载、键盘、有限动画、减少动画、打印和无脚本；页面无横向溢出、脚本错误或外部请求。最终截图已人工查看。

```text
python -m unittest discover -s <SKILL_DIR>/tests -v
python <SKILL_DIR>/scripts/check_release.py
python <SKILL_DIR>/scripts/validate_book.py --run-dir <SKILL_DIR>/examples/curry-2015-16-v100 --strict-editorial
python <SKILL_DIR>/scripts/validate_poster.py --run-dir <SKILL_DIR>/examples/curry-2015-16-v100
```

本轮重放既有证据、文章记录和照片，没有新验证NBA网站实时可达性、重新检索球评或购买/验证官网EPM直接导出。回归与结构验证不证明模型的因果有效性、许可来源无争议或战术判断正确。运行包不含tests与历史案例，完整回归使用full包。

此前记录见 [v0.8.18验证](documentation/validation_v0818.md)、[v0.8.17验证](documentation/validation_v0817.md)及 [CHANGELOG](CHANGELOG.md)。
