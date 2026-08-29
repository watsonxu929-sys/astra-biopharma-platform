# MVP-RC1.2A 产品信息架构、页面职责与 UI 重构前置决策审计

## 1. Executive Conclusion

**结论：RC1.2A 审计完成，推荐 Product Option A。** RC1.2B 的普通产品一级导航应冻结为：`工作台 / 情报 / 企业与人物 / 俱乐部 / 跟进`。资源与 Relationship 降为上下文对象，报告作为情报的阅读入口，采集、加工、审核、治理、批量维护和错误恢复统一归入管理控制台。

审计没有修改任何 Production Route、Service、Model、Template、CSS、JS、导航或数据库业务数据。正式基线为 `release/mvp-rc1.2` / `6bfc16e67beaa20c6ea5e168439d86020b2a2c83`。正式数据库为 `data/app.db`，审计前 SHA256 为 `FED798300231934D170F104C4A4F4676AE90103C9888D29F6A0CD97AA6C1A3FB`，`integrity_check=ok`。

主要事实：

- 当前产品实际一级导航只有 4 个，Club 有真实闭环但被隐藏在一级导航之外。
- `/platform` 已经具备“今天值得处理 + 我的待办”的核心雏形；`/workspace` 的五个 advertised tabs 并未真正实现，且与工作台重复。
- `/processing/jobs` 是后台运营/恢复入口，不是普通用户核心产品。
- `/reports` 是固定 Python 章节的聚合器，不是成熟 Report Engine；真实 Chromium 访问 `/reports/1` 返回 422。
- `/network` 只是 42 人物、23 机构、5 关系的统计 Landing，增加一次无必要点击；主体目录与详情才有业务价值。
- Club 复用 Canonical Organization、Person、Resource、Match、Opportunity、FollowUp、Relationship，不需要新增业务 Model 即可恢复正式产品入口。

本审计只形成 RC1.2B 的决策和范围，不实施任何上述变化。

## 2. Current Product Map

当前真实一级导航：

```text
工作台 / 情报 / 企业与人物 / 跟进
```

当前产品表面同时存在三类内容：

1. **业务消费/行动**：工作台、情报、主体档案、Resource、Opportunity、FollowUp、Relationship、Club 会员与活动。
2. **后台运营**：Source、Collection、Processing Job、Candidate Review、Report Job、Entity Governance、Club operations。
3. **历史或实验表面**：Signals、Research、Watchlists、Legacy Lead 等，与 Canonical 产品职责重叠或不属于 RC1。

完整四层树见 `MVP_RC1_2A_CURRENT_NAVIGATION.md`。核心矛盾不是页面数量，而是普通产品与后台工具在“情报”下混合、两个工作台重复、Club 无正式入口、主体入口多一跳、上下文对象被当作独立模块。

## 3. Page Decision Matrix

正式逐入口决策见 `MVP_RC1_2A_PAGE_DECISION_MATRIX.csv`。矩阵覆盖 L1 一级导航、L2 页面入口、L3 页内区域/伪 Tab 和 L4 实际动作；每项均使用唯一确定的 `KEEP / MERGE / RESTRUCTURE / MOVE_TO_ADMIN / MOVE_TO_UTILITY / HIDE / DELETE_CANDIDATE` 决策。

决策原则：

- 能直接回答高频业务问题并推动 Golden Path 的页面保留或重构。
- 只负责运行、审核、治理、批量、恢复的页面移动到 Admin。
- 共享 Canonical 对象但没有独立高频入口价值的 Resource、Relationship、Graph 降为上下文。
- 没有真实数据源或重复 Canonical 能力的入口隐藏或列为删除候选；本阶段不删除。
- 业务阅读和管理员编辑若共用对象，必须拆分呈现层，不复制 Model 或 Service。

## 4. Workspace

### 真实结构

`/workspace` 不是同一路由下真正工作的五个 Tab。Capability Registry 生成 `?tab=overview|todos|followups|favorites|recent`，但 route 不读取 `tab`，模板固定显示“我的待办 / 待处理联系 / 我的合作 / 最近访问”。因此五个二级入口当前只是五个 URL 指向同一页面。

