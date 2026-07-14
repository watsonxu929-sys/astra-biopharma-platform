# T3 产业关系页面审计报告

## 一、现有页面清单

### 1. 人物与机构
| URL | 入口 | 模板 | 状态 |
|-----|------|------|------|
| `/network/people` | 产业关系→人物发现 | platform/people_discovery.html | 可用，但筛选过多 |
| `/network/people/{person_id}` | 人物卡片→查看详情 | platform/person_card.html | 可用，基本信息完整 |
| `/network/organizations` | 产业关系→机构发现 | platform/organizations.html | 可用，列表视图 |
| `/network/organizations/{org_id}` | 机构卡片→查看详情 | platform/admin_organizations.html | 仅管理员可见 |

### 2. 关系网络
| URL | 入口 | 模板 | 状态 |
|-----|------|------|------|
| `/network/governance` | 产业关系→P3工作台 | p3_network.html (governance) | 可用，主体治理入口 |
| `/network/graph` | P3工作台→关系图谱 | p3_network.html (graph) | 可用，列表视图为主 |
| `/network/paths` | P3工作台→关系路径 | p3_network.html (paths) | 可用，需输入ID |
| `/network/entities/{type}/{id}` | 路径结果→主体详情 | p3_network.html (entity) | 可用，展示关系 |
| `/network/relationships/{id}` | 关系链接→详情 | p3_network.html (relationship) | 可用，展示证据 |

### 3. 人脉推荐
| URL | 入口 | 模板 | 状态 |
|-----|------|------|------|
| `/network/connection-candidates/{person_id}` | P3工作台→连接候选 | p3_network.html (connections) | 可用，需传入ID |
| `/network/recommendations/people` | API | - | 可用，返回推荐列表 |

### 4. 主体治理
| URL | 入口 | 模板 | 状态 |
|-----|------|------|------|
| `/network/governance` | 产业关系→P3工作台 | p3_network.html (governance) | 可用，消歧候选 |
| `/network/relationship-candidates` | P3工作台→关系审核 | p3_network.html (relationship_queue) | 可用，审核队列 |
| `/network/merges/{id}` | 合并预览→详情 | p3_network.html (merge) | 可用，合并预览 |

## 二、问题分析

### 1. 导航混乱
- 二级菜单分散在多个入口
- 没有统一的"产业关系"子菜单结构
- P3工作台入口不够直观

### 2. 页面功能问题
- **人物发现**：筛选条件过多，缺少统计概览
- **机构发现**：缺少卡片视图，信息展示不足
- **关系网络**：仅列表视图，无图形渲染
- **路径查询**：需要手动输入ID，不够友好
- **人脉推荐**：入口隐蔽，推荐理由不够直观

### 3. 数据展示问题
- 直接展示内部ID（如 `person_id`）
- 关系类型显示英文（如 `cooperation`）
- 证据链展示不够清晰
- 缺少数据完整度指标

### 4. 权限问题
- 部分页面无权限控制
- 敏感信息（联系方式）可能泄露

## 三、保留、合并、隐藏建议

### 保留
- `/network/people` - 人物列表（优化筛选）
- `/network/people/{person_id}` - 人物详情（增加关系展示）
- `/network/organizations` - 机构列表（增加卡片视图）
- `/network/paths` - 路径查询（优化界面）
- `/network/governance` - 主体治理（权限控制）

### 合并
- `/network/entities/{type}/{id}` 合并到人物/机构详情
- `/network/graph` 合并到关系网络页面
- `/network/connection-candidates` 合并到人脉推荐

### 隐藏（保留兼容）
- `/network/relationships/{id}` - 改为详情页内嵌展示
- `/network/merges/{id}` - 仅管理员可见

### 新增
- `/relationship-network` - 统一关系网络入口
- `/relationship-network/timeline` - 关系时间线
- `/people/{id}/relationships` - 人物关系详情
- `/organizations/{id}/relationships` - 机构关系详情
- `/recommendations` - 人脉推荐入口

## 四、优先级排序

1. **高优先级**：收敛导航、人物与机构页面优化、关系网络统一入口
2. **中优先级**：路径查询优化、人脉推荐界面化、主体治理权限控制
3. **低优先级**：图形渲染、时间线视图、高级筛选

## 五、技术约束

- 不得新建数据库表
- 复用现有服务（CanonicalRelationshipService, RelationshipNetworkService等）
- 使用现有模板系统（Jinja2）
- 保持向后兼容