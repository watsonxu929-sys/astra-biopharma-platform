# v0.5I 真实来源全链路编排与运行质量中心

## 目标

v0.5I 将 v0.5F 采集、v0.5G 加工、v0.5H 信号和报告串成统一流水线。流水线只保存阶段关联 ID、状态、计数、错误和指标，不复制采集、加工、信号或报告业务数据。

## 页面入口

- `/pipeline`
- `/pipeline/runs`
- `/pipeline/runs/{id}`
- `/pipeline/failures`
- `/pipeline/pilot`

## API 入口

- `GET /api/v1/pipeline/runs`
- `POST /api/v1/pipeline/runs`
- `GET /api/v1/pipeline/runs/{id}`
- `POST /api/v1/pipeline/runs/{id}/continue`
- `POST /api/v1/pipeline/runs/{id}/retry`
- `POST /api/v1/pipeline/runs/{id}/cancel`
- `GET /api/v1/pipeline/dashboard`
- `GET /api/v1/pipeline/quality`
- `POST /api/v1/pipeline/samples/{id}/review`

## 阶段

```text
pending -> collecting -> collected -> processing -> waiting_review
waiting_review -> applying -> signaling -> reporting -> completed/partial
```

人工审核是硬暂停点。候选进入 `pending` 或 `needs_review` 后，流水线进入 `waiting_review`，不会自动批准候选、自动合并主体或自动覆盖正式字段。

## 失败恢复

流水线记录 `failed_stage`、`error_code`、`error_summary`。`retry` 从失败阶段或审核后阶段继续，已完成阶段不会无故重复执行。

同一来源同一时间只能存在一个 active 流水线，active 状态包括：

- `pending`
- `collecting`
- `collected`
- `processing`
- `waiting_review`
- `applying`
- `signaling`
- `reporting`

## 真实来源试运行

配置文件是 `config/pilot_sources.yaml`。默认所有示例来源 `allow_real_run=false`，不会直接访问真实网络。

真实网络脚本：

```powershell
.venv\Scripts\python.exe scripts\pilot_real_sources.py
.venv\Scripts\python.exe scripts\pilot_real_sources.py --source-id 5 --confirm
```

没有 `--confirm` 时只输出 dry-run 范围。即使 `--confirm`，配置里的来源也必须显式 `allow_real_run=true` 才会访问网络。

## Worker

```powershell
.venv\Scripts\python.exe scripts\run_pipeline_worker.py --once
.venv\Scripts\python.exe scripts\run_pipeline_worker.py --source-id 5 --pilot
.venv\Scripts\python.exe scripts\run_pipeline_worker.py --pipeline-run-id 12
.venv\Scripts\python.exe scripts\run_pipeline_worker.py --due-only --limit 10
.venv\Scripts\python.exe scripts\run_pipeline_worker.py --resume-failed
```

Windows 入口：

- `run_pipeline_once_windows.bat`
- `run_pipeline_worker_windows.bat`

## 质量指标

`/api/v1/pipeline/quality` 使用真实运行表计算：

- `source_success_rate`
- `collection_new_item_rate`
- `duplicate_rate`
- `empty_content_rate`
- `processing_success_rate`
- `structure_confidence_average`
- `candidate_per_item`
- `subject_match_rate`
- `ambiguous_match_rate`
- `review_approval_rate`
- `apply_success_rate`
- `signal_generation_rate`
- `report_completion_rate`
- `average_pipeline_duration`

## 安全边界

- 不绕过 robots、登录、验证码或付费墙。
- 不默认访问真实网络。
- 不自动批准候选。
- 不自动合并人物或机构。
- 不自动覆盖正式主体字段。
- 不自动发布报告。
- 不删除、不重建、不清空 `data/app.db`。