| advertised entry | 真实数据源 | 用户级持久化 | 决策 |
|---|---|---:|---|
| 业务概览 | tasks、opportunities、contact intents、resources、favorites 的混合查询 | 部分 | MERGE → `/platform` |
| 我的待办 | `v06_collab_tasks`，按当前用户 | 是 | MERGE → `/platform`，KEEP_PRIMARY |
| 最近跟进 | 应为 `v06_follow_ups`；但 `/workspace` 当前未渲染 | 是 | MERGE → `/platform`，KEEP_PRIMARY |
| 我的收藏 | `v06_favorites`；route 查询但模板未渲染，当前 0 条 | 是 | MOVE_TO_UTILITY |
| 最近访问 | route 未提供 `recent_views`，未发现可靠持久化来源 | 否 | HIDE |
| 待处理联系 | pending contact intents | 是 | MERGE → 工作台待办/企业人物上下文，KEEP_SECONDARY |
| 我的合作 | 当前用户发起的 active `v06_opportunities` | 是 | MERGE → `/opportunities` |

“我的待办”对象是 `v06_collab_tasks`；“最近跟进”对象应是 Canonical `v06_follow_ups`。收藏用于现有 favorite 能力所支持的对象，但当前产品页没有把查询结果展示出来。最近访问没有可验证的产生与持久化机制，不能继续作为正式入口。

目标工作台只保留三块：`今天值得处理 / 我的待办 / 最近跟进`。收藏进入用户工具，最近访问隐藏。

## 5. Workbench Data Logic

### 当前事实

当前 `/platform` 已存在“今天值得处理”。数据来自 `GoldenLoopService.priority_feed`：

- 输入：已发布、非 demo 的 `v06_intelligence_items`。
- 时间：`date(COALESCE(occurred_at,published_at,created_at)) >= date('now','-30 days')`。
- 候选：先取最新 60 条，最终显示 1–20 条。
- Priority：没有持久化 Intelligence priority 字段；由 Q-BAY membership、Canonical Resource、Relationship、Opportunity history、favorites/follows/tags 动态推导 P1–P5。
- Relevant：本函数没有读取独立 persisted relevant 字段；已发布/非 demo 是入口门槛，重要度、事件类型和上下文决定排序。
- Relationship：参与 band 1。
- Q-BAY：通过会员/生态上下文参与 band 1。
- Resource：直接或相关 Resource 进入 band 2；若同时有优先主体上下文可进入 band 1。
- FollowUp：不直接参与情报 feed 排序；它作为工作台单独队列显示。Opportunity 是否存在会参与 band 1。
- 暂不处理：写入 `v05h_intelligence_feedback` 的 `dismissed_today`；只在情报可追溯到 collection item 时可写，否则返回 409。
- 恢复：追加 `restored_today`；最新反馈状态生效。
- 不修改 Intelligence：暂不处理不会删除或改变正式 Intelligence。
- 退出：滚动 30 日窗口让旧情报自然退出；用户当天忽略让项目退出当天列表。

### WORKBENCH_SORTING_SPEC

RC1.2B 必须复用现有数据，不增加评分模型：

1. **Band 1**：时间有效，并存在 Priority Subject、Q-BAY、Canonical Relationship 或 Opportunity 上下文，且现有规则能给出具体下一步。
2. **Band 2**：时间有效，并存在直接或相关 Canonical Resource。
3. **Band 3**：`importance >= 4`，或事件类型为 approval / clinical / financing / merger / policy / expansion。
4. **Band 4**：其他近期已发布、非 demo Intelligence。
5. 同 Band 按事件/发布日期/创建时间较新优先。
6. 应用当前用户当日 dismiss/restore 的最新状态过滤；不改 Intelligence 本身。

空状态固定为：`今天暂时没有需要优先处理的产业动态。`；次级动作固定为 `[查看全部情报]`。

