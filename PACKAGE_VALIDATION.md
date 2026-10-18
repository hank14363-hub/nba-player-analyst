# 分发与维护核验 · v0.8.14

本次2026-10-18仅整理文档，发布版本仍为v0.8.14。当前测试入口见 [TEST_REPORT.md](TEST_REPORT.md)，最近功能修复的实案证据见 [validation_v0814.md](documentation/validation_v0814.md)。

## 维护约定

- `PACKAGE_INFO.json`记录发布版本与能力/案例状态；`check_release.py`核对README、SKILL标题和数据结构版本。
- 数据/claims为0.1.0、研究册内容0.2.0、长图内容0.3.0；发布版本变动不改写旧输入结构。
- `FILE_HASHES.json`记录分发文件的SHA-256，不包含其自身、Python缓存或Git目录。修改分发文件后重新生成并核对。
- 保留`agents/`、`assets/`、`scripts/`、`references/`、`tests/`、`examples/`与`documentation/`原路径；历史案例被回归和参考链接使用，不按旧版本名随意删除。
- 不把本机虚拟环境、缓存、凭证、临时输出或新实案照片混入Skill；原始研究数据按各自来源约束管理。

## 状态解释

Actual EPM的离线导入能力、Kaggle转引真实验收、官网直接导出验收，以及分发包是否携带真实案例分别记录。`epm_value_imported=false`不等于导入器不可用；历史归档的“口径待核验”也不能因导入成功而移除。

完整Skill可按目录复制或打包，避免只上传SKILL.md而漏掉脚本和资源。是否公开案例数据及图片需检查其来源与使用条件；本次未发布到外部仓库。
