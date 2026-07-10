# 统一身份兼容层设计与实施方案

## 1. 目标与边界

本方案面向“产业资源连接平台”的统一身份兼容层，目标是在不破坏现有登录、权限、会员、主体档案和俱乐部功能的前提下，建立 User、Person、Membership、Organization 之间的稳定关系。

本次仅完成现状核对、模型设计、API 设计和迁移方案，不修改业务代码，不创建数据库迁移，不处理历史数据。

## 2. 现状核对

| 对象 | 当前文件或模块 | 当前用途 | 现状判断 | 风险 |
|---|---|---|---|---|
| User | `app/security.py` / `v05a_users` | 内部登录账号、角色、状态、密码、安全计数、最后登录 | 已承担内部后台认证和权限 | 当前未显式绑定 Person，业务身份与登录身份割裂 |
| Person | `app/models.py` / `people` | 人物主体档案、公开角色、组织网络、能力标签、来源和审核字段 | 是正式人物主体 | 联系方式、头像、公开主页等能力分散在会员导入和媒体模块 |
| Organization | `app/models.py` / `organizations` | 企业或机构主体档案、资源需求、来源和审核字段 | 是正式机构主体 | 会员申请和导入可能携带机构名称，存在重复创建风险 |
| Membership | `scripts/migrate_v04f.py` / `v04f_club_memberships` | Q-BAY 会员身份、等级、状态、入会时间、所属人物和机构 | 已有 `person_id`、`organization_id` | 当前唯一活跃会员约束按 Person 生效，未来多俱乐部需扩展 |
| Member Account | `scripts/migrate_v05d.py` / `v05d_member_accounts` | 会员门户账号、密码、安全状态、最后登录 | 绑定 `membership_id`，不是内部 User | 与内部 User 并存，不能直接合并 |
| Member Contact | `scripts/migrate_v05b.py` / `v05b_member_contacts` | 会员联系方式 | 绑定 `membership_id` | 不应自动覆盖 Person 公开联系方式 |
| Media Asset | `scripts/migrate_v05b.py` / `v05b_media_assets` | 头像、导入图片、媒体资源 | 可绑定 `membership_id` 或 `person_id` | 需统一头像优先级与隐私规则 |
| Permission | `app/security.py` | 内部角色与权限集合 | 内部后台权限可复用 | 会员门户权限和机构代表权限尚未统一 |
| Club Application | `scripts/migrate_v04f.py` | 入会申请 | 已有 `matched_person_id`、`matched_organization_id` | 审核前不能自动合并主体 |

## 3. 身份边界

### 3.1 User

User 只负责：

- 登录认证；
- 账号状态；
- 权限角色；
- 安全设置；
- 最后登录；
- 与 Person 的绑定关系。

User 不得替代 Person 业务档案，不保存产业身份详情，不作为资源、需求、机会和内容的唯一业务主体。

### 3.2 Person

Person 负责：

- 姓名；
- 头像；
- 简介；
- 从业经历；
- 专业标签；
- 联系方式；
- 所属机构；
- 公开主页；
- 产业关系。

Person 可以没有登录账号。Person 是产业身份，不是认证账号。

### 3.3 Membership

Membership 负责：

- 会员身份；
- 所属俱乐部；
- 会员等级；
- 入会状态；
- 会员权益；
- 加入和到期时间；
- 会员贡献与活动记录。

Membership 不得复制 Person 基础档案，只引用 Person 和 Organization。

### 3.4 Organization

Organization 负责：

- 企业或机构主体；
- 机构档案；
- 机构主页；
- 机构成员；
- 机构代表；
- 企业情报；
- 资源与机会发布主体。

会员机构不得另建重复 Organization；无法确定匹配时进入候选和人工确认。

## 4. 目标关系

```text
User
0..1 -> Person

Person
0..N -> Membership
0..N -> Organization Affiliation

User
0..N -> Organization Representation

Membership
N..1 -> Club
N..1 -> Person
0..1 -> Organization

Organization
1..N -> Person Affiliation
0..N -> User Representation
```

## 5. 兼容层设计

### 5.1 兼容优先级

第一阶段不新增表，通过只读兼容服务从既有字段组装身份视图：

- `v05a_users` 提供内部账号；
- `people` 提供人物主体；
- `v04f_club_memberships.person_id` 提供会员到人物的关系；
- `v04f_club_memberships.organization_id` 提供会员到机构的关系；
- `v05d_member_accounts.membership_id` 提供会员门户账号到会员身份的关系；
- `v05b_member_contacts.membership_id` 提供受隐私控制的联系方式；
- `v05b_media_assets.person_id` 与 `membership_id` 提供头像候选。

第二阶段再考虑新增统一映射表，名称建议为 `identity_links`，但必须通过单独迁移任务实施。

### 5.2 建议的统一映射表

后续如需落库，建议使用通用兼容映射，而不是改造现有主表：