## 6. Intelligence Processing

总体分类：**ADMIN_OPERATION**。其中手工新建、立即运行、重新加工属于后台恢复/运营动作，不是普通用户产品动作。

真实链路：

```text
Route app/v05g_processing.py
→ ProcessingJobService app/services/processing/processing_job_service.py
→ v05f_collection_items + v04g_source_snapshots
→ v05g_processing_jobs
→ process_job / task registry / collection cascade executor
→ processing blocks + extraction candidates + fact evidence + subject match candidates
→ IntelligenceReviewService
→ IntelligenceProductService.publish_candidate
→ Canonical v06_intelligence_items
```

问题答案：

1. “原始情报编号”字段实际接收的是 Collection Item id，不是正式 Intelligence id。
2. 来源快照编号是 `v04g_source_snapshots` 的 snapshot id，提供 cleaned/raw text。
3. Job 保存于 `v05g_processing_jobs`。
4. `process_job` 由 collection cascade、task registry/worker 或管理员 run-now 调用。
5. 正常采集可自动级联创建并执行 Processing Job。
6. 正常采集不需要人工创建 Job。
7. 管理员只在历史项补处理、失败恢复、指定 snapshot 验证或 queued-only 调度时手工创建。
8. 重新加工会重新生成/更新 blocks 和候选及 Job 状态；不应绕过审核直接覆盖正式情报。
9. Candidate 由 page classification、block split 和确定性抽取规则产生，并保留 evidence。
10. Candidate 经人工审核并调用 `publish_candidate` 后才产生 Canonical Intelligence。
11. 失败会记录 Job/Item failed 状态、error type/message；由重试、reprocess 或 worker 恢复。

RC1.2B 只需把 `/processing/jobs`、候选和审核入口移出普通“情报”导航，不能重写加工链。

## 7. Report Engine

真实分类：**FIXED_TEMPLATE_AGGREGATOR**，不是 REPORT_ENGINE。

Weekly Industry Report 链：

```text
/reports 表单选择 weekly + 日期
→ create_report_job 查询启用的 v05h_report_templates id
→ v05h_report_jobs
→ generate_report
→ 查询 v05e_industry_signals / events / v04c_review_items / collection queued count
→ 固定 Python _render 章节
→ v05h_generated_reports（HTML + Markdown）
→ 页面阅读 / 草稿编辑 / 提交 / 审核 / 归档
```

22 项答案：

1. Report Type：daily、weekly、monthly、subject、track、financing、attraction、qbay。
2. 类型和日期默认值定义在 reports service/route 的 Python 配置中。
3. 是固定渲染结构。
4. 章节为“执行摘要 / 核心产业信号 / 重点事件 / 风险与待核实事项 / 建议行动”。
5. 数据库存在 `v05h_report_templates`，但生成器不读取模板正文；不是实际可替换的模板文件系统。
6. 不支持用户自定义模板。
7. UI 可选 report type、period start、period end；没有企业、赛道或 Q-BAY 主体参数控件。
8. 实际主要按日期筛选；底层 signal query 可收 subject_type/id，但 UI 未传。
9. 不读取 Canonical Intelligence 的 Relevant 状态，未做正式 Relevant 过滤。
10. 没有报告级去重逻辑。
11. 仅按数据类型分固定章节，没有成熟业务分类引擎。
12. 使用查询顺序/限制，不存在独立价值排序模型。
13. 不做主体聚合。
14. 不加入 Canonical Relationship。
15. 不加入 Canonical Resource。
16. 不加入 FollowUp。
17. 没有真正分析逻辑，属于规则化数据装配与固定文案。
18. daily/weekly/monthly 主要差异是时间范围和标题。
19. “企业报告”UI 无企业选择，因此名义能力未成立。
20. “赛道报告”UI 无赛道选择，因此名义能力未成立。
21. 生成后支持 draft edit、submit、approve、archive 的审核状态流。
22. 输出存储和展示为 HTML + Markdown；此链未提供 PDF/DOCX 成品。

