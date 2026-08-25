# MVP-R7 基线

记录时间：2026-08-24（Asia/Shanghai）

## 代码与运行基线

- 唯一正式项目目录：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1`
- 分支：`release/mvp-rc1.2`
- HEAD：`01b9cc61a476df4b4b4cec0c66d79e048591f398`
- 工作区：干净
- 正式数据库：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`
- 数据库 SHA256：`4E9C0E72DE4E606669C8DEAE7EC4AC68A1553C1214C90D617C2A528DC4907256`
- `PRAGMA integrity_check`：`ok`

本基线由只读连接取得。为获得可靠哈希，停止了该目录中占用 8000 端口的既有 `uvicorn --reload` 进程；未停止其他工程进程。

## 正式库记录基线

| 对象 | 数量 |
|---|---:|
| Source | 15 |
| Monitoring Run | 114 |
| Collection Item | 435 |
| Intelligence | 30 |
| Subject Link | 1 |
| Organization | 24 |
| Person | 44 |
| Project | 5 |
| Resource | 30 |
| Match | 0 |
| Opportunity | 11 |
| FollowUp | 4 |
| Canonical Relationship | 25 |
| Intelligence Evidence | 6 |

30 条 Intelligence 的组成并不等于 30 条真实运营样本：

- 20 条为显式 `is_demo=1` 的历史演示数据；
- 5 条为 EMA 真实采集但仍处于 `pending_processing` 的记录；
- 5 条为 R6 已人工核验并发布的真实情报（ID 29–33）。

因此，R7 的真实样本基线是 10 条非演示记录，其中正式发布且已核验为 5 条。后续不会用演示数据虚增真实样本数量。

## 来源基线

### ACTIVE（5）

| ID | 来源 | 频率 | 健康 | 历史采集 | 已形成正式产品 | 基线判断 |
|---:|---|---|---|---:|---:|---|
| 3 | 36克 | manual | degraded | 1 | 0 | 可覆盖融资/企业动态，但稳定性不足，只做受控手工验证 |
| 4 | EMA News RSS | daily | healthy | 206 | 4 | 监管/临床覆盖有效，但泛机构新闻与重复条目较多 |
| 10 | BioNTech Newsroom | daily | healthy | 11 | 0 | 企业官方来源，采集正常，尚未形成合格正式产品 |
| 11 | Roche Media Releases | daily | healthy | 11 | 0 | 企业官方来源，采集正常，尚未形成合格正式产品 |
| 13 | Q-BAY公开项目动态 | weekly | healthy | 1 | 1 | 与运营场景直接相关，已形成主体链接与 Resource |

### CANDIDATE（5）

| ID | 来源 | 覆盖类别 | 基线状态 |
|---:|---|---|---|
| 14 | CDE公开信息 | 监管/政策 | 未实测，保持候选 |
| 15 | NMPA政务服务公告 | 监管/政策 | 未实测，保持候选 |
| 16 | 上海生物医药外资项目政策 | 上海产业政策 | 具体政策页，可作为受控准入候选 |
| 17 | Pfizer Press Release Archive | 企业/BD | 未实测，保持候选 |
| 18 | Novartis Media Releases | 企业/BD | 未实测，保持候选 |

### DISABLED（5）

| ID | 来源 | 原因 |
|---:|---|---|
| 1 | 药明康德 | 连续失败并自动暂停 |
| 2 | 鲸准 | robots denied |
| 5 | FDA Press Announcements | 泛食品/召回列表噪声 |
| 6 | ClinicalTrials.gov Search | 通用检索/术语页，不是具体研究 |
| 12 | AstraZeneca Press Releases | 访问/同意页，质量门不通过 |

调度查询只选择 `is_enabled=1`、未停用、未自动暂停且非 manual 的来源；R7 将继续验证 DISABLED 来源不会被自动调度。

## R6 主体关联误差基线

| Intelligence | 现状 | 误差类别 | 基线结论 |
|---:|---|---|---|
| 29 | 抽取 `LIBTherapeutics`，现有正式主体无匹配 | B：真实新主体候选 | 应向用户显示候选及公开依据，但不得自动创建 Organization |
| 30 | 人事变动正文包含 Ivo Claassen 等人物，未形成 Person 候选 | D：实体提取漏识别 | 应记录漏识别；不能自动新增人物 |
| 31 | EMA 加速审评事件，现有证据片段不足以确认企业/人物 | A：公开事实中缺少可确认主体 | 保持未关联，不强行创建主体 |
| 32 | 抽取 `MeetinghighlightsfromthePharma` | D：标题片段误识别 | 应过滤伪主体，不进入新主体确认入口 |
| 33 | 来源登记主体 Q-BAY 已正确关联；正文另有 5 个噪声候选 | 已有关联 + D：正文噪声 | 保留来源登记主体；噪声不得干扰已确认链接 |

## 价值转化基线

- 已核验真实 Intelligence：5
- 已关联真实 Intelligence：1（ID 33）
- 由真实 Intelligence 形成 Resource：1（ID 33）
- 由 R6 真实 Intelligence 形成 Opportunity：0
- 真实商机结论：尚无足够事实，不得为了指标创建 Opportunity
- 当前页面已有确定性事件类型与“下一步”提示，但尚未明确区分 `INFORMATION / WATCH / ACTIONABLE`，也未在首屏明确区分“产业事件”和“业务机会”。
- 当前主体候选只展示已匹配到现有正式主体的候选；真实新主体候选不会显示。
- 当前追溯包含本情报直接产生的 Resource、Match、Opportunity、FollowUp、Relationship；尚未展示同主体的其他情报上下文。

## R7 约束

- 不新增表、模型、Service、调度器、依赖、版本目录或 AI 能力。
- 只复用 `GoldenLoopService`、现有 Canonical writer、现有采集/审核/发布链和现有模板。
- 正式写入前必须备份 `data/app.db`。
- 自动测试只使用临时数据库。
- 真实样本不足时如实报告，不重复旧内容凑数。
- 没有真实机会时结论为 `NO_REAL_OPPORTUNITY_FOUND`。
