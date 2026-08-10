# MVP-RC1 交付说明

## 产品定位

本版本是生物医药产业情报系统的首个可交付运行基线。系统以公开情报为起点，把正式人物、机构和项目与需求/供给、匹配、合作机会、跟进、结果和产业关系连接起来。Q-BAY 是平台中的社区运营场景，不是第二套资源、机会或关系系统。

## 正式入口

- 登录：`http://127.0.0.1:8000/login`（自动进入正式登录页）
- 首页工作台：`/platform`
- 黄金闭环：`/platform/golden-loop`

正式一级导航只有：工作台、产业关系、情报中心、资源市场、业务协同、Q-BAY 俱乐部。

## 安装与启动

首次安装：

```bat
setup_windows.bat
```

Web 生命周期：

```bat
web_service_windows.bat start
web_service_windows.bat status
web_service_windows.bat stop
```

采集 Worker 独立生命周期：

```bat
collection_worker_windows.bat start
collection_worker_windows.bat status
collection_worker_windows.bat stop
```

`run_windows.bat` 只启动 Web。默认 `APP_RELOAD=false`、`SCHEDULER_ENABLED=false`、`WORKER_ENABLED=false`；Worker 停止时 Web 和黄金闭环仍完整可用。

## 登录方式

使用管理员创建的内部账号登录。viewer 可查看但不能写入；operator 可推进黄金闭环；reviewer/admin 保持现有审核和管理权限。不要启用 `APP_AUTH_DISABLED` 作为正式运行方式。

## 六个核心导航

- 工作台：8 个 Canonical 实时指标和日常入口。
- 产业关系：正式关系、证据和来源回溯。
- 情报中心：已发布情报和情报详情。
- 资源市场：统一需求、供给和来源情报。
- 业务协同：正式 Opportunity、跟进和任务。
- Q-BAY 俱乐部：会员、活动、报名、签到和反馈场景。

## Golden Loop 操作

1. 在情报中心打开一条已发布情报。
2. 进入黄金业务闭环，搜索并关联正式人物、机构或项目。
3. 选择已关联机构，将情报转为需求或供给。
4. 选择一条需求和一条供给，人工确认确定性匹配。
5. 将匹配标记为“感兴趣”，再转为合作机会。
6. 在机会详情登记跟进、下一步、下次跟进时间并创建协作任务。
7. 选择合作达成、未成交或暂停。
8. 只有合作达成且填写可核验证据时，系统才创建正式合作关系。
9. 从关系详情可返回来源机会、匹配和情报。

## 数据库备份与迁移

迁移前先执行现有 `backup_windows.bat`，并在异地目录验证备份可打开。009–011 迁移必须先在副本中执行：

```bat
.venv\Scripts\python.exe scripts\migrate_db.py plan --database <copy.db> --start 009 --target 011
.venv\Scripts\python.exe scripts\migrate_db.py upgrade --database <copy.db> --start 009 --target 011
```

不要手工改表，不要在不明数据库上使用 `--confirm-formal`。迁移器会创建校验过的在线备份；失败时自动恢复。

## 回滚方式

1. 执行 `web_service_windows.bat stop`，确认 Web 已停止。
2. 执行 `collection_worker_windows.bat stop`，停止写入。
3. 保留失败日志和数据库副本。
4. 使用已验证的迁移前完整备份恢复数据库。
5. 切回发布前 Git 标签或提交。
6. 启动 Web，复验登录、`/platform`、关键记录数和数据库完整性。

## 已知限制

- 修改前全量测试已有 46 个历史失败/错误，集中在 006/007/008 旧迁移夹具、旧运行配置契约及环境编码；RC1 未扩大修复这些问题，且未新增失败。
- 存量数据库有 30 项历史外键问题；RC1 验收前后数量不变，不在本轮清理。
- 000–008 空库链仍有历史字段顺序漂移；经真实备份验证的 pre-009 → 011 链已通过。
- 本版本不包含 AI 摘要、AI 匹配、个性化推荐、营销自动化、付费、移动端或全站视觉重构。

## 下一阶段

严格按 `PROJECT_EXECUTION_ROADMAP.md` 进入“数据质量和来源稳定”；当前任务结束后不自动进入下一阶段。
