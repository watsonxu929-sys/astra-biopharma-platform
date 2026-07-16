# CORE-0.6M-R1 P4 最终修复与迁移预演报告

## 修改前基线

- 隔离 worktree：`C:\tmp\industry-intel-core-06m-p4`
- 分支：`feat/p4-club-operations-mvp`
- 起始 HEAD：`6a16907e44768616a8b003ffe9cec918d67c952d`
- 检查点：`checkpoint-p4-club-operations-mvp` 可追溯到同一提交
- 初始状态：干净；Python 3.13.12
- P4 测试：4 passed, 1 failed
- 全量测试：88 passed, 2 failed, 1 skipped
- 失败原因：两项数据库安全测试硬编码 worktree 内 `data/app.db`，未使用统一配置来源
- 正式库：未应用 006/007；无 P4 表；本任务只读

## 问题与修复对照表

| 问题表现 | 根因 | 修改文件 | 修复方式 | 验证 | 结果 |
|---|---|---|---|---|---|
| 会员入口无会话时返回 500 | HTML 异常处理把 303 重定向改成 500 | `app/main.py` | 保留带 Location 的 3xx | `/member/needs` HTTP 303 | 完全解决 |
| `/club` 与 `/club/operations` 同一处理函数 | 两个装饰器叠在首页函数 | `app/v04f_operations.py`、模板 | 拆分运营处理台并复用看板服务 | 两入口 200 且内容不同 | 完全解决 |
| 会员需求/供给页面空白且写旧暂存表 | 模板缺 content 分支，路由未调用统一资源服务 | 会员门户路由/模板 | 直接写 `v06_market_resources`，显示审核状态 | 服务闭环与 HTTP 详情 200 | 完全解决 |
| 会员报名/取消绕过 P4 生命周期 | 门户直接写旧字段 | 会员门户、P4 服务 | 统一调用 `ClubEventService` | 重复报名幂等、取消状态一致 | 完全解决 |
| 取消已批准报名不递补候补 | 服务仅更新取消状态 | P4 服务、验收脚本 | 递补最早候补、写参与记录/审计/领域事件 | 1 次取消、1 次递补 | 完全解决 |
| 取消后保留 registered 参与记录 | 参与记录未同步 | P4 服务 | 取消未签到报名时删除派生参与记录；已签到禁止取消 | `cancelled_participations=0` | 完全解决 |
| 匹配列表只显示 ID/原始 JSON且无详情 | 查询未连接资源，模板无详情分支 | 运营路由/模板 | 展示双方标题、原因、状态和下一步 | 2 个真实匹配详情 200 | 完全解决 |
| 资源详情不能返回发布会员 | 使用全局资源详情入口 | 运营路由/模板 | 增加 P4 资源详情并关联会员 | 4 个真实资源详情 200 | 完全解决 |
| 活动创建/复制可能复用悬空 event_id | SQLite 自动 ID 未考虑迁移后 profile 引用 | 活动路由 | ID 取 events/profile 最大值加一；增加显式权限 | 创建及复制 HTTP 303→详情 200 | 完全解决 |
| 跨会员同标题资源被误判重复 | 重复判断未限定发布会员 | P4 服务 | 仅复用同一 membership 的统一资源 | 闭环重复提交断言 | 完全解决 |
| 失效会员仍可报名/发布 | 仅检查 active，未检查有效期 | P4 服务 | 增加到期日校验 | 服务测试 | 完全解决 |
| 测试硬编码数据库路径 | 未复用唯一配置来源 | 两个测试文件 | 改用 `resolved_db_path()` | 全量回归 | 完全解决 |

## 文件变更清单

- `app/main.py`：修复会员登录重定向被改成 500。
- `app/services/club_operations_service.py`：报名幂等、候补递补、取消一致性、会员有效期及资源幂等。
- `app/v04f_operations.py`：独立运营入口、申请别名、资源/匹配详情和正确跳转。
- `app/v05c_club_events.py`：创建/复制权限与安全 event_id。
- `app/v05d_member_portal.py`：会员发布、报名、取消、匹配统一接入 P4 服务/表。
- `app/templates/v04f_club.html`：P4 运营、资源、匹配页面最小可理解性修复。
- `app/templates/v05d_member_portal.html`：需求/供给表单、状态、空状态、活动和匹配说明。
- `scripts/verify_p4_club_operations_mvp.py`：完整闭环增加取消递补、拒绝和重复提交断言。
- `tests/test_p4_club_operations_mvp.py`：统一测试数据库路径并更新闭环精确预期。
- `tests/test_real_database_protection.py`：使用唯一配置来源。
- `tests/test_core_06m_p4_final.py`：新增 P4 HTTP、活动创建/复制及入口测试。
- `docs/CORE-0.6M-R1-P4-FINAL-REPORT.md`：本报告。

## 测试报告

