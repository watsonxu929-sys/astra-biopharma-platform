# P2.3 Trae 交接

P2.3 业务大框架、服务、API、基础页面和受控试点已完成。Trae 只做前台精修和浏览器验收，不改变领域模型、005 迁移和审核边界。

## 页面入口

- 专题列表：`/research/topics`，每条专题可进入 `/research/topics/{id}/workspace`
- 事件时间线：`/research/events`
- 事件详情与证据：`/research/events/{id}`
- 冲突审核：`/research/conflicts`
- 研究发现：`/research/findings?topic_id={id}`
- 企业对比：`/research/companies/compare-v2`
- 赛道对比：`/research/tracks/{track}/comparison`
- 报告审核：`/research/reports/{id}/review`
- 正式报告仍复用报告中心详情。

## Trae 范围

- 页面样式、卡片/表格布局、筛选和排序。
- 中文状态文案、空状态、错误提示。
- 时间线视觉展示、对比页美化、报告打印样式。
- 浏览器点击验收、响应式小问题和普通测试补齐。
- 验证权限不足时提示、返回路径和菜单高亮。

## 必须保持

- 冲突两值和双方证据同时显示，不自动采用。
- 草稿、待审核、需修改、已通过、已发布状态不可混淆。
- 未审核事件不得进入正式时间线/报告。
- “暂无可靠数据”不可由模型补造。
- ResearchAgent 只能生成草稿。
- 不新增二级菜单，不扩来源，不批量处理历史数据，不触碰俱乐部/业务协同，不开始 P3。

## 浏览器验收建议

在迁移过的数据库副本启动应用，从“专题研究”列表点击进入工作区，依次查看时间线、事件证据、冲突、企业对比、赛道对比、报告草稿和审核动作；检查 HTTP、Console、Network、返回路径、权限与空状态。
