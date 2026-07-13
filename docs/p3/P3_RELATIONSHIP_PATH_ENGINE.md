# P3 关系路径引擎

`RelationshipNetworkService` 在 SQLite 已审核关系上执行受限 BFS，不引入 Neo4j。

## 能力

- 任意 Person、Organization、ProductAsset、Project 两点之间 1—3 跳路径。
- 可限定关系类型、仅当前关系、包含历史关系或指定 `as_of` 日期。
- 返回最短优先的可信路径、每条边、路径最低置信度及证据详情链接。
- 图视图按中心节点展开 1—3 层。

## 硬限制

默认/最大深度 3、返回路径数 20、访问节点数默认 200（服务硬上限 500）、查询时间 750ms。路径内不允许重复节点；达到时间或节点上限时返回 `truncated=true`。

默认只读取 approved、current、public/internal 关系。restricted/private 仅在调用方明确拥有权限并传入 `include_private` 时读取。未审核候选不会进入网络。

## 连接候选

`ConnectionRecommendationService` 仅考虑 2—3 跳且每条边都有结构化证据的路径；一跳已直接连接者排除。输出理由、路径、证据关系 ID、置信度和风险提示，不发消息、不联系对方、不创建机会。
