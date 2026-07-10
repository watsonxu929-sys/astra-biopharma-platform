# 测试指南

## 测试体系

本项目采用pytest作为测试框架，建立最小回归测试体系保护P0/P1核心链路。

## 测试结构

```
tests/
├── conftest.py          # 测试夹具和数据库保护
├── test_app_import.py   # 应用导入和路由注册测试
├── test_p1_migration_idempotency.py  # P1迁移幂等性测试
├── test_domain_integrity_repair.py   # 数据完整性修复测试
├── test_opportunity_confirmation.py  # 机会确认流程测试
└── test_real_database_protection.py  # 正式数据库保护测试
```

## 运行测试

```bash
# 运行所有测试
python -m pytest tests/ -q

# 运行特定测试文件
python -m pytest tests/test_app_import.py -q

# 运行特定测试用例
python -m pytest tests/test_app_import.py::test_fastapi_app_importable -q
```

## 测试数据库规则

1. 所有测试使用临时数据库副本，不修改正式数据库
2. 测试前后计算正式数据库SHA256，发现变化则测试失败
3. 测试结束后自动清理临时数据库
4. 测试不访问互联网
5. 测试不依赖外部SaaS

## 测试夹具

### temp_database

创建正式数据库的临时副本供测试使用。

### temp_db_conn

提供临时数据库的sqlite3连接。

### protect_real_database

自动夹具，确保正式数据库在测试过程中未被修改。

### live_db_path

正式数据库路径。

### live_db_sha256

正式数据库的SHA256哈希值（测试前计算）。

## 测试覆盖范围

### 应用导入测试
- FastAPI应用可以导入
- 路由能够注册
- 应用导入不会自动修改数据库结构
- 核心服务模块可以导入

### P1迁移幂等性测试
- 001迁移可以在副本运行
- 连续运行两次结果一致
- 不重复创建legacy映射
- 不重复新增字段或记录

### 数据完整性修复测试
- 002默认是dry-run
- dry-run不修改数据库
- 有唯一证据的记录可在副本上修复
- 有歧义的记录不会自动修复
- 事务失败时回滚

### 机会确认测试
- Recommendation、MatchCandidate、Lead不能直接成为正式Opportunity
- 正式Opportunity必须有显式人工确认字段
- 确认人和确认时间必须保存

### 正式数据库保护测试
- pytest运行前后正式数据库SHA256完全一致
- 测试代码不会把正式数据库作为写入目标

## 注意事项

1. 运行测试前确保已安装pytest
2. 测试环境需要完整的项目依赖（fastapi、sqlalchemy等）
3. 测试在Windows环境下运行时可能遇到文件权限问题（临时文件清理）
4. 测试不会删除真实业务数据
5. 测试不会修改生产账号密码
