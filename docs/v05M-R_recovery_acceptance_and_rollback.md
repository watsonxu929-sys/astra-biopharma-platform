# v05M-R 异常中断恢复验收与回滚说明

## 修复范围

本次修复覆盖 v0.5M 产品化中文化任务中断后遗留的问题：模板语法错误、用户页面乱码、核心页面 500、会员门户表单缺失、搜索结果模板兼容问题、人物批量录入历史 DOM 钩子缺失、机构详情关联人物展示缺失、会员导入重复提示缺失。

## 覆盖步骤

1. 关闭正在运行的 Web 服务。
2. 备份当前仓库和 `data/app.db`。
3. 将补丁包内容覆盖到项目根目录。
4. 不要覆盖或删除 `data/app.db`、`data/backups/`、`logs/`、`runtime/`、`.env`。

## 验证顺序

```bat
.venv\Scripts\python.exe scripts\check_all_templates.py
.venv\Scripts\python.exe scripts\check_mojibake.py
.venv\Scripts\python.exe scripts\verify_core_pages.py
.venv\Scripts\python.exe scripts\verify_v05m.py
.venv\Scripts\python.exe scripts\verify_all.py
```

也可以双击运行：

```bat
verify_all_windows.bat
```

## 启动方式

```bat
run_windows.bat
```

默认 Web 地址为 `http://127.0.0.1:8000`。Worker 和 Scheduler 不提供新的浏览器端口。

## 回滚方式

1. 停止 Web 服务、Worker 和 Scheduler。
2. 使用本次修复前创建的 `backup_before_v05m_recovery_*` 目录恢复代码文件。
3. 如需要恢复数据库，仅使用备份的 `data/app.db` 文件替换当前数据库，替换前再次备份当前数据库。
4. 重新运行 `verify_all_windows.bat`。

## 人工验收页面

依次打开：`/`、`/intelligence/dashboard`、`/collection/sources`、`/collection/jobs`、`/processing/jobs`、`/processing/review`、`/pipeline`、`/pipeline/runs`、`/signals`、`/reports`、`/reviews`、`/research`、`/club`、`/member/login`。

重点确认：页面无 500、无用户可见版本号、无乱码、中文标题和按钮正常、空状态为中文、会员导入重复提示可见、人物批量录入工具栏存在。
