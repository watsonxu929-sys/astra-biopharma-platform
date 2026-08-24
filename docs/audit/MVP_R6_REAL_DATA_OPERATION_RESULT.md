# MVP-R6 真实产业数据运营最终报告

## 1. 一句话结论

**PASS**。15 个真实来源完成质量分层，7 个受控采集周期稳定运行，5 条真实 Intelligence 正式发布，Q-BAY 完成一条真实 `Intelligence → Organization → Resource` 路径；真实 Chromium、Single Write、Canonical Read、Golden Path 与数据库安全门全部通过。

## 2. Source

最终状态为 ACTIVE 5 / DISABLED 5 / CANDIDATE 5。未追求 20～30 个数字目标，因为当前实测证明 15 个经过分层的来源优于继续增加未验证站点。详细清单见 `MVP_R6_SOURCE_REGISTRY.md` 与 `MVP_R6_SOURCE_RESULT.md`。

## 3. Collection

受控运行 110～116 共 7 周期：6 success、1 unchanged，抓取失败 0，形成 32 个 Collection Item。分布为 new 22、changed 4、duplicate 1、unchanged 5。运行 117 是对禁用候选政策来源的人工尝试，按既有安全规则返回 skipped，未产生 Item。

一次既有 worker 调用同时清空了 14 个历史 pending processing job；这些作业只处理正式库中原有真实采集记录，没有新增采集 Item。相关候选继续按人工审核状态保留，未自动发布或自动创建主体。

## 4. Intelligence

| ID | Source | Original URL | Title | Event Type | Subject Candidate | Confirmed | Why important | Next action |
| ---: | --- | --- | --- | --- | --- | --- | --- | --- |
| 29 | EMA News RSS | https://www.ema.europa.eu/en/news/meeting-highlights-committee-medicinal-products-human-use-chmp-20-23-july-2026 | CHMP 20-23 July 2026 meeting highlights | 监管审批 | 无既有正式主体 | 否 | 监管结论影响上市、注册与准入 | 核对获批主体、产品与适应症 |
| 30 | EMA News RSS | https://www.ema.europa.eu/en/news/new-leadership-team-appointments | New leadership team appointments | 人事变动 | 无既有正式主体 | 否 | 关键人员变化可能影响方向与合作窗口 | 查看人物并关联任职机构 |
| 31 | EMA News RSS | https://www.ema.europa.eu/en/news/ema-fast-tracks-review-medicine-metastatic-pancreatic-cancer | EMA fast tracks pancreatic cancer medicine review | 临床进展 | 无既有正式主体 | 否 | 临床/审评节点影响研发与合作节奏 | 核对研发主体和后续节点 |
| 32 | EMA News RSS | https://www.ema.europa.eu/en/news/meeting-highlights-pharmacovigilance-risk-assessment-committee-prac-6-9-july-2026 | PRAC 6-9 July 2026 meeting highlights | 监管审批 | 无既有正式主体 | 否 | 新安全信息直接影响用药与合规判断 | 核对产品主体与风险措施 |
| 33 | Q-BAY公开项目动态 | https://www.qianrenwuye.com/index.php?a=index&aid=193&c=View&m=home | QBAY（上海）张江药谷孵化器 | 企业扩张 | Q-BAY（上海）生物医药孵化器，高 | 是 | 新载体带来招商、空间、服务与合作需求 | 检查资源需求并创建供给 |

所有说明和动作由确定性事件规则生成；未调用 LLM。

## 5. Entity Candidate

复用现有 `v05g_subject_match_candidates` 和 Source Registry 主体绑定，在已有 people/organizations 中生成候选。候选只展示“可能涉及”、置信度和原因，不自动确认、不自动创建 Person/Organization。

## 6. User Confirmation

Q-BAY 候选经人工点击“确认关联”后写入既有 `core_intelligence_subject_links`；“忽略”路径写入既有 workflow audit，R6 隔离测试通过。正式库新增主体 link 1 条，没有新增人物、企业或项目。

## 7. Golden Path

真实路径：Intelligence 33 → Organization 1（Q-BAY（上海）生物医药孵化器）→ supply Resource 45（供给｜Q-BAY张江药谷孵化空间与公共实验平台）。没有可靠对手方，所以 Opportunity 新增为 0；测试 Golden Path 继续使用隔离数据库。

## 8. Q-BAY

Q-BAY 公开项目页通过统一 Collection → Processing → Intelligence → Entity 流程进入系统；机构详情可反向看到 Intelligence，Resource 自动继承来源情报与正式机构。没有 Q-BAY 专用 crawler、表或 feed。

