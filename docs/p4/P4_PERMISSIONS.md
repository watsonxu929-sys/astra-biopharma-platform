# P4 权限

| 动作 | 后端权限 |
|---|---|
| 查看本人会员上下文、本人报名与反馈 | `membership.view_self` |
| 会员申请审核、会员状态变更 | `manage_club` |
| 活动状态、报名审核、签到码、签到/撤销 | `manage_club` |
| 资源审核、生成/审核匹配 | `manage_club` |
| 会后关系候选和 ClubLead 候选处理 | `manage_club` |
| 俱乐部运营看板和领域事件队列 | `manage_club` |

权限同时在全局 `required_permission` 映射和具体 Web/API 路由校验。未登录或无权限请求返回 401/403，不渲染假成功页。敏感联系方式继续使用既有可见性规则。
