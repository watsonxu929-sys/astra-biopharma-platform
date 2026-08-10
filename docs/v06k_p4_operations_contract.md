# v0.6K P4 俱乐部运营字段契约与闭环验收报告

## 结论

- 交付状态：`data_complete`
- 自动验收：通过。
- 浏览器验收：`manual_browser_acceptance_pending`。Codex 浏览器仅尝试一次，因 Windows ACL 无法启动，未调整 ACL、未重复尝试。
- 可见结果：使用迁移至 008 的隔离数据库启动应用时，`GET /club/operations` 由 500 修复为 200；会员、活动、报名审批、签到、反馈均真实写入临时数据库，刷新及 TestClient 生命周期重启后仍存在。
- 正式数据库：未迁移、未执行 DDL/DML、未写测试数据或迁移记录。

## 根因

`event_date` 确实存在，但属于核心活动表 `events.event_date`，不属于 `v05c_club_event_profiles`。资料表以非空外键 `event_id -> events.id` 关联活动日期。原 `app/v04f_operations.py` 在运营台和俱乐部首页直接从资料表读取/筛选 `event_date`，因此数据库迁移本身成功、Schema Preflight 也可启用，但请求运行到错误 SQL 时仍返回 500。

这不是 ORM 字段遗漏，也不是 007/008 漏迁移。P4 当前没有一套独立 SQLAlchemy ORM，核心路径使用服务层和受控 SQLite SQL。此前定向检查没有建立“查询字段必须存在于实际表”的契约断言，也没有完整覆盖迁移后运营台日期查询，因此未提前发现。

## Schema 与字段契约

迁移后演练库只读审计确认了相关表、列、类型、可空性、默认值、外键和索引。核心事实如下。

| 业务含义 | 数据库字段 | ORM 字段 | 路由/服务字段 | 模板字段 | 最终状态 |
|---|---|---|---|---|---|
| 活动日期 | `events.event_date` (`VARCHAR(50)`, nullable) | 无独立 P4 ORM | `event_date`，通过 `events` JOIN 读写 | `event.event_date` | 一致 |
| 活动开始时间 | 不存在 | 不存在 | 不持久化 | 不展示为已有能力 | 未实现，未擅自加列 |
| 活动结束时间 | 不存在 | 不存在 | 不持久化 | 不展示为已有能力 | 未实现，未擅自加列 |
| 报名截止 | `v05c_club_event_profiles.registration_deadline` | 无独立 P4 ORM | `registration_deadline` | `event.registration_deadline` | 一致 |
| 活动状态 | `v05c_club_event_profiles.lifecycle_status`；`status` 为兼容字段 | 无独立 P4 ORM | 状态机使用 `lifecycle_status` | 服务输出状态 | 一致 |
| 报名状态 | `v05c_club_event_registrations.lifecycle_status`；`status` 为兼容字段 | 无独立 P4 ORM | 审核、候补、取消、签到均使用生命周期状态 | 服务输出状态 | 一致 |
| 报名时间 | `v05c_club_event_registrations.registered_at` | 无独立 P4 ORM | 服务写入 | 报名列表读取 | 一致 |
| 签到时间 | `v05c_club_event_participation.check_in_time`；注册表同步 `checked_in_at` | 无独立 P4 ORM | 签到服务幂等写入 | 详情/运营台读取 | 一致 |
| 反馈时间 | `p4_event_feedback.created_at/updated_at` | 无独立 P4 ORM | 反馈服务写入/更新 | 详情读取 | 一致 |
| 会员有效期 | `v04f_club_memberships.expired_at` + `status` | 无独立 P4 ORM | 有效会员查询排除过期记录 | 运营指标 | 一致 |

活动资料表没有 `event_date`；所有日期排序、筛选和统计必须 JOIN `events e ON e.id=p.event_id`。

## 发现与处理

