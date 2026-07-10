---
name: incremental-codex-delivery
description: Use to control Codex task scope, token budget, file inspection, verification, and delivery for incremental platform work; applies when a task risks broad scans, unrelated refactors, too many changed files, full regression by default, unnecessary ZIP packages, or multi-domain development in one turn.
---

# Incremental Codex Delivery

## 适用场景

- 平台化开发任务可能跨多个业务域。
- 用户要求控制额度、只做小范围修改、只跑专项验证。
- 需要判断是否生成补丁包或运行全量回归。
- 发现范围外问题但不应顺手处理。

## 不适用场景

- 用户明确要求全量回归、完整补丁或发布封板。
- 紧急安全修复必须扩大检查范围。
- 只读问答且不需要文件修改。

## 核心原则

- 一次任务只有一个核心目标。
- 默认只修改 3 到 10 个主要文件。
- 只检查明确文件和直接依赖。
- 默认不运行 `verify_all`。
- 小任务不生成 ZIP。
- 达到验收条件后立即停止。

## 执行步骤

1. 用一句话确认本次核心目标和非目标。
2. 列出预计读取文件和预计修改文件。
3. 先读直接依赖，不做无关全仓扫描。
4. 只实现核心目标，不顺手重构。
5. 运行最小专项验证。
6. 记录范围外问题，不在本任务处理。
7. 仅在阶段封板、用户要求或跨域风险较高时运行全量回归和生成补丁。

## 文件范围控制

- 默认读取目标模块、直接服务、直接模板、直接 API、直接验证脚本。
- 避免重复读取大型文件。
- 禁止扫描日志、备份、上传目录、虚拟环境和正式数据库内容。

## 数据兼容要求

- 小任务默认不改数据库。
- 需要迁移时先切换到数据库迁移流程，并说明备份和回滚。
- 不修改正式数据，不批量重写历史枚举。

## 禁止事项

- 禁止单次 Codex 任务同时开发多个业务域。
- 禁止无关全仓扫描。
- 禁止顺手重构其他模块。
- 禁止每个小任务都运行全量测试和生成完整补丁。
- 禁止发现范围外问题后直接扩大实现范围。

## 验收标准

- 修改范围与核心目标一致。
- 文件数和验证命令可解释。
- 专项验证通过或清楚记录未运行原因。
- 范围外问题只记录，不处理。
- 未生成不必要补丁包。

## 与其他 Skills 的协作关系

- 与 `platform-domain-architecture` 协作限制业务域范围。
- 与 `platform-taxonomy-governance` 协作限制分类扫描范围。
- 与 `identity-network-engine` 协作限制身份映射改造步长。
- 与 `verification-regression` 协作选择专项验证或阶段全量回归。
- 与 `patch-delivery` 协作仅在封板或用户要求时打包。

## 参考文件

- `references/domain-rules.md`
- `references/anti-patterns.md`
- `references/acceptance-checklist.md`
