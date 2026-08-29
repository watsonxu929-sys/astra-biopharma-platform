# MVP-RC1.2B 产品信息架构与全站 UI/UX 验收结果

## 1. PRODUCT_UI_ACCEPTANCE

**PRODUCT_UI_ACCEPTANCE=PASS**

| 人工验收问题 | 结论 | 证据 |
|---|---|---|
| 首页是否一眼知道今天该处理什么？ | YES | 首屏直接显示“今天值得处理”、我的待办和最近跟进，首个业务区块底部由 875px 提前到 300px。 |
| 情报页是否一眼知道发生了什么？ | YES | 详情按事实、主体、关注原因、证据和右侧业务上下文组织。 |
| 企业档案是否一页看懂“我与它的上下文”？ | YES | 同页聚合关系、联系人、情报、资源、跟进和合作证据。 |
| Club 是否重新成为清楚的业务场景？ | YES | “俱乐部”恢复一级入口；首页围绕会员、活动、供需与最近对接。 |
| FollowUp 是否明显是业务闭环终点？ | YES | “跟进”成为一级入口，列表直接显示对象、事项、下一步、负责人、计划时间和状态。 |
| 后台是否明显区别于业务产品？ | YES | 后台显示“管理控制台”和位置；使用中性色、高密度表格、状态与工具操作；提供返回业务产品路径。 |
| 是否减少了页面跳转？ | YES | Workspace 合并至工作台；Relationship、Resource 进入主体和情报上下文。 |
| 是否减少了无意义留白？ | YES | 核心页去除大卡片堆叠，容器扩展并采用紧凑列表/Section。 |
| 是否减少了工程术语？ | YES | 真实 Chromium 检查中，产品页用户可见工程术语为 0。 |
| 是否仍像一个拼接出来的后台系统？ | **NO** | 产品 Shell 固定五个业务入口，管理工具使用独立视觉和导航语义。 |

结论：RC1.2A 的产品信息架构已经落地；没有新增业务系统、业务表、模型、Service 体系、算法、Provider、Scheduler、Worker 或版本目录。

## 2. Product Before / After

同一隔离验收库、同一 Chromium、同一 1440×900 视口保留了 10 组前后证据：

- [Before 证据目录](evidence/mvp_rc1_2b/before/)
- [After 证据目录](evidence/mvp_rc1_2b/after/)
- 最终业务 Header 可见于 [工作台截图](evidence/mvp_rc1_2b/after/01_workbench.png)：工作台 / 情报 / 企业与人物 / 俱乐部 / 跟进。

| 页面 | Before | After |
|---|---|---|
| 工作台 | 两个大卡片，首个区块底部 875px | 无业务装饰卡片，首个区块底部 300px，首屏可见下一业务区块 |
| 情报详情 | 7 个卡片，页面高 2196px | 主内容+右侧上下文，0 个卡片，页面高 1310px |
| Organization | 8 个卡片，信息分散 | 0 个卡片，六类业务上下文同页 |
| 俱乐部 | 7 个大卡片，页面高 1743px | 0 个卡片，页面高 1065px，会员/活动/供需/对接连续 |
| 报告 | 3 个卡片、2 个表格，页面高 3512px | 0 个卡片，明确固定模板聚合器，空态页面不撑高 |
| 管理控制台 | 29 个入口卡片、页面高 9559px | 5 张高密度工具表，0 个入口卡片，页面高 1767px |

变化不是圆角、阴影或装饰升级；证据体现了信息结构、层级、密度、动作主次和跨页连续性的改变。

## 3. Final Navigation

正式业务产品一级导航严格为：工作台 / 情报 / 企业与人物 / 俱乐部 / 跟进。

右侧保留全局搜索、管理控制台和用户入口。关系、资源、报告、情报加工、审核发布、采集任务不再占用一级导航。真实浏览器在全部产品核心页只观察到这一种五项 Header，当前项高亮正确。

## 4. Workbench

`/platform` 成为唯一正式工作台，包含真实的“今天值得处理”、我的待办、最近跟进和低权重个人工具。排序继续调用既有 Golden Loop 规则，没有制造高优先级或 KPI。`/workspace` 保留兼容路由并 302 到 `/platform`；收藏合并为底部 Utility；最近访问从正式产品表面隐藏。

