# TASK-P3：主体治理、产业关系网络与路径引擎

状态：Codex 后端框架、隔离试点与自动化测试完成；等待 Trae 前台精修和真实业务人工核验。

## 已交付

- 006 增量迁移和 12 张 P3 表；迁移默认 dry-run、支持备份、事务、幂等及报告。
- 复用 Person/Organization/Project，新增必要 ProductAsset 兼容主档。
- 别名、公开标识、强/中/弱解析候选、合并预览/审批/重定向/回滚。
- 43 个类型化关系、结构化证据、时态/冲突候选和归档审计。
- 1—3 跳路径、基础图视图和不执行联系动作的连接候选。
- Web/API 同服务入口、隔离试点、验证脚本和 P3 自动化测试。

## 验证顺序

1. `python scripts/run_p3_pilot.py`
2. `python scripts/verify_p3_entity_relationship_network.py`
3. `python -m compileall app scripts tests`
4. 编码、P0/P1/P2 验证脚本
5. `python -m pytest tests -q`

正式迁移必须先运行 dry-run、核对报告和备份后再人工决定是否 apply。本任务没有对正式库执行 006。

## 边界

未开始俱乐部、商务协同、P4、Neo4j、OpenSearch 或 PostgreSQL 迁移；没有自动合并主体、联系推荐对象或创建商机。
