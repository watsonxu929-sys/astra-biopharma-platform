# Anti-Patterns

- 为社区功能新建独立用户、人物、机构表。
- 为资源市场新建独立企业和联系人表。
- 将会员申请中的机构名称直接创建为正式 Organization。
- 将 Lead、Signal、Recommendation、Investment Assessment 分别扩展成互不关联的机会模型。
- 在页面路由中复制业务规则，绕过服务层。
- 每个模块新增自己的状态、标签、地区、角色和附件机制。
- 为一个前台功能新增后台一级导航。
- 将 Worker 或 Scheduler 暴露为新的浏览器端口。
