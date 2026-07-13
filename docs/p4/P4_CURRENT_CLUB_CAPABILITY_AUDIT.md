# P4 当前俱乐部能力审计

审计日期：2026-07-13
审计范围：`app/v04f_operations.py`、`app/v05b_member_import.py`、`app/v05c_club_events.py`、`app/v05d_member_portal.py`、现有 API、服务、模板、迁移脚本及只读正式库结构。
边界：本审计不执行正式库迁移，不修改 P2/P3 架构，不引入支付、票务或自动化平台。

## 1. 当前正式会员模型

- 正式会员身份是 `v04f_club_memberships`，以 `person_id`、`organization_id`、`user_id` 分别关联既有 Person、Organization 和 User，不复制人物或机构主档。
- 会员申请保存在 `v04f_club_applications`；现有状态为 `submitted / under_review / need_more_info / approved / rejected`，批准后直接创建 `active` Membership。
- `v05b_member_contacts` 保存会员联系方式扩展，`v05d_member_accounts` 是历史会员门户账号兼容层；P1 的会员—人物和会员—User 绑定服务已有审计能力。
- 正式库当前有 2 条 Membership、0 条申请；生命周期尚缺独立的批准后激活、暂停/恢复、到期/退出历史和幂等操作记录。

## 2. 当前正式活动模型

- 主活动事实继续使用 `events`；Q-BAY 运营字段使用一对一扩展表 `v05c_club_event_profiles`，不应新建第二套 Event。
- 现有状态为 `draft / published / registration_open / registration_closed / ongoing / completed / cancelled`；缺少 `pending_review`、`archived` 以及状态转换审核记录。
- 已有创建、复制、发布、开放/关闭报名、开始、完成、取消、列表和详情页面，但复杂规则直接位于网页路由，活动 API 仅提供通用只读列表/详情。
- 正式库当前有 1 条 Q-BAY 活动扩展记录。

## 3. 当前正式报名模型

- 报名使用 `v05c_club_event_registrations`，关联 `club_event_id` 和可选 `membership_id`，并保存姓名、机构、职务和联系方式快照。
- 现有状态为 `submitted / approved / waitlisted / rejected / cancelled`；缺少明确的 `pending_review / checked_in / no_show` 状态及 User、Person、Organization、报名理由、关注方向、供需等关联字段。
- 已有公开报名、重复联系方式拦截、审核和候补入口；容量、报名时间窗、取消释放名额和身份级幂等规则尚未形成统一服务。
- 非会员可报名，但当前仅以 `membership_id IS NULL` 推断访客，缺少显式 guest 标记。

## 4. 当前签到和反馈能力

- `v05c_club_event_participation` 已保存出席状态、签到方式/时间、满意度、反馈、贡献和跟进备注；支持手工签到、批量签到和反馈保存。
- 当前签到可用报名号、会员 ID 或姓名，未限制仅已批准报名；没有不可预测 Token、活动范围/有效期校验、撤销/补签/异常记录和完整操作审计。
- 反馈复用 participation 单行，无法完整承载内容、嘉宾、组织评价及多项会后意向，也没有会后候选生成服务。

## 5. 当前供需模型

- P1 正式统一资源模型是 `v06_market_resources`，方向为 `demand / supply`；`UnifiedResourceService` 已提供创建、状态、列表、详情、重复检查和基础匹配。
- `v04f_club_needs`、`v04f_club_offerings`、`v04f_club_matches` 是历史兼容模型。统一资源服务已经只读适配旧供需，但会员详情和会员门户仍存在写旧表入口。
- 正式库当前有 22 条统一资源，旧供需均为 0；P4 新数据必须只写 `v06_market_resources`，旧表继续只读，不恢复双写。
- 统一资源现有发布状态名为 `published`，P4 页面可将其显示为“有效”；不为文案另造资源主表或改变 P1 状态体系。

## 6. 重复写入入口