| 位置 | 原问题 | 真实契约 | 影响 | 处理 |
|---|---|---|---|---|
| `app/v04f_operations.py` | 从活动资料表直接查询 `event_date` | `events.event_date` | 首页/运营台 500 | 改为 JOIN 核心活动表 |
| 俱乐部首页 | 中文服务指标被英文模板键读取 | 统一 `web_metrics` 映射 | 有数据仍显示 0 | 复用同一指标服务 |
| 运营台 | 重复 SQL，并对 SQLite 错误返回 0/空列表 | Schema Preflight + 错误显式暴露 | 假成功/假空状态 | 删除该路径的宽泛降级 |
| 报名/线索页签 | 使用不存在的业务枚举 `candidate`、`pending_review` | 报名 `pending_review`；线索 `pending/reviewed/accepted` | 队列漏数 | 统一真实枚举 |
| `/club/applications` | 仅有 `/club/admin/applications` | 两个路径调用同一处理函数 | 约定入口 404 | 添加同函数别名，不复制逻辑 |
| P4 Schema Preflight | 只覆盖部分表列 | 覆盖 P4 页面和 API 的真实依赖 | 缺列可能变成 500 | 扩充只读能力契约，缺失返回 503 |
| 活动编辑 | 页面链路缺少持久化更新入口 | 同时更新 `events` 与 profile 的真实列 | 无法验收修改后保存 | 增加最小 POST 和审计记录 |
| 活动创建/复制 | 历史副本存在悬空 profile `event_id`，普通自增会复用 | 新编号取 `events.id` 与 profile `event_id` 联合最大值 + 1 | 新建活动唯一约束失败 | 使用既有验证脚本同类兼容策略 |
| 历史外键 | 部分报名/参与外键仍指向 `v04f_club_memberships_old` | 服务已有显式旧库兼容 | 后续迁移维护风险 | 本轮只记录，不改迁移 |

## 运营指标口径

| 指标 | 数据表 | 查询条件 | 排除无效数据 |
|---|---|---|---|
| 会员总数 | `v04f_club_memberships` | 全部会员记录 | 否 |
| 待审核会员 | `v04f_club_applications` | `submitted/under_review/need_more_info` | 是 |
| 有效会员 | `v04f_club_memberships` | `status='active'` 且未过期 | 是，排除过期/非 active |
| 活动总数 | `v05c_club_event_profiles` | 全部活动资料 | 否 |
| 有效报名 | `v05c_club_event_registrations` | `lifecycle_status<>'cancelled'` | 是，排除取消 |
| 待审核报名 | 同上 | `lifecycle_status='pending_review'` | 是 |
| 已签到 | 同上 | `lifecycle_status='checked_in'` | 是 |
| 反馈数量 | `p4_event_feedback` | 实际反馈记录数 | 不使用静态值 |
| 候补人数 | registrations | `lifecycle_status='waitlisted'` | 是 |
| 今日/近期活动 | profiles JOIN `events` | `events.event_date` 与当前日期比较 | 排除 `cancelled/archived` |
| 会后待跟进 | registrations + profiles + feedback | 已完成且已签到、尚无反馈 | 是 |

同一口径由 `ClubOperationsDashboardService.summary()` 生成，俱乐部首页和运营台复用 `web_metrics`，不再各自维护一套 SQL。

## P4 最小闭环验收

所有写入均发生在 pytest 临时目录中的 `v06j_app_migrated.db` SQLite backup 副本，测试结束后由 pytest 清理；未写入项目随包数据库。

