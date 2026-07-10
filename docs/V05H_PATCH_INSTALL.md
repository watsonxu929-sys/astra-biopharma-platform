# v0.5H 补丁安装说明

## 安装步骤

1. 解压补丁到当前仓库根目录。
2. 确认虚拟环境已安装依赖。
3. 运行迁移：

```powershell
.venv\Scripts\python.exe scripts\migrate_all.py
```

4. 运行专项验证：

```powershell
.venv\Scripts\python.exe scripts\verify_v05h.py
```

5. 运行全量回归：

```powershell
.venv\Scripts\python.exe scripts\verify_all.py
```

6. 启动系统：

```powershell
start_windows.bat
```

## 端口配置

默认地址是：

```text
http://127.0.0.1:8000/
```

可在 `.env` 中配置：

```text
APP_HOST=127.0.0.1
APP_PORT=8000
APP_RELOAD=true
APP_OPEN_BROWSER=true
```

## 回滚建议

迁移脚本会在 `data/backups/` 生成数据库备份。需要回滚时，先停止服务，再用备份文件替换 `data/app.db`。

不要删除 `data/`、`logs/` 或 `.venv/` 目录来安装补丁。
