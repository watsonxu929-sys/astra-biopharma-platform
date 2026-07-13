# P3 目标主体模型

## 边界

P3 继续以 `people`、`organizations`、`projects` 为人物、机构和项目正式主档。`v05a_users` 是登录身份，Membership 是资格或组织关联，二者都不替代 Person。旧 `relations` 保留兼容读取，不删除、不批量改写。

仓库原有的 `p2_intelligence_product_candidates` 表示情报产品映射，`v05b_media_assets` 表示媒体文件，均不能表达药物、器械、技术平台和研发管线。因此迁移 006 增加兼容层 `p3_product_assets`，作为当前唯一的 ProductAsset 主档；它与 Project 严格分离。

## 四类主体

| 主体 | 正式存储 | 稳定标识 | P3 行为 |
|---|---|---|---|
| Person | `people` | `external_id` | 复用；同名默认弱匹配 |
| Organization | `organizations` | `external_id` | 复用；不把品牌、院区或会员文本自动建成机构 |
| ProductAsset | `p3_product_assets` | `external_id` | 新增必要兼容主档；支持 drug/device/platform/pipeline 等类型 |
| Project | `projects` | `external_id` | 复用；不得与 ProductAsset 合并建模 |

## 辅助治理表

- `p3_entity_aliases`：类型化别名、语言、有效期、来源、证据及审核状态。
- `p3_entity_external_identifiers`：公开权威标识；数据库约束拒绝敏感标识。
- `p3_entity_resolution_candidates`：从情报、研究、导入和手工入口产生的解析候选。
- `p3_entity_redirects`、`p3_entity_merge_records`：旧 ID 重定向、影响预览、事务合并和回滚。

正式主档字段不会被候选静默覆盖。创建新主体、匹配、合并和关系转正均保留人工审核边界。

## 兼容策略

旧关系继续读取；P3 新关系写入 `p3_canonical_relationships`。P3 页面和 `/api/v1/entity-network` 使用同一服务层。后续迁移只能通过显式脚本逐批完成，禁止全量自动合并历史主体。