| 步骤 | 页面/API | 写入 | 刷新后 | 生命周期重启后 | 结论 |
|---|---|---:|---:|---:|---|
| 提交会员申请 | `ClubMembershipService.submit_application` | 是 | 存在 | 存在 | 通过 |
| 查看并审核申请 | `/club/applications`、审核 POST | 是 | 存在 | 存在 | 通过 |
| 激活并查看会员 | 会员生命周期 POST、`/club/members` | 是 | 存在 | 存在 | 通过 |
| 创建、编辑活动 | 活动 create/update POST | 是 | 存在 | 存在 | 通过 |
| 发布并开放报名 | 活动状态 POST | 是 | 存在 | 存在 | 通过 |
| 报名及审批 | registrations API + 审批服务 | 是 | 存在 | 存在 | 通过；重复报名返回同一记录 |
| 签到 | check-in API | 是 | 存在 | 存在 | 通过；第二次为幂等结果 |
| 反馈 | feedback API | 是 | 存在 | 存在 | 通过；刷新式第二次提交更新同一记录 |
| 真实指标 | `/club/operations` | 读取真实记录 | 增量正确 | 正确 | 通过 |

测试还构造了已过期会员、候补报名和已取消报名，确认有效会员和有效报名不包含无效状态。

## HTTP 结果

| 页面/API | 方法 | 状态码 | 数据库行为 | 结论 |
|---|---|---:|---|---|
| `/club` | GET | 200 | 只读真实指标与活动 | 通过 |
| `/club/members` | GET | 200 | 只读会员 | 通过 |
| `/club/applications` | GET | 200 | 只读申请 | 通过 |
| `/club/events` | GET | 200 | 只读活动 | 通过 |
| `/club/events/{id}` | GET | 200 | 只读活动详情 | 通过 |
| `/club/events/999999` | GET | 404 | 无写入 | 正确 |
| `/club/operations` | GET | 200 | 只读真实指标 | 通过；真实 Uvicorn 临时服务亦为 200 |
| `/club/operations?tab=checkin` | GET | 200 | 只读当日活动/报名 | 通过 |
| 活动 create/update/status | POST | 303 | 写临时库 | 通过 |
| 会员审核/生命周期 | POST | 303 | 写临时库 | 通过 |
| registrations API | POST | 200 | 写临时库；重复幂等 | 通过 |
| check-in API | POST | 200 | 写临时库；重复幂等 | 通过 |
| feedback API | POST | 200 | 写临时库；重复更新 | 通过 |
| 未认证运营页面/API | GET/POST | redirect 或 401/403 | 无写入 | 后端权限未绕过 |
| 缺失 P4 Schema | GET | 503 | 无写入 | 受控降级，不伪装空数据 |

## 测试结果

| 命令 | 结果 | 覆盖 |
|---|---|---|
| `.venv\Scripts\python.exe -m py_compile ...` | 通过 | v0.6K 修改 Python 文件语法 |
| `.venv\Scripts\python.exe -m pytest -q tests\test_v06k_p4_operations_contract.py` | `3 passed` | 字段契约、权限、503、P4 HTTP、完整写入、指标、刷新/重启持久化 |
| 真实 Uvicorn + 临时 DB `GET /club/operations` | 200 | 独立进程 HTTP 渲染 |
| `git diff --check` | 通过 | 补丁空白检查 |

仅出现 FastAPI/Starlette 既有弃用警告；本轮未扩展处理。

## 修改文件

| 文件 | 修改内容 | 原因 | 风险 |
|---|---|---|---|
| `app/v04f_operations.py` | 正确 JOIN 活动表；复用指标服务；修正页签枚举；删除假空降级；增加申请入口别名 | 修复 500 和假指标 | 低，P4 查询范围 |
| `app/services/club_operations_service.py` | 统一真实指标；增加最小活动更新服务与审计 | 字段契约和闭环持久化 | 中，涉及 P4 写入事务 |
| `app/v05c_club_events.py` | 创建/复制权限；安全 event_id；活动更新 POST | 权限和真实活动链路 | 中，已覆盖冲突数据场景 |
| `app/templates/club_operations.html` | 使用统一指标键 | 防止有数显示 0 | 低 |
| `app/templates/v05c_club_events.html` | 增加现有样式的最小编辑表单 | 完成修改持久化闭环 | 低 |
| `app/services/schema_preflight.py` | 扩大 P4 表列只读预检 | 缺表/缺列受控 503 | 低 |
| `app/capability_guard.py` | 将 P4 页面/API 映射到 `club_operations` 能力 | 防 500/假空 | 低 |
| `tests/test_v06k_p4_operations_contract.py` | 新增隔离库定向验收 | 防字段和状态机回归 | 低 |
| `docs/v06k_p4_operations_contract.md` | 本报告 | 可追溯交付 | 无运行风险 |

