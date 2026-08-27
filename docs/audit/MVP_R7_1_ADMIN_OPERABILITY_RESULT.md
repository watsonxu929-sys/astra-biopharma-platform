# MVP-R7.1 管理员可运营性结果

记录日期：2026-08-27（Asia/Shanghai）

## 1. 一句话结论

**PASS**

管理员/Operator 已可在现有网页、现有 Service 和现有 Canonical Writer 上完整运营 Source、Q-BAY Event 与 Resource；真实 Chromium、删除保护、权限、数据库隔离、Single Write、Canonical Read 和历史回归均通过，未进入 R7.2。

## 2. Baseline

- 唯一正式项目：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1`
- Branch：`release/mvp-rc1.2`
- 开始 HEAD：`05abc5b11619a40271bf8cf2a39c4dadeb000ef8`
- 开始 Working Tree：clean
- 正式数据库：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`
- 基线文档：[MVP_R7_1_ADMIN_BASELINE.md](MVP_R7_1_ADMIN_BASELINE.md)
- 开始 `integrity_check`：`ok`

## 3. Source CRUD

- 采集来源改为全宽管理页，提供新增、批量导入、发现来源、正式来源、候选来源和运行记录入口。
- 单个新增执行“填写 URL → 测试 → 显示 HTTP/RSS/HTML/Playwright/正文/标题结果 → 确认保存”。
- 正式 Source 可编辑、测试、启用、停用、删除或退役。
- Chromium 实际完成新增、测试、编辑、停用、重新启用、删除和刷新持久化。
- 修复真实浏览器发现的静态路由遮挡：Source 动态路由使用 `{source_id:int}`，`/import` 与 `/discovery` 不再被捕获为 422。
- Disabled/Deleted Source 不进入 Scheduler：R5B Scheduler Safety 回归通过，验收 Web/Worker/Scheduler 均关闭；正式库 2026-08-27 新增 Run/Item 为 0。

## 4. Source Delete / Retire

- 无 Collection/Intelligence 历史的 Source 物理删除配置。
- 有历史的 Source 只退役：`is_enabled=0`、`health_status=retired`、停止调度并保留历史。
- Chromium 在隔离库退役 Source 4：退役前 Collection Item 209，退役后仍为 209。
- 删除确认页展示名称、URL、当前状态、历史采集数和正式 Intelligence 数。
- 反馈明确区分“来源已删除”和“来源已退役，历史情报保留”。

## 5. Batch Import

- 支持 `name,url` CSV 和逐行 URL 文本。
- Preview 执行 Normalize、重复检查和连接测试。
- Chromium 实际导入 3 个 READY URL；同文件重复识别为 `DUPLICATE_IN_FILE`，非法协议识别为 `INVALID_URL`。
- 保存反馈为“成功新增 3、已存在 0、无效 URL 1、测试失败 0”，没有上传即写库。

## 6. Source Discovery

五个真实官网在独立数据库副本上使用现有 HTTP、feedparser、BeautifulSoup 和提取器完成实测：

| Domain | Homepage | RSS | Sitemap | Newsroom | Candidate | Duplicate | Invalid |
|---|---|---:|---:|---:|---:|---:|---:|
| `www.roche.com` | PASS | 0 | 0 | 8 | 8 | 0 | 0 |
| `www.pfizer.com` | PASS | 0 | 0 | 8 | 8 | 2 | 1 |
| `www.novartis.com` | PASS | 0 | 0 | 8 | 8 | 1 | 0 |
| `www.biontech.com` | PASS | 0 | 6 | 2 | 8 | 5 | 7 |
| `www.wuxiapptec.com` | PASS | 0 | 0 | 8 | 8 | 0 | 1 |
| 合计 | 5/5 | 0 | 6 | 34 | 40 | 8 | 9 |

- 所有发现结果初始 `is_enabled=0`，不会自动成为 ACTIVE Source。
- Chromium 从 Roche 官网真实触发发现，展示发现依据、测试结果和最近内容。
- 重复复验结果：新增 0，重复识别 37；没有重复 Source 行。
- 本轮未接搜索引擎 API、Crawl4AI、Scrapy、Firecrawl 或第二个 Worker。

## 7. Candidate 管理

