# MVP-RC1.2C 情报生命周期与安全删除结果

## 1. PRODUCT RESULT

**MVP-RC1.2C PASS**

情报采集系列继续作为 `CORE_INTELLIGENCE_CAPABILITY` 保留；管理员和运营人员现在可以从正式页面预览真实下游引用，并安全删除、下架、归档或恢复正式情报。删除路径不会级联删除企业、人物、关系、资源、机会或跟进。

基线为 `release/mvp-rc1.2` / `abba6c6ef73b9ee2774b520db4948e62dab2ca4a`。本轮没有新增业务表、业务 Model、第二套 Service、生命周期 V2、Crawler、Provider、Worker 或业务算法，也没有改写 RC1.2B 信息架构。

## 2. Intelligence Collection Preservation

以下正式能力均保留并经浏览器打开验证：采集概览、Source 列表、Source Discovery、批量导入入口、采集任务、原始采集记录、Collection 历史和情报首页。Source 管理、采集运行与原始证据没有因生命周期功能发生回归。

Source 与 Intelligence 分开管理，因为 Source 是未来持续采集的配置，Intelligence 是审核后的业务成果。删除或下架一条情报不能停止来源；退役一个来源也不能抹掉已形成的情报、Snapshot 和业务历史。

## 3. Actual Collection → Intelligence Pipeline

系统抓到网页后，真实链路是：

`v04g_monitoring_sources` → Collection Run → 不可变 Snapshot + 去重 Raw Collection → Processing Job → Processing Worker 产生 Candidate/证据/主体候选 → 人工审核 Candidate → `IntelligenceProductService.publish_candidate` 发布正式 Intelligence → 人工确认 Subject Link → Resource / Match / Opportunity / FollowUp / Relationship。

Candidate 在 Processing Worker 执行加工任务时产生；正式 Intelligence 只有在 Candidate 审核通过并具备证据后，由既有发布 Service 产生。完整表、Service、自动与人工边界见 [生命周期事实审计](MVP_RC1_2C_INTELLIGENCE_LIFECYCLE.md)。

## 4. Processing Automation Status

`PROCESSING_AUTOMATION_GAP=true`

正常 Source 产生新 Collection 后会自动创建 Processing Job，因而不需要管理员逐条手工“新建加工任务”。但任务的实际执行依赖独立 Processing Worker；Worker 未运行时，管理员仍需要“立即执行一次”或启动 Worker。本轮按范围约束只登记该缺口，没有重构 Processing Engine、Scheduler 或 Worker。

## 5. Delete Safety Matrix

删除判断来自正式 Schema 和实际查询，不依赖页面表象。完整矩阵见 [删除安全矩阵](MVP_RC1_2C_INTELLIGENCE_DELETE_MATRIX.csv)。Subject Link、Relationship/Evidence、Resource/Match、Opportunity/FollowUp 或历史报告引用任一非零，都会返回 `PROTECTED_BY_BUSINESS_REFERENCES`。

收藏等纯辅助引用可在安全硬删除时清理；Source、Snapshot、Organization、Person 及核心业务对象永远不由情报删除动作清理。

## 6. Hard Delete

管理员现在从情报详情点击“删除”，先进入 Impact Preview，看到标题、时间、Source、状态及 Raw、Processing、Candidate、Subject Link、Relationship/Evidence、Resource、Match、Opportunity、FollowUp、Report、收藏等真实数量。

只有正式业务引用全部为零时才显示 `SAFE_TO_DELETE` 和确认按钮。确认后删除正式 Intelligence 及纯辅助幽灵链接，并写入既有 `p2_intelligence_audit_log`。如果已有跟进、报告、主体关联或其他正式引用，后端以 409 阻止硬删除并展示具体原因。

## 7. Withdraw

下架将状态写为 `withdrawn` 并记录审计。它适合内容真实但不应继续展示的情报。下架后退出普通情报流、今天值得处理、Organization 正常动态以及新的业务判断；原始证据、历史报告、FollowUp、Opportunity 和 Relationship Evidence 保留。Admin/Operator 可以恢复上架。

不能安全删除时，下架是正确选择，因为它停止继续传播和新业务使用，同时不破坏已经发生的业务历史。

## 8. Archive

归档将状态写为 `archived` 并记录审计。它适合真实但已经过时的情报。归档后不进入最新流和今天值得处理，仍可从历史详情和 Organization 历史动态访问，已有报告继续可追溯。

不能删除的历史有效内容应归档，而不是抹掉其证据和业务上下文。

## 9. Restore

Admin/Operator 可以把 `withdrawn` 或 `archived` 恢复为 `published`。恢复动作写入现有审计日志；恢复后的情报重新按既有时间和排序规则决定是否进入产品流，不制造新的优先级或业务数据。

## 10. Raw Collection Lifecycle

Raw Collection 只有在 Processing Job、Candidate、正式 Intelligence、Resource、Workflow 和重复子记录全部为零时可单独删除。Source 与 Snapshot 始终保留。

对明确的测试、错误或垃圾采集链，管理员可在 Preview 后清理 Raw、Processing Job/Block 及无正式引用的未确认 Candidate。若链上已经形成正式 Intelligence，当前保守流程要求先在正式 Intelligence Impact Preview 中完成安全删除，再清理原始链；任何正式引用存在时整条链都会被阻止。原始采集证据只有在未形成任何正式业务引用的错误链中才可清理，Snapshot 仍作为来源证据保留。