## 正式数据库保护

| 项目 | 任务开始 | 任务结束 |
|---|---|---|
| SHA-256 | `3EB3C405BE2B426B3F96090DC933FD76EE8766ABAC5DB59A005BC2A9F5972151` | 同左 |
| 文件大小 | 4,173,824 bytes | 4,173,824 bytes |
| 修改时间 UTC | `2026-07-14T09:26:29.2039738Z` | 同左 |
| 业务表数（排除 SQLite 内部表） | 164 | 164（哈希相同，最终只读复核） |
| `platform_migration_runs` 记录 | 1 | 1（哈希相同，最终只读复核） |

最终普通哈希读取遇到其他进程共享占用，因此使用 `FileShare.ReadWrite` 的只读文件句柄复核；结果与开始值完全一致。表数和迁移记录数使用 `mode=ro&immutable=1` 查询。未停止未知进程，未生成数据库锁文件。

演练源库也未变化：SHA-256 `560A4007E1D240EAD4DEFA31C988E699155EE0327E5BD2891ED30861A43A9339`。测试和浏览器 Smoke 都先通过 SQLite backup 复制到系统临时目录；浏览器 Smoke 临时进程已停止，临时库已删除。

## 现有历史/辅助脚本，本轮未处理

以下 10 个文件未修改、未重命名、未移动、未删除、未执行，也未让其连接任何数据库：

1. `scripts/check_db_tables.py`
2. `scripts/check_intelligence_data.py`
3. `scripts/check_people_data.py`
4. `scripts/check_recommendations.py`
5. `scripts/check_server_logs.py`
6. `scripts/check_tables.py`
7. `scripts/clean_test_data.py`
8. `scripts/clean_test_opp.py`
9. `scripts/restore_test_opp.py`
10. `scripts/test_workspace.py`

## 未解决/范围外

1. Codex 浏览器受 Windows ACL 限制，人工浏览器验收待完成；没有处理 ACL。
2. 000—008 对全空数据库能建表，但旧运行时部分列并未由该链补齐；v0.6K 按约束未修改统一迁移体系。本轮验收使用 v0.6J 已迁移正式库副本的临时 backup。
3. 部分历史 P4 外键仍指向 `v04f_club_memberships_old`；现有服务有显式兼容，本轮未改迁移。
4. 活动开始/结束时间在真实 P4 Schema 中不存在；未伪造、未新增列。

## 人工浏览器验收清单

在新的正式库副本或专用验收库上，按以下顺序执行，不要使用 `data/app.db`：

1. 打开 `/club`，确认指标和近期活动正常。
2. 打开 `/club/members`。
3. 提交会员申请，在 `/club/applications` 审核，并在会员目录确认。
4. 创建活动，打开活动详情，修改日期/地点并保存。
5. 发布活动并开放报名。
6. 会员报名，运营人员批准报名；重复报名应保持同一记录。
7. 签到两次，第二次应为受控幂等。
8. 提交反馈并刷新，确认内容保留。
9. 打开 `/club/operations` 及各页签，核对会员、报名、签到、反馈、候补数字。
10. 重启 Web 服务，再次检查会员、活动、报名、签到、反馈和运营指标。

## 正式迁移判断

代码与隔离数据闭环已具备，但当前不应立即执行正式库迁移。先完成上述人工浏览器验收，并在维护窗口按既有 v0.6J 流程重新备份、核对副本和回滚材料；确认无误后才具备提交正式迁移审批的条件。本报告不授权、也未执行正式迁移。