另有真实缺陷：Chromium 访问 `/reports/1` 返回 422。代码中 `/reports/{report_id:int}` 装饰器落在 `intelligence_product_detail` 上，而 `report_detail` 没有相应装饰器。这一事实使当前报告阅读链不可用；本轮只记录，不修复。

第一版定位应是“固定业务模板 + 有限可选参数 + 审核后阅读”。现有能力只勉强支撑通用日报/周报；企业专题、赛道、融资、招商和 Q-BAY 周报不能因类型名存在而宣称可用。RC1.2B 不得新增报告算法，只能分离阅读/运营层、呈现真实能力并修复既有页面连续性。

## 8. Enterprise & People

最终决策：**DIRECT_TO_DIRECTORY**。

1. `/network` 的独立价值仅是 42 人物、23 机构、5 有效关系统计与三个快捷入口。
2. 数字分别来自 active `people`、active `organizations`、approved/current `p3_canonical_relationships`。
3. 用户没有必须经过 Landing 的业务理由。
4. 可以直接进入合并的企业/人物目录；以机构为默认 tab。
5. Organization 详情已有基础资料、Relationship、联系人、Intelligence、Resource、FollowUp、历史 Evidence 摘要与监测上下文。
6. Person 详情复用同一主体档案框架，含基础资料、关系、关联情报/资源/跟进和证据上下文。
7. 当前从一级导航查看企业至少需 `/network → organizations → detail` 两次后续点击；直接目录可减少一次。
8. “关系网络”使用 `RelationshipNetworkService.graph`，有真实 Canonical 网络计算。
9. “人脉推荐”使用 `ConnectionRecommendationService` 的关系路径规则，不是 AI；仅有权限用户可用。
10. “主体治理”只应属于 Admin。

Organization 详情支撑度：

| 目标职责 | 支撑度 | 依据 |
|---|---|---|
| Basic | AVAILABLE | Canonical Organization 字段与档案头 |
| Relationship | AVAILABLE | Canonical current relationships |
| Person | PARTIAL | 联系人主要由 `people.organization_network LIKE organization name` 和关系上下文派生，缺少明确结构化组织任职链 |
| Intelligence | AVAILABLE | Subject Link + Canonical Intelligence |
| Resource | AVAILABLE | Canonical `v06_market_resources` |
| FollowUp | AVAILABLE | Canonical `v06_follow_ups` |
| Opportunity | PARTIAL | service/business trace 可查询，但模板没有独立 Opportunity 区 |
| Evidence | PARTIAL | 档案给摘要/关系链接，完整 Evidence 在 Relationship 详情 |

RC1.2B 只能重组现有查询结果，不得为 PARTIAL 项新增表或 Model。

## 9. Q-BAY Club

最终选择：**OPTION 1 — 俱乐部恢复为一级正式业务场景**。

### 存量清单

- Routes：`app/v04f_operations.py`、`app/v05b_member_import.py`、`app/v05c_club_events.py`、`app/v05d_member_portal.py`；API 包括 `clubs.py`、`club_operations.py`、`events.py`、`membership_person_link.py`、`membership_user_link.py`。
- Templates：`club_home.html`、`club_members.html`、`club_operations.html`、`club_matches.html`、`club_events.html`、`v04f_club.html`、`v04f_club_apply.html`、`v05b_member_import.html`、`v05c_club_events.html`、`v05d_member_portal.html`、`v05d_member_admin.html`。
- Services：`club_operations_service.py`、`club_matching_service.py`、`membership_access_service.py`、`membership_person_link_service.py`、`membership_user_link_service.py`、member import services。
- Canonical Models：Organization、Person、Event、MarketResource、Match Candidate、Opportunity、FollowUp、Relationship 等；没有第二套正式 Q-BAY Organization Model。
- Scene tables：`v04f_club_applications`、`v04f_club_memberships`、`v05c_club_event_profiles`、registrations、participation、member activity scores、`v05d_member_accounts`、profile/privacy/content/match feedback、notifications、announcements、membership history、event feedback、check-in token/audit、event relationship candidates、club lead candidates、domain events、operation audit。
- Frozen legacy tables：`v04f_club_needs`、`v04f_club_offerings`、`v04f_club_matches`、legacy lead records；正式产品读写已切 Canonical。
- Capabilities：`club`、`club.home`、`club.members`、`club.events`、`club.matching`、`club.operations`，以及 admin.club / account.membership。

