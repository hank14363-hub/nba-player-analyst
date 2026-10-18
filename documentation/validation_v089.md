# v0.8.9 验证范围 · 2026-10-17

- 479项标准库回归通过，含原52项EPM测试和新增20项Kaggle来源/拒绝路径测试。
- 公开Kaggle元数据HTTP200，当前版本1；两张完整CSV按公开单文件地址HTTP200下载，其SHA-256与此前v1快照一致。
- 奎克利2025–26：真实Actual文件导入、原始字节/行保留、官方身份与GP/MIN匹配、分量校验、run_analysis --input确定性复算、原文件伴随传递核验通过。
- 模型与来源HTML片段生成通过，来源明确显示Kaggle转引；本次没有新建完整研究册，也未开展新的浏览器布局验收。
- 勒布朗2017–18缺Actual行、2025–26分钟差0.425均拒绝，历史候选没有登记进报告指标。
- 官网直接导出结构与接口仍未验证成功；Kaggle上游模型版本、独立类型码说明和置信区间仍缺失。未宣称全602行或更早赛季通过。
- 原CSV与真实案例仅保留用户项目，Skill分发目录不含该EPM真实案例；epm_value_imported仍为false。Kaggle真实导入验收状态另记epm_kaggle_real_import_verified=true。

现场证据位于用户项目2026-10-17/kaggle-epm：download-verified.json、quickley-v089/imported/epm_import_audit.json、quickley-v089/evidence、两个lebron检查目录、test-results-v089.txt。
