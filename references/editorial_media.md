# 研究册影像、动效与来源呈现（v0.6）

研究册使用纸白/暖灰底、深色文字与少量球队主色，图表沿用同一浅色体系；结论长图保持独立的深色设计。不得通过重绘改变数值、分母或来源。滚动入场、数据条展开和阅读进度仅用于阅读导向，支持 prefers-reduced-motion；无脚本仍可阅读。

加入真实赛场照片或 GIF 时，先实际查阅素材出处、日期、摄影者与授权。照片用于展示人物，不能代替录像观察。跨年份素材在可见图注中标注实际拍摄年份，不能只放在替代文本或展开来源里，也不能暗示是分析赛季的回合。照片轮播必须写明“照片轮播，非连续回合录像”；未实际观看并登记的影片不能支撑 observation。

将已取得的素材放入本次研究目录，使用可复现的本地 JPEG/PNG/GIF。在 sources.json 登记 EXT_ 来源：provider、url、retrieved_at、status、source_type=illustrative_media、credit、license、license_url、media_date、changes；display_title 可给出简短中文名称，title 保留原始素材名。合成轮播可用 media_items 逐张登记原页。图像授权与文章数据来源分别保留。

media_content.json 使用独立 schema_version=0.1.0，identity 与研究球员/赛季/比赛类型一致。items 的字段：

|字段|作用|
|---|---|
|id|唯一的安全 ID|
|slot|cover / scoring / creation / defense|
|kind|photo / photo_slideshow / game_clip；后二者使用GIF并提供静态预览|
|path / sha256|研究目录中的相对路径与文件SHA256|
|poster_path / poster_sha256|GIF的静态JPEG/PNG预览与摘要|
|title / alt / caption|简短标题、替代文本、日期和证据用途说明|
|source_ids|已登记的影像来源|

渲染器把媒体内嵌进单文件HTML，不依赖外部图片服务。单文件8 MB、媒体总量12 MB限制用于控制体积；更大的媒体应先缩放或选短片段。GIF默认显示静态预览，点击播放/暂停；离开视口、页面隐藏或打印时恢复静态，减少动画偏好下也不会自动播放。不把GIF登记为普通photo以隐藏播放行为。

来源区按研究主题分组：核心统计、投篮事件、追踪数据、球队/在场、影像及其他补充；来源ID锚点保留，正文引用能展开对应卡片。人可读名称、口径、查阅时间和短链接先显示，完整请求与摘要折叠；完整指标表另行折叠。来源搜索筛选后，引用跳转会恢复目标来源。不要删去原始请求或把旧抓取日期改成本次编辑日期。
