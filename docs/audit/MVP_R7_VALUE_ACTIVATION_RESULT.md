# MVP-R7 真实产业情报价值激活结果

## 1. 一句话结论

**PASS**

R7 用 7 个受控真实采集周期和全部 11 条非演示 Intelligence 完成价值、主体和行动性复核；新建 1 条真实政策 Intelligence，不制造 Organization、Person、Resource 或 Opportunity。系统现在明确区分产业事件与我们的业务机会，并在现有 Canonical 读写链上提供可解释主体候选、价值判断、相关上下文和真实下一步。

## 2. Real Intelligence

- 基线非演示真实 Intelligence：10 条，其中 5 条已发布、5 条待处理。
- R7 新增并发布：1 条（ID 34，上海生物医药外资高能级项目政策通知）。
- 最终非演示真实样本：11 条，其中 6 条已发布、5 条待处理。
- 人工评审：11/11；实际样本不足 20，因此按任务要求评审全部。
- 评审明细：[MVP_R7_INTELLIGENCE_REVIEW.csv](MVP_R7_INTELLIGENCE_REVIEW.csv)。
- 没有重复抓取旧内容来虚增正式 Intelligence；26 个重复/未变化采集 Item 没有再次发布产品。

7 个受控周期：

| Run | Source | 结果 | Collection | 重复/未变化 | 新情报 |
|---:|---|---|---:|---:|---:|
| 118 | 36氪 | unchanged | 1 | 1 | 0 |
| 119 | EMA News RSS | unchanged | 1 | 1 | 0 |
| 120 | BioNTech Newsroom | unchanged | 11 | 11 | 0 |
| 121 | Roche Media Releases | unchanged | 11 | 11 | 0 |
| 122 | Q-BAY公开项目动态 | unchanged | 1 | 1 | 0 |
| 123 | 上海生物医药外资项目政策 | success | 1 | 0 | 1 |
| 124 | EMA News RSS | unchanged | 1 | 1 | 0 |

采集失败 0，Extraction failure 0，精确重复再次生成正式 Intelligence 0。

## 3. Source

| 状态 | Before | After | 变化 |
|---|---:|---:|---|
| ACTIVE | 5 | 6 | Source 16 经具体正式政策页验证后 PROMOTE_ACTIVE |
| CANDIDATE | 5 | 4 | Source 14/15/17/18 KEEP_CANDIDATE |
| DISABLED | 5 | 5 | Source 1/2/5/6/12 保持停用 |

ACTIVE 仍控制在 5～10 个范围。5 个 DISABLED 来源的调度测试通过，未进入 Scheduler due 列表。本轮没有新增 Source，也没有一次性启用全部候选。

## 4. Quality

- Relevant Intelligence Rate：10 / 11 = **90.91%**。
- 唯一判为不相关的样本是兽药委员会新闻（ID 26），不属于当前人用生物医药运营重点。
- 政策标题优先级的确定性 Bug 已修复：标题明确为“政策/通知/措施”时，不再被正文中的“临床”等词误导。
- ID 32 的历史事件类型仍偏差（风险安全会议被归为审批），作为已知数据债务记录，本轮不改正式历史事实。
- 正式发布只复制已 approved/applied 的主体候选；被拒绝的主体名不再进入 Intelligence 正式字段。

## 5. Entity

- Subject Candidate Precision：2 / 2 = **100%**（以用户实际可见的候选计）。
- Subject Candidate Coverage：2 / 3 = **66.67%**（以有明确且可识别主体的已发布真实情报计）。
- ID 29 的 LIBTherapeutics 作为“发现新企业候选”展示名称、来源和上下文；创建/忽略进入既有 Canonical 审核入口，未自动创建 Organization。
- ID 33 通过来源登记主体正确关联 Q-BAY。
- ID 30 的两个人名仍是 1 个明确漏识别样本；新增的谨慎“英文人名 + 任职动作”规则只产生人工候选，不自动关联。
- Organization 匹配复用现有 name、standard_name、short_name 字段；同名 Person 保持 ambiguous，绝不自动确认。
- 标题片段、作者或机构噪声通过既有质量规则过滤，不向用户伪装成正式主体。

## 6. Actionability