| 字段 | 含义 |
|---|---|
| `id` | 主键 |
| `link_no` | 业务编号 |
| `source_type` | `user`、`member_account`、`membership`、`person`、`organization` |
| `source_id` | 来源对象 ID |
| `target_type` | `person`、`organization`、`membership` |
| `target_id` | 目标对象 ID |
| `relation_type` | `login_person`、`member_person`、`member_organization`、`represent_organization`、`author_person`、`publisher_organization`、`opportunity_owner` |
| `status` | `candidate`、`active`、`rejected`、`revoked` |
| `confidence` | 匹配置信度 |
| `verified_by` | 确认人 |
| `verified_at` | 确认时间 |
| `source_note` | 来源说明 |
| `created_at` | 创建时间 |
| `updated_at` | 更新时间 |

设计原则：

- 不把 User 字段直接加到 Person；
- 不把会员账号直接合并为内部 User；
- 不自动合并同名 Person 或 Organization；
- 不自动公开会员联系方式；
- 所有模糊匹配进入候选确认。

## 6. 数据读取视图

### 6.1 当前账号身份视图

`IdentityContext` 建议结构：

```json
{
  "user": {
    "id": 1,
    "username": "admin",
    "role": "admin",
    "role_label": "系统管理员"
  },
  "person": {
    "id": 12,
    "name": "张三",
    "binding_status": "active"
  },
  "memberships": [
    {
      "id": 5,
      "member_no": "M-0005",
      "level": "standard",
      "level_label": "标准会员",
      "status": "active",
      "status_label": "有效"
    }
  ],
  "organizations": [
    {
      "id": 8,
      "standard_name": "某某生物科技有限公司",
      "relation_type": "represent_organization",
      "permission_scope": ["publish_resource", "respond_opportunity"]
    }
  ]
}
```

### 6.2 人物身份视图

Person 页面应聚合：

- 基础人物档案；
- 会员身份列表；
- 所属机构关系；
- 可公开联系方式；
- 活动参与记录；
- 已授权的资源、需求和机会；
- 产业关系路径。

### 6.3 机构身份视图

Organization 页面应聚合：

- 机构档案；
- 人员归属；
- 授权代表；
- 企业情报；
- 已发布资源；
- 已发布需求；
- 招商、合作、投资和销售机会；
- 相关产业信号与报告。

## 7. API 设计

本节为后续接口设计，不在本任务实施。

| 接口 | 方法 | 用途 | 权限 |
|---|---|---|---|
| `/api/v1/identity/me` | GET | 返回当前登录账号的统一身份视图 | 登录用户 |
| `/api/v1/identity/users/{user_id}/person-binding` | GET | 查看 User 与 Person 绑定状态 | `manage_users` 或本人 |
| `/api/v1/identity/users/{user_id}/bind-person` | POST | 绑定或提交绑定候选 | `manage_users` |
| `/api/v1/identity/persons/{person_id}/memberships` | GET | 查看人物会员身份 | `view_internal` 或本人授权 |
| `/api/v1/identity/persons/{person_id}/organizations` | GET | 查看人物机构关系 | `view_internal` 或公开范围 |
| `/api/v1/identity/organizations/{organization_id}/representatives` | GET | 查看机构代表 | `view_internal` 或机构管理员 |
| `/api/v1/identity/organizations/{organization_id}/representatives` | POST | 新增机构代表候选或授权 | `manage_club` / `manage_users` |
| `/api/v1/member/identity` | GET | 会员门户身份视图 | 会员登录 |
| `/api/v1/member/profile-change` | POST | 复用现有资料变更申请 | 会员登录 |

API 约束：

- 机器值继续返回英文；
- 必须增加中文展示字段，如 `status_label`、`role_label`、`relation_type_label`；
- 不暴露密码、令牌、完整敏感联系方式；
- 模糊绑定接口只创建候选，不直接覆盖正式主体。

## 8. 权限设计

### 8.1 内部后台权限

继续复用 `app/security.py` 的角色和权限：

- `admin`：系统管理；
- `operator`：业务运营；
- `reviewer`：数据审核；
- `viewer`：只读查看。

内部 User 权限决定后台管理能力，不自动决定 Person 的公开身份。

### 8.2 会员门户权限

会员门户继续以 `v05d_member_accounts` 认证，绑定 Membership 后获得：

- 查看本人会员信息；
- 提交资料变更；
- 发布需求或供给申请；
- 查看授权范围内的匹配与通知；
- 管理个人隐私设置。

会员账号不直接拥有后台权限。

### 8.3 机构代表权限

机构代表关系应按范围授权：

- `manage_org_profile`：维护机构资料候选；
- `publish_resource`：代表机构发布资源；
- `publish_demand`：代表机构发布需求；
- `respond_opportunity`：响应合作或招商机会；
- `manage_org_members`：管理机构成员候选；
- `register_event`：代表机构报名活动。

机构代表权限不等同于系统管理员权限。

## 9. 历史数据兼容方案

