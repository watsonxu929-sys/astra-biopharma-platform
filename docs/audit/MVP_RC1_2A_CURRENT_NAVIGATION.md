# MVP-RC1.2A 当前导航与页面树

审计基线：`release/mvp-rc1.2` / `6bfc16e67beaa20c6ea5e168439d86020b2a2c83`。本清单来自路由、Capability Registry、模板与 Chromium 151.0.7922.34 的实际渲染，不按历史文档推断。

## 当前一级导航

当前普通产品一级导航由 `app/services/navigation_service.py` 的 `PRIMARY_ORDER` 生成，实际只有：

```text
工作台 / 情报 / 企业与人物 / 跟进
```

`俱乐部`、`资源`与`报告`虽仍有真实页面和能力注册，但不在一级导航。管理用户另见“管理控制台”入口。

## 四层真实产品树

```text
工作台（L1）
├─ 工作台首页 /platform（L2）
│  ├─ 今天值得处理（L3）
│  │  ├─ 查看情报、查看并决定下一步（L4）
│  │  └─ 暂不处理、恢复今天已忽略（L4）
│  └─ 我的待办（L3）
│     └─ 查看全部跟进（L4）
└─ 我的工作区 /workspace（L2；二级导航把它表现为五个 tab，但页面并未实现 tab 切换）
   ├─ 业务概览 ?tab=overview（L3）
   ├─ 我的待办 ?tab=todos（L3；实际页显示 v06_collab_tasks）（L4：打开待办链接当前无已注册目标）
   ├─ 最近跟进 ?tab=followups（L3；实际页未显示 FollowUp）（L4）
   ├─ 我的收藏 ?tab=favorites（L3；查询 v06_favorites，但模板未渲染）（L4）
   ├─ 最近访问 ?tab=recent（L3；route 未提供 recent_views，未发现持久化来源）（L4）
   ├─ 待处理联系（L3；pending contact intents）（L4：进入人物链接当前目标不一致）
   └─ 我的合作（L3；当前用户发起的 active opportunities）（L4：打开机会）

情报（L1）
├─ 情报 /intelligence（L2）
│  ├─ 筛选、分页、情报卡片（L3）
│  └─ 查看详情、查看主体、查看资源、决定下一步、暂不处理（L4）
├─ 情报详情 /intelligence/{id}（L2）
│  ├─ 摘要与状态、主体候选/关联、关系上下文、资源上下文、来源追溯（L3）
│  └─ 确认主体、查看/创建资源、检查匹配、创建机会、状态操作（L4，按权限显示）
├─ 订阅 /subscriptions（L2）
│  └─ 查看、创建或维护订阅（L3/L4）
├─ 采集 /collection（L2；普通导航当前可见）
│  ├─ 来源、采集运行、采集项（L3）
│  └─ 运行采集、查看采集项、进入加工（L4；管理操作）
├─ 情报加工 /processing/jobs（L2；普通导航当前可见）
│  ├─ Job列表、手工任务表单、加工候选（L3）
│  └─ 新建、立即运行、重新加工、进入候选（L4；管理/恢复操作）
├─ 审核发布 /processing/review-queue（L2；普通导航当前可见）
│  └─ 候选审核、发布为 Canonical Intelligence（L3/L4；管理操作）
├─ 报告中心 /reports（L2）
│  ├─ 生成任务、已生成报告、报告模板（L3）
│  └─ 选择类型和日期、生成、查看、编辑草稿、提交、审核、归档（L4）
└─ 其他历史入口（L2）
   ├─ Source Discovery、Sources、Collection Runs（管理）
   ├─ Signals、Research、Watchlists（历史/实验）
   └─ Candidates、Processing Blocks（管理/恢复）

企业与人物（L1）
├─ 关系 Landing /network（L2）
│  ├─ 42 位有效人物、23 家有效企业/机构、5 条有效关系（L3）
│  └─ 进入人物、机构、关系网络（L4）
├─ 人物 /network/people（L2）
│  └─ 搜索、筛选、打开人物档案（L3/L4）
├─ 企业/机构 /network/organizations（L2）
│  └─ 搜索、筛选、打开机构档案（L3/L4）
├─ 主体档案 /network/entities/{type}/{external_id}（L2）
│  ├─ 基础资料、关系、联系人、情报、资源、跟进、历史证据、监测（L3）
│  └─ 查看关系/情报/资源/机会、发起联系、管理监测（L4，编辑应属管理层）
├─ 关系网络 /network/graph（L2）
│  └─ 真实 Canonical Relationship 图与路径（L3/L4）
├─ 人脉推荐 /network/recommendations（L2）
│  └─ 基于关系路径的确定性推荐与查看路径（L3/L4）
└─ 主体治理 /network/governance（L2）
   └─ 候选、合并、治理、时间线（L3/L4；仅管理员/审核者）

跟进（L1）
├─ 合作机会 /opportunities（L2）
│  └─ 筛选、打开机会、进入下一步（L3/L4）
├─ 机会详情 /opportunities/{id}（L2）
│  ├─ 来源情报、资源、匹配、主体、当前状态、任务、跟进、证据（L3）
│  └─ 登记 FollowUp、更新任务、登记 Outcome、补 Evidence（L4）
├─ 协作首页 /collaboration（L2）
│  └─ 机会、任务、会议汇总（L3/L4）
├─ 行动任务 /collaboration/tasks（L2）
│  └─ 查看与更新任务（L3/L4）
└─ 会议 /collaboration/meetings（L2）
   └─ 查看与完成会议（L3/L4）

未进入一级导航的真实业务场景
└─ 俱乐部 /club
   ├─ 俱乐部工作台（会员体验/运营体验分支）
   ├─ 会员 /club/members（当前普通 viewer 从 Club 二级入口进入会到无权限页）
   ├─ 活动 /club/events（普通 viewer 可读）
   ├─ 会员申请 /club/apply
   ├─ 供需与匹配 /club/matches（正式读已切 Canonical Resource/Match）
   ├─ 运营 /club/operations（管理）
   ├─ 活动创建、报名、审核、签到、反馈（业务/管理动作分层）
   └─ 会员账号与通知 /member/*（会员自助层）

上下文业务入口（当前有页面但非一级）
├─ 资源市场 /resources
│  ├─ demand / supply 筛选、资源详情、匹配候选
│  └─ 创建、编辑、关闭、安全删除（管理动作）
├─ Relationship 详情 /relationships/{id}
│  └─ 来源 Opportunity、Evidence、Intelligence 反向追溯
└─ 全局搜索 /search
   └─ 搜索 Intelligence、Person、Organization、Resource 等现有对象

管理控制台
└─ /admin/platform
   ├─ Source / Source Discovery / Collection
   ├─ Processing Job / Candidate Review / Publish
   ├─ Entity Governance / Relationship Governance
   ├─ Club operations / Member import / Event operations
   ├─ User / Permission / Identity link
   ├─ Data integrity / migration / audit / system operations
   └─ Report generation/review and recovery operations
```

