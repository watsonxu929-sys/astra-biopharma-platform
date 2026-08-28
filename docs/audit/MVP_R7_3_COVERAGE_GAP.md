# MVP-R7.3 Priority Subject Source Coverage Gap

记录日期：2026-08-28（Asia/Shanghai）

正式基线：`release/mvp-rc1.2` / `4448436d9858bc848c0f4701f487e2f31c352ee4`。正式数据库：`data/app.db`；R7.3 前 SHA256 `FED66707481C994A2BF012AA95DC1F9D3B625F5583A36132D56F16CF355410A2`；`integrity_check=ok`。

## Why coverage was 1 / 13

13 个 Priority Subject 中只有 8 个 Organization；5 个 Person 不适合按“企业官网 Source”监测。8 个 Organization 中，只有 Q-BAY（上海）生物医药孵化器已有经过运营验证且绑定主体的 ACTIVE Source。其余档案没有 approved `official_domain`、已确认 Source domain、Relationship Evidence 官网链接或官方 Intelligence 链接。6 个 Organization 名称还是泛称、匿名名或历史网络描述，不能据此猜测域名。

| Subject | Organization ID | Current Website | Official Domain Known | Current Source | Source Coverage | Gap Reason | Resolution |
|---|---|---|---|---|---|---|---|
| Q-BAY（上海）生物医药孵化器 | ORG-20260626-000001 | 已确认 Source 页面 | YES（confirmed Source domain） | Q-BAY公开项目动态 | COVERED_ACTIVE | OTHER（已解决） | 保留 ACTIVE；7 次受控周期验证 |
| Q-BAY赫利克斯菁英俱乐部 | ORG-20260626-000002 | 无 | NO | 无 | MANUAL_DOMAIN_REQUIRED | NO_WEBSITE_DATA | 管理员从 Organization 详情提交候选官网并确认 |
| 杭州钱塘区和达高科相关平台 | ORG-20260626-000003 | 无 | NO | 无 | NOT_MONITORABLE | ENTITY_DATA_INCOMPLETE | 先治理为明确法人/平台主体，再解析官网 |
| 上市公司俱乐部 | ORG-20260626-000005 | 无 | NO | 无 | NOT_MONITORABLE | ENTITY_DATA_INCOMPLETE | 名称不唯一；先确认具体运营主体 |
| 上市公司俱乐部创投分会 | ORG-20260626-000006 | 无 | NO | 无 | NOT_MONITORABLE | ENTITY_DATA_INCOMPLETE | 分会名称不构成可唯一解析的官网主体 |
| 世界顶尖科学家国际联合科学实验室（WLA Labs）相关历史网络 | ORG-20260626-000008 | 无 | NO | 无 | NOT_MONITORABLE | ENTITY_DATA_INCOMPLETE | 当前记录是“相关历史网络”，不是已确认正式主体 |
| 并就相关话题受邀深圳中欧创新实验室、华创证券、丹纳赫行业交流、长三角创新中心 | ORG-20260630-000001 | 无 | NO | 无 | NOT_MONITORABLE | ENTITY_DATA_INCOMPLETE | 误把履历句子抽成 Organization；需主体治理 |
| 某细胞治疗生物科技公司 | ORG-20260701-000001 | 无 | NO | 无 | NOT_MONITORABLE | ENTITY_DATA_INCOMPLETE | 匿名主体，禁止反推官网 |
| 陈绵辉 | — | 不适用 | NO | 无 | NOT_MONITORABLE | OTHER | Person 不按企业官网 Source 监测；应由已确认任职 Organization 提供覆盖 |
| 陶伟龙 | — | 不适用 | NO | 无 | NOT_MONITORABLE | OTHER | Person 不按企业官网 Source 监测 |
| Admin | — | 不适用 | NO | 无 | NOT_MONITORABLE | OTHER | 系统角色，不是公开监测主体 |
| 许毛毛 | — | 不适用 | NO | 无 | NOT_MONITORABLE | OTHER | Person 不按企业官网 Source 监测 |
| 链接官群体 | — | 不适用 | NO | 无 | NOT_MONITORABLE | ENTITY_DATA_INCOMPLETE | 群体角色，不是可绑定官网的 Person/Organization |

## Resolution delivered

- 复用 `p3_entity_external_identifiers` 的 `pending / approved / rejected`，不新建表或模型。
- Organization 详情可验证候选官网；第三方媒体、百科、社交、招聘和企业数据库域名被拒绝。
- 候选必须由页面标题、品牌标识或 Schema.org Organization 与主体匹配；只在管理员确认后成为 `official_domain`。
- 确认后直接复用 R7.1 Source Discovery；Candidate 继续 disabled，必须管理员启用。
- Source 与 Organization 使用现有 `subject_type / subject_id` 绑定，兼容历史内部 ID 并统一新候选为 Canonical external ID。

结论：此前不是 Discovery 缺失，而是 Canonical 官网事实和主体质量不足。R7.3 没有用猜测或媒体页面填充覆盖率。