### 16 项答案

1. Club 首页仍在：`/club`。
2. RC1 隐藏原因是 `PRIMARY_ORDER` 不含 Club，不是能力被删除。
3. 普通 viewer 能进入 `/club` 和 `/club/events`。
4. Member 数据和运营能力可用，但 viewer 进入当前可见 `/club/members` 会到无权限页，阅读/管理边界需要重构。
5. Event 可用，有列表、详情和生命周期。
6. 发起活动可用，但应归 Club Admin operation。
7. 报名可用，并有审核、签到、撤销签到和反馈。
8. Supply/Demand 正式读写使用 Canonical `v06_market_resources`；旧 club needs/offerings 已冻结。
9. Match 使用 Canonical `p4_resource_match_candidates`；旧 club matches 已冻结。
10. Club Membership 通过 canonical Person/Organization id 和绑定服务关联核心主体。
11. 没有第二套正式 Q-BAY Organization Model。
12. 没有第二套正式 Resource；历史表仍存在但不作为正式读写。
13. 没有第二套正式 Opportunity；使用 `v06_opportunities`。
14. 被隐藏的包括 Club 一级入口、会员/运营若干二级能力；代码和数据并未消失。
15. 恢复入口本身只需已有导航/Capability/权限呈现调整；无需新增业务能力。具体 LOC 由 RC1.2B 在冻结范围内控制，本审计不预估伪精确数字。
16. 不需要新增任何业务 Model。

选择一级的理由：会员、活动、报名、签到、供需、匹配、通知和运营形成独立高频场景与商业闭环；五个一级导航仍可控；所有核心对象继续复用 Canonical Core。Club 是 Scenario，不是第二套平台。

## 10. User Product vs Admin Console

### USER_PRODUCT

- 工作台：今天值得处理、我的待办、最近跟进。
- 情报消费：列表、详情、订阅辅助、已审核报告阅读。
- 企业/人物：目录、档案、关系上下文、确定性人脉路径。
- 俱乐部：会员阅读/自助、活动阅读/报名、Canonical 供需与匹配上下文。
- 跟进：Opportunity、FollowUp、Task、Meeting、Outcome、Evidence/Relationship 追溯。
- 必要上下文：Resource、Match、Relationship、全局搜索、收藏。

### ADMIN_CONSOLE

- Source、Source Discovery、Collection、Run、Item、Snapshot。
- Processing Job、Block、Candidate、Review Queue、Publish、reprocess、错误恢复。
- Entity/Relationship Governance、merge、候选确认。
- Club membership/application/import/binding、活动创建审核签到反馈、operation queue。
- Report Job、生成、草稿编辑、审核、归档、恢复。
- User、Permission、Identity、Integrity、Migration、Audit、Scheduler/Worker/System operation。

边界规则：业务页只读核心事实和执行获授权业务动作；所有新增/编辑/导入/批量/审核/治理/重跑/恢复进入管理控制台。两层调用相同 Service/Canonical Model，禁止复制业务逻辑。

## 11. UI Density Audit

真实 Chromium 版本 `151.0.7922.34`；在 1366 宽检查 12 页，在 1920 宽复验 6 个核心页，另检查 viewer 4 个页面。受检页面横向溢出 0、Page Error 0、request failure 0、乱码 0。唯一 Console Error 和非 2xx 是 `/reports/1` 的 422。

由于宿主 ACL 阻止内置图像查看器读取截图，视觉判断结合真实页面 DOM、全页截图尺寸、可见区块/表单/表格数量和浏览器事件完成；截图由 Playwright 成功生成于隔离临时目录，未作为仓库产物提交。

