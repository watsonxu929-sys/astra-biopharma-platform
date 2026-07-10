# 能力复用地图

原文件已发生不可逆问号替换，历史备份同样损坏。本页依据实际代码重建。

- 主体：复用 `organizations`、`people`、`projects`，禁止模块自建主体表。
- 身份：复用 `v05a_users`、Membership 与身份链接服务；User、Person、Membership 分离。
- 情报：复用采集、加工、审核、信号、报告和统一情报服务。
- 资源：新写入使用 `UnifiedResourceService`；旧 resources/needs/offerings 兼容读取。
- 机会：新写入使用 `UnifiedOpportunityService`；推荐、匹配、Lead 只能作为候选来源，正式机会须人工确认。
- 公共能力：复用权限、隐私过滤、审计、搜索、文件、任务和调度。

详表见 [CAPABILITY_MAP.md](CAPABILITY_MAP.md)。
