# MVP-R7.2 Opportunity Discovery Result

记录日期：2026-08-28（Asia/Shanghai）

## 1. 一句话结论

**PASS — `NO_REAL_OPPORTUNITY_FOUND`。** 系统已围绕 13 个真实 Priority Subject 展示可解释的主体、Resource、Relationship 与下一步上下文；没有把已发生的行业事件、融资、合作或扩张直接制造成我们的 Opportunity。

## 2. Priority Subject Universe

- 真实、可解释主体：13（Organization 8，Person 5）。
- P1：4；P2：5；P3：4；P4：0；P5：0。
- 集合只来自现有 Q-BAY 会员、Canonical Resource、已审核 Relationship、非 demo Opportunity 历史和现有关注能力。
- 排除 10 个 demo Organization、inactive 错误标题主体和没有业务依据的泛行业主体。
- 逐项证据见 `docs/audit/MVP_R7_2_PRIORITY_SUBJECTS.md`。

## 3. Source Coverage

- 13 个 Priority Subject 中仅 1 个已有主体级 ACTIVE Source：Q-BAY（上海）生物医药孵化器。
- 其余 12 个主体的 Canonical 档案没有可验证官网字段；没有根据模糊名称猜测官网，也没有自动激活 Candidate。
- R7.1 Source Discovery 的边界继续有效：发现结果只能成为 Candidate，必须由管理员确认后 ACTIVE。
- 本轮没有盲目增加 ACTIVE Source，也没有修改 R7.1 的 Source CRUD / Discovery / Import 行为。

## 4. Real Intelligence Sample

- 累计真实人工评审样本：11；其中 published 非 demo 6，pending processing 5。
- 7 个受控真实采集周期没有产生可发布新内容，因此没有重复旧新闻、复制 Intelligence 或发布低质量内容凑到 30。
- 人工评审明细：`docs/audit/MVP_R7_2_INTELLIGENCE_REVIEW.csv`。
- 已复核至少 5 个高价值 Industry Event 案例：监管会议、外部合作、审批、临床、风险安全、Q-BAY 扩张和政策；全部正确区分 Industry Event 与 Our Opportunity。

## 5. Relevant Intelligence Rate

- Relevant：10 / 11。
- **Relevant Intelligence Rate：90.91%**。
- 唯一不相关样本为兽药委员会信息，超出当前人用生物医药运营重点。

## 6. Priority Subject Hit Rate

- Priority Subject 相关 Intelligence：1 / 11。
- **Priority Subject Hit Rate：9.09%**。
- 命中项为 Intelligence 33 → Q-BAY（上海）生物医药孵化器。
- 该指标仍低，说明当前 Source 组合尚未充分围绕业务网络；这是下一轮真实运营的首要瓶颈，不以伪造主体或新闻掩盖。

## 7. Subject Candidate Precision

- 人工确认的正向候选没有发现误匹配。
- **Subject Candidate Precision：100%**，保持高于 95% 底线。
- Organization 名称规则新增公司后缀、空格、标点和大小写规范化；只有唯一精确规范化匹配才确认。
- 已存在多个规范化命中时返回 ambiguous；RapidFuzz 仅在 ≥0.97 且领先第二候选 ≥0.03 时给出人工候选，不降低阈值。

## 8. Subject Candidate Coverage

- 当前 11 条真实样本上的可评审 Coverage 仍为 R7 的 **66.67%**，没有虚报样本内提升。
- 新规则补齐的是 Organization 中文全称/法定后缀/空格标点/高相似候选能力；本轮 7 个采集周期没有产生新的真实别名样本可用于提高分子。
- 现存漏识别主要为英文 Person 与机构实体（例如 Ivo Claassen、Melanie Carr、EMA/EISMEA），属于实体抽取 Coverage，不允许用降低阈值解决。

## 9. Actionability

- ACTIONABLE_SIGNAL：1 / 11。
- 人工判定的 Actionable 命中正确：1 / 1。
- **Actionable Precision：100%**。
- 其他融资、审批、临床、合作、政策事件均保持 LEVEL 1，不因 event_type 自动升级。

## 10. Resource Signals

- POSSIBLE_SUPPLY：1；POSSIBLE_DEMAND：0；NO_RESOURCE_SIGNAL：10。
- **Resource Signal Precision：1 / 1 = 100%**。
- Intelligence 33 已有用户确认的 Canonical Resource 45 及主体相关资源，因此显示 POSSIBLE_SUPPLY。
- 页面同时明确显示“公开信息尚未确认具体采购、合作或供给意向”，不会自动创建 Resource。
- 正式 Resource 数量保持 30；本轮制造虚假 Resource：0。

