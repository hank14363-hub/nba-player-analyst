# 数据来源与访问策略 · v0.8.14

## 官方来源及已保留核验

历史联网核验日期：2026-10-12，本轮文档整理未重新探测网络。固定 nba_api==1.11.4 的项目环境中，完整参数请求实际取得2024-25球员基础、Advanced、Scoring、每百回合、球队基础/Advanced、四类追踪及活塞On/Off。基础响应569行；球队30行；On与Off各21行。Advanced初次超时，之后单独有限重试取得。实际成功证据见官方案例 sources.json 和 network_diagnostic.json；不保证其他网络、赛季或以后服务始终可达。

nba_api 是第三方开源客户端，数据服务是 NBA Stats。原包依赖/DNS失败与本次简化URL超时都不能证明官方数据不存在。使用客户端的完整参数；不要把只有Season/PerMode等几项参数的临时请求当成唯一可达性测试。

|来源ID|接口|Measure / PerMode|
|---|---|---|
|P_BASE|leaguedashplayerstats|Base / Totals|
|P_ADV|leaguedashplayerstats|Advanced / Totals|
|P_100|leaguedashplayerstats|Base / Per100Possessions|
|P_SCORE|leaguedashplayerstats|Scoring / Totals|
|T_BASE|leaguedashteamstats|Base / Totals，完整联盟|
|T_ADV|leaguedashteamstats|Advanced / Totals|
|TR_CATCH/TR_PULL/TR_PASS/TR_DRIVE|leaguedashptstats|CatchShoot/PullUpShot/Passing/Drives / PerGame|
|P_ONOFF|teamplayeronoffsummary|Advanced / Totals，明确球队|
|P_SHOT|shotchartdetail|ContextMeasure=FGA / Events，真实逐次事件|

保存实际参数、原抓取时间、行数、行SHA256、完整来源链接和状态。缓存按endpoint+参数+schema区分，默认24小时；--offline可读过期缓存但标记stale，不更新原抓取时间；--refresh忽略缓存。

来源优先：实际官方响应；提供可核验元数据的合法导出；定义核实的公开备用源。切换只读备用来源时清楚告知，保留provider及字段映射。不能把RealGM/Basketball-Reference个人ORtg/DRtg写成球队在场表现。索引摘录若作为补充，记录direct_page_verified=false、完整样本与原页访问结果，并在展示处就近说明。不能用搜索摘要中的散落数字拼接追踪数据。

普通网络/服务器错误有限重试；403/401、429、非JSON和未知结构不盲目重试。诊断脚本探测一次，保存分类；不写请求凭证或响应正文。基础失败且无合法可靠导入则停止事实性评价；其他表失败为missing。不要自动代换demo，不修改系统代理，不使用代理池绕过限制。

## 定义与上游参考

- https://github.com/swar/nba_api/tree/v1.11.4/src/nba_api/stats/endpoints
- https://www.nba.com/stats/help/glossary
- On/Off、MIN场均返回特例及新追踪字段见 advanced_data.md。

接口源码核对、离线测试、实时取数和语义判断是不同验证。本次官方案例不包含录像观察或阵容调整因果结论。


高阶影响力公开采集、原站/转引区别、历史日期、窗口核验和补数契约见 [impact_models.md](impact_models.md)。v0.8.1已支持BRef、LEBRON公开转引及DARKO历史页面；网络可访问不保证模型比赛范围一致。

## Kaggle历史备用数据 · v0.8.2

已检查deocheng/nba-data-1946-2026版本1（上传者2026-08-18快照）。用 [kaggle_import.md](kaggle_import.md) 转换独立常规赛包，保留BR口径、文件摘要和原始选中行；不替换已保存官方原表。On/Off只用player_onoff真实两组并核对独立官方球队分钟。此基础适配器不导入EPM、坐标和季后赛；EPM另走下述独立路径。

## 高阶影响力与EPM

在线run_analysis默认尝试BREF、LEBRON和历史Actual EPM访问审计；DARKO需明确历史日期。独立collect_impact默认只选BREF，其命令默认值与主流程不同。方法、失败分类与原始快照见 [impact_models.md](impact_models.md)。

用户合法Actual导出用 [epm_import.md](epm_import.md) 离线核验；Kaggle Actual/历史表用 [kaggle_epm.md](kaggle_epm.md) 独立导入。已审查v1 Actual表仅含2025–26，成功核验单球员不代表全表或其他年份可用。历史归档可显式接入，但日期、估计类型与比赛范围限制保留，不能当作整季Actual。离线导入成功不表示官网受限入口已恢复。

## Sumitro v56历史备用来源

新增独立适配器，流程与限制见 [sumitro_import.md](sumitro_import.md)。BR基础、投篮结构、赛季失误/造犯规汇总、BREF模型和BR五轴比较保留自身口径，不替代NBA官方追踪/On-Off。

## 请求重试与故障命令（v0.8.5）

瞬时超时/连接/5xx采用有上限的指数退避与随机抖动，最多仍受--retries限制。401/403、格式错误不重试；429仅在有效Retry-After不超过15秒时等待至少该时间再有限重试，缺失/超长/无效则停止。日期格式Retry-After也核验；不重试绕过访问限制。

新运行输出repair_commands.json/md，缺少实际On/Off球队时保留阻塞说明，不猜球队。Kaggle等带重算契约的导入包不自动混入官方行。每条补抓独立生成新数据包，使用后重跑分析和结论核验。基础取数网络失败且指定--out时，fetch_failure.json提供初始取数重试命令，无可补抓基础包。
