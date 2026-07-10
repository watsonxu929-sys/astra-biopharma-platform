# 安装与启动

## 环境要求

- Windows 本地开发环境
- Python 3.11 或兼容版本
- 项目依赖安装在 `.venv`
- 默认 Web 访问地址：`http://127.0.0.1:8000`

## 初始化

双击或在 PowerShell 中执行：

```bat
setup_windows.bat
```

该脚本会创建虚拟环境、安装依赖，并准备本地运行目录。

## 数据迁移

```bat
migrate_all_windows.bat
```

迁移前请确认已备份 `data/app.db`。不要手动删除、重建或清空正式业务表。

## 启动系统

```bat
run_windows.bat
```

浏览器打开 `http://127.0.0.1:8000`。Worker 和 Scheduler 作为后台进程运行，不提供新的浏览器端口。

## 验证

```bat
verify_all_windows.bat
```

如只验证本次产品化中文化修复，可运行：

```bat
verify_v05m_windows.bat
```
