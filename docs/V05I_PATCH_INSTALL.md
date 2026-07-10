# v0.5I 补丁安装与回滚说明

## 安装

```powershell
.venv\Scripts\python.exe scripts\migrate_all.py
.venv\Scripts\python.exe scripts\verify_v05i.py
.venv\Scripts\python.exe scripts\verify_all.py
start_windows.bat
```

## Windows 入口

- `migrate_v05i_windows.bat`
- `verify_v05i_windows.bat`
- `run_pipeline_once_windows.bat`
- `run_pipeline_worker_windows.bat`
- `project_tools_windows.bat`

## 回滚

迁移前会在 `data/backups/` 生成数据库备份。回滚时：

1. 停止应用和 Worker。
2. 恢复补丁前文件。
3. 用迁移前备份替换 `data/app.db`。
4. 重新运行 `verify_all_windows.bat`。

## 人工验收

建议验收路径：

1. 在 `/collection/sources` 准备一个公开来源。
2. 在 `/pipeline/runs` 创建 dry-run 流水线。
3. 确认进入 `waiting_review`。
4. 跳转到现有 `/processing/candidates` 审核候选。
5. 回到流水线详情点击 Continue。
6. 查看阶段、候选、信号、报告和质量指标。
