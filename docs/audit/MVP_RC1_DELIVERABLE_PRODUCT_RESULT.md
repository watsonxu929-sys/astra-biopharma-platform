# MVP-RC1 可交付初版产品验收结果

## 1. PRODUCT ACCEPTANCE

**PRODUCT_ACCEPTANCE=PASS**

产品已收敛到一条可理解、可操作、可回流的正式主线：用户登录后先处理“今天值得处理”的产业动态，在一页内看懂事件、主体、关系和资源，再由人工确认建立 Canonical FollowUp；新待办立即回到工作台，Web 重启后仍存在。

八个产品问题的答案：

1. 产品核心是把优先产业情报转化为有依据、可追溯的人工跟进，而不是展示采集与候选管线。
2. 用户登录后第一件事是查看工作台“今天值得处理”，打开优先级最高且仍在 30 天有效窗口内的动态。
3. 原文是证据层，中文标题与摘要是阅读层；本轮无自动 Provider，英文验收样本使用隔离库内明确标记的人工中文副本，原文始终保留。
4. 情报详情“涉及谁”展示 Canonical 主体或原始名称；不可靠时不猜类型，EMA/EISMEA 不再被当成 Project。
5. “与我们的关系”及 Organization 360 的“我们的关系、关键联系人、历史合作证据”直接回答“我认识谁”。
6. 情报“相关资源”和 Organization 360 的“资源 / 需求”直接展示已有 Canonical Resource；没有时明确显示“暂无相关资源”。
7. operator 在情报详情填写事项、原因、下一步和计划时间后建立现有 Canonical FollowUp；来源 Intelligence 通过现有 Opportunity 容器可追溯，未新建 CRM 或表。
8. 与任务前相比，黄金主线少跨 2 个独立页面（关系、资源改为上下文聚合），普通用户少看 8 组候选/加工/技术字段，少做 3 项“去哪里找主体、关系、资源”的检索判断；历史基线没有可比的 Guess Count，故不伪造百分比，当前真实验收 Guess Count 为 0。

## 2. Golden User Path

真实 Chromium 路径：`/login` → `/platform` → 今天值得处理 → Intelligence 33 → Organization `ORG-20260626-000001` → 返回情报 → 建立 FollowUp → 返回工作台 → 我的待办看到新 FollowUp。

- operator 全程未进入管理控制台、Source、Collection 或候选审核。
- FollowUp 创建成功后显示“跟进已创建”“查看跟进”“返回工作台”。
- 工作台刷新后立即显示新事项“核实该产业动态对当前业务的影响”。
- Web 停止并重新启动后，该事项仍可见，`restart_persistence.json` 为 PASS。
- viewer 页面不显示写按钮，直接向同一写端点发请求仍返回 403。

## 3. Product Core

唯一正式产品核心是：**Priority Intelligence → 中文业务阅读 → Subject / Relationship / Resource Context → Human Decision → Canonical FollowUp**。

采集、Source Candidate、Extraction、Review Queue、数据质量和系统配置继续存在，但仅属于管理控制台，不构成普通用户产品主线。系统没有自动生成 Opportunity，也没有增加 Match、Priority、Crawler、Graph 或 Agent 能力。

## 4. Navigation Decision

**NAVIGATION_DECISION**

| 决策 | 结果 | 用户频率与独立价值 | 黄金路径影响 |
|---|---|---|---|
| 正式一级导航 | 工作台 / 情报 / 企业与人物 / 跟进 | 对应日常发现、理解、查主体、推进四类高频任务 | 顺序直接映射黄金主线 |
| 关系保留一级导航 | NO | 关系只有放在主体或情报语境中才有明确业务意义 | 降为上下文后少一次离开主体档案的跳转 |
| 资源保留一级导航 | NO | 独立资源市场仍可作为辅助能力浏览，但理解情报/企业时无需再次搜索 | 情报和 Organization 直接聚合相关资源，少一次跨模块跳转 |

任务前普通用户一级入口为 5 个：工作台、情报、关系、资源、协作。任务后为 4 个：工作台、情报、企业与人物、跟进。

## 5. Workbench

登录后的产品首页首先展示“今天值得处理”，不再先展示平台能力、采集状态或工程指标。

排序固定为：P1（有效期内 + Organization/Q-BAY/Relationship + 明确动作）→ P2（有效期内 + Resource）→ P3（重要产业动态）→ P4（普通相关情报），同级较新优先。“今天”使用当前时间向前 30 天的明确窗口；2026-06-03 的 Intelligence 34 在 2026-08-29 验收时不进入队列。

“暂不处理”只保存当前用户的轻量状态，不删除或修改 Intelligence；操作后卡片立即退出，用户可从“今天已忽略”恢复。无优先动态时使用指定成品文案：“今天暂时没有需要优先处理的产业动态。”并提供“查看全部情报”。

“我的待办”只显示当前用户需要推进的 Canonical FollowUp，包含对象、事项、下一步、计划时间和状态。

## 6. Intelligence UX

普通用户详情按业务顺序固定为六块：

