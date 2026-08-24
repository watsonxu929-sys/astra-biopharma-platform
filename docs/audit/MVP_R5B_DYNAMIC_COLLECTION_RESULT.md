# MVP-R5B 动态网页采集能力实测与最终收口

日期：2026-08-24（Asia/Shanghai）

## 1. 最终结论

`KEEP_CURRENT`

保留 HTTP/feedparser/Playwright/Trafilatura 当前采集链；Crawl4AI不进入requirements、项目venv、生产代码或正式运行时。

## 2. 用户可见结果

当前系统可对robots允许的正式动态来源稳定取得可抽取正文：36Kr、ClinicalTrials和AstraZeneca走Playwright，其余有效样本优先走HTTP。没有新增模型、表、Service、路由、UI、版本目录、数据库或业务能力。

## 3. 调度安全门

R5B先修复pytest可显式指向正式库及直接调用cycle的绕过。R5A+R5B定向31项全过；全量pytest期间正式来源运行新增0、正式collection item新增0，正式库冻结SHA与最大ID完全不变。

## 4. R5A记录复核

Source 4的items 387–406共20条：真实changed 5条、现有规则识别的unchanged/ignored 15条、测试或错误记录0条。全部KEEP；不删除、不强制处理、不发布。详见 `MVP_R5B_R5A_COLLECTION_REVIEW.md`。

## 5. 当前链实测

10个实际抓取URL覆盖企业官网、媒体JS、监管Feed/列表/详情、动态检索、Consent和懒加载列表。HTTP足够7个，Playwright需要3个，Playwright后仍失败0个。36Kr增加有界DOM稳定等待后连续3次成功，耗时2726–2858ms、正文538–694字、网络失败0。

## 6. Crawl4AI隔离PoC

| 项目 | 结果 |
| --- | --- |
| 版本 | 0.9.2 |
| 许可证 | Apache-2.0 + attribution（上游说明） |
| 方式 | 系统Temp独立venv，in-process Python library；无Docker、无Server、无LLM、无正式DB |
| 直接依赖元数据 | 54项 |
| PoC环境 | 108个已安装包、730087156 bytes |
| 36Kr | 3/3取得694字，但3/3均有相同页面console error |
| AstraZeneca | 当前Playwright PASS；Crawl4AI返回anti-bot HTTP 403 |
| 其余来源 | 大体等价；EMA feed在PoC中缺HTML title，不能算完整提升 |
| 清理 | Temp PoC目录已删除；项目 `.crawl4ai` 不存在 |

版本与安装依据：[PyPI 0.9.2](https://pypi.org/project/Crawl4AI/)、[GitHub release](https://github.com/unclecode/crawl4ai/releases/tag/v0.9.2)、[上游License变更说明](https://github.com/unclecode/crawl4ai/blob/main/CHANGELOG.md)。PoC只把Crawl4AI当render/fetch候选，正文仍由Trafilatura 2.2.0抽取。

## 7. Crawl4AI准入门判定

| Gate | 结果 |
| --- | --- |
| 至少2个正式、robots允许来源由当前Playwright无法可靠处理 | FAIL：仅36Kr初始不完整；简单等待后已3/3通过 |
| 候选同URL连续3次稳定 | 36Kr PASS，但有稳定的页面console error |
| 简单Playwright配置仍不能解决 | FAIL：一行有界等待已解决 |
| 不新增DB/Server/Docker/模型 | PoC PASS |
| Windows可运行 | PASS |
| 候选不比当前链退化 | FAIL：AstraZeneca由PASS退化为403 |
| 收益显著高于依赖成本 | FAIL：约696MiB、108包，仅render用途过重 |
| Trafilatura保持唯一抽取器 | PASS |
| robots/登录/验证码/访问控制不绕过 | PASS |
| 可清洁回滚 | PASS：PoC已删除 |

关键Gate失败，因此不得准入。

## 8. 代码变更

- `app/services/collection_scheduler.py`：pytest显式非正式库保护。
- `app/services/collectors/playwright_adapter.py`：最多2秒、最少0.5秒的DOM稳定等待。
- `tests/test_mvp_r5a_oss_foundation.py`：调度路径改用显式临时库并增加正式库拒绝测试。
- `tests/test_mvp_r5b_dynamic_collection.py`：锁定有界等待、Trafilatura唯一抽取器、Crawl4AI不进入生产依赖。

生产Python为 +14/−2，净+12 LOC，低于KEEP_CURRENT上限100 LOC；没有第二套Fetcher/Registry/Service/路由体系。

## 9. 测试与浏览器

- R5A+R5B定向：31 passed。
- 全量pytest：147 passed / 1 skipped / 15 failed / 3 errors（166 collected）。
- 历史15/3集合仍集中在旧migration、v06i runtime/schema、v06j migration、v06k P4旧契约；R5A/R5B/R2/R3/R4/Golden新增失败0。
- Chromium 151.0.7922.34在1366×768和1600×900访问工作台、情报、关系、资源、机会、Q-BAY、搜索共14次：200=14；Console Error 0、Page Error 0、Network Failure 0、HTTP 4xx/5xx 0、横向溢出0。

## 10. 数据安全

任务入口正式库SHA为 `A4697537789349B26070A149F6533A19FA5E0525BEE30A220B1F47D428A82951`。遗留孤儿Web进程在14:15写入2条真实EMA记录后，隔离冻结SHA为 `53A5C361A861A214C0BFA433EC66DC0831976C99D7E6765C981F5F722C74F6B7`；该进程已停止，未删除真实数据。

冻结后浏览器、动态smoke、全量pytest前后SHA、runs `106/max109`、items `403/max406`和7张核心表完全不变；integrity始终 `ok`。所有写测试只使用OS临时测试库，结束后均删除。

## 11. 来源运营建议

- 鲸准：robots denied且配置为RSS但实际是JS应用，保持不采集，待运营方人工决定是否停用/更换合规入口。
- FDA：当前正式状态disabled/quarantined，本轮不擅自启用。
- EMA：5个真实changed item仍为pending processing，不在R5B强制Worker或发布。
- Web启动入口继续强制 `SCHEDULER_ENABLED=false`；Scheduler应只由独立命令启动。

## 12. 已清理产物

Crawl4AI临时venv、其runtime/cache、临时浏览器库、临时动态smoke库、临时Web日志和候选服务均已删除；正式项目无Crawl4AI依赖、`.crawl4ai`目录、测试账号或marker。

## 13. 回滚

最终提交仅包含调度安全、Playwright有界等待、合同测试和审计文档。回滚执行 `git revert <MVP-R5B commit>`；无数据库迁移、无数据回滚、无依赖卸载。任务到R5B停止，不进入后续阶段。
