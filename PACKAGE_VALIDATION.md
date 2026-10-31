# 分发与维护核验 · v1.0.0 · V1.00

发布号1.0.0，展示名V1.00；data/claims为0.1.0、book为0.2.0、poster为0.3.0，百分位方向协议和图片日志为0.2.0，新增radar_protocol为1.0.0。详细验证见 [validation_v100.md](documentation/validation_v100.md)。

- `PACKAGE_INFO.json`记录当前版本、674项回归和随包库里V1.00案例；旧案例保留原路径与统计。
- 恢复38个历史缺失文件，逐一匹配原v0.8.18的FILE_HASHES；另恢复库里原bundle与BR原页并匹配保留清单/来源哈希，未以新数据替代旧证据。
- `FILE_HASHES.json`列出本目录逐文件SHA-256，排除自身、Git、缓存与环境。ZIP另附`DISTRIBUTION.json`，记录payload摘要和实际省略项；包内两清单不参与自身摘要。
- full保留历史案例和回归；runtime保留相同运行代码/资源/方法文档、当前库里案例与合成结构示例，省略旧examples和tests。运行包文档中的历史路径需完整包。
- 当前例为保留证据重放，沿用两张CC BY 2.0照片、文章记录和来源时间。全明星照片明确只作人物展示；不当作本季常规赛战术证据。
- `epm_value_imported=false`及`official_case_epm_imported=false`仍表示当前随包库里案例未含真实EPM；不改变标志制造支持。不包含Kaggle历史EPM完整原表、凭证或Python环境。
- 安装前对照本轮开始时的已安装文件哈希，冲突时停止覆盖；修改文件保存可恢复备份。分发使用新的ZIP路径并核验CRC、payload哈希及运行包解压后的研究册/长图。

此文定义核验范围；具体安装/归档结果保存在交付目录的`installation.json`与`distribution-results.json`。本轮未发布GitHub。
