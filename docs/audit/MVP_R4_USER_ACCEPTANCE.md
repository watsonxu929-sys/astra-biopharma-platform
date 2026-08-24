# MVP-R4 普通运营人员验收记录

验收日期：2026-08-24（Asia/Shanghai）

验收方式：本机现有 Playwright + Chromium `151.0.7922.34`，真实加载HTML/CSS/JavaScript并操作页面。正式数据库仅用于只读页面检查；完整写入链使用操作系统临时测试数据库。

## 操作结果

| 阶段 | 普通用户操作 | 主要点击 | 人工填写核心字段 | 手工ID | 结果 |
| --- | --- | ---: | ---: | ---: | --- |
| 情报 → Resource | 打开情报、按名称选择两个主体、点击“创建需求/创建供给”并提交 | 6 | 需求类别与内容、供给类别与内容，共4项 | 0 | 来源情报、方向、标题、描述背景和所选主体均自动继承 |
| Resource → Match | 打开需求Resource，阅读候选卡片并点击“确认匹配” | 2 | 0 | 0 | 候选显示双方主体、资源类别、重合点、有效状态和确定性推荐理由 |
| Match → Opportunity | 点击“转为合作机会” | 1 | 0 | 0 | demand、supply、双方主体、Match及Intelligence来源自动继承 |
| Opportunity → FollowUp | 在当前机会中填写沟通内容和下一步并提交 | 1 | 2 | 0 | 无需重新选择Opportunity，跟进进入当前商务时间线 |
| Outcome → Relationship | 记录成功结果和Evidence并提交，再进入形成的关系 | 2 | 3 | 0 | Evidence及Canonical Relationship自动形成并可反向查看 |

整条链人工填写核心字段共9项；手工输入数据库ID严格为0。页面按业务阶段直接跳转，没有无业务意义的中间页。

## 可理解性检查

- 情报详情用“发生了什么 / 涉及谁 / 我能做什么”说明用途与下一步。
- 主体详情聚合相关情报、当前资源、合作机会、跟进和关系，并给出下一步行动。
- Resource候选解释“为什么推荐”，不是只显示分数或内部状态。
- Opportunity详情说明合作双方、来源、当前阶段、最近跟进、待办和下一步。
- 空状态使用运营语言，不显示后台式 `0 records`。
- 正式页面不要求用户理解“Golden Loop”、步骤编号或内部主键。

## 真实浏览器证据

证据目录：`docs/audit/evidence/mvp_r4/`

- `01_workspace.png`：工作台与“今天值得处理”。
- `02_intelligence.png`：情报业务起点。
- `03_subject.png`：主体业务轨迹。
- `04_resource_match_candidates.png`：Resource及解释型候选。
- `05_match_confirmed.png`：匹配确认。
- `06_opportunity.png`：合作机会工作台。
- `07_follow_up.png`：跟进结果。
- `08_outcome.png`：合作达成。
- `09_relationship.png`：正式关系与Evidence。
- `10_qbay.png`：Q-BAY运营场景。
- `11_search.png`：全局搜索。
- `browser_result.json`：URL、HTTP状态、viewport、console、page error、network和数据库隔离结果。

1366×768与1600×900均无横向溢出；Console Error、Page Error、失败请求和非预期HTTP错误均为0。

## 结论

PASS。普通运营人员可在不输入内部ID的前提下完成“看情报 → 找主体/资源 → 确认匹配 → 推进合作 → 沉淀证据与关系”。
