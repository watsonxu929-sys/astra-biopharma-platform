# 旧模型兼容与下线计划

## 正式写入

- 身份：User 使用 `v05a_users`，Person/Organization 使用主体模型，Membership 使用 `v04f_club_memberships` 并经会员链接服务写入。
- 情报产品：使用统一情报服务；发布记录保留 `source_record_type`、`source_record_id`、`evidence_hash`。
- 资源：使用 `UnifiedResourceService` 写入 `v06_market_resources`。
- 机会：使用 `UnifiedOpportunityService` 写入 `v06_opportunities`；没有 `human_confirmed=True` 一律拒绝。
- 跟进/任务：只通过统一机会服务写入 `v06_follow_ups`、`v06_collab_tasks`。

## 兼容读取

`resources`、`v04f_club_needs`、`v04f_club_offerings`、旧 Lead/Action/Recommendation、v05 信号/报告继续读取，不删除旧表。v04/v05 页面暂不重写。

## 禁止继续扩展

`v05d_member_accounts` 不扩展为第二套用户；旧资源、Need、Offering、Lead 页面不得增加新的跨域业务规则；推荐/匹配/Agent 入口不得直接生成正式 Opportunity。

## 下线条件

只有在映射率、冲突清单、旧页面替换、全量编译和核心冒烟全部通过后，才可单独任务评估停止旧写入。表删除不在当前范围。
