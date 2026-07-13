# P3 当前主体与关系模型审计

审计日期：2026-07-13。依据实际 ORM、SQLite 结构、服务、路由和模板，不按历史文档推测；正式库仅做只读结构与聚合查询。

## 1. 当前正式主体表

- `people`：正式自然人主档，44条；`v05a_users.person_id` 可选绑定人物，User不替代Person。
- `organizations`：正式机构主档，24条；Membership通过`person_id/organization_id`引用，不另建会员人物/机构。
- `projects`：正式项目主档，5条；与机构通过owner字段及关系表连接。
- 当前没有正式ProductAsset主表。`p2_intelligence_product_candidates`只是情报产品关联表，`v05b_media_assets`是媒体文件，不应作为产业产品资产。
- `relations`：旧正式关系表，26条；只保存两端external_id、自由文本关系类型、period和一段evidence_source。

## 2. 重复主体来源

- 手工录入、粘贴分析、批量人物导入、会员资料、情报主体匹配和历史演示数据均可能产生名称变体。
- 正式库标准名称精确重复当前为0，但v04E已有4组机构重复候选，其中1组被判断为same_entity，未执行正式合并。
- 现有`v04e_entity_aliases`仅1条；缺少语言、有效期、审核状态、证据及产品研发代号等类型。
- `v05g_subject_match_candidates`可承接加工候选，但正式库当前为0，状态与P3治理状态不统一。

## 3. 仍在使用的关系表

- `relations`被人物/机构详情、主体中心、研究专题、关系API、旧路径服务和推荐服务读取，必须兼容保留。
- `v04c_pending_relations`、`v04c1_canonical_relations`、`v05g_extraction_candidates`保存历史/加工关系候选，不能替代统一正式关系。
- `organization_user_links`、`organization_membership_links`和Membership映射属于账号/会员兼容关系，不是产业关系主表。
- P2.3的`p2_3_event_subjects`与`p2_3_fact_assertions`可作为关系候选和证据来源，不应复制主体。

## 4. 页面与能力现状

- `/subjects/{type}/{id}`和人物/机构详情能展示旧关系、时间线和简单1—2跳路径，但只支持人物、机构、项目。
- `/review/entities`模板是通用候选表格壳，与v04E真实dashboard/candidate详情上下文不完全一致；没有合并预览、历史和回滚页面。
- `/network`主要展示人物推荐、关注和联系意向，不是产业关系图谱；`/network/organizations`只是机构列表。
- `/api/v1/relationship-paths`只查询目标到Q-BAY会员锚点，不支持任意两点、关系类型、历史关系或路径证据。
- 产品详情、关系证据详情、关系候选审核和基础网络可视化缺失。

## 5. 证据和时态缺口

- 旧relations 26条都有非空evidence_source，但证据只是文本，未结构化关联Snapshot/Raw/Candidate/Assertion/Event。
- 18条“任职”关系period为空；旧表没有valid_from、valid_to和is_current。
- 关系类型共有9种，全部为自由文本；包含“运营/负责”“服务与链接”等复合表达，没有正式方向与反向名称。
- 9条旧关系的source端点无法解析到当前people/organizations/projects，路径服务会把它们显示为未知主体。
- 旧关系审核状态混用中文历史值，19/26为待核验；可见性包含内部、本人、限制。

## 6. 可能制造重复的写入入口

- 通用新增页、`/admin/people`、`/admin/organizations`、粘贴分析和批量人物保存均可写正式主档。
- v04D批量人物逻辑只按同名/机构做局部防重；同名人物仍需人工消歧。
- 会员资料已有审核和映射流程，P3不得因会员填写机构名直接新建Organization。
- P2加工已坚持候选优先；P3应复用其证据和匹配特征，不自动应用到正式主档。

## 7. 兼容保留与可复用能力

- 保留people、organizations、projects、relations及所有v04/v05候选、会员和账号表。
- 复用v04E名称归一化、谨慎的人物同名评分、别名和重复扫描入口。
- 复用SecurityMiddleware、view_internal/edit_data/review_data、审计日志和主体隐私字段。
- 复用P2 EvidenceSnapshot、RawIntelligence、FactCandidate、FactAssertion和IndustryEvent作为结构化证据链。
- 复用`subject_profile_service`详情聚合和`relationship_path_service`的有界BFS思想，但新增正式P3服务，不把Q-BAY锚点逻辑扩成全局模型。

## 8. P3必须解决

1. 建立产品资产兼容主档、统一别名和外部标识。
2. 统一解析候选状态与强/中/弱匹配，不自动合并同名人物。
3. 建立可预览、审批、重定向、回滚的事务合并机制。
4. 建立受控类型、方向、时态、可信度、可见性和审核状态的正式关系兼容层。
5. 让关系证据可追溯到P2证据链，删除关系不删除证据。
6. 提供任意两点1—3跳路径、证据、权限和资源限制。
7. 提供不执行联系动作的人脉推荐候选接口和可操作页面骨架。
