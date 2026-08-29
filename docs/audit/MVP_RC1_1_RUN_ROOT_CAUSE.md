# MVP-RC1.1 Windows RUN Root Cause Audit

## Verified entry and call chain

1. 用户当前唯一可见的根目录双击入口是 run_windows.bat。
2. 它由 cmd.exe 执行，并调用 scripts/windows/start_web_windows.bat。
3. 旧脚本最终使用 PowerShell Start-Process 启动项目 .venv Python，再执行 uvicorn app.main:app。
4. Working Directory 由两个 BAT 都切换到脚本计算出的项目根目录；中文绝对路径本身不是本次根因。
5. Python 明确来自项目 .venv，不依赖预先激活 venv，也不回退到随机系统 Python。
6. .env 位于项目根目录；旧 BAT 仅手工读取 APP_ENV/HOST/PORT/RELOAD/OPEN_BROWSER，应用自身再加载完整 .env。
7. 数据库通过 app.settings 从 DATABASE_URL / APP_DB_PATH 解析，默认正式位置为项目根目录 data/app.db。
8. 默认监听 127.0.0.1:8000。
9. 旧脚本用 PowerShell Start-Process -WindowStyle Hidden 创建后台 Uvicorn，没有 cmd /c 嵌套；根 BAT 随后立即结束。

## Reproduced failure

- 复现时端口 8000 为 FREE，但 runtime/web.pid 遗留值为 PID 6052。
- PID 6052 已被 LenovoInternetSoftwareFramework.exe 复用，实际不是本项目 Uvicorn。
- 旧 start_web_windows.bat 只用 tasklist 判断该数字 PID 是否存在，没有检查命令行、端口或 /health。
- 因此它在 0.20 秒内错误输出 Web is already running. PID 6052 并返回 1。
- 根 run_windows.bat 在失败分支直接 exit /b 1，没有人类可读的停留路径；双击窗口表现为“一闪而过”。
- 端口上没有 Web，/health 不可访问，证明这不是“正常已有实例”。
- 旧 stop 脚本正确拒绝误杀 PID 6052，但不会清理这个失效 PID 文件。
- 经确认端口空闲且命令行不匹配后，仅删除 stale PID 文件，未终止外部进程。

## Additional root causes

1. 正常启动仅证明 Start-Process 成功，不等待 Uvicorn 导入、数据库打开或路由就绪。
2. /login 与 /platform 从未进入启动成功判定。
3. Uvicorn 的即时异常被重定向到日志，但根入口仍可能先显示 Web started 后退出。
4. 任意端口占用一律报错，无法区分本项目健康实例与其他程序。
5. 成功与失败都没有稳定、中文、可操作的最终状态；失败路径没有 pause。
6. 相对路径在当前脚本中已通过 cd /d 正确自定位，不是本次闪退根因。
7. 隐藏 Uvicorn 子进程按设计独立于父窗口；Web 是否随窗口退出不是主因，错误的 PID 判定和缺少健康检查才是。

## Minimal repair decision

- 保留 run_windows.bat 为唯一正式用户入口。
- 保留后台独立 Web 生命周期语义，关闭启动窗口不会误杀已就绪服务。
- 让 BAT 自定位根目录并固定项目 .venv Python；Python 缺失时在失败路径记录日志并停留。
- 用一个小型 scripts/windows/run_web_launcher.py 完成只读 DB preflight、stale PID 校验、同项目实例识别、端口冲突分类、有限健康等待、日志和安全 stop/status。
- 成功必须同时满足 /health、/login、/platform；失败返回明确非零退出码。
- pause 只存在于根 RUN 的失败路径；成功路径显示 READY 后有限停留，后台 Web 继续运行。
