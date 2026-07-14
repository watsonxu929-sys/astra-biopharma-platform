# T4 俱乐部前台审计报告

## 一、现有页面清单

### 1. 俱乐部首页
- **URL**: `/club`
- **入口**: 一级菜单"俱乐部"
- **数据来源**: v04f_club.html模板, ClubOperationsDashboardService
- **是否可操作**: 是，但信息堆砌
- **状态**: 可用但需优化，需突出任务队列

### 2. 会员中心
- **URL**: `/member`
- **入口**: 二级菜单"会员"
- **数据来源**: v05d_member_portal.html模板
- **是否可操作**: 是，会员自助查看资料、活动、供需
- **状态**: 可用，功能完整

### 3. 会员申请
- **URL**: `/club/apply`
- **入口**: 俱乐部首页按钮
- **数据来源**: v04f_club_apply.html模板, ClubMembershipService
- **是否可操作**: 是
- **状态**: 可用

### 4. 会员管理
- **URL**: `/club/members`
- **入口**: 俱乐部首页面板
- **数据来源**: v04f_club.html (mode=members), ClubMembershipService
- **是否可操作**: 是，查看会员列表和详情
- **状态**: 可用

### 5. 活动管理
- **URL**: `/club/events`
- **入口**: 二级菜单"活动"
- **数据来源**: v05c_club_events.html模板, ClubEventService
- **是否可操作**: 是，创建、查看、管理活动
- **状态**: 可用

### 6. 活动报名
- **URL**: `/club/events/{id}/register`
- **入口**: 活动详情页
- **数据来源**: v05c_club_events.html (mode=public_register), ClubEventService
- **是否可操作**: 是
- **状态**: 可用

### 7. 报名管理
- **URL**: `/club/events/{id}/registrations`
- **入口**: 活动详情页按钮
- **数据来源**: v05c_club_events.html (mode=registrations), ClubEventService
- **是否可操作**: 是，审核报名、签发签到码、签到
- **状态**: 可用

### 8. 签到管理
- **URL**: `/club/events/{id}/checkin`
- **入口**: 活动详情页
- **数据来源**: v05c_club_events.html, ClubEventService
- **是否可操作**: 是，手工签到
- **状态**: 可用

### 9. 活动反馈
- **URL**: `/club/events/{id}/registrations/{rid}/feedback`
- **入口**: 报名管理页
- **数据来源**: v05c_club_events.html, ClubEventService
- **是否可操作**: 是，活动完成后提交反馈
- **状态**: 可用

### 10. 会员供需
- **URL**: `/club/resources`
- **入口**: 俱乐部首页面板
- **数据来源**: v04f_club.html (mode=resources), ClubResourceMatchingService
- **是否可操作**: 是，审核供需
- **状态**: 可用

### 11. 资源匹配
- **URL**: `/club/matches`
- **入口**: 二级菜单"供需与匹配"
- **数据来源**: v04f_club.html (mode=matches), ClubResourceMatchingService
- **是否可操作**: 是，生成匹配、审核候选
- **状态**: 可用

### 12. 活动关系候选
- **URL**: `/club/relationship-candidates`
- **入口**: 俱乐部首页面板
- **数据来源**: v04f_club.html (mode=relationship_candidates), ClubResourceMatchingService
- **是否可操作**: 是，复核会后关系候选
- **状态**: 可用

### 13. 潜在线索
- **URL**: `/club/leads`
- **入口**: 俱乐部首页面板
- **数据来源**: v04f_club.html (mode=club_leads)
- **是否可操作**: 是，查看线索候选
- **状态**: 可用

### 14. 会员申请审核
- **URL**: `/club/admin/applications`
- **入口**: 俱乐部首页面板
- **数据来源**: v04f_club.html (mode=applications), ClubMembershipService
- **是否可操作**: 是，审核会员申请
- **状态**: 可用

## 二、现有问题

### 1. 导航结构混乱
- 二级菜单条目过多（9项），不符合T4要求的5项
- 详情页和管理页混杂在菜单中
- 缺少"会员目录"页签

### 2. 首页信息堆砌
- 统计数字直接展示数据库字段名（members, active_members等）
- 缺少任务队列概念
- 普通会员和运营人员视角未区分

### 3. 中英文混杂
- 部分页面显示英文状态值（submitted, under_review等）
- 字段名未中文化（lifecycle_status, pilot_batch_id等）

### 4. 权限控制不完善
- 部分页面缺少后端权限校验
- 敏感信息（手机号、邮箱）权限控制不完整

### 5. 流程不直观
- 报名流程状态流转不清晰
- 会后跟进和线索生成边界不明确

## 三、保留、合并、隐藏建议

### 保留
- `/club` - 俱乐部首页，需重构
- `/club/events` - 活动列表，保留
- `/club/matches` - 匹配推荐，保留
- `/club/apply` - 会员申请，保留
- `/member` - 会员门户，保留

### 合并
- `/club/admin/applications` → 合并到运营管理
- `/club/resources` → 合并到供需与匹配
- `/club/relationship-candidates` → 合并到运营管理（会后跟进）
- `/club/leads` → 合并到运营管理（潜在线索）

### 隐藏（改为内部链接）
- `/club/members` - 会员管理，仅运营人员可见
- `/club/events/{id}/registrations` - 报名管理，仅运营人员可见
- `/club/import` - 数据导入，仅管理员可见

### 新增页签
- 会员目录（在会员页面内）
- 我的报名（在活动页面内）
- 资源需求/供给（在供需与匹配页面内）
- 会员/报名/供需审核（在运营管理页面内）

## 四、T4优化方向

1. **收敛导航**：二级菜单从9项缩减到5项
2. **重构首页**：突出任务队列，区分会员和运营视角
3. **中文化**：统一中文标签和状态显示
4. **权限加固**：后端校验权限
5. **流程优化**：清晰的报名、审核、签到、反馈流程
6. **边界明确**：会后关系≠认识，认识≠合作，线索≠商机