## 11. Candidate Lifecycle

只有 `pending`、`needs_review` 或 `rejected` 且没有 Product、Relationship Evidence、Signal、Application Log 等正式引用的 Candidate 才能删除。`approved`、`applied`、`published`、`merged` 或已有正式引用的 Candidate 一律保护。候选删除写入既有审计日志，原始 Snapshot 保留。

## 12. Bulk Operations

情报管理模式支持多选下架、归档、恢复和删除。批量操作逐条执行并返回成功数、失败数及每条保护原因；一条受保护记录不会导致整批回滚。隔离库真实浏览器验收已验证 5 条混合数据的 Partial Success。

## 13. Permission

Formal Intelligence 生命周期动作仅 Admin / Operator 可用；Raw Collection 删除要求 Admin 或 `manage_monitoring`；Candidate 删除要求 Admin 或 `review_data`。Viewer 页面不显示危险按钮，且真实 POST 对 DELETE、WITHDRAW、ARCHIVE、RESTORE、BULK_DELETE、RAW_DELETE、CANDIDATE_DELETE 全部返回 403，不是仅靠前端隐藏。

## 14. Downstream Protection

删除 Intelligence 不会删除 Organization、Person、Relationship、Relationship Evidence、Resource、Match、Opportunity、FollowUp 或 Source。多个下游引用并无数据库 FK，Service 因此显式查询；Subject Link 即使数据库定义了级联，也被产品规则视为正式业务引用并阻止硬删除。

隔离库受保护场景验证：Intelligence 删除被阻止，随后允许下架；对应 Opportunity 和 FollowUp 均继续存在。浏览器验收过程中发现并最小修复了一个真实历史详情缺陷：非 published 详情不再被 Golden Loop 的 published-only 查询误判为 404。

## 15. Workbench / Organization / Report Effects

下架和归档情报退出“今天值得处理”；恢复后按既有规则重新评估。Organization 最近动态只展示 published 和 archived，withdrawn 不再作为正常动态出现；archived 有历史状态标识且链接有效。历史报告引用会阻止硬删除，下架或归档不会修改已生成报告；新业务判断继续只消费 published 情报。

## 16. Chromium

项目现有 Playwright 驱动真实 Chromium `151.0.7922.34`，使用正式库克隆出的隔离验收库和临时 Admin/Operator/Viewer 账号。应用实际加载 HTML/CSS/JS，并完成安全删除、受保护删除后下架、归档/恢复、批量 Partial Success 与 Viewer 后端 403。

- 页面/场景：15
- Console Error：0
- Page Error：0
- Network Failure：0
- Unexpected 404/500：0
- 横向溢出：0（含 1024px）
- 用户可见乱码、undefined、null：0

Codex 内置浏览器通道曾因 Windows ACL/orchestrator helper 无法启动；记录一次后按任务要求切换到项目现有 Playwright，没有将工具通道异常误判为产品失败。证据索引及10张正式截图位于 [浏览器验收证据](evidence/mvp_rc1_2c/browser_acceptance.json)。

## 17. Database Safety

正式数据库：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`

- 前 SHA256：`FED798300231934D170F104C4A4F4676AE90103C9888D29F6A0CD97AA6C1A3FB`
- 后 SHA256：`FED798300231934D170F104C4A4F4676AE90103C9888D29F6A0CD97AA6C1A3FB`
- 前后 `integrity_check`：`ok`
- 核心计数前后完全一致：Intelligence 31、People 44、Organizations 24、Projects 5、Subject Links 1、Resources 30、Match Candidates 0、Opportunities 11、FollowUps 4、Relationships 25、Relationship Evidence 25、Sources 15、Collection items 521、Snapshots 60、Processing jobs 49、Candidates 160。
- RC1.2C 临时账号残留：0；验收情报标记残留：0。

所有破坏性测试和浏览器写操作均在隔离数据库完成；正式数据库只读。

## 18. Tests

- RC1.2C 新增生命周期与安全删除测试：8 passed。
- RC1.2C + RC1/RC1.1/RC1.2B/R7.1/R5B 关键联合回归：43 passed。
- 既有情报管线与价值激活定向回归：16 passed。
- Python compileall：passed。
- 全量 pytest：`15 failed / 3 errors / 1 skipped`，与任务开始时历史基线完全一致；新增失败/错误为0。失败集合仍仅为既有 migration、v06i runtime baseline 和 v06k P4 operations 历史债务。

## 19. Remaining Problems

1. `PROCESSING_AUTOMATION_GAP=true`：新 Collection 自动入 Processing 队列，但 Processing Worker 未运行时仍需人工触发执行。
2. 错误采集链若已经形成安全可删的正式 Intelligence，需要先经正式 Intelligence Impact Preview 删除，再执行 Raw 链清理；当前没有新增一个跨层级的一键级联删除动作，以避免误删。
3. 历史 pytest 的 15 failed / 3 errors / 1 skipped 仍存在，本轮未扩大也未按要求清理。

上述问题不违反 RC1.2C 的24项 PASS 硬条件。本轮完成后停止，不进入 RC1.2D、RC1.3、R8 或自动翻译。