空状态为“今天暂时没有需要优先处理的产业动态”，并提供查看全部情报入口。“暂不处理”仍是用户级反馈，不删除 Intelligence，并保留恢复入口。

## 5. Intelligence

`/intelligence` 改为紧凑情报消费列表，优先展示标题、时间、类型、主体、摘要与业务上下文。采集、加工、审核入口已移出普通产品导航。

`/intelligence/{id}` 固定为：标题/时间/来源/类型、发生了什么、涉及主体、为什么值得关注、与我们的关系、相关资源、下一步行动、原文与证据。桌面采用事实主栏和业务上下文侧栏；未新增翻译 API，`AUTO_TRANSLATION_READY=false` 保持不变。

## 6. Enterprise & People

`/network` 已执行 DIRECT_TO_DIRECTORY，进入即显示企业与机构目录，不再显示低价值统计 Landing。`/network/organizations` 兼容重定向至 `/network`；人物保留为二级目录。目录使用现有 Canonical 数据聚合 Q-BAY 身份、动态、联系人、Relationship、Resource 和 FollowUp 摘要，不展示空字段。

## 7. Organization 360

Organization 详情在一页内展示概览、我们的关系、关键联系人、最近产业动态、资源/需求、正在跟进和历史合作证据。缺失维度使用“当前未发现直接关系”“暂无相关资源”“暂无已记录联系人”“暂无进行中的跟进”等业务空态。“建立/查看跟进”保持为业务动作，主体治理明确降为管理员工具。

## 8. Q-BAY Club

“俱乐部”恢复为正式一级入口，页面标题为“Q-BAY俱乐部”。首页只使用真实会员、活动、Resource 和 FollowUp 数据，连续展示近期活动、会员动态、供需与匹配、最近对接。会员、活动、供需与匹配可由俱乐部二级导航自然找到；活动运营和会员导入只从管理控制台进入。

Club 仍只是 Scenario UX，继续复用 Organization、Person、Resource、Match、Opportunity、FollowUp 和 Relationship，没有恢复 Legacy Core。

## 9. FollowUp

`/opportunities` 重构为“跟进”一级页，按待处理、进行中、已完成的现有状态语义展示对象、事项、下一步、负责人、计划时间和状态。详情继续使用现有 Opportunity/FollowUp 数据；没有新增项目管理、Lead 或 CRM 能力。

## 10. Reports

报告位于“情报 → 报告”，文案明确说明它是“固定模板聚合器”：选择现有固定报告类型和现有参数后生成，不暗示 AI、自由设计或自动研究。`/reports/1` 已在真实 Chromium 中返回 200。生成、审核和编辑被明确标识为管理员操作。

## 11. Admin Console

管理后台同时具备三类区分信号：标题和浏览器标题明确显示“管理控制台”及当前位置；管理首页使用 5 张高密度工具表，情报加工以表格、状态、紧凑表单和错误反馈为主；中性色、弱品牌装饰、工具化布局与业务产品视觉分离，并提供“返回业务产品”。普通业务 Header 不再展示情报加工、审核发布或采集任务。

## 12. UI Design System

`app/static/platform.css` 集中建立并复用 Typography、Spacing、Color、Border、Radius、Shadow、Container、Grid、Button、Badge、Tabs、Table、Form、Card、Empty State、Alert、Breadcrumb 和 Page Header 规则。基础间距使用 4/8/12/16/24/32；业务容器按可用空间扩展至 1440px；核心正文为 14px，标题层级统一。

没有引入 UI 框架；主要变更集中于模板、共享 CSS 和少量 presentation route。

## 13. Information Density

| 页面 | 首个核心区块底部 | 页面总高 | 结论 |
|---|---:|---:|---|
| 工作台 | 300px | 1248px | 首屏完整显示摘要并看到“今天值得处理” |
| 情报详情 | 499px | 1310px | 首屏完整显示事实摘要并看到后续主体/上下文 |
| Organization | 387px | 1573px | 首屏完整显示身份与关系摘要并看到后续上下文 |

核心产品页大卡片数量明显下降；表格只用于后台和天然二维信息。1024px 下页面无严重横向溢出、导航覆盖、按钮遮挡或正文截断。

