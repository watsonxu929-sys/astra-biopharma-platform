# MVP-R5A OSS Foundation Result

日期：2026-08-24（Asia/Shanghai）

## 1. 一句话结论

**PASS**：feedparser、Trafilatura、RapidFuzz与既有APScheduler已经分别成为Feed、正文、通用相似度和正式定时调度的唯一基础底座；Canonical业务模型、R2/R3/R4/Golden Path保持不变，Production Python净减少81 LOC。

## 2. Before

Before存在ElementTree手工RSS/Atom遍历、两套通用DOM正文规则、三个模块直接SequenceMatcher调用，以及APScheduler、自研scheduler_jobs脚本、专用Collection Worker和统一Worker并行入口。真实调用图见 `MVP_R5A_REPLACEMENT_MAP_BEFORE.md`。

## 3. OSS

| Component | Version | License | Direct requirement |
| --- | ---: | --- | --- |
| feedparser | 6.0.14 | BSD-2-Clause | `>=6.0.14,<7.0` |
| Trafilatura | 2.2.0 | Apache-2.0 | `>=2.2,<3.0` |
| RapidFuzz | 3.14.5 | MIT | `>=3.14.5,<4.0` |
| APScheduler | 3.11.3 | MIT | `>=3.10,<4.0` |

商业使用和上游索引见 `MVP_R5A_OSS_LICENSES.md`。

## 4. RSS

`collection_service._parse_rss`是唯一Feed adapter；feedparser负责RSS/Atom、时区、HTML summary和容错语法，项目保留title/url/published_at/author/summary/guid到ExtractedPage的业务映射。RSS与Atom fixture逐字段通过；损坏Feed和合法空Feed均明确为 `PARSE_FAILED`。生产代码已无ElementTree/XML手工Feed遍历。

## 5. Extraction

Trafilatura共享helper同时供Collection、URL extractor和HtmlParser使用；fallback仅删除script/style/noscript后取基础文本。10个正式库既有不同URL快照只读比较全部人工PASS，10个覆盖中文/企业/政府/复杂导航的确定性fixture全部PASS；空正文0、乱码0。详细字符数和边界判断见 `MVP_R5A_EXTRACTION_COMPARISON.md`。

## 6. Fuzzy

生产代码已无difflib/SequenceMatcher。统一helper把RapidFuzz ratio规范为原有0..1范围；Entity标准化、机构后缀规则、字段bonus、阈值和人工决策保持不变，未增加任何自动合并。中文企业、人名、中英文、空格、大小写和标点回归通过。

## 7. Scheduler

APScheduler仅注册一个 `collection_cycle`。Timed、manual和统一task queue的due-only执行均调用该callable；Windows脚本只托管APScheduler，不再读scheduler_jobs或自行判断due。删除专用Collection Worker CLI/BAT，统一Worker只保留非定时任务执行。新增pytest保护：无显式测试DB时拒绝启动Scheduler；显式临时DB的注册测试通过。

## 8. Deleted Code

- RSS custom LOC removed：24。
- Extraction custom LOC removed：108。
- Fuzzy direct/custom basis LOC removed：7。
- Scheduler duplicate entry LOC removed：122（含46 LOC CLI、29 LOC BAT和47 LOC自研scheduler脚本逻辑）。
- 删除文件：`scripts/run_collection_worker.py`、`scripts/windows/collection_worker_windows.bat`。
- 未新增业务表、Model、业务Service、版本目录、Canonical写入口或大框架。

## 9. LOC

统计口径为Git HEAD和当前工作树的 `app/**/*.py + scripts/**/*.py`：68837 → 68756，净减少81 LOC。测试与审计文档不计入Production LOC。

## 10. Data Safety

正式库：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`。

| 项目 | Before | Final |
| --- | --- | --- |
| SHA256 | `26328F6DED572A3942424D54CF4A67C5A298F5413177B21FD96086D3BCCE4404` | `FEB87D87349AC2032A0F17BA1B3F47693200BE43B57E1016FAEE793BDEA07B52` |
| integrity_check | ok | ok |
| 7张Canonical核心表 | 25 / 44 / 24 / 29 / 0 / 11 / 25 | 完全相同 |
| v05f_collection_items | 391 | 399 |

SHA和采集行变化来自任务开始前11:19已运行的正式Web/Scheduler及13:30、13:45真实EMA Source运行，内容均为正式Source 4的真实Feed，不是虚假验收数据。13:45全量pytest还暴露了Scheduler默认DB隔离风险；最终代码已增加“pytest必须显式传测试DB”的硬保护并定向通过。按禁止事项未删除或回滚这些真实正式采集记录。R5A计划内的网络smoke、浏览器账号和验收写链均使用系统临时测试库；临时库、账号、日志已删除，正式库无R5A marker或虚假Source。

## 11. Tests

- R5A最终定向：27 passed。
- R2 Single Write、R3 Canonical Read/Migration、R4 Golden Path、RC1 Golden Loop、P2 Intelligence publication联合定向：44 passed（调度保护前；受影响业务代码其后未变）。
- 全量pytest实际执行：135 passed / 1 skipped / 15 failed / 3 errors。
- 全量执行后新增的1项DB保护和5项中文结果标签测试单独PASS；没有重复运行第二次全量。
- 15 failed / 3 errors仍是R4既有migration幂等、v06i旧Settings/Schema、v06j旧migration和v06k旧Dashboard契约集合；R5A/R2/R3/R4/Golden Path新增失败0。

## 12. Real Collection Smoke

使用正式Source 4配置 `EMA News RSS / https://www.ema.europa.eu/en/news.xml`，但运行于专用测试模板派生的系统临时库（没有复制正式库）。首轮：SUCCESS、新增2、快照2、排队2；复跑：识别重复1，另1条因实时页面内容变化判为changed。Fetch → feedparser Parse → Trafilatura Extract → Normalize → Deduplicate完整；测试库integrity_check=ok并已删除。日志结果现在区分 `FETCH_FAILED / PARSE_FAILED / EXTRACTION_EMPTY / DUPLICATE / SUCCESS`，包含URL、parser、extractor、result、elapsed_ms和error_type。

真实Chromium 151.0.7922.34在1366×768与1600×900访问工作台、情报、关系、资源、Opportunity、Q-BAY和搜索共14次：200=14，404/500=0，Console Error=0，Page Error=0，Network Failure=0，横向溢出=0，四个OSS名称用户可见=0；候选服务和临时浏览器库已停止/删除。

## 13. Remaining Infrastructure Debt

只登记、不在R5A实现：Crawl4AI候选、Search底座、Splink、NetworkX、Observability。Playwright继续保留为动态渲染能力。回滚方式：对最终单一R5A提交执行 `git revert <R5A commit>`，随后按原requirements恢复环境；无需数据库迁移或数据回滚。
