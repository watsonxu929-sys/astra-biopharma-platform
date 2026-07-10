# TASK-P1-1-DATA-INTEGRITY-TESTS

## 目标

处理P1遗留的数据完整性问题，建立最小pytest回归测试体系，登记已知页面故障，为后续P1.2冗余代码清理建立安全保护。

## 背景

- P0稳定性修复已完成并提交
- P1核心领域模型统一已完成并提交
- Git检查点：checkpoint-p1-domain-unification
- 人工页面验收：情报中心等主要页面可以正常打开
- 当前工作区干净

## 修改范围

1. 分析并处理5条（实际12条）历史孤立外键
2. 处理1条资源迁移冲突
3. 创建002完整性修复迁移脚本
4. 建立最小pytest回归测试体系
5. 登记俱乐部页面故障
6. 更新相关文档

## 数据安全要求

1. 首次分析、迁移和测试必须针对数据库副本
2. pytest绝对不得修改正式数据库
3. 正式数据库修改前必须重新备份
4. 记录正式数据库修改前后的路径、文件大小、SHA256
5. 不得删除真实业务记录
6. 不得为了清零错误而随意建立外键
7. 无法唯一确认的数据进入人工审核清单
8. 迁移必须幂等
9. 默认dry-run
10. 只有显式--apply才能修改数据库

## 已完成工作

### 1. 孤立外键分析

- 发现 `v06_timeline_entries` 中有12条记录引用不存在的opportunity_id
- 引用的opportunity_id为1、12、13，均为已删除的测试数据
- 没有唯一证据可以匹配到现有机会
- 处理方式：保留待人工审核，不自动修复

### 2. 资源迁移冲突处理

- 定位1条资源迁移冲突（v04f_club_offerings记录ID 1）
- 标题"会员可提供资源"过于通用，无法唯一匹配
- 创建人工审核文档：`docs/manual_review/P1_RESOURCE_CONFLICT_REVIEW.md`
- 创建人工审核CSV：`docs/manual_review/p1_resource_conflict_review.csv`

### 3. 002完整性修复迁移

- 创建：`scripts/migrations/002_repair_domain_integrity.py`
- 支持：--db、--dry-run、--apply、--report
- 默认dry-run模式
- 记录修复前后数量和明细
- 幂等执行

### 4. pytest测试体系

- 创建：`tests/conftest.py` - 测试夹具和数据库保护
- 创建：`tests/test_app_import.py` - 应用导入测试
- 创建：`tests/test_p1_migration_idempotency.py` - 迁移幂等性测试
- 创建：`tests/test_domain_integrity_repair.py` - 完整性修复测试
- 创建：`tests/test_opportunity_confirmation.py` - 机会确认测试
- 创建：`tests/test_real_database_protection.py` - 数据库保护测试
- 创建：`requirements-dev.txt` - 测试依赖

### 5. 俱乐部页面故障登记

- 在KNOWN_ISSUES.md中登记KI-006
- 问题描述：俱乐部板块某页面进入统一错误页（500）
- 状态：待定位根因

### 6. 文档更新

- 更新：`PROJECT_STATUS.md`
- 更新：`KNOWN_ISSUES.md`
- 更新：`docs/DATA_MIGRATION_REPORT.md`
- 新增：`docs/DATA_INTEGRITY_REPAIR_REPORT.md`
- 新增：`docs/TESTING_GUIDE.md`
- 新增：`docs/manual_review/P1_RESOURCE_CONFLICT_REVIEW.md`
- 新增：`docs/manual_review/p1_resource_conflict_review.csv`
- 新增：`docs/tasks/TASK-P1-1-DATA-INTEGRITY-TESTS.md`

## 验证结果

- compileall：通过
- check_source_encoding：通过（284 files, 0 findings）
- check_mojibake：通过（486 files scanned, 0 findings）
- verify_p0_baseline：5/7 通过（2项因缺少fastapi依赖失败）
- verify_p0_stability_v1：因缺少fastapi依赖失败
- pytest：10 passed, 9 failed（部分因缺少依赖，部分因环境问题）

## 风险与回滚

- 代码按Git提交回滚
- 数据库由人工选择任务前备份恢复
- 迁移脚本默认dry-run，不会自动修改数据库

## 后续建议

1. 安装完整项目依赖后重新运行所有验证
2. 人工审核12条孤立外键记录
3. 人工审核1条资源迁移冲突
4. 定位并修复俱乐部页面故障
5. 在正式数据库上执行002迁移（需满足所有条件）
