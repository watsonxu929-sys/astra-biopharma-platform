# MVP-RC1.1 RUN 与 Translation 验收结果

## 1. RUN_ACCEPTANCE

RUN_ACCEPTANCE=PASS

RUN_WINDOW_FLASH_EXIT=FIXED

唯一正式入口仍为根目录 run_windows.bat。它能从非项目工作目录自定位到中文项目路径，固定使用项目 .venv Python，先执行只读环境/数据库/端口检查，再启动独立后台 Web；只有 /health、/login、/platform 都正常后才输出 RUN_STATUS=READY。失败返回明确非零退出码，根 RUN 默认在失败路径 pause，成功路径不无限停留。

## 2. RUN_ROOT_CAUSE

根因不是简单缺少 pause。真实复现时端口 8000 空闲，但 runtime/web.pid 遗留 PID 6052，且该 PID 已被 LenovoInternetSoftwareFramework.exe 复用。旧脚本只检查数字 PID 是否存在，于 0.20 秒内错误报告 Web 已运行并退出；根 BAT 在失败时直接 exit，窗口表现为闪退。

同时，旧流程只确认 PowerShell Start-Process 成功，不验证 Uvicorn 是否完成导入、数据库能否打开或页面是否健康。完整证据见 MVP_RC1_1_RUN_ROOT_CAUSE.md。

## 3. RUN_BEFORE_AFTER

| 项目 | Before | After |
|---|---|---|
| 正式入口 | run_windows.bat | run_windows.bat，仍为唯一入口 |
| Project Root | BAT cd /d，自定位正确 | BAT + Python 双重自定位 |
| Python | 固定 .venv，但仅存在性检查 | 固定 .venv，解释器一致性与核心模块检查 |
| stale PID | 只要 PID 数字存在就误判运行中 | 校验命令行；PID 复用时仅清理 PID 文件 |
| 端口占用 | 一律失败 | 健康同项目=成功；其他程序=明确错误 13 |
| DB | 由 Uvicorn 启动时才暴露问题 | 启动前只读 integrity_check |
| 成功判定 | Start-Process 返回 | /health + /login + /platform |
| 失败可见性 | 直接 exit | 中文原因、建议、日志、退出码；双击失败 pause |
| 日志 | Web stdout/stderr | 增加 logs/startup.log 阶段化、脱敏记录 |
| 停止 | 长 PowerShell 命令 | 同一启动器安全校验 PID 后停止进程树 |

实现过程中还发现 UTF-8 中文 BAT 在 cmd 下可能被错误切分。最终 BAT 控制语句保持 ASCII，设置 code page 65001 和 PYTHONIOENCODING=utf-8，中文状态由 Python 输出；真实错误场景已确认可读。

## 4. Cold Start

- 初始端口 8000：FREE。
- 调用位置：C:\Windows，不依赖用户先 cd。
- 调用入口：正式 run_windows.bat。
- 隔离数据库：正式库的临时副本，Scheduler/Worker 明确 false。
- 完成时间：6.33 秒。
- 退出码：0。
- RUN_STATUS=READY。
- /login=200，/platform=200。
- 关闭 RUN 父窗口后后台 Web 继续运行。
- 正式数据库 SHA256 未变化。

## 5. Restart

- 第一次启动 PID 10372。
- 第二次重复 RUN 返回 0，提示系统已经在运行，PID 仍为 10372，未创建第二个实例。
- 正式 stop 返回 0，端口监听从 1 变为 0。
- 再次正式 RUN 完成时间 5.53 秒，PID 6224，/login 与 /platform 均为 200。
- Chromium 重启持久性检查 PASS：首次浏览器建立的 FollowUp 在重启后仍可见。
- 最终 stop 返回 0，端口 8000 监听 0，runtime/web.pid 不存在。

## 6. Failure Scenarios

| 场景 | 结果 | 退出码 | 恢复 |
|---|---|---:|---|
| 项目 Python 不存在 | 显示 PYTHON_NOT_FOUND、setup 建议和日志路径 | 10 | 仅隔离脚本副本，无项目改动 |
| 测试 DB 路径不存在 | 显示 DATABASE_NOT_FOUND 和检查建议 | 12 | 未访问或修改正式 DB |
| 端口被其他程序占用 | 显示 PORT_IN_USE_BY_OTHER_PROCESS | 13 | 临时占用进程已停止，端口监听 0 |

失败日志包含时间、Python、Project Root、阶段、错误类型与退出码。对 startup.log 的敏感模式扫描为 0；没有输出 .env、API Key、Token、Authorization 或密码。

## 7. Translation Acceptance

TRANSLATION_ACCEPTANCE=BLOCKED_PROVIDER_REQUIRED