1. 发生了什么；
2. 涉及谁；
3. 为什么值得关注；
4. 与我们的关系；
5. 相关资源；
6. 下一步。

原文与公开证据放在末尾折叠区。CND ID、Candidate Type、Extraction、Pipeline、Entity Link Task、Review Queue 等加工字段不再出现在普通用户主视图。空值统一为“当前未发现直接关系”“暂无相关资源”“暂无进行中的跟进”“暂无已记录联系人”，真实浏览器未发现 `null`、`None`、`undefined`、`—` 或乱码。

旧的 `/reports/products/{id}` 产品详情入口以 303 统一到 `/intelligence/{id}`；processing 页面只回到正式情报入口，不保留第二套详情体系。

## 7. Translation Status

```text
TRANSLATION_MODE=MANUAL_ACCEPTANCE_FALLBACK
TRANSLATION_PROVIDER_REQUIRED=true
AUTO_TRANSLATION_READY=false
```

仓库没有可复用的自动 Translation/LLM Provider，本轮没有新增 Provider。Intelligence 29、30、32 的准确中文标题与摘要仅写入一次性隔离验收数据库，并标记 `MANUAL_CURATED_ACCEPTANCE_SAMPLE`；正式库、模板和代码中没有按标题硬编码映射。页面默认展示中文阅读层，英文标题、摘要、来源和链接仍保留在“原文与公开证据”。

RC1.1 的唯一候选任务是：**自动英→中语言加工**。本任务不启动 RC1.1。

## 8. Entity Quality

最小规则修正仅用于避免明显类型错误：Agency、Council、Committee、Authority 等机构后缀可识别为 Organization；纯机构缩写不再仅因大写而进入 Project，Project 缩写必须包含数字或连字符等项目证据。聚焦用例中 EMA/EISMEA 均不属于 Project，`ABC-123` 仍属于 Project。

| 指标 | 验收结果 | 分母说明 |
|---|---:|---|
| Extraction Precision | 3/3 | 聚焦规则样本中 2 个机构实体 + 1 个明确项目均为真实实体 |
| Entity Precision | 3/3 | 上述三个预测均不是事件标签 |
| Entity Type Precision | 3/3 | EMA/EISMEA=Organization，ABC-123=Project |
| Entity Linking Precision | 1/1 | 浏览器样本 Intelligence 33 的 Canonical Organization 链接正确 |
| Human Review Utility | N/A | 五条浏览器样本未产生需要普通用户处理的 Entity 审核任务，分母为 0；不伪造比率 |

融资、合作、监管审批、产品发布等 Event Type 不作为普通用户 Entity 候选展示；不可靠名称保留原始文本并降级为 unresolved，不猜错误类型。

## 9. Organization 360

Organization 页面按以下顺序聚合：基础资料、我们的关系、关键联系人、最近产业动态、资源 / 需求、正在跟进、历史合作证据。用户从情报点击主体后，不需要分别进入关系、资源和协作一级模块拼接信息。

Q-BAY 只表现为 Organization 的关系上下文（入驻、会员或合作机构），不再表现成第二个平台。管理监测信息仅在管理员末尾区域保留，不打断业务阅读。

## 10. FollowUp Closure

FollowUp 复用现有 `v06_follow_ups`。由于该 Canonical 表的 `opportunity_id` 为必填，服务在用户明确提交时复用现有 `v06_opportunities` 创建最小 `follow_up` 容器，并保存 `source_intelligence_id`；这是现有约束下的可追溯写入，不是自动 Opportunity Discovery，也不是新模型。

- 必填业务信息：对象、事项、原因、下一步、负责人（当前用户）、计划时间、状态。
- 写入仅发生在 operator 人工确认后；重复提交同一来源与负责人时复用容器。
- `Intelligence → Opportunity container → FollowUp` 可直接人工统计。
- 创建后立即回流“我的待办”，Web 重启后仍存在。

## 11. Manual Usability Metrics

| 指标 | 实测 |
|---|---:|
| Golden Path Click Count（工作台到建立成功） | 4 |
| Guess Count | 0 |
| Completion Time | 2.92 秒 |
| Context Switch Count | 2 |
| 全部验收交互 Click Count | 11 |

计时由真实 Chromium 在工作台首屏加载完成后开始，在“跟进已创建”出现时结束。完整原始数据见 `MVP_RC1_PRODUCT_ACCEPTANCE.csv` 和 `browser_acceptance.json`。

## 12. Reduced User Entries

| 项目 | Before | After | 减少 |
|---|---:|---:|---:|
| 普通用户一级导航 | 5 | 4 | 1 |
| 黄金主线需独立打开的关系/资源页面 | 2 | 0 | 2 个页面跳转 |
| 普通情报详情的工程/加工字段组 | 8 | 0 | 8 组 |
| 为定位主体/关系/资源所需的检索性判断 | 3 | 0 | 3 项 |

降级或移除的正式入口包括：关系一级入口、资源一级入口、旧 reports 产品详情、processing 产品详情、普通用户候选/加工入口。独立资源浏览能力和管理控制台未删除，只从黄金主线降级为辅助或管理员上下文。

