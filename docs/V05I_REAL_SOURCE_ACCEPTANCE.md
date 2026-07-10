# v0.5I 真实来源验收说明

真实网络验收不进入默认 `verify_all`。默认验证只使用 inline 本地 HTML 和临时 SQLite。

## 执行条件

- 来源是公开页面。
- 配置在 `config/pilot_sources.yaml`。
- `allow_real_run=true`。
- 显式执行 `--confirm`。
- 单次不超过 20 条。
- 尊重 robots。
- 不绕过登录、验证码或付费墙。

## 命令

```powershell
.venv\Scripts\python.exe scripts\pilot_real_sources.py --source-id 1
.venv\Scripts\python.exe scripts\pilot_real_sources.py --source-id 1 --confirm
```

## 验收类别

- 企业新闻栏目：发现链接、抓取正文、去重、候选进入审核。
- 管理团队页：识别 team 页面，多人物拆分，栏目标题不作为人物。
- 产品管线页：识别项目/产品，不自动覆盖阶段。
- 政府或园区栏目：静态分页，政策或招商事件分类，多企业不合并。
- RSS：按 GUID/link 去重。
- 动态页面：只有配置为 Playwright 且确认时才尝试；不可用时记录错误，不影响普通 HTTP 来源。
