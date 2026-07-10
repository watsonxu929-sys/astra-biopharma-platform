# 项目级 Skills 使用指南

本仓库的项目级 Skills 位于 `.skills/`。它们用于把稳定的项目规则、脚本入口和重复开发流程沉淀成 Codex 可组合调用的工作流。

## Skills 目录

- `.skills/project-development/`：通用功能开发、改动前盘点、复用现有模块、完成后自检。
- `.skills/service-api-separation/`：网页路由、`/api/v1` JSON API 和 `app/services/` 共享服务分离。
- `.skills/safe-database-migration/`：所有数据库表、字段、索引和迁移脚本变更。
- `.skills/verification-regression/`：专项验证脚本、历史回归、临时数据库验证和验证结果汇报。
- `.skills/patch-delivery/`：手动覆盖补丁、打包目录、替换步骤、迁移验证顺序和回滚。
- `.skills/intelligence-collection/`：公开情报采集、监测任务、快照、哈希、去重、失败隔离。
- `.skills/intelligence-processing/`：情报加工、主体拆分、候选抽取、证据置信度、人工审核。

## AGENTS.md 与 Skills 的区别

`AGENTS.md` 是仓库级长期规则，记录项目定位、技术栈、数据安全、开发方式和交付约束。`.skills/*/SKILL.md` 是可组合工作流，记录某类任务如何执行、调用哪些现有脚本、如何验证、失败时如何处理。

公共规则放在 `AGENTS.md`，不要在每个 Skill 中大量重复。具体流程、输入、步骤和回执格式放在对应 Skill 中。

## 如何在 Codex 任务中调用

可以在任务中显式写出 Skill 名称，例如：

```text
使用 project-development、service-api-separation 和 verification-regression，
为只读健康检查 API 输出开发计划，不实际修改代码。
```

Codex 执行时应先读 `AGENTS.md`，再读被调用的 `.skills/<name>/SKILL.md`，并核对仓库真实文件和命令。

## 常见组合方式

- 新增普通功能：`project-development` + `verification-regression`
- 新增 API：`project-development` + `service-api-separation` + `verification-regression`
- 新增数据库字段或表：`project-development` + `safe-database-migration` + `verification-regression`
- 做正式补丁交付：相关开发 Skill + `verification-regression` + `patch-delivery`
- 新增采集任务：`intelligence-collection` + `intelligence-processing` + `verification-regression`
- 加工采集结果：`intelligence-processing` + `verification-regression`

## 调用示例

示例一：

```text
使用 project-development、safe-database-migration、verification-regression 和 patch-delivery Skills，
开发新的情报采集任务模块。
```

示例二：

```text
使用 service-api-separation Skill，
把主体查询网页路由改造成网页和 /api/v1 共用服务。
```

## 新增或修改 Skill

1. 先确认规则是否应进入 `AGENTS.md`，还是应进入某个 Skill。
2. 新增 Skill 时使用 lowercase hyphen-case 名称，并至少提供 `SKILL.md`。
3. `SKILL.md` frontmatter 只保留 `name` 和 `description`。
4. 引用仓库真实存在的文件和命令，不复制整段业务代码。
5. 只在确有必要时增加 `references/`、`scripts/`、`assets/`。
6. 更新后运行 Skill 基础校验，并做一个小型模拟任务。

## 如何验证 Skill 生效

基础格式校验：

```powershell
python C:\Users\Lenovo\.codex\skills\.system\skill-creator\scripts\quick_validate.py .skills\project-development
```

对每个 Skill 运行同样的校验。随后用一个不修改业务代码的小任务模拟调用，例如：

```text
检查当前项目中新增一个只读健康检查 API 时，应该调用哪些 Skills，并输出执行计划，不真正修改代码。
```

期望结果：

- 识别 `AGENTS.md`。
- 选择 `project-development`、`service-api-separation`、`verification-regression`。
- 不选择 `safe-database-migration`。
- 不提出重建数据库。
- 不要求复制业务逻辑。
- 给出符合当前仓库命令的验证计划，例如先检查 `/api/v1/health`，再按需运行 `verify_all_windows.bat`。