- `/club/members/{id}/needs`、`/offerings` 直接写旧供需表；会员门户也有旧内容申请/写入路径，需要改为统一资源服务或兼容跳转。
- 会员申请审核、活动创建/状态、报名审核、签到和反馈均在网页路由内直接执行 SQL；API 没有共享同一套业务服务。
- 活动反馈同时写 participation 的多个字段，后续若新增结构必须以服务统一写入，避免网页/API 再次分叉。
- `v04f_lead_records` 是既有 Lead，但其创建逻辑面向正式主体漏斗；P4 会后结果先落 ClubLead 候选，不写 `v06_opportunities`。

## 7. 页面和菜单交叉

- `/club` 同时承担首页、指标和多业务入口；`/club/members`、`/club/events`、`/club/matches`、`/member`、`/member/admin` 已存在。
- capability registry 同时注册“会员中心、活动、会员撮合、会员申请、会员管理、活动管理、供需管理、数据导入、俱乐部运营”，其中“俱乐部运营”目前错误指向会员列表，“供需管理”指回 `/club`。
- 详情页由列表进入，当前未作为菜单项；这一原则应保留。P4 只收敛工作入口与角色可见性，不重构全站菜单。
- 模板仍直接展示 `successful_matches`、`recent_events`、`event_registrations`、`today_checkins` 等键值，需要由中文指标定义替代。

## 8. 已经可以复用的服务

- 身份与权限：`membership_access_service`、`membership_person_link_service`、`membership_user_link_service`、`authorization_service`、`permissions_for`。
- 会员导入：`member_import_service` 及 v05b 草稿/人工确认流程。
- 资源：`UnifiedResourceService` 和 `/api/v1/resources`，正式写入 `v06_market_resources`。
- 主体关系：P3 的实体解析、关系类型注册、关系候选、证据、审计和路径服务；006 迁移尚未应用到正式库，只能在测试副本上作为 007 的前置。
- 通用主体、活动与组织 API 可用于只读关联；现有活动 API 不足以承载 Q-BAY 运营状态机。

## 9. 需要兼容的历史入口

- 保留 `/club`、`/club/apply`、`/club/admin/applications*`、`/club/members*`、`/club/events*`、`/club/registrations`、`/club/matches*`、`/member*` 和 `/member/admin*`。
- 保留 `v04f_club_needs/offerings/matches` 与 v05d 历史账号/内容表的只读展示或明确跳转；禁止删除旧表和批量迁移历史脏数据。
- 保留 `events` 与 `v05c` 数据，不重建、不清空；新增列和表必须由幂等 007 迁移完成。
- 旧页面提交 URL 如需收敛，继续接收并转交新服务，避免书签和既有表单失效。

## 10. 本轮需要补齐的业务断点

1. 建立共享 Club 服务层和完整的会员、活动、报名状态转换，所有运营动作做后端权限校验。
2. 保留申请记录并实现审核、激活、变更、暂停、恢复、到期和退出的可追踪历史与审计。
3. 补齐活动审核/归档、报名时间窗/容量/候补/取消释放名额、Token 签到、撤销/补签/异常及结构化反馈。
4. 会后仅生成带活动证据的关系候选；同场参会不等于认识。P3 暂不支持 Event 端点和 P4 事件关系类型，因此用 P4 兼容候选保存原始语义，人工审核后才映射到 P3 可接受的正式关系，绝不修改 P3 架构。
5. 会员新增供需只写 `v06_market_resources`，建立可解释、幂等、受控的资源匹配候选；不得自动联系。
6. 建立 ClubLead 候选及人工转换入口，禁止自动创建 `v06_opportunities`。
7. 建立中文运营工作台、角色化入口、内部领域事件和操作审计，并让网页与 `/api/v1` 复用同一业务服务。
8. 007 默认 dry-run；仅在包含 006 的数据库副本运行受控试点，所有试点记录带 `pilot_batch_id`，正式库保持不变。

## 结论

现有系统具备 P4 的主体骨架，但缺少统一服务、完整状态机、审计、Token 签到、结构化会后沉淀和新资源/候选闭环。P4 应采用增量扩展与兼容适配，不复制主档、不恢复双写、不把活动弱互动自动升级为正式关系或商机。
