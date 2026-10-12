# 数据来源与访问策略 · v0.4

本次核验：2026-10-12。固定 nba_api==1.11.4 的项目环境中，完整参数请求实际取得2024-25球员基础、Advanced、Scoring、每百回合、球队基础/Advanced、四类追踪及活塞On/Off。基础响应569行；球队30行；On与Off各21行。Advanced初次超时，之后单独有限重试取得。实时成功证据见官方案例 sources.json 和 network_diagnostic.json；不保证其他网络、赛季或以后服务始终可达。

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

保存实际参数、原抓取时间、行数、行SHA256、完整来源链接和状态。缓存按endpoint+参数+schema区分，默认24小时；--offline可读过期缓存但标记stale，不更新原抓取时间；--refresh忽略缓存。

来源优先：实际官方响应；提供可核验元数据的合法导出；定义核实的公开备用源。切换只读备用来源时清楚告知，保留provider及字段映射。不能把RealGM/Basketball-Reference个人ORtg/DRtg写成球队在场表现。索引摘录若作为补充，记录direct_page_verified=false、完整样本与原页访问结果，并在展示处就近说明。不能用搜索摘要中的散落数字拼接追踪数据。

普通网络/服务器错误有限重试；403/401、429、非JSON和未知结构不盲目重试。诊断脚本探测一次，保存分类；不写请求凭证或响应正文。基础失败且无合法可靠导入则停止事实性评价；其他表失败为missing。不要自动代换demo，不修改系统代理，不使用代理池绕过限制。

## 定义与上游参考

- https://github.com/swar/nba_api/tree/v1.11.4/src/nba_api/stats/endpoints
- https://www.nba.com/stats/help/glossary
- On/Off、MIN场均返回特例及新追踪字段见 advanced_data.md。

接口源码核对、离线测试、实时取数和语义判断是不同验证。本次官方案例不包含录像观察或阵容调整因果结论。


高阶影响力公开采集、原站/转引区别、历史日期、窗口核验和补数契约见 [impact_models.md](impact_models.md)。v0.8.1已支持BRef、LEBRON公开转引及DARKO历史页面；网络可访问不保证模型比赛范围一致。