## 14. Golden Path Metrics

| 指标 | RC1 基线 | RC1.2B |
|---|---:|---:|
| Click Count | 4 | 4 |
| Guess Count | 0 | 0 |
| Completion Time | 未记录 | 3.22s |
| Context Switch Count | 未记录 | 2 |
| Navigation Depth | 未记录 | 2 |

真实 Chromium 在隔离数据库中完成“工作台 → 情报 → Organization → FollowUp → 工作台”。创建操作只发生在隔离验收库；随后验收库已从正式库重新建立，正式数据未写入。

## 15. Navigation Metrics

- Golden Path：4 次点击，Guess Count 0，成功回到工作台。
- Club Path：俱乐部 → 会员 Organization → Resource → 跟进，4 次点击，Guess Count 0，Context Switch 0。
- `/workspace`：302 至 `/platform`，不再形成第二套工作台。
- viewer 真实浏览器后端写入检查：FollowUp 403、报告编辑 403、俱乐部活动创建 403。

## 16. RC1.2A Decision Implementation

下表逐行复核 RC1.2A 决策矩阵。DELETE_CANDIDATE 表示已从正式产品表面隐藏并保留历史兼容，本轮未物理删除底层能力。

| RC1.2A 页面/入口 | Route | 决策 | RC1.2B |
|---|---|---|---|
| 工作台 / 工作台首页 | `/platform` | RESTRUCTURE | IMPLEMENTED |
| 工作台 / 今天值得处理 | `/platform` | KEEP | IMPLEMENTED |
| 工作台 / 今天已忽略 | `/platform` | KEEP | IMPLEMENTED |
| 工作台 / 我的工作区 | `/workspace` | MERGE | IMPLEMENTED |
| 工作台 / 我的待办 | `/workspace?tab=todos` | MERGE | IMPLEMENTED |
| 工作台 / 最近跟进 | `/workspace?tab=followups` | MERGE | IMPLEMENTED |
| 工作台 / 我的收藏 | `/workspace?tab=favorites` | MOVE_TO_UTILITY | IMPLEMENTED |
| 工作台 / 最近访问 | `/workspace?tab=recent` | HIDE | IMPLEMENTED |
| 工作台 / 待处理联系 | `/workspace` | MERGE | IMPLEMENTED |
| 工作台 / 我的合作 | `/workspace` | MERGE | IMPLEMENTED |
| 情报 / 情报首页 | `/intelligence` | RESTRUCTURE | IMPLEMENTED |
| 情报 / 情报详情 | `/intelligence/{id}` | RESTRUCTURE | IMPLEMENTED |
| 情报 / 订阅 | `/subscriptions` | MOVE_TO_UTILITY | IMPLEMENTED |
| 情报 / 采集与数据源 | `/collection` | MOVE_TO_ADMIN | IMPLEMENTED |
| 情报 / 来源管理 | `/collection/sources` | MOVE_TO_ADMIN | IMPLEMENTED |
| 情报 / 采集运行 | `/collection/runs` | MOVE_TO_ADMIN | IMPLEMENTED |
| 情报 / 情报加工 | `/processing/jobs` | MOVE_TO_ADMIN | IMPLEMENTED |
| 情报 / 加工候选 | `/processing/candidates` | MOVE_TO_ADMIN | IMPLEMENTED |
| 情报 / 审核发布 | `/processing/review-queue` | MOVE_TO_ADMIN | IMPLEMENTED |
| 情报 / 报告中心 | `/reports` | RESTRUCTURE | IMPLEMENTED |
| 情报 / 报告详情 | `/reports/{id}` | RESTRUCTURE | IMPLEMENTED |
| 情报 / 报告生成 | `/reports` | MOVE_TO_ADMIN | IMPLEMENTED |
| 情报 / 产业信号 | `/signals` | HIDE | IMPLEMENTED |
| 情报 / Research | `/research` | HIDE | IMPLEMENTED |
| 情报 / Watchlists | `/watchlists` | DELETE_CANDIDATE | IMPLEMENTED |
| 企业与人物 / 关系 Landing | `/network` | RESTRUCTURE | IMPLEMENTED |
| 企业与人物 / 人物 | `/network/people` | KEEP | IMPLEMENTED |
| 企业与人物 / 企业/机构 | `/network/organizations` | KEEP | IMPLEMENTED |
| 企业与人物 / 主体档案·身份 | `/network/entities/{type}/{external_id}` | RESTRUCTURE | IMPLEMENTED |
| 企业与人物 / 主体档案·关系 | `/network/entities/{type}/{external_id}` | RESTRUCTURE | IMPLEMENTED |
| 企业与人物 / 主体档案·联系人 | `/network/entities/{type}/{external_id}` | KEEP | IMPLEMENTED |
| 企业与人物 / 主体档案·情报 | `/network/entities/{type}/{external_id}` | RESTRUCTURE | IMPLEMENTED |
| 企业与人物 / 主体档案·资源 | `/network/entities/{type}/{external_id}` | RESTRUCTURE | IMPLEMENTED |
| 企业与人物 / 主体档案·跟进 | `/network/entities/{type}/{external_id}` | RESTRUCTURE | IMPLEMENTED |
| 企业与人物 / 主体档案·证据 | `/network/entities/{type}/{external_id}` | KEEP | IMPLEMENTED |
| 企业与人物 / 关系网络 | `/network/graph` | MERGE | IMPLEMENTED |
| 企业与人物 / 人脉推荐 | `/network/recommendations` | KEEP | IMPLEMENTED |
| 企业与人物 / 主体治理 | `/network/governance` | MOVE_TO_ADMIN | IMPLEMENTED |
| 上下文 / 资源市场 | `/resources` | MERGE | IMPLEMENTED |
| 上下文 / 需求 | `/resources?type=demand` | KEEP | IMPLEMENTED |
| 上下文 / 供给 | `/resources?type=supply` | KEEP | IMPLEMENTED |
| 上下文 / Resource 详情 | `/resources/{id}` | RESTRUCTURE | IMPLEMENTED |
| 上下文 / 匹配 | `/resources/matching` | MERGE | IMPLEMENTED |
| 上下文 / 资源维护 | `/resources/new|edit` | MOVE_TO_ADMIN | IMPLEMENTED |
| 跟进 / 合作机会 | `/opportunities` | RESTRUCTURE | IMPLEMENTED |
| 跟进 / 机会详情 | `/opportunities/{id}` | RESTRUCTURE | IMPLEMENTED |
| 跟进 / 协作首页 | `/collaboration` | MERGE | IMPLEMENTED |
| 跟进 / 行动任务 | `/collaboration/tasks` | MERGE | IMPLEMENTED |
| 跟进 / 会议 | `/collaboration/meetings` | KEEP | IMPLEMENTED |
| 跟进 / Relationship 详情 | `/relationships/{id}` | KEEP | IMPLEMENTED |
| 跟进 / Legacy Lead | `/collaboration/leads` | DELETE_CANDIDATE | IMPLEMENTED |
| 俱乐部 / 俱乐部首页 | `/club` | RESTRUCTURE | IMPLEMENTED |
| 俱乐部 / 会员 | `/club/members` | RESTRUCTURE | IMPLEMENTED |
| 俱乐部 / 活动 | `/club/events` | RESTRUCTURE | IMPLEMENTED |
| 俱乐部 / 活动运营 | `/club/events/create|{id}/status|checkin` | MOVE_TO_ADMIN | IMPLEMENTED |
| 俱乐部 / 会员申请与账户 | `/club/apply|/member/*` | RESTRUCTURE | IMPLEMENTED |
| 俱乐部 / 俱乐部供需 | `/club/matches?tab=my` | MERGE | IMPLEMENTED |
| 俱乐部 / 俱乐部匹配 | `/club/matches` | MERGE | IMPLEMENTED |
| 俱乐部 / 俱乐部运营 | `/club/operations` | MOVE_TO_ADMIN | IMPLEMENTED |
| 俱乐部 / 会员导入 | `/club/member-import` | MOVE_TO_ADMIN | IMPLEMENTED |
| 工具 / 全局搜索 | `/search` | KEEP | IMPLEMENTED |
| 管理控制台 / 管理首页 | `/admin/platform` | RESTRUCTURE | IMPLEMENTED |
| 管理控制台 / 用户权限 | `/system/users|permissions` | KEEP | IMPLEMENTED |
| 管理控制台 / 数据完整性 | `/admin/integrity` | KEEP | IMPLEMENTED |