| 页面 | effective_content_density | unused_whitespace | card_overuse | action_hierarchy | navigation_clarity | empty_state_quality | visual_consistency | 事实摘要 |
|---|---|---|---|---|---|---|---|---|
| 工作台 | GOOD | GOOD | ACCEPTABLE | ACCEPTABLE | GOOD | GOOD | GOOD | 2 个主区、1238px 高；同屏出现多个同权重“查看并决定下一步” |
| 情报列表 | GOOD | GOOD | GOOD | ACCEPTABLE | GOOD | ACCEPTABLE | GOOD | 1999 字符、2166px 高；内容密度足但扫描层级需加强 |
| 情报详情 | GOOD | GOOD | ACCEPTABLE | POOR | GOOD | ACCEPTABLE | GOOD | 7 个区块、4 个表单、2375px 高；依据和动作分散 |
| 企业与人物 Landing | POOR | POOR | ACCEPTABLE | ACCEPTABLE | POOR | ACCEPTABLE | GOOD | 226 字符、768px 高，只是统计与跳转，增加一层 |
| Organization 详情 | ACCEPTABLE | GOOD | POOR | ACCEPTABLE | ACCEPTABLE | ACCEPTABLE | GOOD | 8 个区块、1813px 高；上下文齐但卡片化和优先级不足 |
| 俱乐部 | ACCEPTABLE | ACCEPTABLE | POOR | ACCEPTABLE | POOR | GOOD | ACCEPTABLE | 7 个卡片、1743px 高；无 L1 高亮且会员入口权限不一致 |
| 跟进 | GOOD | GOOD | GOOD | ACCEPTABLE | GOOD | ACCEPTABLE | GOOD | 1039 字符、1540px 高；适合列表但状态动作需统一 |
| 报告 | ACCEPTABLE | GOOD | POOR | POOR | ACCEPTABLE | ACCEPTABLE | ACCEPTABLE | 3 卡片、2 表格、3512px 高；消费/生成/审核混合，详情422 |
| 管理控制台 | POOR | GOOD | POOR | POOR | ACCEPTABLE | ACCEPTABLE | POOR | 29 卡片、7489 字符、9559px 高；缺乏后台视觉区分和任务聚焦 |

RC1.2B 的 Before/After 截图范围确认存在：工作台、情报列表、情报详情、企业与人物（目标需合并成目录后对比）、Organization 档案、俱乐部、跟进、报告、管理控制台。

## 12. Product Option A

**一级导航**：工作台 / 情报 / 企业与人物 / 俱乐部 / 跟进。

- 普通用户首页：`/platform`，含今天值得处理、我的待办、最近跟进。
- Club：正式一级场景。
- Reports：情报二级的审核后阅读；生成/审核在 Admin。
- Resource：情报、主体、Club、Opportunity 的上下文页；全局搜索可达。
- Relationship：主体/机会的上下文和闭环证据页；图谱为企业与人物次级视图。
- Admin：独立“管理控制台”入口，容纳所有运行、审核、治理和恢复。
- 隐藏：recent visits、Signals 正式入口、Research、Watchlists、Legacy Lead。
- 合并：Workspace → Platform；Collaboration home/tasks → Followup；Network Landing → Direct Directory；Graph → Enterprise secondary view；Club supply/match → Canonical context。

优点：五个一级均对应高频业务问题；Club 的商业场景被明确恢复；Canonical 架构不变；普通用户不再看到采集加工术语。代价：RC1.2B 必须认真重构 Club 的普通阅读与管理权限呈现。

## 13. Product Option B

**一级导航**：工作台 / 情报 / 企业与人物 / 跟进。

- 普通用户首页、Reports、Resource、Relationship、Admin、隐藏和合并策略与 Option A 相同。
- Club：放在“企业与人物”的二级场景，入口为 Q-BAY 生态。