## 11. Relationship Context

- 修正了既有查询把 Canonical Relationship 的 external ID 当内部数值 ID 使用的问题。
- Intelligence 33 现在可显示 Q-BAY 的已审核、current Relationship、相关联系人和 Evidence 数量。
- 查询仅使用现有 `p3_canonical_relationships` / `p3_relationship_evidence`；没有引入图工具或第二套关系模型。

## 12. Next Action Utility

- 存在合理下一步的样本：2；有用下一步：2。
- **Next Action Utility：100%（2 / 2）**。
- Intelligence 29：确认 LIBTherapeutics 新主体候选。
- Intelligence 33：查看现有 Resource 并检查 Match。
- 其余样本明确“暂不处理”，不生成 Agent 式自动动作。

## 13. Opportunity Discovery

**`NO_REAL_OPPORTUNITY_FOUND`**。

- 严格顺序已实现：Intelligence → Subject → Resource / Relationship Context → 五项 Qualification → Human Confirmation → Canonical Opportunity。
- 准入条件：明确主体、未解决需求/合作信号、可调用 Resource/Relationship、具体下一步、时间有效性，必须全部成立。
- 规则复核发现单独关键词“需求”过宽，已收紧为“采购需求 / 合作需求 / 资源需求 / 需求尚未”等事实短语。
- Intelligence 33 有主体、资源、关系、下一步和时效，但公开信息没有确认尚未解决的需求，因此 **不具备创建 Opportunity 的条件**。
- 现有 Opportunity 11 条均为历史 demo/manual；本轮正式 Opportunity 新增 0，虚假 Opportunity 新增 0。
- Intelligence → Opportunity：0 / 11 = 0%；该数值允许且诚实。

## 14. Q-BAY Value

- Q-BAY 作为第一真实试验场已可从 Intelligence 33 反向看到主体、3 项相关 Resource、1 条已审核 Relationship 及 Evidence。
- 对运营问题“要不要联系这家公司”的当前回答是：先查看 Resource / Match，确认是否存在尚未解决的合作需求；现有公开项目事实本身不足以联系并创建商机。
- Intelligence → Resource：1 / 11 = 9.09%。

## 15. Source ROI

| ACTIVE Source | runs | success | new collection | duplicate | Intelligence | Relevant | Priority Hit | Actionable | Resource Signal | Opportunity Signal |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 36氪 | 4 | 3 | 1 | 2 | 0 | 0 | 0 | 0 | 0 | 0 |
| EMA News RSS | 57 | 52 | 13 | 192 | 9 | 8 | 0 | 0 | 0 | 0 |
| BioNTech Newsroom | 4 | 4 | 8 | 36 | 0 | 0 | 0 | 0 | 0 | 0 |
| Roche Media Releases | 4 | 4 | 10 | 33 | 0 | 0 | 0 | 0 | 0 | 0 |
| Q-BAY公开项目动态 | 5 | 5 | 1 | 4 | 1 | 1 | 1 | 1 | 1 | 0 |
| 上海生物医药外资项目政策 | 4 | 3 | 1 | 2 | 1 | 1 | 0 | 0 | 0 | 0 |

- 本轮 7 周期结果：fetched 27，new 0，duplicate/unchanged 26，changed 1，failed 0，queued 0。
- 保持 ACTIVE：Q-BAY（唯一 Priority/Actionable 命中）、EMA（有监管相关价值）、上海政策（有区域政策价值）。
- 观察并建议管理员评估降为 Candidate：36氪、BioNTech、Roche；当前只有 4 次累计运行，证据不足以在本轮自动停用，但它们仍为 0 Priority Hit / 0 Actionable，且 list page 噪声较高。

## 16. AI Readiness

**NOT_READY**。

- 真实人工评审样本只有 11，未达到 ≥30。
- 复杂人工纠正/规则失败不足 10，Resource Signal / Actionability 复杂判断也不足 10。
- 当前主要瓶颈仍是 Source 覆盖、主体档案官网缺失、别名与 Person/机构实体 Coverage，不足以准入 AI Assisted Pilot。
- 不推荐 R8，不选择 AI 问题。

## 17. OSS Need Check