- Candidate 复用现有 Source 表的 `health_status=candidate` 与 `compliance_note`，没有新表或 Candidate V2。
- 列表显示名称、URL、Domain、Organization、发现方式、类型、测试、最近内容和重复状态。
- Chromium 启用真实 Roche Candidate 38，忽略 Candidate 37；重启后 Candidate 38 仍为 `healthy/enabled`。
- 修复批量导入 Candidate 缺少 `discovery.test` 时的模板 500，缺失测试元数据现在安全降级显示。

## 8. Q-BAY Event

- Operator 活动页显示明显的“发起活动”和“活动管理”；Viewer 不显示。
- 创建、编辑、发布、开放报名、Viewer 查看与报名、取消均通过真实 Chromium。
- 有报名活动的删除请求得到清晰保护反馈，不再因全局 409 渲染规则变成 500。
- 隔离库 Event 3 在多次 Web 重启后保持 `cancelled`，报名记录 1 条完整保留。
- 另建无报名 Draft 4，并通过网页安全删除。
- Event 写入统一调用现有 `ClubEventService`；原复制入口也改为复用同一 Service，Route 新增直接 SQL 写入为 0。

## 9. Resource

- Operator/Admin 可创建、编辑现有模型字段、上架、关闭归档、安全删除和批量删除。
- 无引用 Resource 47 经 Chromium 创建、编辑并物理删除。
- 有 Opportunity 引用 Resource 46 不显示物理删除按钮，直接删除请求也被保护；关闭后为 `archived`，重启后状态保持。
- 批量选择安全 Resource 48、49 与受保护 Resource 46：安全项删除 2，受保护项保留 1，未整批回滚。
- 全部 Resource 写操作调用既有 `UnifiedResourceService` Canonical Writer；未修改 Canonical Schema。

## 10. Permission

- Operator（Admin 权限为其超集）真实完成 Source、Event、Resource 管理。
- Viewer UI 不显示 Source 的新增/导入/发现/批量/编辑/测试/启停/删除，Event 的编辑/状态/删除，Resource 的发布/编辑/关闭/删除/批量入口。
- Viewer 对 17 个关键写入口逐项发起真实请求：Source 8 项、Event 4 项、Resource 5 项，全部 HTTP 403。
- Viewer 仍可查看 Event、报名和查看 Resource；Source 列表/详情为只读。

## 11. Delete Safety

- Source 有历史时退役，209 条 Collection Item 保留。
- Event 有报名或非 Draft 时拒绝硬删并提示取消/结束；无报名 Draft 可删。
- Resource 有 Match、Opportunity 或 Canonical Relationship 引用时拒绝硬删；可关闭归档。
- R7.1 测试未删除 Organization、Person、Intelligence、Opportunity、Relationship 或正式数据。

## 12. Database Safety

正式库前后业务口径完全一致：

| 指标 | Before | After |
|---|---:|---:|
| Source 总数 / ACTIVE / CANDIDATE / DISABLED | 15 / 6 / 4 / 5 | 15 / 6 / 4 / 5 |
| 有历史 Source / 从未成功 Source | 9 / 5 | 9 / 5 |
| Event / Draft / Published / Ended / Cancelled / Registration | 1 / 1 / 0 / 0 / 0 / 0 | 1 / 1 / 0 / 0 / 0 / 0 |
| Resource / demand / supply / active / closed | 30 / 8 / 22 / 30 / 0 | 30 / 8 / 22 / 30 / 0 |
| 有 Match 引用 / 有 Opportunity 引用 / 无下游 | 0 / 0 / 30 | 0 / 0 / 30 |

- Before 主文件 SHA256：`F8EB52A538F12E73EFAC47F989E04FD907E6864BF2D61A56A9D71550E6DDCE0D`
- After 主文件 SHA256：`270F12A7CB8DEED20D1E40AFCC5354AA6CA0D2AD80F714701A0F4F8470D42F2D`
- After `PRAGMA integrity_check`：`ok`
- 主文件物理 SHA 发生变化，未伪装为字节不变。审计结果表明这是既有 WAL checkpoint：主文件最后写入为 2026-08-27 16:53，最终 WAL 为 0；库中最新 5 个 Scheduler Run 和 25 个 Item 均产生于 2026-08-25，已在 R7.1 基线读取前存在。
- 正式库没有 R7.1/r71 标记、临时账号、2026-08-27 新业务时间戳或审计写入；全部基线业务计数完全一致。因此没有正式业务数据变化。
- 所有自动测试使用 OS 临时数据库；Chromium 使用独立副本。临时 Web、数据库、账号、Source、Event、Resource、报名和日志已随临时目录整体删除。

