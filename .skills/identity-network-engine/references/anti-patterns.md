# Anti-Patterns

- 用 User 表保存产业人物画像。
- 用 Member 表复制 Person 的姓名、履历、联系方式并长期分叉。
- 会员填写机构名称时直接新建正式 Organization。
- 资源发布时新建联系人表而不关联 Person/Member。
- 活动报名绕过会员和隐私偏好直接公开手机号或邮箱。
- 关注、关系、引荐各自建立不可互通的关系表。