优点：一级导航更短。缺点：会员、活动、报名、签到、供需和运营动作被埋在主体目录之下，不能表达 Club 的独立商业场景；用户从 Club 到日常动作的 Navigation Depth 增加，也继续弱化当前已存在的闭环。

## 14. Recommended Product Structure

**RECOMMEND OPTION A。**

目标树详见 `MVP_RC1_2A_TARGET_NAVIGATION.md`。推荐的五个一级分别回答：

- 工作台：今天处理什么。
- 情报：发生了什么。
- 企业与人物：涉及谁、认识谁。
- 俱乐部：会员/活动/供需如何运营。
- 跟进：机会下一步如何推进并形成证据关系。

资源和 Relationship 没有足够独立高频价值成为一级，但有很高 Golden Path 价值，因此必须保留为上下文。报告当前能力不足以成为一级，也不应删除；它应成为“情报”的审核后消费产物。

## 15. RC1.2B Feature Freeze

### RC1_2B_FEATURE_FREEZE

禁止新增：业务表、业务 Model、业务 Service 体系、Crawler、Provider、AI、Search、推荐算法、匹配算法、新业务场景、新报告算法、新翻译 Provider、新数据治理逻辑。

只允许：信息架构调整、已有页面合并、已有入口重排、页面聚合、视觉系统统一、交互连续性优化、后台/产品视觉分层、空状态优化、桌面响应式适配。

如果实现时发现缺功能，只登记，不顺手实现。Reports 不得扩展为模板设计器；Club 不得新建第二套核心对象；Workspace 不得新建访问历史系统；工作台不得新建评分模型。

## 16. RC1.2B UI Principles

1. **INFORMATION_FIRST**：不增加 Hero、插画、装饰 KPI、大面积留白或无意义图标；视觉只服务信息理解、业务判断、下一步。
2. **DESKTOP_FIRST**：正式验收 1366 / 1440 / 1920；1024 不严重横溢、不遮挡按钮、表格可操作；不以手机端牺牲桌面密度。
3. **管理控制台三个可见信号**：顶部明确“管理控制台”；表格/筛选/批量/状态为主；中性灰/深灰低饱和视觉，与深蓝白色业务产品明显不同。
4. **统一组件**：Typography、Spacing、Container、Grid、Button、Badge、Tabs、Table、Form、Card、Empty State、Alert、Modal、Breadcrumb、Page Header 全站一致。
5. **避免 Card 泛滥**：只有数据边界明确时用 Card；优先 Section、List、Table、Inline Metadata、Divider。
6. **动作层级**：每页原则上最多 1 个 Primary；Secondary、Tertiary/Text、Danger 清楚分级。
7. **空状态**：不得出现 `null / None / — / [] / 空白卡 / 技术提示`。Relationship、Resource、FollowUp、Intelligence 分别使用业务语言。
8. **密度梯度**：工作台、情报详情、企业档案是最高信息密度核心页；后台允许更高表格密度；辅助工具可以更轻。
9. **测量**：人工记录 Golden Path Click Count、Guess Count、Completion Time、Context Switch Count、Navigation Depth；不开发 Telemetry。
10. **Before / After**：同分辨率保存九个指定页面截图；目标合并页以旧入口截图对照新合并页。

## 17. No-Code-Change Confirmation

- Production Code Diff：0。
- Route / Service / Model / Template / CSS / JS / Navigation Diff：0。
- DB Business Write：0；浏览器验收使用 `.tmp_rc1_2a_browser/audit.db` 隔离副本和临时账号。
- 正式业务核心计数审计前：Intelligence 31、People 44、Organizations 24、Projects 5、Subject Links 1、Resources 30、Match Candidates 0、Opportunities 11、FollowUps 4、Relationships 25、Relationship Evidence 25。
- 正式数据库审计前 SHA256：`FED798300231934D170F104C4A4F4676AE90103C9888D29F6A0CD97AA6C1A3FB`；`integrity_check=ok`。
- 正式数据库审计后 SHA256：`FED798300231934D170F104C4A4F4676AE90103C9888D29F6A0CD97AA6C1A3FB`；`integrity_check=ok`；上述 11 项核心计数逐项一致。
- 隔离数据库、临时账号、浏览器证据、可视化副本与临时日志已在提交前删除，残留为 0。
- 本阶段唯一 Git 内容为 `docs/audit/` 下四份审计产物。

