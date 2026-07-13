# P4 目标俱乐部模型

P4 不建立第二套 User、Person、Organization、Membership、Event、MarketResource 或 Opportunity。Q-BAY 是 community 业务板块，复用平台正式主体。

| 业务对象 | 正式/兼容模型 | P4 增量 |
|---|---|---|
| 会员申请与资格 | `v04f_club_applications`、`v04f_club_memberships` | 生命周期字段、`p4_membership_history`、审计与领域事件 |
| 活动 | `events` + `v05c_club_event_profiles` | 运营状态、报名窗口、审核字段和试点标识 |
| 报名与出席 | `v05c_club_event_registrations`、`v05c_club_event_participation` | 统一状态、正式会员关联、Token 签到与审计 |
| 活动反馈 | 参与记录兼容读取 | `p4_event_feedback` 保存结构化反馈 |
| 供需资源 | `v06_market_resources` | 活动来源、审核、试点标识；旧供需表只读 |
| 匹配 | 受控候选 | `p4_resource_match_candidates`，不自动联系 |
| 会后关系 | P3 正式关系人工审核边界 | `p4_event_relationship_candidates`，同场不等于认识 |
| 线索 | 候选层 | `p4_club_lead_candidates`，不自动创建 `v06_opportunities` |

网页路由和 `/api/v1` 共用 `app/services/club_operations_service.py`。迁移 `007_club_operations_mvp.py` 仅做增量建表/加列，默认 dry-run、应用前备份、事务失败回滚且可重复执行。