### 9.1 不变更内容

- 不修改 `v05a_users` 主键；
- 不修改 `people` 主键和 `external_id`；
- 不修改 `organizations` 主键和 `external_id`；
- 不修改 `v04f_club_memberships` 现有记录；
- 不修改 `v05d_member_accounts` 登录方式；
- 不自动合并同名人物或机构。

### 9.2 分阶段实施

| 阶段 | 目标 | 动作 | 验收 |
|---|---|---|---|
| 阶段 0 | 文档封板 | 完成本方案 | 不改业务代码 |
| 阶段 1 | 只读兼容服务 | 新建 `identity_context_service`，从现有表读取身份视图 | 不新增表，接口只读 |
| 阶段 2 | 绑定候选 | 为 User 与 Person、机构代表关系提供候选确认流程 | 模糊匹配不自动生效 |
| 阶段 3 | 映射表迁移 | 单独新增 `identity_links` 迁移 | 迁移前备份，可回滚 |
| 阶段 4 | API 接入 | 增加统一身份 API，内部与会员门户分别接入 | API 保持英文机器值和中文 label |
| 阶段 5 | 页面接入 | 账号、人物、机构、会员页面展示统一身份关系 | 不破坏旧入口 |
| 阶段 6 | 治理固化 | 将状态、关系类型、权限范围接入统一 taxonomy | 无重复枚举 |

### 9.3 回填策略

只允许生成候选，不允许静默生效：

- `v04f_club_memberships.person_id` 可生成 `membership -> person` 的已确认映射；
- `v04f_club_memberships.organization_id` 可生成 `membership -> organization` 的已确认映射；
- `v05d_member_accounts.membership_id` 可生成 `member_account -> membership` 的已确认映射；
- `v05a_users.display_name` 与 `people.name` 的匹配只能生成候选；
- 会员申请中的姓名、手机号、邮箱、机构名只能生成候选；
- 机构名称相似、人物同名、手机号重复等情况必须进入人工审核。

## 10. 与现有业务域的关系

| 业务域 | 使用方式 |
|---|---|
| identity | 统一管理 User、Person、Membership、Organization 和兼容映射 |
| intelligence | 情报、信号、报告引用正式 Person 和 Organization，不引用会员账号 |
| network | 关系路径以 Person 和 Organization 为节点，User 仅作为操作者 |
| community | Q-BAY 会员、活动、内容复用 Membership 和 Person |
| marketplace | 资源和需求发布主体优先使用 Organization，必要时关联 Person/Membership |
| opportunity | 机会负责人可以是 User 操作者，也可以绑定 Person 或 Organization |

## 11. 资源与机会发布身份

资源、需求和机会应区分操作者与业务主体：

- `actor_user_id`：谁在系统中执行操作；
- `publisher_person_id`：谁作为个人身份发布；
- `publisher_organization_id`：代表哪个机构发布；
- `membership_id`：是否来自会员权益或会员门户；
- `owner_user_id`：内部跟进负责人；
- `owner_person_id`：业务负责人；
- `source_identity_link_id`：来源映射依据。

当前阶段不要求立即增加这些字段，可先在服务层设计中明确，不把 `owner` 字符串继续扩展为唯一身份来源。

## 12. 反模式

禁止：

- User、Person、Member 各自维护重复姓名和联系方式；
- Member 成为独立人物副本；
- 会员机构重复创建 Organization；
- 社区单独建立第二套用户体系；
- 资源市场单独建立第二套企业和联系人；
- 机构代表权限直接等同后台管理员权限；
- 同名人物或同名机构自动合并；
- 联系方式从会员表自动公开到人物主页；
- 招商线索、融资需求、采购需求全部复制成无关联模型；
- 每个模块维护一套标签、地区和状态枚举。

## 13. 最小必要开发任务

建议下一步第一个开发任务为：

> 新建只读统一身份上下文服务，不新增表，不改登录流程，只提供内部账号和会员账号的身份视图。

建议文件范围：

- `app/services/identity_context_service.py`
- `app/api/v1/identity.py`
- `app/api/v1/__init__.py` 或现有 API 注册文件
- `scripts/verify_identity_context.py`

不建议在第一步同时做：

- User 与 Person 自动绑定；
- 会员账号和内部 User 合并；
- 机构代表权限落库；
- 公开主页重构；
- 历史数据回填。

## 14. 验收标准

后续实施统一身份兼容层时，至少满足：

- User 可返回账号、角色、权限和绑定 Person 状态；
- Person 可返回会员身份和机构归属；
- Membership 不复制 Person 基础档案；
- Organization 不因会员机构重复创建；
- 会员账号仍可按现有方式登录；
- 内部后台账号仍可按现有方式登录；
- API 机器值保持英文，并提供中文 label；
- 模糊匹配只进入候选；
- 敏感联系方式按隐私设置过滤；
- 不破坏 Q-BAY 俱乐部、权限和历史主体数据。
