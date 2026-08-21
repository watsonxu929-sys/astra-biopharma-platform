# MVP-R2 Canonical Single Write Result

## A. 一句话结果

**PASS** — 8个领域各保留1个既有Canonical Write Owner，Route与非Owner直写均为0，Golden Loop在临时库完整通过，正式数据库前后完全一致。

R1状态继续保持 `PARTIAL / manual_browser_acceptance_pending / TOOLING_BLOCKED`；本任务没有重开R1浏览器验收，也没有修改导航或页面体系。

## B. Before

| Domain | 修改前Active Writer | 主要问题 |
|---|---:|---|
| Intelligence | 3 | Candidate审核Owner、Collection绕过审核、Admin Route ORM直写 |
| Resource | 4组Canonical + 2个Legacy入口 | Golden Loop、Q-BAY补列/审核、Need/Offering副本 |
| Match | 2个Canonical + 1个Legacy状态入口 | Golden与Q-BAY各自持久化 |
| Opportunity | 3 | Unified、Golden、Business各自写；另有shadowed死Writer |
| FollowUp | 3 | Unified、Golden、Business各自写；另有shadowed死Writer |
| Task | 3个Canonical + 4个Legacy Action入口 | 协作Task和`actions`并行写 |
| Relationship | 3个Canonical + 1个Legacy入口 | Canonical、Golden、Entity Governance、导入Legacy |
| Evidence | 2 | Canonical与Golden各自写 |

完整调用链见 `MVP_R2_WRITE_MAP_BEFORE.md`。

## C. After

| Domain | 唯一Owner | Writer数 |
|---|---|---:|
| Intelligence | `IntelligenceProductService` | 1 |
| Resource | `UnifiedResourceService` | 1 |
| Match | `GoldenLoopService` | 1 |
| Opportunity | `UnifiedOpportunityService` | 1 |
| FollowUp | `UnifiedOpportunityService` | 1 |
| Task | `UnifiedOpportunityService` | 1 |
| Relationship | `CanonicalRelationshipService` | 1 |
| Relationship Evidence | `CanonicalRelationshipService` | 1 |

- Route direct canonical writers：`0`。
- 非Owner Service direct canonical writers：`0`。
- 平台等价Legacy表新增写入口：`0`。
- 新增业务Service / Model / DB表 / 版本目录：均为`0`。

## D. 删除或冻结了什么

- `routes_platform.py`：删除Admin Intelligence ORM直写；人工录入只建草稿，发布必须满足审核Candidate+Evidence门禁。
- `platform_service.py`：删除被后置delegate覆盖的Opportunity/FollowUp/Task重复ORM实现。
- `golden_loop_service.py`：删除Resource、Opportunity、FollowUp、Task、Relationship、Evidence的复制SQL。
- `club_operations_service.py`：删除Q-BAY Resource补列/审核SQL和Match生成/审核/转化SQL。
- `business_collaboration_service.py`：删除Opportunity补列/阶段、FollowUp、Task直接SQL。
- `entity_governance_service.py`：删除Relationship端点直接UPDATE。
- `product_recovery_service.py`：删除Collection到Intelligence的ORM绕过发布。
- `v05b_member_import.py`：删除导入时自动写`relations / v04f_club_needs / v04f_club_offerings`。
- `v05d_member_portal.py`：删除Legacy Need/Offering发布和Legacy Match状态更新。
- `v04f_operations.py`、`signal_service.py`、`recommendation_service.py`：冻结旧`actions`写入口。

按Before Map计：删除/冻结直接Writer组`11`组；其余入口改为delegate。

## E. Delegate了什么

- Admin与Collection发布 → `IntelligenceProductService`。
- Golden Loop与Q-BAY Resource → `UnifiedResourceService`。
- Q-BAY规则Match、审核和机会关联 → `GoldenLoopService` Match owner。
- Platform、Golden Loop、Business Collaboration、Q-BAY Lead转化 → `UnifiedOpportunityService`。
- Platform、Golden Loop、Business Collaboration FollowUp/Task，以及Q-BAY活动独立业务任务 → `UnifiedOpportunityService`。
- Golden Loop won结果、Entity Governance合并/回滚 → `CanonicalRelationshipService`。

