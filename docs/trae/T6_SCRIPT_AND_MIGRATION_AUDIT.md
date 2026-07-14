# T6 脚本与迁移审计报告

## 一、T5.1新增脚本清单

### 已提交脚本

| 文件 | 状态 | 用途 |
|------|------|------|
| scripts/migrations/008_business_collaboration_mvp.py | ✅ 正式迁移 | 创建P5增量表 |
| scripts/manual_recovery/add_p5_opportunity_columns_DEPRECATED.py | ⚠️ 已归档 | 临时补列脚本 |
| scripts/manual_recovery/add_p5_follow_up_columns_DEPRECATED.py | ⚠️ 已归档 | 临时补列脚本 |

### 未提交脚本（验收专用）

| 文件 | 用途 | 操作目标 |
|------|------|---------|
| scripts/create_acceptance_db.py | 创建验收数据库 | data/acceptance/t5_1_mvp.db |
| scripts/run_acceptance_migrations.py | 执行验收迁移 | 验收库 |
| scripts/test_business_closure.py | 业务闭环测试 | 验收库 |
| scripts/create_additional_test_data.py | 创建验收数据 | 验收库 |
| run_acceptance_windows.bat | 验收环境启动 | 验收库 |

### 审计结论

1. **008迁移**：作为正式可保留迁移入口，包含完整的P5表创建逻辑，支持幂等执行
2. **临时补列脚本**：已被008迁移覆盖，已移入manual_recovery并标记DEPRECATED
3. **验收脚本**：所有脚本默认指向验收库，不允许操作正式库
4. **无重复修改**：同一结构只在008迁移中定义一次

## 二、迁移脚本审查

### 008_business_collaboration_mvp.py

#### 创建的表

1. **v04f_lead_records** - 线索记录表（支持现有表补列）
2. **p5_opportunity_participants** - 机会参与方
3. **p5_opportunity_stage_history** - 阶段历史
4. **p5_opportunity_sources** - 机会来源
5. **p5_opportunity_meetings** - 会议记录
6. **p5_opportunity_artifacts** - 文件材料
7. **p5_opportunity_risks** - 风险记录
8. **p5_domain_events** - 领域事件
9. **p5_operation_audit** - 操作审计

#### 幂等性验证

- ✅ CREATE TABLE IF NOT EXISTS
- ✅ CREATE INDEX IF NOT EXISTS
- ✅ ALTER TABLE ADD COLUMN 带存在检查
- ✅ 重复执行无错误

## 三、.gitignore更新

已添加排除项：

- data/acceptance/
- data/*.db
- data/*.db-shm
- data/*.db-wal
- logs/*
- backups/
- .env

## 四、安全检查

- ✅ 验收脚本不指向正式库
- ✅ 无硬编码密码或密钥
- ✅ 临时数据库路径已排除Git
- ✅ 日志目录已排除Git

## 五、风险提示

1. 008迁移尚未在正式库执行（符合计划）
2. 验收库数据为测试数据，不可用于生产
3. 临时补列脚本已归档，不再维护
