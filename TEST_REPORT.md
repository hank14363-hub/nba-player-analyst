# 测试记录 · v0.8.14

2026-10-18文档整理：统一入口、使用说明、版本索引与默认行为描述；脚本、算法、资源和案例内容保持原样。此次重新运行595项离线回归、Skill格式检查和发布版本检查；文档相对链接、脚本入口与分发文件摘要另行核验。

| 验证类别 | 范围与记录 |
|---|---|
| 离线回归 | 595项；包括原始文件与摘要、身份/赛季/分钟、模型分量、百分位、渲染一致性及拒绝路径 |
| v0.8.14实案 | 配图替代检索、许可/日期与本地文件；库里1,596/1,598次真实坐标、缺失两次单列；[完整记录](documentation/validation_v0814.md) |
| 浏览器 | 上轮修复已检查1440/390/320px、图片解码与图注、筛选、点亮、平面/舞台、减少动画和无脚本；本轮文档整理未重做视觉改版 |
| 雷达与高亮 | [v0.8.12](documentation/validation_v0812.md)、[v0.8.13](documentation/validation_v0813.md) |
| 百分位 | [v0.8.11](documentation/validation_v0811.md) |
| 历史与Actual EPM | [v0.8.10](documentation/validation_v0810.md)、[v0.8.9](documentation/validation_v089.md)、[v0.8.8](documentation/validation_v088.md) |

复核命令：

```text
python -m unittest discover -s <SKILL_DIR>/tests -v
python <SKILL_DIR>/scripts/check_release.py
python <SKILL_DIR>/scripts/validate_book.py --run-dir <研究目录> --strict-editorial
python <SKILL_DIR>/scripts/validate_poster.py --run-dir <研究目录>
```

合成/离线回归不证明当前网站仍可访问；结构和数值通过不证明篮球结论、图片身份与许可、因果解释或战术建议。图片原页核验与人工语义审阅另做，不能用自动检查替代。
