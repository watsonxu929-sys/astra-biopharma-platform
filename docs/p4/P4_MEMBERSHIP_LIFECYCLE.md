# P4 会员生命周期

申请状态：`submitted → under_review → need_more_info / approved / rejected / withdrawn`。批准产生待激活会员资格，随后支持 `activate`、`change`、`suspend`、`resume`、`expire`、`withdraw`。

P4 语义状态通过 `ClubMembershipService` 映射到既有 SQLite 约束允许的兼容状态，不重建正式表。每次人工动作写入 `p4_membership_history` 和 `p4_operation_audit`；批准与激活还产生内部领域事件。重复提交相同审核或状态动作返回幂等结果。

会员资格始终关联既有 User、Person 和 Organization。系统不自动合并同名人物或机构，不覆盖正式主体字段。
