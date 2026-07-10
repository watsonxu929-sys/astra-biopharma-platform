# 数据迁移报告

迁移：`scripts/migrations/001_core_domain_unification.py`。

## 正式库执行结果

- 执行时间：2026-07-10。
- 模式：先 `--dry-run`，再 `--apply`。
- 新增字段：16；删除/重命名字段：0；旧表删除：0。
- 记录现状：User 1、Person 44、Organization 24、Membership 2、RawIntelligence 1、IntelligenceProduct 20、历史 Resource 8、历史 Offering 1、MarketResource 22、Opportunity 11、FollowUp 4、CollaborationTask 4。
- 确定映射：6。
- 冲突：1 条历史资源/供给记录无法唯一匹配，已写入 `platform_migration_conflicts`，状态 `pending`。
- 未迁移：1；未静默覆盖。
- 原有孤立外键：`v06_timeline_entries` 5 条，迁移前后未增加，待人工修复。

## 备份与回滚

一致性备份：`data/backups/app_before_001_core_domain_unification_20260710_110104_386155.db`；SHA256 `0E9743F46294FDACFE39F88074686704D08EE0E88FF0EC74025F5D0AB2455F45`，完整性检查为 `ok`。

回滚需要停止服务，由人工确认后用该备份整体恢复；脚本不提供自动破坏性回滚。代码可回滚 P1 Git 提交，但数据库新增列可以保留，不影响旧代码读取。

## 幂等验证

在正式库副本连续执行两次 `--apply`，映射和冲突数量保持稳定；P1 验证 7/7 通过。
