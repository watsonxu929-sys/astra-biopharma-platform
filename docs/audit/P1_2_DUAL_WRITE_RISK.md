# P1.2-A 双重写入风险审计

## 风险列表

| 业务动作 | 新写入入口 | 旧写入入口 | 是否双写 | 风险等级 | 推荐停用 | 优先级 |
|---|---|---|---|---|---|---|
| 会员注册/绑定 | v04f_club_memberships | v05a_users | 是 | 中 | 停用v05a_users写入 | P2 |
| 情报创建 | v06_intelligence_items | v04d_intelligence | 否 | 低 | 已迁移完成 | P4 |
| 资源创建 | v06_market_resources | v04f_club_offerings | 是 | 中 | 停用v04f_club_offerings写入 | P2 |
| 商机创建 | v06_cooperation_opportunities | v05c_opportunities | 否 | 低 | 已迁移完成 | P4 |
| 人物创建 | v06_subjects | v04a_persons | 否 | 低 | 已迁移完成 | P4 |
| 机构创建 | v06_subjects | v04b_organizations | 否 | 低 | 已迁移完成 | P4 |
