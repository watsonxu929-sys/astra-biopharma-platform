# P4 Trae 前台交接

## 可精修页面

- `/club/operations`：中文运营指标和工作队列。
- `/club/admin/applications*`、`/club/members*`：会员审核与生命周期。
- `/club/events*`、`/club/registrations`：活动、报名、签到和反馈。
- `/club/resources`、`/club/matches`：统一供需审核和匹配候选。
- `/club/relationship-candidates`、`/club/leads`：会后关系与线索候选。

## 必须保持的业务约束

- 详情页从列表进入，不新增重复一级/二级菜单。
- 页面状态使用中文，操作失败显示真实 401/403/409，不做假成功。
- 旧供需表只读；新供需只写 `v06_market_resources`。
- 同场参与不等于认识；匹配不等于自动联络；ClubLead 不等于 Opportunity。
- 不修改 P2/P3 领域模型，不引入支付、票务或自动化平台。

## 人工验收

使用数据库副本应用 006/007 后，从“俱乐部运营”依次点击会员申请、会员详情、活动、报名审核、签到、反馈、资源审核、匹配、会后关系和线索候选。检查返回路径、菜单高亮、权限提示、中文状态、Console 和 Network。正式库当前未应用 007，因此不应直接用正式库做写操作验收。