- INFORMATION：不具备明确业务动作的参考信息。
- WATCH：产业事实值得跟踪，但尚无经用户确认的 Resource/Opportunity。
- ACTIONABLE：必须已有经用户确认的 Resource 或 Opportunity，不能因“发布新闻”自动成立。
- 系统标记 ACTIONABLE：1 条（ID 33）。
- 人工确认真正可行动：1 条。
- Actionable Precision：1 / 1 = **100%**。
- ID 34 政策事件为 WATCH，不因为政策利好自动制造资源需求或机会。

## 7. Business Conversion

- 已有真实路径保持：Intelligence 33 → Q-BAY Organization → Resource 45。
- R7 新增 Intelligence → Resource：0。
- R7 新增 Intelligence → Opportunity：0。
- R7 新增 Organization：0；Person：0。
- 行业中发生合作、审批、政策等事实只标记为 **产业事件**。
- 只有我们能够参与、推进或链接且有可执行动作时才标记为 **业务机会**。
- 本轮结论：**NO_REAL_OPPORTUNITY_FOUND**。这是准确判断，不是失败。

## 8. Q-BAY

- Intelligence 33 的 Q-BAY 主体关联与 Resource 45 保持完整。
- Q-BAY Organization 详情在真实 Chromium 中能够看到对应产业情报。
- Intelligence 33 能查询同主体已有 Resource 与其他相关上下文。
- 未建立 Q-BAY 第二套动态表或第二套主体模型。

## 9. Relationship Evidence

- R7 新增 Relationship Evidence：0。
- R7 新增 Canonical Relationship：0。
- 当前真实样本没有足够事实与人工确认来新增关系证据，未自动生成关系。

## 10. Matching

- 正式 Match 候选：0 → 0。
- R7 没有新增真实 Resource，因此没有新的真实匹配候选。
- 未修改 Matching 算法，也未制造对侧 Supply/Demand。

## 11. Dashboard

“今天值得处理”继续复用现有工作台，并增加真实指标：

- 高价值新情报；
- 待确认主体；
- ACTIONABLE 线索；
- 有 Match 候选的 Resource；
- 待跟进 Opportunity。

空值显示真实 0，不放虚假样例。既有 pending_subjects 与列表筛选口径保持一致，RC1.2 工作台验收回归通过。

## 12. Database

