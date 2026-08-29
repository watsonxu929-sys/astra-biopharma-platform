# MVP-RC1.2A 目标产品导航

## 决策

RC1.2B 的目标一级导航冻结为：

```text
工作台 / 情报 / 企业与人物 / 俱乐部 / 跟进
```

采用产品方案 A：`俱乐部`恢复为正式一级业务场景。`资源`与`Relationship`是围绕情报、主体、俱乐部和机会出现的上下文对象，不独立占一级；`报告`作为情报消费的二级入口；采集、加工、审核、治理和恢复操作全部进入管理控制台。

## USER_PRODUCT 目标树

```text
工作台 /platform
├─ 今天值得处理
│  ├─ 查看情报与依据
│  ├─ 执行一个明确下一步
│  └─ 暂不处理 / 恢复今天已忽略
├─ 我的待办
│  └─ 进入机会或任务
└─ 最近跟进
   └─ 继续进行中的机会

情报 /intelligence
├─ 情报列表
│  └─ 筛选、查看详情
├─ 情报详情
│  ├─ 事实、来源、主体、业务价值、下一步
│  ├─ 相关 Relationship / Resource / Opportunity 上下文
│  └─ 普通用户只做被授权的业务动作
├─ 订阅（辅助入口）
└─ 报告
   ├─ 已审核报告列表
   └─ 报告阅读页

企业与人物 /network
├─ 企业/机构目录（默认）
├─ 人物目录
├─ 主体档案
│  ├─ 基础资料
│  ├─ 最近情报
│  ├─ 联系人和 Relationship
│  ├─ Resource
│  ├─ Opportunity / FollowUp
│  └─ Evidence
├─ 关系网络（上下文视图）
└─ 人脉推荐（有权限时的次级入口）

俱乐部 /club
├─ 俱乐部首页
│  ├─ 会员：我的活动、供需、推荐、申请、通知
│  └─ 运营：今日待处理业务摘要，不直接塞入维护表单
├─ 会员
│  ├─ 普通业务目录/档案读取
│  └─ 会员维护、导入、绑定进入 Admin
├─ 活动
│  ├─ 活动列表、详情、报名
│  └─ 创建、审核、签到、反馈管理进入 Admin
├─ 需求与供给
│  └─ 使用 Canonical Resource 的 Club 场景筛选
└─ 我的会员账户
   └─ 资料、通知、报名、偏好

跟进 /opportunities
├─ 合作机会
├─ 机会详情
│  ├─ 来源 Intelligence / Resource / Match
│  ├─ 主体与关系上下文
│  ├─ FollowUp / Task
│  └─ Outcome / Evidence / Relationship
├─ 我的待办
└─ 会议（次级）
```

## 辅助工具区

不进入一级或业务二级主树：

- 全局搜索。
- 我的收藏：使用 `v06_favorites`，置于用户工具/账号菜单。
- 订阅：可以保留在情报的辅助入口。
- 最近访问：在没有真实持久化来源前隐藏，不展示空壳入口。
- Resource 与 Relationship 的全局列表可作为上下文/搜索落点存在，但不能与五个业务场景争夺一级导航。

## ADMIN_CONSOLE 目标树

```text
管理控制台 /admin/platform
├─ 情报运行
│  ├─ Source / Source Discovery
│  ├─ Collection / Run / Item / Snapshot
│  ├─ Processing Job / Block / Candidate
│  ├─ Review Queue / Publish
│  └─ 失败恢复 / 重新加工 / 运行记录
├─ 主体与关系治理
│  ├─ Person / Organization 管理
│  ├─ Candidate / Merge / Governance
│  └─ Relationship / Evidence 治理
├─ 俱乐部运营
│  ├─ Membership / Application / Import / Binding
│  ├─ Event 创建、报名审核、签到与反馈
│  ├─ Club operation queue
│  └─ Resource/Match/Lead candidate 审核
├─ 报告运营
│  ├─ 固定报告生成参数
│  ├─ Job / Draft / Review / Approve / Archive
│  └─ 错误恢复
└─ 系统治理
   ├─ User / Permission / Identity
   ├─ Integrity / Migration / Audit
   └─ Scheduler / Worker / System operations
```

同一业务对象允许“普通用户阅读 + 管理员维护”，但边界必须是两个呈现层：业务页只提供阅读和合法业务动作；新增、编辑、导入、批量、审核、重跑、治理、恢复等动作只能从管理控制台进入。底层继续复用同一 Canonical Model 与 Service。

## 页面职责冻结

| 目标页面 | 唯一首要业务问题 | Primary Action（最多1个） |
|---|---|---|
| 工作台 | 今天最值得处理什么？ | 打开最高优先事项 |
| 情报列表 | 最近有哪些值得看的产业动态？ | 打开情报 |
| 情报详情 | 发生了什么、涉及谁、下一步是什么？ | 执行建议下一步 |
| 企业/人物目录 | 我要找的主体是谁？ | 打开主体档案 |
| Organization 档案 | 这是谁、发生什么、认识谁、有什么资源、在跟进什么？ | 开始/继续跟进 |
| 俱乐部 | 会员/活动/供需今天要处理什么？ | 进入当前首要 Club 动作 |
| 跟进 | 哪个机会需要继续推进？ | 打开机会 |
| 报告阅读 | 当前周期有哪些已审核结论？ | 阅读报告 |
| 管理控制台 | 哪项数据或运行工作需要维护？ | 进入选定管理模块 |

## 导航深度目标

- 从一级导航到任一核心业务对象详情：最多 2 次点击。
- `/network` 采用 `DIRECT_TO_DIRECTORY`：默认直接展示企业/人物目录，不再用纯统计 Landing 增加一跳。
- Intelligence → Subject → Opportunity/FollowUp 保持上下文连续；不要求用户返回全局列表重新寻找对象。
- Club → Event/Member/Resource 最多 2 次点击；管理动作可多一层进入 Admin。

## 工作台与空状态规格

工作台只保留三块高频内容：`今天值得处理`、`我的待办`、`最近跟进`。现有排序规则冻结，不在 RC1.2B 发明新评分模型。

无优先情报时必须显示：

> 今天暂时没有需要优先处理的产业动态。

次级动作固定为：`[查看全部情报]`。

`暂不处理`仅改变当前用户当天的工作台反馈状态，使该项退出今日列表；不得修改或删除 Intelligence。用户可在“今天已忽略”恢复。

## 俱乐部决策

选择 `OPTION 1`：俱乐部恢复为一级正式业务场景。

理由：Club 已有会员申请、会员身份、活动、报名、签到、反馈、供需、匹配、通知和运营队列等独立且重复发生的动作，能形成商业场景闭环；底层 Organization、Person、Resource、Match、Opportunity、FollowUp、Relationship 继续复用 Canonical Core，因此恢复入口不需要新增业务 Model，也不破坏架构。

## RC1.2B 边界

目标树只授权：入口重排、已有页面合并、页面聚合、视觉统一、交互连续性、空状态、桌面适配、产品/后台分层。它不授权新增表、Model、Service 体系、Crawler、Provider、AI、Search、推荐/匹配/报告算法、翻译 Provider 或数据治理逻辑。
