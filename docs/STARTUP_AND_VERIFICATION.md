# 启动、迁移、验证与回滚

## 顺序

1. `backup_windows.bat`。
2. `migrate_all_windows.bat`；迁移失败立即停止，不通过页面重试建表。
3. `.venv\Scripts\python.exe scriptserify_p0_baseline.py`。
4. `verify_all_windows.bat`。
5. `run_windows.bat`，访问首页与 `/health`。

## 验证安全

P0 验证把真实 `data/app.db` 复制到临时目录后执行页面和 API 冒烟；正式库只以只读 URI 检查。不得用模拟数据代替真实库副本，也不得在报告记录真实密码。

## 回滚

停止服务，保留失败日志；确认外部 ZIP SHA256 后恢复代码，数据库仅由人工选择任务前备份恢复。禁止删除或重建 `data/app.db`。Git 回滚应按 P0/P1 独立提交执行。

## 人工验收

首页、登录、情报、企业、人物、会员、活动、资源、商机、任务和健康页无 500；核心 API 返回 JSON；普通 GET 前后正式数据库哈希不因结构迁移改变。