| OSS | 结论 | 依据 |
|---|---|---|
| Meilisearch | NOT_NEEDED | 11 条样本和 13 个 Priority Subject 不构成搜索性能瓶颈。 |
| Splink | NOT_NEEDED | 当前瓶颈是官网/别名与人工确认，不是大规模概率实体消歧。 |
| NetworkX | NOT_NEEDED | 现有 Canonical Relationship 已能回答“认识谁”，无复杂图计算瓶颈。 |
| changedetection.io | NOT_NEEDED | 7 周期的现有 hash/change 机制已正确识别 26 个重复/未变与 1 个 changed；当前瓶颈是业务命中率。 |

本轮未安装任何 OSS。

## 18. Database

- 正式路径：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`。
- Baseline SHA256：`270F12A7CB8DEED20D1E40AFCC5354AA6CA0D2AD80F714701A0F4F8470D42F2D`。
- 7 个真实周期后 SHA256：`FED66707481C994A2BF012AA95DC1F9D3B625F5583A36132D56F16CF355410A2`。
- SHA 变化只来自 7 条真实 Monitoring Run 与 27 条可追溯 Collection Item/Snapshot 运行记录；核心业务计数前后完全一致。
- 最终 `integrity_check=ok`。
- 测试前后 SHA 均为 `FED667...10A2`；pytest 期间正式 Source 运行新增 0、正式采集新增 0、核心计数变化 0。
- 保护备份：`data/backups/MVP_R7_2_PREWRITE_20260828.db`，SHA256 `78481DB2F65A946075A309FA4B35FD641FF646FA39BC8EE1D931B24AA6B99744`，`integrity_check=ok`（忽略交付，不提交）。
- 浏览器使用 OS 临时正式库克隆与临时 operator/viewer；实例、账号、数据库和日志均已删除。

## 19. Tests

- R7.2 定向规则：6 / 6 PASS。
- R2–R7.2 联合回归：62 / 62 PASS。
- R2 Single Write、R3 Canonical Read、R4 Golden Path、R5 OSS、R5B Scheduler Safety、R6 Data Quality、R7 Value Activation、R7.1 Admin Operability 均通过。
- 全量 pytest：**15 failed / 3 errors / 1 skipped**，与既有历史债务数量和失败文件集合一致；新增历史失败 0。
- 历史失败仍集中于旧 migration/idempotency、v06i runtime baseline、v06j migration chain、P4/v06k 旧契约，不在本轮清理。

## 20. Chromium

- 方式：项目现有 Playwright + 真实 Chromium；内置浏览器控制第一次连接被 Windows orchestrator helper 终止，作为 tooling failure 记录后未重试业务代码。
- Chromium：151.0.7922.34；viewport：1366×768、1600×900。
- 实际页面：工作台、Intelligence 列表、Priority Intelligence 详情、Subject Candidate、Organization 详情、Resource 列表/详情、Opportunity 列表/详情、Q-BAY、Source 管理、全局搜索，共 12 条正式路径；另以 viewer 执行关键写权限探针。
- 页面非 200：0；404/500：0；Console Error：0；Page Error：0；Network Failure：0；横向溢出：0；用户可见 undefined/null：0。
- viewer 写请求：403（真实浏览器 fetch，预期）。
- 证据：`docs/audit/evidence/mvp_r7_2/browser_acceptance.json` 及 13 张页面/权限截图。

## 21. Remaining Problems

1. Priority Subject Hit Rate 仅 9.09%，真实 Source 覆盖只有 1 / 13；下一步应先由管理员补齐可信官网并确认 Candidate，而不是接入 AI。
2. Subject Candidate Coverage 的真实样本指标仍为 66.67%；英文 Person/机构实体仍有漏识别，需要更多人工样本后再判断是否达到 AI 准入门。
3. 两个 P1 会员 Organization 名称质量不足，应先做人工主体治理；本轮不覆盖正式主体字段。
4. BioNTech、Roche、36氪当前业务命中率低，应继续观察并由管理员决定降级，不能仅因技术采集成功率保留。
5. 历史 15 failed / 3 errors 保持原债务集合，本轮未扩大也未清理。

## Delivery constraints and rollback

- 新增业务表 0；新增 Model 0；新增 Service 体系 0；新增 Scheduler 0；新增版本目录 0；新增大型依赖 0。
- Production Python 净新增 352 LOC，低于 400 目标。
- Legacy Read / Write 新增 0；生产 LLM / OSS 接入 0。
- 代码回滚：在确认最终提交后执行 `git revert <MVP-R7.2 commit>`。
- 数据回滚：7 个周期均为真实、可追溯运行记录，默认保留；如确需数据库恢复，必须先停服并经用户明确确认后使用已验证的 PREWRITE 备份，不得在日常回滚中直接覆盖正式库。

最终判定：**PASS**。
