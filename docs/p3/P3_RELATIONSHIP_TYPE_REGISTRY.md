# P3 关系类型注册表

迁移 006 注册 43 个受控类型。每个类型包含稳定键、中文正向名、中文反向名、允许的主客体类型、是否对称及风险级别；正式关系不能写任意自由文本。

| 分组 | 数量 | 类型键 |
|---|---:|---|
| 人物—机构 | 12 | employed_by、formerly_employed_by、founder_of、cofounder_of、legal_representative_of、director_of、executive_of、advisor_to、scientific_advisor_to、investor_in、contact_for、member_of |
| 机构—机构 | 13 | invests_in、controls、subsidiary_of、parent_of、strategic_partner_of、research_partner_of、licenses_to、licensed_from、acquired、supplies_services_to、jointly_established、located_in_park、member_organization_of |
| 机构—产品 | 7 | develops、owns、licenses_product、commercializes、manufactures、sponsors_clinical_trial、supports_product |
| 人物—产品/项目 | 5 | inventor_of、leads、researcher_for、advisor_for、participates_in |
| 项目—机构 | 6 | initiated_by、participated_by、funded_by、serviced_by、undertaken_by、cooperated_by |

高风险类型（例如投资、控制、法定代表、产品研发/持有）转正时必须带证据。对称类型在路径计算时可双向遍历，但数据库仍保存唯一事实记录和明确方向。

注册表通过迁移幂等 upsert 维护；停用类型使用 `active=0`，不删除历史类型键。
