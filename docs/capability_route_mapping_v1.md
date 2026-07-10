# Capability Route Mapping v1

| 功能名称 | 原路由 | 新一级菜单 | 新二级菜单 | 新入口 | 所需权限 | 处理方式 |
|---|---|---|---|---|---|---|
| 会员管理 | `/club/members` | 俱乐部 | 会员管理 | `/club/members` | `manage_club` | direct |
| 会员门户 | `/member` | 俱乐部 | 会员中心 | `/member` | `membership.view_self` | direct |
| 会员导入 | `/club/import` | 俱乐部 | 数据导入 | `/club/import` | `manage_club` | admin_only |
| 会员申请 | `/club/apply` | 俱乐部 | 会员申请 | `/club/apply` | public | direct |
| 会员活动 | `/club/events` | 俱乐部 | 俱乐部活动 | `/club/events` | `view_internal` | direct |
| 供需撮合 | `/club/matches` | 俱乐部 | 会员撮合 | `/club/matches` | `manage_club` | direct |
| 人物档案 | `/people`, `/network/people` | 人脉与机构 | 人物发现 | `/network/people` | `view_internal` | adapted |
| 组织管理 | `/organizations`, `/network/organizations` | 人脉与机构 | 机构发现 | `/network/organizations` | `organization.view_self` | adapted |
| 身份关联 | `/me/industry-profile` | 人脉与机构 | 我的产业身份 | `/me/industry-profile` | `identity.view_self` | direct |
| 情报采集 | `/collection/sources` | 情报与研究 | 情报采集 | `/collection/sources` | `manage_monitoring` | admin_only |
| 数据加工 | `/processing/jobs` | 情报与研究 | 数据加工 | `/processing/jobs` | `review_data` | admin_only |
| 数据审核 | `/review` | 情报与研究 | 数据审核 | `/review` | `review_data` | admin_only |
| 情报监测 | `/watchlists`, `/signals` | 情报与研究 | 企业动态 | `/signals` | `view_internal` | direct |
| 信号 | `/signals` | 情报与研究 | 企业动态 | `/signals` | `view_internal` | direct |
| 报告 | `/reports` | 情报与研究 | 报告管理 | `/reports` | `review_data` | admin_only |
| 研究 | `/research` | 情报与研究 | 专题研究 | `/research` | `view_internal` | direct |
| 资源市场 | `/resources` | 资源与合作 | 资源供给/需求 | `/resources` | `view_internal` | adapted |
| 合作机会 | `/opportunities` | 资源与合作 | 合作机会 | `/opportunities` | `view_internal` | adapted |
| 商务跟进 | `/actions`, `/opportunities` | 资源与合作 | 商务跟进 | `/opportunities` | `view_internal` | adapted |
| 任务 | `/workspace` | 资源与合作 | 协作任务 | `/workspace` | `view_internal` | direct |
| 审计日志 | `/admin/audit` | 管理控制台 | 操作审计 | `/admin/audit` | `manage_users` | admin_only |
| 数据校验 | `/admin/data-integrity`, `/review` | 管理控制台 | 数据完整性 | `/admin/data-integrity` | `review_data` | admin_only |
| 系统管理 | `/system/operations` | 管理控制台 | 系统运维 | `/system/operations` | `manage_users` | admin_only |
| 旧情报列表 | `/intelligence/legacy` | 情报与研究 | 数据审核 | `/intelligence/legacy` | `review_data` | deprecated_readonly |
| 旧资源列表 | `/resources/legacy` | 资源与合作 | 资源供给/需求 | `/resources/legacy` | `view_internal` | deprecated_readonly |