NOT_IMPLEMENTED：0。

## 17. Existing Bug Fixes

`/reports/1 -> 422` 的 Root Cause 是 `/reports/{report_id:int}` 装饰器被错误叠加到 `intelligence_product_detail`，使 FastAPI 按错误签名要求 `product_id`。最小修复将该装饰器绑定回 `report_detail`，并修正四个把 `{report_id:int}` 当作 Python f-string 表达式的重定向。

同时保留了 Resource 详情原有的推荐理由、确认匹配和暂不匹配操作；没有修改 Match 算法。

## 18. Chromium

- 验收方式：项目现有 Playwright + 本机真实 Chromium；没有新增测试框架或下载浏览器。
- 浏览器版本：Chromium 151.0.7922.34。
- 视口：1024×768、1366×768、1440×900、1920×1080。
- 页面/视口组合：63。
- Unexpected 404/500：0。
- Console Error：0。
- Page Error：0。
- Network Failure：0。
- 严重横向溢出：0。
- 乱码、用户可见 undefined/null：0。
- 产品页工程术语：0。
- `/reports/1`：200。

正式 After 截图共 10 张，覆盖工作台、情报列表、情报详情、企业与人物、Organization、俱乐部、跟进、报告、情报加工和管理控制台。

## 19. Tests