## 当前结构的可验证矛盾

- `Capability Registry` 把 `/workspace?tab=...` 注册为五个二级入口，但 `/workspace` 不读取 `tab`；它们实际打开同一固定页面。
- 工作台首页已经承担“今天值得处理 + 我的待办”，`/workspace` 再次汇总待办/合作，职责重复。
- `情报`二级导航同时混入消费页、数据采集、加工、审核和报告生成，USER_PRODUCT 与 ADMIN_CONSOLE 未分离。
- `/network` 是统计/入口 Landing，而不是目录；用户访问企业需再多一跳。
- `俱乐部`拥有独立业务闭环但无一级导航高亮；viewer 可进首页/活动，却不能从页面给出的“会员”入口进入会员目录。
- `/reports` 可列出和生成记录，但真实 Chromium 打开 `/reports/1` 返回 422；当前报告详情链不成立。
- `/processing/jobs` 是后台操作与恢复工具，却在普通情报导航中占据正式入口。

## 浏览器事实

- 引擎：Chromium `151.0.7922.34`。
- 视口：1366 宽与 1920 宽；22 个页面/身份组合。
- 除 `/reports/1` 的既有 422 外，其余受检页面状态正常；Page Error 0、request failure 0、横向溢出 0、用户可见乱码 0。
- `/reports/1` 同时产生唯一 Console Error；这属于当前产品事实，不在本审计任务修复。
