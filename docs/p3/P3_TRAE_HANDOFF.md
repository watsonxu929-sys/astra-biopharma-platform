# P3 Trae 交接

后端路由和页面骨架已存在：

- `/network/governance`
- `/network/entities/{entity_type}/{entity_id}`
- `/network/products/{product_id}`
- `/network/relationship-candidates`
- `/network/relationships/{id}`
- `/network/paths`
- `/network/graph`
- `/network/connection-candidates/{person_id}`

## Trae 范围

1. 关系图谱节点颜色、尺寸、图例和关系线展示。
2. 基本筛选、分页、排序、空状态和中文状态映射。
3. 人物/机构/产品/项目关系卡片和时间线视觉展示。
4. 合并影响预览与历史页面布局。
5. 移动端适配及真实浏览器点击验收。
6. 旧模板 `status_label` 小问题。

## 不得改变

- Web/API 必须继续调用 P3 服务层。
- 不在模板写跨表业务逻辑。
- 弱匹配不得自动合并；合并必须人工审批。
- 未审核、restricted/private 关系不得泄露。
- 不自动联系、发消息或创建机会。
- 不新建第二套 Person/Organization，也不引入 Neo4j。

建议使用 `C:\tmp\p3_entity_network_pilot.db` 验收并设置 `APP_DB_PATH`，不要连接正式库执行写操作。
