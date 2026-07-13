# P4 内部领域事件

`p4_domain_events` 是本地待消费队列，不是外部消息总线。当前事件包括：

- `membership.approved`、`membership.activated`
- `event.published`
- `registration.approved`、`registration.checked_in`
- `feedback.submitted`
- `resource.approved`
- `match.accepted`
- `lead.created`

事件保存聚合类型/ID、JSON 负载、操作者、时间、状态和试点批次。状态为 `pending / consumed / failed / ignored`。P4 不接入 Activepieces，不对外发送通知；后续消费者必须幂等并保留消费结果。
