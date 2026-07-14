# T1 采集运行时审计报告

审计日期：2026-07-14
数据库：data/app.db（正式库）

## 1. 当前是否已有调度器

**结论：有调度逻辑，但未自动运行。**

- `app/services/intelligence_flow_service.py` 包含 `schedule_due_collection_jobs()` 函数，可以为到期的数据源创建采集任务
- `app/services/tasks/task_registry.py` 注册了 `collection` 任务处理器，调用 `schedule_due_collection_jobs` 和 `run_collection_worker_with_cascade`
- **但是**：`app/core/config.py` 中 `SCHEDULER_ENABLED` 默认值为 `False`，应用启动时不会自动启动调度器
- **没有**：APScheduler 或类似定时任务框架的实际注册和运行机制

## 2. 调度器是否真的在应用启动后运行

**结论：否，调度器未运行。**

- 配置 `scheduler_enabled: bool = False`（config.py 第57行）
- 应用启动流程中没有任何代码自动调用 `schedule_due_collection_jobs`
- 唯一的调度入口是手动调用 API 或命令行脚本
- 最近一条任务（id=6, JOB-20260709-00001）状态为 `pending`，自7月9日起从未执行

## 3. 当前启用来源有哪些

| ID | source_no | 名称 | source_type | is_enabled | auto_paused | check_frequency |
|---|---|---|---|---|---|---|
| 1 | MON-20260701-00001 | 药明康德 | official_site | 1 | 0 | daily |
| 2 | MON-20260702-00001 | 鲸准 | rss | 1 | 1 | manual |
| 3 | MON-20260702-00002 | 36克 | webpage | 1 | 0 | manual |

**注意：这些来源均非P2.2已验证来源。**

## 4. 来源配置存储在哪里

来源配置存储在 `v04g_monitoring_sources` 表中，关键字段：
- `source_no`: 来源编号
- `name`: 来源名称
- `source_type`: 来源类型（rss/webpage/list_page/dynamic_page等）
- `url`: 源URL
- `is_enabled`: 是否启用
- `auto_paused`: 是否自动暂停（连续失败后自动触发）
- `check_frequency`: 检查频率（manual/hourly/daily/weekly）
- `collection_mode`: 采集模式（http/rss/api/playwright/auto）
- `max_links`: 单次最大链接数
- `crawl_detail_pages`: 是否抓取详情页

## 5. 当前任务是否会自动生成CollectionJob

**结论：否，不会自动生成。**

- `check_frequency` 字段用于判断是否应该运行，但实际调度逻辑从未被触发
- 没有定时任务扫描到期的数据源
- 只有手动调用 `create_job()` 或 API `/api/v1/collection/sources/{id}/run` 才会创建任务
- `schedule_due_collection_jobs()` 函数虽然存在，但无人调用

## 6. 最近一次运行记录在哪里

最近运行记录存储在 `v04g_monitoring_runs` 表中：

| ID | run_no | source_id | status | created_at | finished_at |
|---|---|---|---|---|---|
| 6 | JOB-20260709-00001 | 3 | pending | 2026-07-09 | - |
| 5 | JOB-20260702-00004 | 3 | success | 2026-07-02 | 2026-07-02 |
| 4 | JOB-20260702-00003 | 2 | skipped | 2026-07-02 | 2026-07-02 |
| 3 | JOB-20260702-00002 | 2 | failed | 2026-07-02 | 2026-07-02 |
| 2 | JOB-20260702-00001 | 2 | failed | 2026-07-02 | 2026-07-02 |

**问题：任务 #6 自7月9日起一直处于 pending 状态，从未被执行。**

## 7. 为什么前台感受不到自动采集

1. **调度器未启用**：`SCHEDULER_ENABLED=False`，应用启动后不会自动调度
2. **来源频率配置不当**：现有3个来源中有2个为 `manual`，1个为 `daily`
3. **没有自动运行机制**：没有定时任务扫描和执行到期任务
4. **前台缺少可见化**：没有"今日自动采集"入口，没有来源运行状态面板
5. **历史任务堆积**：pending任务未被清理和执行
6. **没有运行状态展示**：用户无法看到上次/下次运行时间、成功/失败统计

## 8. 当前三个最适合正式试运行的已验证来源

根据 P2.2 试点报告（批次 `P22-20260711-CODEX`），已成功验证的来源：

| 优先级 | 来源 | 类型 | 采集方式 | 验证状态 | 理由 |
|---|---|---|---|---|---|
| 1 | EMA News RSS | RSS | RSS | 成功 | 标准RSS格式，无需额外解析，稳定性高 |
| 2 | FDA Press Announcements | 静态列表页 | HTTP | 成功 | 结构化页面，适合作为静态来源代表 |
| 3 | ClinicalTrials.gov Search | 动态页面 | Playwright | 成功 | 动态渲染页面，验证Playwright能力 |

**这三个来源将作为T1的正式试运行来源。**
