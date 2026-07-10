# 生物医药产业情报系统项目规则

本仓库是 Windows 本地运行的生物医药产业情报系统。主系统服务于公开情报沉淀、主体档案、人物、项目、资源、事件、关系、行动任务、审核、结构化接入、监测和推荐；Q-BAY 俱乐部只是其中一个业务板块，不应反向主导整体架构。

## 技术栈

- FastAPI
- SQLAlchemy
- Jinja2
- SQLite 开发环境
- 原生 JavaScript 和现有 CSS
- Windows 批处理脚本作为本地运行、迁移、验证和维护入口

## 架构原则

- 业务逻辑优先进入 `app/services/`。
- 网页路由和 `/api/v1` API 应调用同一套服务逻辑。
- 不在模板或路由中复制复杂业务规则。
- 不建立第二套企业、人物、项目、事件、资源、会员、活动或情报监测主体模型。
- 不建立 API 专用的重复数据表；需要新增接口时复用既有模型、服务和权限。
- 增量修改，先做小范围扫描和最小可验证变更，避免全仓无关重构。
- 新功能交付时同时考虑迁移、验证、回滚和人工验收。

## 数据安全

- 不删除、不重建、不清空 `data/app.db`。
- 禁止对正式业务表执行 `DROP TABLE` 或破坏性重建。
- 数据库变更前必须备份，优先使用现有迁移工具链。
- 不修改既有主键、业务编号和已确认主体字段。
- 不自动合并同名人物或机构。
- 不自动覆盖正式主体字段；不确定内容进入候选、审核或人工确认流程。
- 写入、审核、权限和隐私相关改动必须保留审计思路，避免暴露密码、令牌、完整敏感联系方式、数据库路径和堆栈信息。

## 开发方式

- 开发前先定位相关模型、路由、服务、模板、API 和脚本，控制 `rg` 扫描范围。
- 优先复用 `app/services/`、`app/api/v1/`、`app/templates/`、`scripts/`、`tools/windows/` 中的既有模块。
- 检查循环 import、N+1 查询、模板变量缺失、死链接、权限遗漏和隐私过滤遗漏。
- Windows 脚本保持可双击运行、失败停留、日志可读。
- 控制 Codex 额度：优先读关键文件，不把 README 或业务代码整段复制进规则或 Skill。

## 常用命令

```bat
setup_windows.bat
migrate_all_windows.bat
verify_all_windows.bat
run_windows.bat
project_tools_windows.bat
backup_windows.bat
run_monitoring_once_windows.bat
```

历史迁移、验证、演示、诊断和维护入口保留在 `tools/windows/archive/`、`tools/windows/demo/`、`tools/windows/diagnostics/`、`tools/windows/maintenance/` 和 `tools/windows/reports/`。Python 迁移、验证、导入、备份和监测脚本保留在 `scripts/`。

## 交付规则

- 不交付 `.venv/`、`venv/`、`logs/`、`data/app.db`、`data/backups/`、`data/*.db*`、`__pycache__/`、`.env` 或本地临时文件。
- 交付补丁时提供完整覆盖目录或下载包说明，不要求用户零散复制代码片段。
- 补丁说明必须包含覆盖步骤、迁移顺序、验证顺序、启动方式、回滚方式和人工验收场景。

## 项目级 Skills

项目级 Skill 位于 `.skills/`。`AGENTS.md` 记录长期仓库规则；`.skills/*/SKILL.md` 记录可组合、可执行的工作流。需要特定流程时，显式调用对应 Skill，并在执行前重新核对仓库真实文件和命令。
