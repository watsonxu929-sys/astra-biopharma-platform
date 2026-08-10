# MVP-RC1 迁移恢复清单

## 恢复结论

现存 Git 仅包含 000–008，存量数据库已包含 009–011 结构。本清单记录的是根据 `data/backups` 中迁移前数据库与当前 `data/app.db` 的只读 Schema 对比恢复出的迁移事实，不声称恢复了遗失的历史业务提交。

恢复后的正式迁移链为：

- `009_intelligence_production_loop`
- `010_intelligence_opportunity_loop`
- `011_feedback_outcome_loop`

迁移器默认目标为 011；从已知 pre-009 存量基线恢复时使用 `--start 009 --target 011`，避免把历史 000–008 漂移误当作本次任务的修复对象。

## 结构事实

009 恢复情报生产闭环所需的主体关联、工作流事件及审核/发布追踪结构。`core_intelligence_workflow_events` 的 `intelligence_item_id`、`collection_item_id`、`to_status`、`actor_username` 保持非空约束，并保留 `(intelligence_item_id, id)` 索引。

010 在既有正式表上增加情报、供需、匹配与机会之间的来源字段和唯一性索引，包括：

- `v06_market_resources.source_intelligence_id`
- `p4_resource_match_candidates.opportunity_id`
- `v06_opportunities.source_intelligence_id`
- `v06_opportunities.source_demand_resource_id`
- `v06_opportunities.source_supply_resource_id`
- `v06_opportunities.source_match_id`
- `v06_follow_ups` 的下一步、联系结果和阶段字段

011 在既有正式表上增加匹配意向、商务结果、关闭信息、关系回流和证据来源字段，包括：

- Match 的 `intention_status`、结构化原因、操作者和时间
- Opportunity 的 `outcome_status`、结果说明、关闭人/时间、关系 ID
- FollowUp 的下一次跟进时间
- Canonical Relationship 的来源机会、来源匹配、来源情报和置信等级

## 安全能力

统一入口：

```bat
.venv\Scripts\python.exe scripts\migrate_db.py plan --database <copy.db> --start 009 --target 011
.venv\Scripts\python.exe scripts\migrate_db.py upgrade --database <copy.db> --start 009 --target 011
```

保障：

- plan/status 只读；
- 正式数据库必须显式 `--confirm-formal`；
- 应用前创建 SQLite 在线备份并校验 `integrity_check`；
- 每步在事务中执行；
- 不新增外键错误；
- 失败自动从备份恢复；
- 成功历史带迁移校验和，重复执行返回 `up_to_date`；
- 已存在且结构完整的 009–011 可安全 adoption，不重复改表。

## RC1 预演结果

- pre-009 副本：`MVP_RC1_RECOVERY/mvp_rc1_009_011_rehearsal.db`
- 009：成功
- 010：成功
- 011：成功
- 第二次执行：`up_to_date`
- 注入 010 失败：自动恢复成功
- 失败前后逻辑 SHA256：`54415e911228ff761ff2870eb054f4149bdaf41f90d7e85247326e80d5da9e5d`
- `integrity_check`：`ok`
- Opportunity：11 条保持
- 历史外键问题：30 项，前后不变
- RC1 工作数据库 SHA256：`A28E2DE7B71E608931088B262D6304B0426954CE0C064185C4133A38ED63D138`，未应用迁移、未写入验收数据

## 已知边界

000–008 的空库链仍存在既有 007/008 字段顺序漂移测试失败；这属于修改前已存在的历史迁移问题。本轮只对经真实备份验证的 pre-009 → 011 恢复链负责，不伪造或重写更早历史。