Q-BAY仍保留Membership、Member Account、Event、Registration、Check-in等场景数据；Need/Offering/Match/Opportunity/FollowUp/Relationship/Task不再拥有第二套正式写模型。`v04f_lead_records`仅作为候选线索阶段数据，不作为正式Opportunity，转化时只由Opportunity owner落正式记录。

## F. Legacy冻结事实

正式`app/**/*.py`静态扫描确认以下平台等价表无INSERT/UPDATE/DELETE：

```text
resources
v04f_club_needs
v04f_club_offerings
v04f_club_matches
relations
actions
```

历史数据未迁移、未删除；查询适配仍可读。基础设施`task_queue / task_runs`不属于业务Task，本轮未改。

## G. Golden Loop与回归

- `tests/test_mvp_r2_single_write_contract.py`：`4 passed`。
- R2 + RC1 Golden + RC1.2 + R1产品表面 + Opportunity + P3 Relationship定向集合：`41 passed`。
- Q-BAY Club Operations排除已知migration前置债务后：`4 passed`。
- 临时库完整链：Intelligence → Resource → Match → Opportunity → FollowUp → won/lost/paused → Relationship → Evidence。
- won产生1条Relationship和Evidence；lost/paused均不产生Relationship。
- 三用例临时写入：Resource 6、Match 3、Opportunity 3、FollowUp 3、Relationship 1；脚本最终清理完成，marker残留0。
- viewer关键写操作：`403`；integrity：`ok`；Legacy六表行数前后完全一致。
- 真实Uvicorn + HTTP/session：登录POST `303`；`/platform /intelligence /network /resources /collaboration /club`全部`200`。

全量pytest共126项：`107 passed / 1 skipped / 15 failed / 3 errors`。18个非通过项全部位于既有migration幂等、v06i旧Settings/Schema契约、v06k旧Dashboard契约或P4 migration前置验证；R2契约和本轮修改路径为0失败。它们与RC1.1登记的历史债务同类，但由于R1期间测试拓扑变化，不能把当前15/3伪装成原12/34的逐项同集合。

## H. 正式数据库保护

| 项目 | Before | After |
|---|---|---|
| SHA256 | `6BDDFF2C592EB671D219F0E88CF2D8778FD9A18D6CD891AB861C62D70685B402` | `6BDDFF2C592EB671D219F0E88CF2D8778FD9A18D6CD891AB861C62D70685B402` |
| integrity_check | `ok` | `ok` |
| 非内部表数量 | 187 | 187 |

8张Canonical表行数前后：`25 / 20 / 0 / 11 / 4 / 4 / 0 / 0`，完全一致。

Legacy保护表行数前后：`raw_intelligence=1, resources=8, needs=0, offerings=1, matches=0, lead_records=0, v06_follows=0, task_queue=0, task_runs=0, actions=7, relations=26, v04c1关系=0, v04c1证据=0`，完全一致。

所有写入验收使用Windows OS临时数据库；HTTP临时账号、数据库、WAL/SHM和日志已删除。

## I. 规模变化

- Production tracked LOC：`+562 / -877`，净`-315`。
- Tests：新增`111 LOC`。
- Audit docs：`294 LOC`（4个R2文档）。
- 修改/新增文件：17个正式源码、1个测试、4个审计文档，共22个。
- 新增业务Service：0；新增Model：0；新增表：0；新增依赖：0；新版本目录：0。
- Canonical Owner：8个领域各1个；Route direct writer：0。

正式产品代码净新增为负，未触发“净新增超过200 LOC”的停止条件，也未建立Repository、Registry、Command Bus或其他新架构层。

## J. 已知遗留

1. R1真实Chrome证据仍为`TOOLING_BLOCKED / manual_browser_acceptance_pending`，不属于R2失败。
2. 全量pytest的migration/v06i/v06k历史契约债务继续登记，不在R2恢复Legacy行为。
3. Legacy历史数据尚未迁移；按任务要求等待独立R3判断，本轮没有提前执行。
4. `v04f_lead_records`保留候选线索工作流；它不是正式Opportunity副本，正式转化只写`v06_opportunities`。

## 验收结论

MVP-R2全部15项PASS条件满足。回滚方式：对最终单一R2提交执行`git revert <R2最终commit>`；R1独立提交`b54ad1339504baaed2ac71dbfa4c74edf946acd1`不受影响。