AUTO_TRANSLATION_READY=false

TRANSLATION_PROVIDER_REQUIRED=true

当前中文阅读层、英文原文证据层和失败 fallback 仍正常：已有中文直接跳过加工；英文无中文结果时显示“中文加工暂时失败/待补充，可查看英文原文”的安全阅读层，原始 title、summary、content、source URL 和时间不被覆盖。没有自动生成中文标题或 100–250 字中文摘要，因此不声称 Translation PASS。

## 8. Translation Provider

TRANSLATION_PREFLIGHT=PROVIDER_NOT_AVAILABLE

| 检查 | 结果 |
|---|---|
| 独立 Translation Provider | 未发现 |
| TRANSLATION_PROVIDER 配置 | false |
| 既有 OpenAIProvider | 仅分析接口，当前不可用 |
| OPENAI_API_KEY 配置 | false |
| OpenAI SDK | 不存在 |
| EXTERNAL_AI_ENABLED | false |
| title_zh / summary_zh metadata 容器 | 已存在，可供未来 Provider 复用 |

本轮未购买 API、未接 OpenAI/DeepL、未下载本地模型、未新增 Provider、依赖、业务表、Model、Scheduler 或 AI 平台。Provider 缺失不影响 RUN，系统仍可正常使用。

## 9. Real Translation Samples

未执行三条自动翻译样本，因为没有可用 Provider。RC1 Chromium 回归使用的三条人工中文样本仍明确标记 MANUAL_CURATED_ACCEPTANCE_SAMPLE，仅存在于已删除的隔离数据库，用于验证页面连续性；它们不计入 AUTO_TRANSLATION_READY，也未写入 MVP_RC1_1_TRANSLATION_ACCEPTANCE.csv。

## 10. RC1 Golden Path Regression

真实浏览器由正式 RUN 启动的 127.0.0.1:8000 实例提供，而不是手工 uvicorn。

路径：/login → 工作台 → 中文情报 → Intelligence 33 → Organization → 返回情报 → 创建 FollowUp → 工作台我的待办。

| 指标 | 结果 |
|---|---:|
| Chromium | 151.0.7922.34 |
| Golden Path Click Count | 4 |
| Completion Time | 2.94 秒 |
| Guess Count | 0 |
| Context Switch Count | 2 |
| Console Error | 0 |
| Page Error | 0 |
| Network Failure | 0 |
| 非预期 404/500 | 0 |
| 横向溢出 | 0 |
| viewer 写操作 | 403 |

应用内浏览器控制初始化因 Windows ACL helper 失败一次；随后停止重试，使用项目现有 Playwright Chromium 完成同一正式 RUN 实例的真实验收。该工具通道异常不影响产品结果。

## 11. Tests

- RC1.1 定向测试：8/8 PASS。
- R2–R7.5 + RC1 + RC1.1 联合隔离回归：96/96 PASS。
- 新增覆盖：Root/Python resolution、DB 只读 preflight、端口冲突、stale PID、失败 pause、密钥脱敏、Provider 不可用、中文跳过和英文 fallback。
- 全量 pytest：15 failed / 3 errors / 1 skipped，与 RC1 历史基线完全一致；新增失败 0、新增 error 0。
- 历史集合仍为 migration idempotency、P4、v06i/v06j/v06k 旧契约债务，未在本轮扩大或修复。

## 12. Database Safety

正式数据库：data/app.db。

- 前后 SHA256：FED798300231934D170F104C4A4F4676AE90103C9888D29F6A0CD97AA6C1A3FB，完全一致。
- integrity_check=ok。
- 核心计数前后保持：Intelligence 31、People 44、Organizations 24、Projects 5、Subject Links 1、Resources 30、Matches 0、Opportunities 11、FollowUps 4、Relationships 25、Evidence 25。
- 正式 rc11 验收账号 0。
- 测试翻译、FollowUp、反馈和账号仅写入隔离副本；隔离目录已删除。
- pytest 前后正式 DB SHA256 完全一致，正式 Scheduler 运行 0、正式采集新增 0。

## 13. Remaining Problems

RUN_ACCEPTANCE=PASS

RUN_WINDOW_FLASH_EXIT=FIXED

TRANSLATION_ACCEPTANCE=BLOCKED_PROVIDER_REQUIRED

最终状态：MVP-RC1.1 BLOCKED — TRANSLATION_PROVIDER_REQUIRED

RUN 修复具备独立交付价值，按任务授权使用提交信息 MVP-RC1.1 Windows run stability。要完成 RC1.1，唯一外部决策是人工选择并配置一个 Translation Provider；本任务不代替用户选择，不进入 RC1.2、R8 或其他产品阶段。
