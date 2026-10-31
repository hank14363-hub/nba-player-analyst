# 研究册成稿门槛

这份清单用于解决“数据算出来了，但研究册没有落地”的问题。它不要求每个球员都拥有所有数据；缺失时必须在研究册中显示原因和下一步，而不能悄悄删掉模块。

## 三个容易遗漏的模块

### 配图

完整图文研究必须在 `media_research.json` 中留下实际执行记录：

- `status=complete`：至少有一张已经核验、实际查看并嵌入的本地图片；
- `status=limited`：已尝试但某些用途缺素材，写清 `stop_reason`、剩余用途和原因；
- `status=skipped`：仅适用于用户明确要求纯数据、离线或不需要图片的范围。

每张采用图片都要在 `media_content.json` 中关联 `EXT_MEDIA_` 来源、原页、署名、许可、文件哈希和可见图注。历史照、全明星、热身图和日期未知素材可以用于人物或环境展示，但不能冒充本赛季比赛或战术证据。图片不能证明命中、对位、防守质量或高阶模型结论。

### 高阶数据雷达

当 `analysis.json` 有至少一个可用的高阶百分位组，并且请求没有关闭 `advanced_percentiles` 时，成稿默认在 `book_content.json` 写入：

```json
{"percentile_presentation":"radar"}
```

雷达只能使用同一来源、同一完整纳入样本、所有轴均有值的画像（优先十/十一轴，六轴作为回退）；原始值和百分位必须同时显示，轴方向说明必须保留。不能把雷达面积写成综合分、能力评分或联盟排名。历史EPM混合日期、样本不足或字段缺失时，保留表格和“暂缺”说明，不强行画雷达。

如果用户明确选择条形图，可以写 `percentile_presentation=bars`；这是有意的视觉选择，不是遗漏。没有可用百分位时，研究册应显示缺失原因和需要补充的来源。

### 球评文章

完整研究默认检索并直接阅读署名原文。`book_content.commentary_research` 必须是 `complete`、`limited` 或 `skipped`，不能保持 `pending`；实际读过的文章要在 `commentary_cards` 中形成“作者观点—本研究回应—下一步验证问题”，并在 `report.md` 和 `claims.json` 中留下归属明确的回应。文章中的阶段数字不能直接替换整季统计。

没有可用搜索或浏览工具时，使用 `limited` 并写 `search_tool_unavailable`；文章受限、无作者或只有摘要时，写排除原因。不能把搜索建议、文章标题或链接列表当作已阅读。

## 最终验收顺序

1. 先完成 `report.md`、`claims.json`、`book_content.json`、`media_research.json` 和 `media_content.json`，再渲染。
2. 运行 `validate_report.py`，确保所有数字和来源可回溯。
3. 运行 `render_research_book.py --force`，确认图片、雷达、文章回应卡和来源跳转出现在HTML中。
4. 运行 `validate_book.py --strict-editorial`。出现 `media_research_missing`、`commentary_not_attempted`、`commentary_pending`、`commentary_unwritten` 或 `percentile_radar_missing` 时，研究册不能称为完成。
5. 在桌面和窄屏检查图片裁切、雷达可读性、文章卡片换行和来源锚点；自动检查不证明图片身份、许可、文章概括或篮球语义正确。

V1.00罗盘的环上刻度与迁移要求见 [radar_compass.md](radar_compass.md)。缺刻度不估填；旧研究可以保留静态六轴，也可从保留总体在新目录明确升级。