## RC1.2B IMPLEMENTATION SCOPE

RC1.2B 只能处理以下列表。若发现遗漏，必须先报告，不得扩面。

### KEEP AS IS

- `/network/people` 与 `/network/organizations` 的 Canonical 查询能力（允许被组合成目录 tabs）。
- `/network/recommendations` 的现有确定性关系路径逻辑。
- `/relationships/{id}` 的 Canonical 证据追溯能力。
- `/search` 的既有跨对象查询逻辑。
- 数据层与 Service 层现有 Canonical 读写规则。

### RESTYLE

- `/intelligence` 情报列表。
- `/opportunities` 跟进列表。
- `/search` 搜索结果。
- `/collaboration/meetings` 作为跟进次级视图。
- 后台用户权限、完整性、运行记录典型表格页。

### RESTRUCTURE

- `/platform`：今天值得处理、我的待办、最近跟进与动作层级。
- `/intelligence/{id}`：事实、主体、上下文、证据、下一步。
- `/network`：DIRECT_TO_DIRECTORY，机构/人物目录为默认内容。
- `/network/entities/{type}/{external_id}`：档案摘要及 Intelligence/Relationship/Person/Resource/Opportunity/FollowUp/Evidence 聚合。
- `/resources/{id}`：来源、主体、Match 与 Opportunity 连续性。
- `/opportunities/{id}`：来源、判断、行动、结果、证据层级。
- `/club`：正式一级场景并分普通会员阅读与运营摘要。
- `/club/members`：普通目录读取与管理维护分层。
- `/club/events`：活动消费/报名与创建/审核/签到分层。
- `/reports`：报告阅读与生成审核分层，准确呈现固定聚合能力。
- `/reports/{id}`：恢复现有报告阅读页连续性，不新增报告算法。
- `/admin/platform`：建立后台视觉信号、任务分组和高密度布局。

### MERGE

- `/workspace` 的业务概览、待办、最近跟进 → `/platform`。
- `/workspace` 我的合作、`/collaboration`、`/collaboration/tasks` → 跟进结构。
- `/network/graph` → 企业与人物的关系次级视图。
- `/resources`、demand/supply、matching → 情报/主体/Club/机会的 Resource 上下文；保留必要落点。
- `/club/matches`、Club supply/demand → Canonical Resource/Match 场景视图。

### MOVE TO ADMIN

- `/collection`、Source、Source Discovery、Run、Item、Snapshot。
- `/processing/jobs`、blocks、candidates、review queue、publish、reprocess。
- `/network/governance`、candidate、merge、relationship governance。
- Report Job 创建、草稿编辑、submit/approve/archive/recovery。
- Club application/membership 管理、member import/binding、event create/review/check-in/feedback、`/club/operations`。
- Resource 创建、编辑、关闭、安全删除等管理动作。
- User/Permission/Identity/Integrity/Migration/Audit/System operation。

### HIDE

- `/workspace?tab=recent`，直到存在真实持久化来源。
- Signals 作为普通正式产品入口。
- Research/ResearchAgent/Provider 实验入口。
- 所有 processing/collection/candidate 工程术语的普通产品入口。
- 当前不能由真实参数与数据支撑的 subject/track/qbay 等报告类型宣传。

### DELETE CANDIDATE

- 重复 Canonical Opportunity 的 Legacy Lead 产品页。
- 重复现有 favorites/tags/priority subject 的历史 Watchlist 产品页。
- 只包装重复入口且合并后无独立用户价值的旧 Workspace/Collaboration Landing 模板。

`DELETE CANDIDATE` 仅是后续人工批准的退役清单；RC1.2A 和 RC1.2B 均不得据此删除数据表或历史恢复资产。