- RC1.2B 定向测试与受影响既有测试：28 passed。
- 最终全量 pytest：15 failed / 3 errors / 1 skipped。
- RC1.2A 前基线：15 failed / 3 errors / 1 skipped。
- 新增失败：0；新增错误：0；历史失败集合未扩大。

既有债务仍集中于历史 migration 幂等、v0.6I runtime 假设、旧 P4 演练和 v0.6K contract fixture；本轮没有为改善数字恢复 Legacy 行为。

## 20. Database

正式数据库：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`

- Before SHA256：`FED798300231934D170F104C4A4F4676AE90103C9888D29F6A0CD97AA6C1A3FB`
- After SHA256：`FED798300231934D170F104C4A4F4676AE90103C9888D29F6A0CD97AA6C1A3FB`
- integrity_check：ok

| 核心业务对象 | Before | After |
|---|---:|---:|
| Intelligence | 31 | 31 |
| People | 44 | 44 |
| Organizations | 24 | 24 |
| Projects | 5 | 5 |
| Subject Links | 1 | 1 |
| Resources | 30 | 30 |
| Match Candidates | 0 | 0 |
| Opportunities | 11 | 11 |
| FollowUps | 4 | 4 |
| Relationships | 25 | 25 |
| Relationship Evidence | 25 | 25 |

所有自动验收写操作均使用 `.tmp_rc1_2b/audit.db`；正式库不是测试写目标。隔离库中的临时账号、Opportunity、FollowUp 和时间线记录已通过重建隔离副本清除，并在提交前删除整个临时目录。

代码规模（提交前暂存统计口径）：

- Production Python：+61 / -95；净 -34。
- Templates：+389 / -894；净 -505。
- Shared CSS：+293 / -0。
- Tests：既有测试 +24 / -15，新增 RC1.2B 测试 65 行。
- Audit/docs：本报告及 20 张正式 Before/After PNG 证据；PNG 合计 3,732,955 bytes。
- 新增业务表/Model/Service/Scheduler/版本目录/大型依赖：均为 0。

修改范围：5 个 presentation/navigation Python 文件、14 个模板、1 个共享 CSS、6 个测试文件、本报告及正式证据目录。

## 21. Remaining Problems

1. 历史 pytest 债务仍为 15 failed / 3 errors / 1 skipped，本轮按冻结要求不处理。
2. 自动翻译仍未接入，`AUTO_TRANSLATION_READY=false`；英文原文继续按 RC1 既有策略显示。
3. Watchlists 和 Legacy Lead 仅从正式产品表面隐藏并标记删除候选，没有物理删除底层兼容能力。
4. 本轮没有新增报告模板设计器、搜索算法、AI、推荐/匹配算法或任何业务模型；这些都不属于 RC1.2B。

所有 RC1.2B 直接 FAIL 条件均未触发。最终结论：

**MVP-RC1.2B PASS**
