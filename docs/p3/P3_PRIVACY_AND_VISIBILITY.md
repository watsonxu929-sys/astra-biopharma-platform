# P3 隐私与可见性

P3 复用现有 view_internal、edit_data、review_data、use_recommendations 和 manage_users 权限。

| 操作 | 最低权限 |
|---|---|
| 查看 public/internal 已审核网络 | view_internal |
| 创建解析/关系候选、提交合并 | edit_data |
| 审核候选、批准/回滚合并 | review_data |
| 获取连接候选 | use_recommendations |

正式关系可见性为 public、internal、restricted、private。普通路径和图视图只读取 public/internal；restricted/private 必须由有权调用方显式请求。未审核候选关系永不进入正式网络。

外部标识只允许公开权威类型，`is_sensitive=0` 为数据库硬约束。禁止保存或展示身份证号、私人手机、私人邮箱、未公开身份信息、内部备注和商务敏感关系。

连接候选只返回研判理由和已有证据路径，不代表联系授权，也不自动发送消息、建立联系意向或创建商机。
