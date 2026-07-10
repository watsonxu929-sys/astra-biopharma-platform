# Domain Rules

## 六大核心业务域

- `identity`：产业身份与组织中枢，承载 User、Person、Member、Organization、Project 和身份映射。
- `intelligence`：产业情报与智研中心，承载采集、加工、审核、信号、报告、研究和招商研判来源。
- `network`：产业关系与协同网络，承载关系、关注、推荐、匹配和引荐路径。
- `community`：产业社群与内容中心，承载会员门户、俱乐部、活动、报名、公告和通知。
- `marketplace`：产业资源与交易中心，承载资源、需求、供给、服务、场地和技术成果。
- `opportunity`：产业机会与合作中心，承载招商、融资、投资、销售、采购、合作、人脉引荐机会。

## 跨域调用

- 跨域优先调用 `app/services/` 中现有服务。
- 情报域可产生信号，信号可进入机会域形成 Lead 或 Action。
- community 的会员供需进入 marketplace 前必须建立兼容映射。
- network 的推荐和匹配结果可以服务 community、marketplace、opportunity，但不直接替代业务对象。

## 前台与后台

- 前台不得暴露采集任务、加工任务、审核队列、技术字段和内部审计。
- 后台不得绕过会员隐私偏好公开联系方式。
- 同一对象可有前台展示页和后台管理页，但必须共享服务层。
