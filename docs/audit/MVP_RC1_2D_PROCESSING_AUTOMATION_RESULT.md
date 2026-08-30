# MVP-RC1.2D Processing Automation Result

## 1. PRODUCT RESULT

**PASS — `PROCESSING_AUTOMATION_GAP=false`.**

正常链路已经收敛为：`Source → Collection → Raw Snapshot → Existing Processing Job → Existing Executor → Extraction / Candidate`。正常采集不再要求管理员手工创建加工任务；自动加工没有扩大审核、发布或高风险业务事实的权限。

- Processing 产品分类：`ADMIN_OPERATION`
- Collection 产品分类：`CORE_INTELLIGENCE_CAPABILITY`
- `AUTO_TRANSLATION_READY=false`，本轮未接翻译、AI、Search Provider 或新 Crawler。
- 新业务表 / Model / Service体系 / Scheduler体系 / 版本目录 / 大型依赖：均为 0。
- Production Python 净新增：`+100 LOC`，低于 300 LOC 约束。

## 2. Root Cause

根因不是缺少 Processing 系统，而是既有 Collection Runner 在创建 `v05g_processing_jobs` 后立即返回，没有调用既有 Processing Executor，任务因而停留在 `pending`。完整证据见 `MVP_RC1_2D_PROCESSING_AUTOMATION_ROOT_CAUSE.md`。

## 3. Before Processing Flow

`Collection Success → 创建 Processing Job → 返回 → 管理员进入 /processing/jobs → 手工执行`。

正常流程的 Processing 额外人工点击至少为 2：进入加工后台、执行任务。

## 4. After Processing Flow

`Collection success/partial + 合格新内容 → advance_processing_after_collection → 既有 create_processing_job → 既有 run_processing_worker_once/process_job → Candidate / needs_review`。

自动化只推进现有 Raw/Candidate 流程；不会自动确认 Organization、Relationship、Resource、Opportunity、FollowUp，也不会绕过审核发布。

## 5. Automatic Trigger

唯一正式衔接函数为 `advance_processing_after_collection`。定时 Collection Cycle、统一 Collection Runner 和管理员显式执行某个 Collection Run 都进入此函数；Route 不复制 Processing 写逻辑。

准入条件为：Run 是 success/partial、Source 启用且未退役/暂停、Raw 为 queued、去重状态为 new/changed、无 duplicate_of、Snapshot 非 Pilot 且正文存在、同一 Raw 不存在 pending/running/success/needs_review Job。

单次执行沿用现有小批量边界，最多处理 20 条；没有新增 Web 内大批量队列或后台基础设施。

## 6. Idempotency

- Service 层对同一 Raw 的活动或成功 Job 返回现有 Job，并标记 `idempotent=true`。
- 自动准入查询再次排除已有活动/成功 Job。
- 重复 Collection 被标记为 unchanged/duplicate/ignored，不再排队。
- 隔离 Chromium 连续采集同一内容：自动 Job 数始终为 1，第二次自动加工 0 条。
- 重复 Runner、Scheduler Tick 和人工误点的定向测试均未产生重复 Job、Candidate 或正式 Intelligence。

## 7. Failure / Retry

隔离验收人为构造一条 Snapshot 无效的 Processing Job：

- 失败状态、错误类型和原因被持久化；Raw 保留。
- 同一批中的正常任务继续成功，不被失败记录阻塞。
- Operator 在正式 `/processing/jobs` UI 点击“重新加工”后，状态由 failed 进入 needs_review，旧错误字段被清空。
- 不存在无限自动高速重试；失败等待管理员恢复或既有 Scheduler 节奏。

## 8. Restart Persistence

pending Job 写入 SQLite 后停止并重新启动隔离 Web。重启后后台仍显示“等待后台执行器”；下一次既有 Collection Runner/Scheduler 周期在没有新 Collection 的情况下继续清理 pending 队列，最终进入 needs_review。任务未丢失，也未创建重复 Job。

正式 RUN 复验：

- Cold Start：READY
- Existing Instance：识别已运行实例，不重复启动
- Stop → Start：READY
- 最终状态：Web 运行中；Worker、Scheduler 未启动且无陈旧 PID 文件

## 9. Processing Admin UX

`/processing/jobs` 已降级为“情报加工运行与异常恢复”：

- 显示今日加工、今日成功、待处理、失败。
- 核心列表为待处理/失败原因和“重新加工”。
- 手工创建 Job 与单次 Worker 放入折叠的“高级操作”，不再是 Primary Action。
- Viewer 看不到恢复按钮和高级操作。
- 无异常/等待任务时显示业务化空状态，不显示 null、数组或技术空值。

## 10. Manual Click Reduction

从“管理员触发一次采集”到“新内容进入正确后续状态”：

- Processing 阶段额外人工点击：`0`
- Manual Job Required For Normal Flow：`0`
- 管理员只有在失败重试、指定记录重新加工或异常恢复时才进入 Processing 页面。

## 11. RC1.2C Lifecycle Regression

定向测试确认：

- 已删除 Collection 不会重新进入 Processing。
- withdrawn Intelligence 不会因旧 Collection 被重新发布。
- archived Intelligence 不会回到最新正式流。
- 自动 Processing 不执行正式发布，因此 RC1.2C DELETE / WITHDRAW / ARCHIVE / RESTORE 语义不变。
- Source 新增、Discovery、Candidate、退役与删除逻辑未修改。

