# P4 活动生命周期

活动状态：`draft → pending_review → published → registration_open → registration_closed → ongoing → completed → archived`，异常分支为 `cancelled`。状态转换由 `ClubEventService` 校验，网页与 API 不再各自复制规则。

报名状态：`pending_review / approved / waitlisted / rejected / cancelled / checked_in / no_show`。服务校验报名时间窗、容量和重复身份；满额后进入候补，取消后保留记录。签到仅接受已批准报名。

签到码使用不可预测随机值，数据库只保存 SHA-256 摘要与末尾提示；校验活动范围、有效期和使用状态。手工签到、Token 签到、重复尝试、补签和撤销均写 `p4_checkin_audit`。活动完成后可提交结构化反馈。
