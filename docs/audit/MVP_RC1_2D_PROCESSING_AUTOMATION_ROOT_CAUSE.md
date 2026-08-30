# MVP-RC1.2D Processing Automation Root Cause

## 结论

`PROCESSING_AUTOMATION_GAP=true` 的根因是既有 Collection Runner 只完成了“创建 Processing Job”，没有继续调用既有 Processing Executor。缺的是一段接线，不是 Processing 模型、Service、Scheduler 或队列基础设施。

## 当前事实

1. Collection 正式完成状态为 `success`、`partial`、`unchanged` 或 `failed`；只有 `success` / `partial` 且产生 `processing_status='queued'` 的新内容具备自动加工资格。
2. `collection_service.process_job` 抓取 Source，写入 Snapshot 与 Raw Collection，并把质量合格、非重复内容标记为 `queued`。
3. `intelligence_flow_service.run_collection_worker_with_cascade` 调用 Collection Executor，随后由 `create_processing_jobs_for_collection_run` 创建现有 `v05g_processing_jobs`，`trigger_type='collection_worker'`。
4. Processing Executor 已存在：`processing.processing_job_service.process_job`。它负责正文分类、Block、Candidate、主体匹配、错误状态和 Raw Collection 状态推进。
5. APScheduler 已存在且只注册一个 `collection_cycle`；统一 Worker 与命令行入口也已存在。本任务不新增 Scheduler 或 Worker。
6. 当前断点：Collection Runner 创建 Processing Job 后立即返回，没有调用 `run_processing_worker_once`。因此 Job 长期停留在 `pending`，管理员只能在 `/processing/jobs` 手工执行。

## 现有保护

- Raw Collection 只有 `queued`、`failed`、`needs_review` 等既有状态可进入 Processing。
- Collection 去重会把重复/未变化内容标记为 `ignored`，不会进入正常队列。
- Processing Candidate 现有唯一索引阻止同一 Job 内重复候选。
- Processing `process_job` 会把单条异常记录为 `failed`，保留 Raw 和错误原因。
- Candidate 审核与正式发布仍是现有独立质量门；自动 Processing 不自动确认主体、关系、资源、机会或跟进。

## 缺失保护

`v05g_processing_jobs` 没有“同一 Collection 的活动 Job”唯一索引。当前主要依靠 Raw 的 `processing_status` 从 `queued` 原子推进到 `processing`，但重复 Runner 或误点仍缺少 Service 级幂等返回。RC1.2D将在现有 `create_processing_job` 内补充查询保护，不新增表或索引。

## 唯一正式触发点

唯一自动触发语义确定为：

`Collection Runner 完成一次 success/partial Run` → `advance_processing_after_collection` → `create_processing_jobs_for_collection_run` → `run_processing_worker_once` → 既有 `process_job`。

定时 Scheduler、统一 Worker和管理员显式执行某个Collection Run都复用这一衔接函数。Route 不实现另一套 Processing 写逻辑。

## 自动加工准入

自动加工必须同时满足：

- Collection Run 状态为 `success` 或 `partial`；
- Source `is_enabled=1`、未退役、未自动暂停；
- Raw Collection 仍存在，状态为 `queued`；
- Snapshot 存在且正文非空；
- Raw 不是 duplicate / unchanged，且没有 `duplicate_of_item_id`；
- Snapshot 不是 Pilot 数据；
- 同一 Raw 没有 pending/running/success/needs_review Processing Job。

不满足条件的记录只保留为采集历史，不自动创建加工任务。

## 失败、重试与重启

- 单条 Processing 失败由既有 Executor 写入 `failed` 和 `error_type/error_message`；Runner继续处理后续 Job。
- 管理员在 `/processing/jobs` 对失败 Job执行“重新加工”，仍调用同一个 `process_job`。
- pending Processing Job持久化在SQLite。Web或Scheduler重启后，下一个既有 Collection Cycle会先/继续清理 pending 队列，不创建重复 Job。

## 生命周期边界

自动化只推进 Raw → Candidate。它不发布正式 Intelligence，因此不会恢复已下架/归档情报，也不会重建已删除 Collection。RC1.2C的 DELETE / WITHDRAW / ARCHIVE / RESTORE 语义保持不变。
