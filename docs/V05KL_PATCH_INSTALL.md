# v0.5K-L 补丁安装、回滚与验收

## 安装

1. 运行 `setup_windows.bat` 安装依赖。
2. 复制 `.env.example` 为 `.env`，按部署环境填写端口、数据库和密钥。
3. 运行 `migrate_all_windows.bat`。迁移会先备份 `data/app.db` 到 `data/backups/`。
4. 运行 `verify_v05kl_windows.bat` 和 `verify_all_windows.bat`。
5. 运行 `start_all_windows.bat` 启动 Web、Worker 和调度器。

## 回滚

1. 运行 `stop_all_windows.bat` 停止本项目进程。
2. 从 `data/backups/app_before_v05kl_*.db` 或 `data/backups/app_before_migrate_all_*.db` 选择回滚点。
3. 将当前 `data/app.db` 另存为人工备份。
4. 使用选定备份替换 `data/app.db`。
5. 运行旧版本验证脚本确认回滚成功。

## 人工验收

- 打开 `/system/operations`，检查健康、队列、质量指标是否可见。
- 创建一个 `cleanup` 任务并确认 Worker 可执行。
- 创建一次手动备份，随后使用 `restore_backup.py --dry-run` 验证备份。
- 运行 `pilot_real_sources.py --list` 和 `--dry-run`，确认不会触发真实网络采集。
- 确认普通只读用户不能进入 `/system/operations`。
- 确认 API v1 仍保留英文机器字段，新增展示字段不破坏旧字段。