## 13. Remaining Product Problems

没有发现阻断 RC1 的 P0/P1 产品缺陷。唯一明确缺口是英文情报尚无自动中文加工 Provider：当前页面能避免用户首先面对大段英文，并能用人工样本验证信息架构，但这不等于自动翻译 READY。

唯一后续候选为 RC1.1“自动英→中语言加工”；未启动、未实现、未接入任何 Provider。其余历史测试债务继续按既有分类冻结，不在本轮恢复 Legacy 行为。

## 14. Tests

- R2–R7.5 + RC1/RC1.2 联合隔离回归：**88/88 PASS**。
- 新增 RC1 产品用例覆盖：四项一级导航、EMA/EISMEA 类型、人工翻译标记与原文保留、30 天队列、按用户忽略/恢复、空状态、Organization 360 顺序、FollowUp 回流与 viewer 403。
- 全量 pytest 最终集合：**15 failed / 3 errors / 1 skipped**，与历史基线完全一致；新增失败 0、新增 error 0。
- 历史失败仍集中在 migration idempotency、P4 Legacy、v06i/v06j/v06k 的旧配置与迁移假设，不影响本轮产品主线，未为美化数字恢复 Legacy。
- pytest 期间正式 Source 运行与正式采集新增均为 0；联合测试前后正式 DB SHA256 完全一致。

## 15. Database

正式数据库唯一位置：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`。

| 检查 | 验收前 | 最终 |
|---|---|---|
| SHA256 | `1B0A91D596BB64A50BF9552B29FB8447F353494BCC78531523DBC3D72F19B33B` | `FED798300231934D170F104C4A4F4676AE90103C9888D29F6A0CD97AA6C1A3FB` |
| integrity_check | ok | ok |
| Intelligence / People / Organizations / Projects | 31 / 44 / 24 / 5 | 31 / 44 / 24 / 5 |
| Subject Links / Resources / Matches | 1 / 30 / 0 | 1 / 30 / 0 |
| Opportunities / FollowUps | 11 / 4 | 11 / 4 |
| Relationships / Evidence | 25 / 25 | 25 / 25 |
| 临时验收账号 | 0 | 0 |

文件哈希变化的原因已定位并处置：首次启动隔离实例时，PowerShell 的 URL 格式化警告使一次临时用户名登录请求误连正式配置，新增了唯一一条匿名 `login_failed` 审计行 ID 251；没有写业务表。按已授权的测试污染恢复流程先创建保护备份，再精确删除该行。SQLite 写入/回滚后的页布局使文件级 SHA 未回到旧值，但全部核心业务计数、正式账号、最大业务记录集合保持不变，`integrity_check=ok`；随后 88 项测试前后哈希严格保持 `FED798...` 不变。保护备份位于忽略交付的 `data/backups/MVP_RC1_PRE_AUDIT_CLEANUP_20260829.db`。

所有 FollowUp、反馈、人工中文样本和临时账号只存在于 `.rc1_acceptance_tmp/acceptance.db`；验收结束后目录已删除，端口 8017 监听为 0。

## 16. Chromium

浏览器：真实 Playwright Chromium **151.0.7922.34**（复用本机已有浏览器，无依赖下载）。应用内浏览器首次尝试因 Windows ACL/orchestrator helper 失败，记录为验收通道异常后立即切换项目现有 Playwright，没有据此判断产品失败。

| 项目 | 结果 |
|---|---:|
| 五条真实 Intelligence 覆盖 | 5/5 PASS |
| Golden User Path | PASS |
| Web restart persistence | PASS |
| viewer 写端点 | 403 PASS |
| Console Error | 0 |
| Page Error | 0 |
| Network Failure | 0 |
| 非预期 HTTP 404/500 | 0 |
| 横向溢出（1366×768、1920×1080） | 0 |
| 用户可见 undefined/null/乱码/工程术语 | 0 |

证据目录：`docs/audit/evidence/mvp_rc1/`，包含工作台、情报、Organization、FollowUp 创建、宽屏工作台和重启持久性截图，以及两份 JSON 原始结果。

## 17. Architecture

| 约束 | 实际新增 |
|---|---:|
| 业务表 | 0 |
| Model | 0 |
| Service 体系 | 0（扩展现有 `GoldenLoopService`） |
| Scheduler / Crawler / Search Provider | 0 |
| OSS / LLM / Agent / Graph | 0 |
| 版本目录 | 0 |
| 大型依赖 | 0 |

Tracked 产品代码/模板差异为 `+664 / -334`，净增 330 LOC；变化集中在既有查询聚合、导航、页面呈现、交互和 Entity 规则。Tracked 既有测试更新为 `+23 / -19`，新增 RC1 产品隔离测试 199 行，新增真实浏览器验收脚本 346 行。没有第二套业务模型、Service、Registry 或路由体系。

回滚方式：回滚最终单一 Git 提交即可恢复代码和审计文件；`data/app.db` 不在 Git 提交中。若需要核查本次审计清理前的数据库状态，使用上述保护备份进行离线比对，不直接覆盖正式库。

**最终结论：PASS**
