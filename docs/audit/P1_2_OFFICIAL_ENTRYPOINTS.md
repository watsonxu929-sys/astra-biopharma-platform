# P1.2-A 正式入口清单

## 入口列表

| 名称 | 路径 | 调用来源 | 是否正式 | 是否重复 | 建议 |
|---|---|---|---|---|---|
| FastAPI应用入口 | app/main.py | 启动脚本 | 是 | 否 | 保留 |
| 路由总注册 | app/main.py | 应用入口 | 是 | 否 | 保留 |
| 模板根目录 | app/templates/ | app.main | 是 | 否 | 保留 |
| 静态资源根目录 | app/static/ | app.main | 是 | 否 | 保留 |
| 正式启动脚本 | run_windows.bat | 用户双击 | 是 | 否 | 保留 |
| 数据库路径解析 | app/settings.py | 全局 | 是 | 否 | 保留 |
| 迁移入口 | scripts/migrations/ | migrate_all_windows.bat | 是 | 否 | 保留 |
| 验证入口 | scripts/verify_p0_baseline.py | verify_all_windows.bat | 是 | 否 | 保留 |
| pytest入口 | tests/ | python -m pytest | 是 | 否 | 保留 |
