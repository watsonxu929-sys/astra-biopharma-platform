# P3 合并与回滚

## 状态机

`preview → pending_approval → merged → rolled_back`；预览也可拒绝，失败状态保留审计。

1. `preview` 读取源/目标主体，列出别名、公开标识和 P3 正式关系影响，并检查标识冲突，不写主档。
2. 发起人使用 edit_data 提交审批。
3. 审核人使用 review_data 执行；事务迁移 P3 别名、标识和关系端点，创建旧 ID 重定向，并软停用来源主体。
4. 回滚按 `rollback_payload_json` 恢复端点、别名、标识和来源主体状态，停用重定向。

## 安全约束

- 未进入 pending_approval 不得执行。
- 源与目标类型必须一致且均存在。
- 来源主体不物理删除；正式确认字段不被预览覆盖。
- 同类型公开标识冲突会阻断合并。
- 所有关键动作写入 `p3_relationship_audit`。
- 旧 `relations` 不批量重写；旧 ID 经 redirect 解析，避免破坏兼容读取。

回滚即本轮的误合并拆分恢复机制。更复杂的一对多拆分需要独立人工方案，不在 P3 自动执行。
