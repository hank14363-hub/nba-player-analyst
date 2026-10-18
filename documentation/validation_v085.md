# v0.8.5优化说明

按优先级完成四项：

1. **第三方解析可靠性**：必需字段与DARKO选择器外置provider_schemas.json；采集审计保存配置摘要，区分schema_changed、sample_unavailable、access_restricted、http_error及其他数据/传输失败。新增已保存真实BRef735行、DARKO历史50行的回放，以及结构变更、日期错配测试。身份、日期、样本、模型语义核验仍由代码负责。
2. **补抓与有边界的重试**：新证据目录保存repair_commands.json/md，包括逐表argv及PowerShell命令，不自动执行；每条输出新目录。真正On/Off需实际球队记录，缺身份/球队则明确阻塞。Kaggle导入合同不自动混入官方行。基础网络取数失败且指定--out时，fetch_failure.json提供初始采集重试命令，而非不存在的基础表补抓包。NBA瞬时失败保留原有指数退避上限并加入随机抖动；429仅在有效Retry-After不超过15秒时有限重试，超长/无效/缺失则停止；401/403不重试。
3. **版本分离**：PACKAGE_INFO.json是发布版本单一来源；RELEASE_VERSION=0.8.5，DATA_SCHEMA_VERSION=0.1.0，VERSION保留为结构版本兼容别名。新sources.json登记producer_release，研究册/长图显示当前发布版本。历史长图按原manifest声明的版本复算，不改旧成果。check_release.py检查README/SKILL标题与数据结构版本。
4. **语言规则配置化**：JARGON、TERMS与夸张标签迁入language_rules.json，独立配置结构与规则版本校验；保留已有表达建议，不自动改写原文或统计。

## 结果

375项回归全部通过，无跳过，新增26项可靠性测试；旧官方v0.8.1研究册和长图复算通过，Skill结构与发布一致性检查通过。本机先备份v0.8.4再安装v0.8.5，完整ZIP另附。没有重新撰写勒布朗研究册，没有发布GitHub。

本轮使用历史公开页面快照和注入的HTTP失败验证，不宣称当前第三方网站或NBA端口已联网恢复。结构配置不能保证未来网页永不变化；补抓命令运行时若目标目录已被占用，脚本会拒绝覆盖。多条补抓命令互相独立，不把它们的结果自动串成合并数据包。

## 使用

```text
python <SKILL_DIR>/scripts/check_release.py
python <SKILL_DIR>/scripts/run_analysis.py --player-id 2544 --season 2025-26 --tracking --shots --on-off-team-id 1610612747 --out <新目录>
```

读取新证据目录的repair_commands.md，根据实际失败选择命令。补抓后用修复数据包在另一新目录重新运行分析，再修改正文与claims。已有报告不会自动多出这些辅助文件。

改表达建议时编辑references/language_rules.json；改第三方选择器时先回放真实快照，再运行全部测试，不能放宽球员、赛季或历史日期核验。新研究册继续使用validate_book.py --strict-editorial检查内容完成度。

统一CLI和包结构迁移保留到后续：先用本轮故障日志验证是否确实需要，以免重构破坏旧脚本与离线安装。EPM访问问题仍需匹配赛季的合法数据，不由上述可靠性修改解决。
