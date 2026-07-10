# Identity Network Rules

## 统一关系

```text
User -> 可绑定 Person
Person -> 可拥有 Membership
Membership -> 可关联 Organization
User/Member -> 可成为作者、发布者、活动参与者、机会负责人
Person/Organization -> 可被关注、建立关系、请求引荐
```

## 现有对象

- User：内部账号，承载后台权限。
- Person：产业人物正式档案。
- Membership：俱乐部会员身份。
- Member Account：会员门户账号。
- Organization：企业/机构正式主体。
- Contact：会员隐私联系方式。

## 映射策略

- 先做可选绑定，后做数据治理。
- 先保留文本 owner，再逐步增加结构化 owner 映射。
- 对外展示使用脱敏视图，对内后台使用权限过滤。