- 修改前 P4：4 passed, 1 failed。
- 修改前全量：88 passed, 2 failed, 1 skipped。
- 修改后 P4：7 passed。
- 修改后全量：92 passed, 1 skipped。
- 新增测试：2 个；原失败均由统一测试数据库路径修复，无断言降级。
- 等效 HTTP：俱乐部首页、运营、申请、活动、供需、匹配、ClubLead 均为 200；活动创建/复制为 303 后详情 200。
- 真实详情 HTTP：4 个资源详情和 2 个匹配详情均为 200；接受后状态 `converted_to_lead`，拒绝后状态 `rejected`。
- 完整闭环：5 会员、2 组织、2 活动、10 报名、1 取消、1 递补、6 签到、3 反馈、3 需求、3 供给、4 匹配、4 ClubLead。
- 幂等：重复报名未新增；重复生成匹配为 0；取消记录无孤立 participation；Opportunity 保持 11。

## 006/007 迁移预演

- 安全源副本：`C:\tmp\core06m_p4_formal_rehearsal_copy.db`
- 应用副本：`C:\tmp\core06m_p4_006_007_rehearsal_20260716.db`
- 失败回滚副本：`core06m_p4_failure_rollback_006_20260716.db`、`core06m_p4_failure_rollback_007_20260716.db`
- HTTP 验收副本：`core06m_p4_http_acceptance_20260716.db`
- 初始/006 备份 SHA256：`79aa84277a057b706dcdba99330ccf3d6e4a4f4e768db6cb07373372a9ec4e4c`
- dry-run：006/007 均成功，数据库哈希不变。
- 006：成功，缺失 P3 表由 12 变 0，自动备份完整。
- 007：成功，缺失 P4 表由 9 变 0，自动备份完整。
- 重复执行：006/007 再连续执行成功；逻辑快照前后均为 `4c1adabf4b140dd59d7a1953c8a777f726c4f738155e0382bda74f49afed2d0b`。
- 数据保留：people 44、organizations 24、memberships 2、event profiles 1、resources 20、opportunities 11，前后相同。
- 中途失败：分别在 006/007 `apply_schema` 后强制异常；事务回滚后 schema 完全相同、残留新表 0、integrity=ok。
- 回滚恢复：从 006 前备份恢复后 SHA256 与初始副本一致，integrity=ok。
- 外键检查：副本迁移前已有 30 条历史违反项，迁移后仍为 30；006/007 未新增。列入后续问题，不在本任务修复。
- 正式库 SHA256（任务前后）：`57896BA14E690EBE4CD74661B1B431256621CC9724EA4441996554A4B5E7EA25`，大小和修改时间未变化。
- 结论：**READY**。006/007 可按现有备份工具链进入正式迁移。

## 人工验收（18 步）

1. 备份正式库并再次记录 SHA256。
2. 在测试/副本环境启动 Web，确认 Scheduler/Worker 关闭。
3. 登录运营账号，打开 `/club`，确认俱乐部首页。
4. 打开 `/club/operations`，确认独立运营处理台及队列。
5. 打开会员申请，新增申请并审核通过、激活会员。
6. 进入会员详情，确认 Person、Organization、User 关联和状态记录。
7. 创建活动，发布并开放报名。
8. 用会员门户报名至满员，再提交一名会员进入候补。
9. 取消一个已通过名额，确认最早候补自动变为已通过。
10. 对已通过报名签到，确认状态刷新为已签到。
11. 完成活动并提交反馈，确认反馈关联活动和报名。
12. 从会员门户发布需求，确认进入统一资源表待审核。
13. 发布供给，确认发布主体和返回会员链接。
14. 运营审核通过需求与供给并生成候选匹配。
15. 进入匹配详情，确认双方标题、原因、分数和状态。
16. 接受一条匹配并形成 ClubLead；确认详情显示跟进记录。
17. 拒绝另一条匹配；刷新后确认不再显示待处理。
18. 重复报名/生成匹配，确认无重复；检查正式库哈希未变化。

## 后续问题清单

- 当前正式库安全副本在本任务开始前已有 30 条外键违反项；006/007 未增加。建议另立数据库历史一致性审计任务，不在 P4 本轮处理。
- `TestClient` 输出 Starlette/httpx 弃用警告；不影响本轮功能，后续依赖升级单独处理。
- 本轮未进入真实浏览器 UI，会话和页面采用等效 HTTP 验收；人工点击步骤如上。

## 最终结论

P4 真实闭环已跑通；受测 P4 路径无非预期 404/500；需求发布、供给发布、匹配接受/拒绝和 ClubLead 均可用；数据真实写入临时数据库；正式数据库未变化；006/007 预演通过。结论为 **READY**，建议在完成即时备份和维护窗口确认后执行正式迁移；本任务不进入 P5 或其他下一阶段开发。