正式数据库：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`

| 对象 | Before | After | 解释 |
|---|---:|---:|---|
| Source | 15 | 15 | 无新增 |
| Monitoring Run | 114 | 121 | 7 个受控周期 |
| Collection Item | 435 | 462 | 27 个真实抓取结果；其中 26 个重复/未变化、1 个新政策页 |
| Intelligence | 30 | 31 | 新增真实政策 ID 34 |
| Intelligence Evidence | 6 | 7 | ID 34 官方页面证据 |
| Subject Link | 1 | 1 | 无未经确认关联 |
| Organization | 24 | 24 | 无虚假主体 |
| Person | 44 | 44 | 无虚假人物 |
| Project | 5 | 5 | 无变化 |
| Resource | 30 | 30 | 无虚假资源 |
| Match | 0 | 0 | 无变化 |
| Opportunity | 11 | 11 | 无虚假机会 |
| FollowUp | 4 | 4 | 无变化 |
| Canonical Relationship | 25 | 25 | 无变化 |

- Before SHA256：`4E9C0E72DE4E606669C8DEAE7EC4AC68A1553C1214C90D617C2A528DC4907256`
- After SHA256：`F8EB52A538F12E73EFAC47F989E04FD907E6864BF2D61A56A9D71550E6DDCE0D`
- After `PRAGMA integrity_check`：`ok`
- 操作前备份：`data/backups/app_mvp_r7_before_operation_20260824_170539.db`
- 备份 SHA256：`4E9C0E72DE4E606669C8DEAE7EC4AC68A1553C1214C90D617C2A528DC4907256`

SHA变化完全由上述真实受控运营写入解释。没有测试账号、浏览器验收数据或临时标记写入正式库。

## 13. Scheduler Safety

- R2～R7定向pytest前后：Monitoring Run 121、Collection Item 462，完全一致。
- 定向pytest前后正式库SHA256均为 `F8EB52A538F12E73EFAC47F989E04FD907E6864BF2D61A56A9D71550E6DDCE0D`。
- 全量pytest后上述计数、SHA和 integrity_check 再次一致。
- 自动测试使用OS临时测试数据库；正式 Source 运行增量 0，正式采集新增 0。
- 浏览器验收使用正式库只读克隆和临时 operator，验收实例、账号及临时目录均已清理。
- 8000端口最终无监听实例。

## 14. Tests

- R2 Single Write、R3 Canonical Read、R4 Golden Path、R5 OSS、R5B Scheduler Safety、R6 Data Quality、R7：**54 passed / 54**。
- R7新增验收：**7 passed / 7**。
- RC1.2工作台指标兼容回归：通过。
- 全量pytest：**15 failed / 3 errors**。
- 与R6历史集合一致：domain integrity/migration、旧P4、v06i runtime baseline、v06j migration chain、v06k P4 rehearsal contract。
- 新增历史失败：**0**。
- 未为测试数字恢复Legacy行为，也未处理本任务外历史债务。

## 15. Chromium

验收通道：项目已有 Playwright + 本机 Chromium（Computer Use 首次出现宿主 kernel/transport 失败后按规则立即切换）。

- Chromium：`151.0.7922.34`
- 视口：1366×768、1920×1080
- 实际页面：工作台、情报列表、情报详情、主体候选、Organization详情、Resource、Opportunity列表/详情、Q-BAY、Source管理、全局搜索。
- HTTP 404/500：0
- Console Error：0
- Page Error：0
- Network Error：0
- 横向溢出：0
- 用户可见 undefined/null：0
- 用户可见乱码/替换字符：0
- 新政策 Intelligence 可被全局搜索找到。
- 验收截图位于 [evidence/mvp_r7](evidence/mvp_r7/)；保留 11 张最终证据，冗余/误命名截图已清理。

## 16. AI Readiness

**NOT_READY**

真实样本只有 11 条，Actionable正样本1条，新的Resource signal和Match正样本均为0。最明确的问题是1条Person漏识别、1条历史事件误分类和多个标题/机构噪声候选。详细证据见 [MVP_R7_AI_READINESS.md](MVP_R7_AI_READINESS.md)。R7未接入任何AI、SDK或模型。

## 17. Remaining Problems

1. 非演示评审样本只有11条，仍低于20条建议规模。
2. 5条真实EMA记录仍为 pending_processing，需要后续真实运营逐条审核，不能自动发布。
3. ID 30仍记录为Person抽取漏识别；新规则只对后续候选生效，不改写历史正式数据。
4. ID 32历史事件类型偏差未在本轮重写。
5. 正式主体库对外部EMA/BioNTech/Roche生态覆盖有限；Coverage达标但样本小。
6. 本轮没有新的真实Resource、Opportunity、Match或Relationship Evidence正样本。
7. 全量pytest保留15 failed / 3 errors历史债务，本轮未扩大。

## 约束与代码规模

- 新增业务表：0
- 新增Model：0
- 新增Service体系：0（只修改既有Service）
- 新增Scheduler：0
- 新增版本目录：0
- 新增依赖：0
- Legacy读写：0
- Production Python：+195 / -13，净 **+182 LOC**
- 产品模板：+29 / -3，净 **+26 LOC**
- 没有第二套Entity、Intelligence、Recommendation或Lead体系。

## 回滚

- 代码：对单一提交 `MVP-R7 intelligence value activation` 执行标准 `git revert <R7提交SHA>`。
- 数据：先停止Web/Worker，再通过现有恢复流程使用操作前备份；恢复必须由用户明确确认，R7不自动覆盖正式数据库。
- Source 16：如需只回滚运营状态，使用现有Source管理入口将其恢复为 candidate/disabled，不改Schema。

## PASS条件复核

R7的25项PASS条件均满足：真实采集稳定、Source状态可控、Disabled不调度、重复不重复发布、全部真实样本已评审、候选可解释、同名不自动关联、新主体需人工确认、产业事件与业务机会分离、不制造Opportunity、详情回答“发生什么/涉及谁/为何关注/下一步”、Q-BAY关联可见、Canonical链保持、Legacy读写0、pytest不触发正式采集、数据库增量可解释、Chromium通过、无新表/Model/版本目录，且历史失败集合未扩大。
