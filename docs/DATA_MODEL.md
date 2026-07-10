# 数据模型边界

- User：`v05a_users`，只表示登录、安全状态、角色和最后登录；不等于 Person。
- Person：`people`，表示现实产业人物及画像；可关联多个 Organization。
- Membership：`v04f_club_memberships`，表示 Person 的俱乐部资格；通过 `person_id`、`organization_id`、`user_id` 映射，不复制人物主档。
- Organization：`organizations`，覆盖企业、机构、医院、高校、投资机构、服务商和园区。
- PersonOrganizationRelation：复用主体关系/关系服务，关系带类型、来源和时间范围；历史数据的时间字段完整性待业务确认。
- MarketResource：正式模型 `v06_market_resources`，`direction` 为 `demand` 或 `supply`；旧资源表只兼容读取和迁移。
- Opportunity：正式模型 `v06_opportunities`；FollowUp、TimelineEntry、CollabTask 均关联机会。候选不能自动转正式机会。
- 情报生命周期：CollectionSnapshot 映射监测快照/采集项；RawIntelligence 映射 `raw_intelligence`；FactCandidate 映射加工候选和审核项；IntelligenceProduct 映射正式情报项、信号和报告。发布内容必须保留来源 URL、哈希或证据引用。

旧表本次不删除；稳定 ID、旧 ID、新 ID 和冲突记录由迁移映射表保存。
