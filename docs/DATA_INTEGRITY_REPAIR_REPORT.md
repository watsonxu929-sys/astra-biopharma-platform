# 数据完整性修复报告

## 迁移信息

- 迁移ID：002_repair_domain_integrity
- 执行时间：2026-07-10
- 模式：dry-run（默认），可通过 --apply 执行

## 修复范围

### 孤立外键分析

**表**: `v06_timeline_entries`

发现 12 条记录引用不存在的 opportunity_id：

| 记录ID | opportunity_id | 事件类型 | 创建时间 | 描述摘要 |
|---|---|---|---|---|
| 1 | 1 | created | 2026-07-03 | 合作机会「Test Opp」已创建 |
| 2 | 1 | stage_change | 2026-07-03 | 阶段从「lead」变更为「contacted」 |
| 3 | 1 | follow_up | 2026-07-03 | 跟进记录：test follow-up |
| 4 | 1 | task | 2026-07-03 | 任务创建：Test Task |
| 23 | 12 | created | 2026-07-03 | 合作机会「Test Opp」已创建 |
| 24 | 12 | stage_change | 2026-07-03 | 阶段从「lead」变更为「contacted」 |
| 25 | 12 | follow_up | 2026-07-03 | 跟进记录：test follow-up |
| 26 | 12 | task | 2026-07-03 | 任务创建：Test Task |
| 27 | 13 | created | 2026-07-03 | 合作机会「Test Opp」已创建 |
| 28 | 13 | stage_change | 2026-07-03 | 阶段从「lead」变更为「contacted」 |
| 29 | 13 | follow_up | 2026-07-03 | 跟进记录：test follow-up |
| 30 | 13 | task | 2026-07-03 | 任务创建：Test Task |

**分析结论**：
- 所有孤立外键引用的都是测试数据（"Test Opp"）
- 引用的 opportunity_id（1、12、13）已从数据库中删除
- 没有唯一证据可以匹配到现有机会
- **处理方式**：保留待人工审核，不自动修复

### 资源迁移冲突

**冲突ID**: 1

| 字段 | 值 |
|---|---|
| 来源表 | v04f_club_offerings |
| 来源记录ID | 1 |
| 标题 | 会员可提供资源 |
| 状态 | pending |

**分析结论**：
- 标题过于通用，无法唯一匹配到正式资源
- **处理方式**：保留待人工审核，已登记到 `docs/manual_review/P1_RESOURCE_CONFLICT_REVIEW.md`

## Legacy映射统计

- 已建立映射数：6
- 映射表：`platform_entity_mappings`

## 自动修复情况

- 可自动修复：0 条
- 需要人工审核：13 条（12条孤立外键 + 1条资源冲突）

## 建议

1. 孤立外键记录涉及已删除的测试机会，建议人工确认是否需要保留或清理
2. 资源冲突需要人工确认映射关系或创建新记录
3. 迁移脚本已设置为默认dry-run，确保安全
