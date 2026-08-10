# MVP-RC1 Canonical 数据契约

## 总原则

RC1 执行 `Single Write + Compatible Read`：正式业务写入只有一套目标表；旧表和旧页面可继续读取，但不得为黄金链产生新的正式记录。网页路由和 `/api/v1` 必须调用同一套 `app/services/` 业务逻辑。

## A. Canonical 正式写

| 业务对象 | 唯一正式表 | 写入规则 |
| --- | --- | --- |
| Intelligence | `v06_intelligence_items` | 仅已发布情报进入黄金链 |
| Person | `people` | 不自动合并同名人物 |
| Organization | `organizations` | 不覆盖已确认主体字段 |
| Project | `projects` | 复用现有项目主键 |
| IntelligenceSubjectLink | `core_intelligence_subject_links` | operator 人工确认，幂等写入 |
| Relationship | `p3_canonical_relationships` | 仅 won 且有证据时写入 |
| RelationshipEvidence | `p3_relationship_evidence` | 与正式关系同事务写入 |
| Resource | `v06_market_resources` | 保留来源情报与正式主体 |
| MatchCandidate | `p4_resource_match_candidates` | 确定性规则与人工确认 |
| Opportunity / Outcome | `v06_opportunities` | 保留来源匹配、供需和情报 |
| FollowUp | `v06_follow_ups` | 记录事实、下一步和下次跟进 |
| Task | `v06_collab_tasks` | 归属唯一 Opportunity |

## B. Compatibility 只读

以下存量业务表可作为历史读取来源或适配输入，不作为 RC1 黄金链新写入目标：

- `raw_intelligence`
- `resources`
- `relations`
- `v04f_club_needs`
- `v04f_club_offerings`
- `v04f_club_matches`
- `v04f_lead_records`
- P5 旧线索、机会、任务和参与方表

正式用户入口不得引导用户在这些表中建立与 Canonical 重复的新业务对象。

## C. 暂时保留

Q-BAY 独有业务继续保留现有表和服务：会员申请、会员身份、活动、报名、签到、反馈。采集、加工、审核、报告和主体治理的存量支撑表也继续保留。本轮不删除、不重建、不批量迁移这些数据。

## D. 待后续治理

重复的旧 Need/Offering/Match/Lead/Opportunity/Relationship 写入口、旧命名页面和不再承担正式写入的内部模块，后续按使用证据逐项下线。RC1 不做大规模删除，也不清理 30 项历史外键问题。

## 强制不变量

- Match 未人工标记“感兴趣”不得转 Opportunity。
- 相同供需组合和相同 Match 转机会必须幂等。
- `lost`、`paused` 或证据不足的 `won` 不得创建 Canonical Relationship。
- 正式合作关系必须能回溯到 Opportunity、Match、Intelligence 和证据。
- viewer 的所有黄金链写请求由后端返回 403。
- 正式表已有 11 条 Opportunity 不得被验收脚本修改或重复生成。