## 9. KPI

| KPI | 结果 |
| --- | ---: |
| Collection Success Rate | 100%（7/7） |
| Extraction Success Rate | 100%（16/16） |
| Duplicate Rate | 18.75%（6/32） |
| Intelligence Publish Rate | 18.52%（5/27 人工审核候选） |
| Subject Candidate Coverage | 20%（1/5） |
| Confirmed Subject Coverage | 20%（1/5） |
| Intelligence → Resource | 1 |
| Intelligence → Opportunity | 0 |

## 10. Database

| 指标 | Baseline | Final |
| --- | ---: | ---: |
| Source | 6 | 15 |
| Monitoring Run | 106 | 114 |
| Collection Item | 403 | 435 |
| Intelligence | 25 | 30 |
| People | 44 | 44 |
| Organizations | 24 | 24 |
| Projects | 5 | 5 |
| Intelligence Subject Link | 0 | 1 |
| Resource | 29 | 30 |
| Match | 0 | 0 |
| Opportunity | 11 | 11 |
| FollowUp | 4 | 4 |
| Canonical Relationship | 25 | 25 |

基线 SHA256：`53A5C361A861A214C0BFA433EC66DC0831976C99D7E6765C981F5F722C74F6B7`。最终 SHA256：`4E9C0E72DE4E606669C8DEAE7EC4AC68A1553C1214C90D617C2A528DC4907256`。最终业务数据发生真实运营变化，因此文件 SHA256 合理变化；最终 `integrity_check=ok`。正式库中测试账号为 0。

## 11. Scheduler Safety

- pytest 前后：Monitoring Run 114、max run id 117；Collection Item 435、max item id 438，完全一致。
- 核心业务表行数前后完全一致；pytest 正式采集运行增量 0、正式采集记录增量 0。
- 正式文件哈希在测试后出现 SQLite 技术性变化，但逐表逻辑摘要与测试前验收副本比较，仅隔离副本自己的临时用户、登录审计和候选确认时间不同；正式业务表未被测试写入。
- 全量 pytest：15 failed / 3 errors，与 R5B 历史失败集合一致；新增历史失败 0。

## 12. Chromium

验收方式：项目现有 Playwright + 本机真实 Chromium `151.0.7922.34`，正式库的 OS 临时副本，真实鉴权和实际表单点击。应用内浏览器通道因宿主 Windows ACL helper 退出（`apply deny-read ACLs`）不可用，立即切换既有 Playwright，没有据此修改产品。

14 个步骤通过：登录、工作台、情报列表、情报详情、Subject Candidate、确认关联、企业详情、人物详情、Resource、Opportunity 列表/详情、Q-BAY、Collection 管理、全局搜索，以及 1366×768 / 1600×900 两个视口。

- Console Error: 0
- Page Error: 0
- Network Failure: 0
- 正式页面 404/500: 0
- 横向溢出: 0

首次 Chromium 验收发现 `/platform/search?q=Q-BAY` 因 Jinja 将字典 `items` 键解析成方法而返回 500；两行模板修复和回归测试后全量复验通过。截图证据位于 `docs/audit/evidence/mvp_r6/`。

## 13. Code Size

- 生产文件：9 个，`+415 / -32`，净增 383 LOC。
- 其中 Python 为 `+381 / -30`，模板为 `+34 / -2`。
- 新增业务表 0；新增 Model 0；新增 Service 文件/体系 0；新版本目录 0。
- 新增 R6 测试文件 1 个（5 个测试）；审计文档 5 份；截图 14 张。

## 14. Remaining Problems

1. 实体候选覆盖仅 20%，根因是现有正式主体库不含 EMA/BioNTech/Roche 相关机构；保持低覆盖比乱建主体更安全。
2. 企业官网列表页仍可能产生较多低质量候选；统一质量门已收紧，下一周期应观察噪声率后决定是否继续 ACTIVE。
3. 历史全量 pytest 保持 15 failed / 3 errors，均为既有 migration/runtime baseline/P4 rehearsal 债务；R6 不恢复 Legacy 行为。
4. Source 16 的人工运行因 disabled 状态安全跳过；它必须完成具体入口验证后才能转 ACTIVE。

## 验收条件

R6 定向测试 5/5，R2～R6 定向 52/52；Single Write、Canonical Read、Legacy Read/Write=0、Golden Path、动态 Playwright、数据库隔离和 Chromium 全部通过。R6 至此停止，不进入下一阶段。
