# MVP-R7.2 Priority Subject Universe

记录日期：2026-08-28（Asia/Shanghai）

## Universe rule

- `P1`：active/pending Q-BAY Membership 直接关联的 Organization 或 Person。
- `P2`：拥有非 archived Canonical Resource 的 Organization。
- `P3`：出现在已审核 Canonical Relationship 中的 Organization 或 Person。
- `P4`：拥有非 demo Opportunity 历史的主体；当前为 0。
- `P5`：管理员明确收藏、关注或标签的主体；当前为 0。
- 同时满足多个条件时取最高优先级。排除 `[DEMO]`、inactive 错误标题主体和没有上述依据的泛行业主体。

当前真实、可解释集合为 **13 个主体**。没有为达到 20～50 的建议规模加入 demo、占位公司或无业务依据主体。

## Subjects

| Subject | Type | Priority | 为什么优先 | Q-BAY关系 | Resource | Relationship | Opportunity | Intelligence | 官网 | Source覆盖 |
|---|---|---|---|---|---:|---:|---:|---:|---|---|
| 某细胞治疗生物科技公司 | Organization | P1 | active Q-BAY会员组织；已有1项资源 | 会员组织 | 1 | 0 | 0 | 0 | 未登记 | 无 |
| 并就相关话题受邀深圳中欧创新实验室、华创证券、丹纳赫行业交流、长三角创新中心 | Organization | P1 | active Q-BAY会员组织记录 | 会员组织；名称需治理 | 0 | 0 | 0 | 0 | 未登记 | 无 |
| 陈绵辉 | Person | P1 | active Q-BAY会员人物 | 会员 | 0 | 0 | 0 | 0 | 不适用 | 无 |
| 陶伟龙 | Person | P1 | active Q-BAY会员人物；已有1项资源 | 会员、总监 | 1 | 0 | 0 | 0 | 不适用 | 无 |
| Q-BAY（上海）生物医药孵化器 | Organization | P2 | 已有3项资源、1条正式关系和1条已关联情报 | Q-BAY主体 | 3 | 1 | 0 | 1 | 有公开项目页 | ACTIVE Source 1 |
| Q-BAY赫利克斯菁英俱乐部 | Organization | P2 | 已有1项资源和1条正式关系 | Q-BAY俱乐部 | 1 | 1 | 0 | 0 | 未登记 | 无 |
| 杭州钱塘区和达高科相关平台 | Organization | P2 | 已有1项资源和1条正式关系 | Q-BAY合作网络 | 1 | 1 | 0 | 0 | 未登记 | 无 |
| 上市公司俱乐部 | Organization | P2 | 已有1项资源和2条正式关系 | 产业连接生态 | 1 | 2 | 0 | 0 | 未登记 | 无 |
| 世界顶尖科学家国际联合科学实验室（WLA Labs）相关历史网络 | Organization | P2 | 已有1项资源和1条正式关系 | 历史合作网络 | 1 | 1 | 0 | 0 | 未登记 | 无 |
| 上市公司俱乐部创投分会 | Organization | P3 | 已有1条已审核正式关系 | 产业连接生态 | 0 | 1 | 0 | 0 | 未登记 | 无 |
| Admin | Person | P3 | Q-BAY负责人；已有2项资源和2条正式关系 | 项目负责人 | 2 | 2 | 0 | 0 | 不适用 | 无 |
| 许毛毛 | Person | P3 | Q-BAY联合发起人；已有2条正式关系 | 联合发起人 | 0 | 2 | 0 | 0 | 不适用 | 无 |
| 链接官群体 | Person | P3 | 已有1条正式关系 | 产业资源连接角色 | 0 | 1 | 0 | 0 | 不适用 | 无 |

## Coverage result

- Priority Organization：8；Priority Person：5。
- 有主体级 Source 覆盖：1 / 13；其中 ACTIVE：1。
- 其余 12 个主体的正式档案没有可验证官网字段，不能仅凭名称自动激活来源。
- 后续 Source Discovery 只生成 Candidate；管理员核对主体官网后才能 ACTIVE。
- 两个 P1 Organization 的名称质量不足，仍保留其会员优先依据，但不得据此自动做外部实体匹配或创建机会。