## 13. Tests

- R7.1 定向测试：`4 passed / 4`。
- R2 Single Write、R3 Canonical Read、R4 Golden Path、R5 OSS、R5B Scheduler Safety、R6 Data Quality、R7 Value Activation、R7.1：`58 passed / 58`。
- 全量 pytest：`15 failed / 3 errors`。
- 与 R2–R7 已登记集合一致：domain integrity/migration、旧 P4、v06i runtime baseline、v06j migration chain、v06k P4 rehearsal contract。
- R7.1 新增失败：0；历史失败集合未扩大；未恢复 Legacy 行为。

## 14. Chromium

- 首选 Computer Use 因 Windows ACL/orchestrator helper 失败一次，记录为 `TOOLING_BLOCKED` 后立即切换项目已有 Playwright；没有把工具故障当作产品失败或通过。
- 引擎：Chromium `151.0.7922.34`；视口：1366×768；实际加载 HTML/CSS/JS 并执行表单、按钮、Cookie 会话和后端权限请求。
- 页面/流程：工作台、Source 列表/详情/新增/导入/发现、Candidate、Event 列表/详情/编辑/报名、Resource 列表/详情/编辑、operator/viewer 双会话、重启持久化。
- 非预期 HTTP 404/500：0。
- Console Error：0；Page Error：0；横向溢出：0。
- 证据：[evidence/mvp_r7_1](evidence/mvp_r7_1/)；19 张截图与 [browser_result.json](evidence/mvp_r7_1/browser_result.json)。

## 15. LOC

- Production Python：`+731 / -131`，净 `+600 LOC`。
- 产品模板：`+69 / -35`，净 `+34 LOC`。
- 新增 R7.1 测试：180 行。
- 基线文档：62 行；浏览器结果 JSON：33 行；最终报告为本文件。
- 新增业务 Model：0；业务表：0；第二套 Service：0；版本目录：0；大型依赖：0；新 Scheduler/Worker：0。
- 新 Route 直接 `db.add`/`conn.execute` 写入：0；Legacy Read/Write：0。

修改产品文件：

- `app/routes_platform.py`
- `app/security.py`
- `app/services/club_operations_service.py`
- `app/services/collection_service.py`
- `app/services/unified_resource_service.py`
- `app/v05c_club_events.py`
- `app/v05f_collection.py`
- `app/templates/club_events.html`
- `app/templates/v05c_club_events.html`
- `app/templates/v05f_collection.html`
- `app/templates/platform/resources.html`
- `app/templates/platform/resource_form.html`
- `app/templates/platform/resource_detail.html`

## 16. Remaining UX Problems

1. Source Discovery 是同步请求，真实官网较慢时页面等待可能超过 30 秒；功能可用，但后续可考虑在不建立第二套 Worker 的前提下改善进度提示。
2. 批量导入 Candidate 没有实时抓取元数据时会显示通用 READY；不会 500，但解释粒度低于官网 Discovery Candidate。
3. Event 表单只使用现有 Schema，未为结束时间、独立联系方式等展示字段扩表。
4. 全量 pytest 仍保留 15 failed / 3 errors 历史债务，本轮不处理。

## 回滚

- 代码：对提交 `MVP-R7.1 admin operability and source discovery` 执行标准 `git revert <R7.1提交SHA>`。
- 数据：本提交不包含正式数据库写入或迁移，无需数据回滚。

## PASS 条件复核

30 项硬条件全部满足：Source CRUD/测试/Preview/Discovery/Candidate/退役/调度安全，Event 创建/编辑/发布/Viewer 查看报名/删除保护/安全 Draft 删除，Resource 编辑/安全删除/受保护关闭/批量部分成功，Viewer 403 与 UI 显隐，Single Write、Canonical Read、Legacy 0、测试 Scheduler 隔离、Chromium 和历史失败集合均通过。
