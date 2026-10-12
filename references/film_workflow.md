# 带定位的录像观察

统计不能证明绕掩护、阅读防守、跑位等技术判断。先确定待验证问题，再按不同防守压力、对手和结果采样，保留成功与失败，并说明选择依据；不要只挑支持既有结论的回合。

每次证据包输出 `film_records.template.json`，其空 observations 明确表示尚无录像观察。填入真实、实际查看过的记录后，用 `run_analysis.py --input <数据包> --film <记录JSON> ... --out <新目录>` 登记。脚本验证定位和结构，不会观看视频，也不能验证观察者身份或链接确实支持结论。

每条 observations 需：

|字段|含义|
|---|---|
|id|唯一 ID，例如 O01|
|game_id / game_date|NBA 完整10位比赛 ID / YYYY-MM-DD|
|period / game_clock|节次（加时为5及以后）/ 节内剩余 MM:SS|
|video_url / video_timecode|可追溯视频链接 / 视频播放位置 HH:MM:SS；不能与比赛时钟互换|
|observer / observed_at|实际观察者 / 带时区观察时间|
|evidence_kind|direct_observation 或 user_reported；后者正文归因于用户|
|observation|可观察的具体动作、任务和结果，避免只写“防守差”|
|alternative_explanation|队友、任务、对手或比赛状态的替代解释|
|selection_basis|为何选择该回合、属于哪个取样层|
|outcome|success / failure / neutral|

可额外记录对位、阵容、任务、事件 ID、比赛阶段和截图授权信息。不要为了填满字段编造观看经历或视频时间码。只用出手事件定位比赛时，将其存为待看清单，不能存入 observations。

claims 的 observation 引用 FILM，填写 observation_ids 和精确 observation_reference，给出 caveats，并就近引 `[FILM]`。程序拒绝未知记录 ID，校验记录摘要、赛季/比赛类型、节次时钟和视频时钟；记录变化需新建导入。正文需要观察者归因，不能把 user_reported 写成模型亲眼观看。录像假说未验证时保持 inference。

坎宁安 v0.5 示例只提供空模板和待验证计划，没有声称观看过录像，也没有填个人防守评分。下一步真正的工作是收集可访问的视频，再人工记录具体回合；这需要实际视频证据。