## 12. Real Controlled Collection

正式库只运行一个既有 ACTIVE 真实来源一次：

- Source：EMA News RSS（ID 4）
- Run：ID 144，`JOB-20260830-00001`
- 时间：2026-08-30 14:09:49 → 14:10:13（Asia/Shanghai）
- 结果：`NO_NEW_CONTENT`；Collection status=unchanged，result=DUPLICATE
- new=0，changed=0，duplicate=1，queued=0
- Processing created=0，processed=0，failed=0

没有为验收制造正式 Intelligence、Resource、Opportunity 或其他业务数据。新增的一条 Raw Collection 是该真实来源的可追溯重复采集历史，引用既有 Snapshot。

隔离浏览器 Scenario A–F 指标：

| 指标 | 结果 |
|---|---:|
| Collections Successful | 1 |
| Processing Auto Queued | 1 |
| Processing Successful / needs_review | 1 |
| Processing Failed（受控异常） | 1 |
| Processing Retried | 1 |
| Duplicates Prevented | 1 |
| Manual Job Required For Normal Flow | 0 |

证据阶段时间：Source 13:58:25、自动加工 13:58:27、失败恢复 13:58:28、Candidate 13:58:29、重启恢复 13:58:40、Viewer 13:58:43、情报详情 14:15:47。

## 13. Tests

- RC1.2D 新增定向测试：`7 passed`
- RC1.2D + RC1.2C + R5A + Golden Loop + RUN 联合回归：`54 passed`
- 全量 pytest：`15 failed / 3 errors / 1 skipped`
- 历史基线：`15 failed / 3 errors / 1 skipped`
- 新增失败/错误：`0`

历史集合仍只涉及既有 migration idempotency、v06i runtime baseline、v06j migration chain、v06k P4 contract 等已分类债务；本轮不清理这些债务。

## 14. Chromium

- 验收方式：项目现有 Playwright + 已安装真实 Chromium，无依赖下载
- 浏览器版本：Chromium `151.0.7922.34`
- 尺寸：1366×768 与 1024×768
- 已真实操作/打开：Source 详情、发起采集、Collection 结果、Processing 状态、失败页、UI 重试、Candidate、情报首页、情报详情 ID 29、重启恢复、Viewer 只读页
- Processing 手工创建 Job 点击数：0
- Viewer 后端写入：create=403、retry=403、worker=403
- Console Error=0；Page Error=0；Network Failure=0；404/500=0；横向溢出=0

正式证据位于 `docs/audit/evidence/mvp_rc1_2d/`，含 7 张截图、主流程 JSON 和情报详情 JSON。Computer Use 首次因 Windows ACL helper 失败后按规则切换项目 Playwright，没有把工具通道问题报告为产品问题。

## 15. Database Safety

正式数据库：`data/app.db`

- 采集前 SHA256：`FED798300231934D170F104C4A4F4676AE90103C9888D29F6A0CD97AA6C1A3FB`
- 采集前 integrity_check：ok
- 备份：`data/backups/app_20260830_140841.db`
- 备份 SHA256：与采集前正式库相同
- 采集后 SHA256：`23CC1FF101C793F33974F0D702A16128BCD3EE06CCA10AEB3A3D52EC63FF60EF`
- 采集后 integrity_check：ok

正式变化解释：Collection Runs 140→141；Collection Items 521→522；Snapshots 60→60；Processing Jobs 49→49；Candidates 160→160。Intelligence 31、People 44、Organizations 24、Projects 5、Subject Links 1、Resources 30、Match Candidates 0、Opportunities 11、FollowUps 4、Relationships 25、Relationship Evidence 25 均不变。

pytest 期间正式 Source Run=0、正式 Processing=0、正式业务写入=0。隔离验收测试账号、Source、Collection、Candidate、数据库和 Web 均已删除；正式库 `rc12d_*` 用户、受控测试 Source、测试 Intelligence marker 均为 0。

## 16. Remaining Problems

- 既有全量 pytest 历史债务仍为 15 failed / 3 errors / 1 skipped，本轮未扩大也未修复。
- 正式 EMA 受控周期没有新内容，因此正式库未产生新的自动 Processing；自动闭环由真实 Chromium 的本机受控网页和隔离正式库副本完成验证。
- Windows 会在验收控制 Python 进程存活时锁住临时 SQLite；控制进程退出后专用临时目录已安全清理，最终残留为 0。
- 自动翻译继续冻结；本轮没有开始 RC1.2E、RC1.3 或 R8。

## 必须回答

1. Source 采集成功后，合格且非重复的新 Raw 会自动创建既有 Processing Job，并由既有 Executor 进入 Extraction/Candidate 和现有审核状态。
2. 正常流程不再需要手工“新建情报加工任务”。
3. “情报加工”页面属于管理员和运营人员的异常恢复工具，不是普通用户核心功能。
4. 管理员只在加工失败、待处理异常、指定记录重新加工或系统恢复时进入该页面。
5. 加工失败会保留 Raw 与错误原因，不阻塞后续记录；管理员可在正式 UI 重试。
6. 同一条信息不会在正常 Runner、重复 Tick 或误点下重复生成有效加工任务和正式情报。
7. 系统重启后 pending Job 保留在 SQLite，下一个既有 Runner/Scheduler 周期继续处理，不会丢失。
