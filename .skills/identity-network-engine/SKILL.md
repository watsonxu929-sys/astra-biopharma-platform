---
name: identity-network-engine
description: Use when designing, reviewing, or implementing identity and network relationships among User, Person, Membership, Organization, contacts, authors, resource publishers, demand publishers, opportunity owners, activity participants, watchlists, relationships, referrals, privacy controls, and member-to-subject compatibility mappings.
---

# Identity Network Engine

## 适用场景

- 账号绑定人物档案、会员身份或代表机构。
- 会员发布资源、需求、机会、内容或参与活动。
- 用户关注人物、机构、资源、机会，或申请关系引荐。
- 需要处理联系方式、关系、活动记录的隐私控制。

## 不适用场景

- 单纯登录页样式调整。
- 单个主体字段编辑。
- 与身份、关系、隐私无关的情报采集或报告生成。

## 核心原则

- User 不是 Person 的替代品。
- Member 不是独立人物副本。
- Organization 不得因会员机构重复创建。
- 使用兼容映射，不破坏现有内部登录、会员门户和俱乐部功能。
- 同名人物不得自动合并。
- 公开主页与后台档案权限分离。

## 执行步骤

1. 判断对象是账号、人物、会员身份、机构、联系人、发布者、参与者还是负责人。
2. 优先复用 `v05a_users`、`people`、`v04f_club_memberships`、`organizations`、`v05d_member_accounts`。
3. 查找现有映射字段：membership 的 person/organization、member account 的 membership、resource owner、lead subject、action owner。
4. 若缺少映射，设计兼容映射层，不直接合并表。
5. 明确隐私边界：联系方式、关系、活动参与、会员资料变更不得直接公开。

## 文件范围控制

- 优先查看：`app/models.py`、`app/security.py`、`app/v04f_operations.py`、`app/v05d_member_portal.py`、`app/services/subject_*`、`app/services/watchlist_service.py`。
- 只查相关身份、关系、会员、权限和隐私字段。

## 数据兼容要求

- 不修改现有 User、Person、Membership、Organization 主键。
- 不自动创建正式 Organization 来承载会员填写的机构名称。
- 会员资料修改继续走审核或变更请求。
- 联系方式继续遵守隐私偏好和敏感字段过滤。

## 禁止事项

- 禁止 User、Person、Member 各自维护重复姓名和联系方式。
- 禁止社区单独建立第二套用户体系。
- 禁止资源市场单独建立第二套企业和联系人。
- 禁止同名人物自动合并。
- 禁止前台公开后台档案中的敏感联系方式、审核记录和内部备注。

## 验收标准

- 明确 User、Person、Membership、Organization 的关系。
- 明确是否需要兼容映射或中间表。
- 明确发布者、作者、参与者、负责人引用哪个身份。
- 明确隐私控制和权限边界。
- 未破坏现有登录、权限、会员门户和俱乐部流程。

## 与其他 Skills 的协作关系

- 与 `platform-domain-architecture` 协作判断身份能力归属。
- 与 `platform-taxonomy-governance` 协作处理角色、关系类型和隐私分类。
- 与 `incremental-codex-delivery` 协作避免一次性重构身份体系。

## 参考文件

- `references/domain-rules.md`
- `references/anti-patterns.md`
- `references/acceptance-checklist.md`
