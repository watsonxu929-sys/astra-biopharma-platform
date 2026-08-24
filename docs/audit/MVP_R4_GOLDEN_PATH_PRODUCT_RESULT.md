# MVP-R4 Golden Path产品验收报告

验收日期：2026-08-24（Asia/Shanghai）

## 1. 一句话结论

**PASS**：现有Canonical能力已经组织成普通运营人员可以完成的真实合作推进流程；正式库未写入验收数据，真实Chromium验收、Golden Path、R2/R3契约和目录清理均通过。

## 2. 产品Before / After

Before：情报、主体、资源、匹配、机会和关系虽已Canonical化，但上下文分散，详情页仍有工程术语、内部ID输入和不清晰的下一步。

After：用户从情报详情按业务语言关联主体并创建需求/供给；Resource直接展示可解释候选；确认后创建Opportunity；在当前机会内记录FollowUp和Outcome；成功结果自动形成Evidence与Canonical Relationship。正式一级导航没有增加，用户界面不再把该流程称为“Golden Loop”。

## 3. Root Cleanup

- Root files BEFORE：75。
- Root files AFTER：11。
- 删除：52个已由Git历史保留、无当前runtime/README/测试/迁移依赖的历史报告、v05迁移/验证启动器及一次性脚本。
- 移动：12个仍有效的Windows维护和生命周期脚本至 `scripts/windows/`，并修正根目录解析及互相调用。
- 保留：`.env`、环境示例、Git/工程规则、README、pytest配置、四个仍有调用方的requirements清单和唯一正式启动入口 `run_windows.bat`。
- R3回滚备份 `data/migration_backup/pre_mvp_r3_20260824_093559.db` 保留、被Git忽略且不是runtime DB。

完整逐文件依据见 `docs/audit/MVP_R4_ROOT_CLEANUP.md`。删除后的app import、启动、生命周期脚本、契约、Golden Path及HTTP检查通过。

## 4. Intelligence

情报详情现在以“发生了什么 / 涉及谁 / 我能做什么”组织。operator可按名称选择现有Person、Organization或Project；可从当前情报直接创建需求或供给。来源情报和主体上下文在后台继承，页面不要求输入Subject ID或Intelligence ID。

## 5. Subject

Person/Organization详情使用现有Canonical数据组合基础信息、相关情报、当前资源、Opportunity、已确认关系、最近FollowUp和下一步。创建资源与查看关系的动作带入当前主体，不建立第二套Subject模型。

## 6. Resource

资源市场继续只使用Canonical Resource与 `direction=demand|supply`。从情报进入创建页时，方向、来源、推荐标题、背景和已选主体自动带入。列表卡片说明主体、内容、状态、来源、有效期和候选数；空候选给出补充类别/描述的实际建议。

## 7. Matching

匹配复用既有 `UnifiedResourceService` 和P4 Match模型，没有Matching V2。候选规则为方向相反、发布/有效、类别与关键词/行业/地区重合、显式owner不同，并排除已拒绝组合。候选卡展示对方主体、资源、类别、重合点、双方有效状态及中文推荐理由；用户可“确认匹配”或“暂不匹配”。

## 8. Opportunity

确认后的Match可一键“转为合作机会”。Opportunity通过R2唯一Canonical Writer创建，并自动继承demand、supply、双方主体、Match来源及相关Intelligence；不重复填写Resource、Match或Subject ID。详情页展示双方、来源、阶段、跟进、待办和下一步。

## 9. FollowUp

FollowUp表单固定在当前Opportunity上下文中。用户只填写沟通内容、下一步及可选的时间/方式/下次日期，不需要重新选择Opportunity ID；提交后回到同一商务时间线。

## 10. Outcome

用户使用业务语言记录合作结果。成功结果继续调用R2/R3已有后端链形成证据与关系；lost/rejected/cancelled保留Opportunity、FollowUp和Outcome历史，但契约测试确认不会形成虚假Relationship。

## 11. Relationship / Evidence

真实测试数据库中的成功流程生成1条Evidence和1条Canonical Relationship；关系页可反向看到Opportunity、Evidence和Intelligence。R3遗留的1条MANUAL_REVIEW经证据核对决定EXCLUDE，未伪造主体或证据，也未写正式库。

## 12. User Acceptance

- 核心流程主要点击：12次。
- 人工填写核心字段：9项。
- 手工内部ID：0。
- 重复填写上游字段：0。
- 无无业务意义的中间页面。

逐阶段记录见 `docs/audit/MVP_R4_USER_ACCEPTANCE.md`。

## 13. Database Safety

- 正式数据库：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db`。
- Preflight SHA256：`7A36C67B16925C69C708E7DD7B3040A6B8C3C48C02E956D76CDA291871A980E7`。
- 最终测试复核后SHA256：`F5185791D660895E351FC49D0B38DDEDDCDB4F7011D099ECD8A048202B1AACE9`。
- `integrity_check=ok`。
- 12张核心表前后行数逐表一致，正式验收数据写入为0。
- 文件SHA变化来自只读Uvicorn连接后的SQLite WAL/checkpoint技术性变化；业务快照无变化。
- 自动写验收只使用OS临时测试数据库，验收目录已删除；正式库无测试账号、marker或虚假业务对象。

## 14. Tests

- R4新增测试失败：0。
- R2 Single Write Contract：通过。
- R3 Canonical Read/Migration Contract：通过。
- Golden Path E2E：通过，按页面/服务正式路径生成Candidate、确认Match、创建Opportunity、FollowUp、Outcome、Evidence和Relationship。
- viewer/权限与正式入口定向回归：通过。
- 全量pytest：114 passed / 1 skipped / 15 failed / 3 errors；失败和错误名称与R4前已知历史集合一致，新增历史失败0。

## 15. HTTP / Browser

- in-app浏览器通道首次连接因同一Windows ACL helper错误失败；未反复重试或据此改业务代码。
- 项目已有Playwright与本机缓存Chromium `151.0.7922.34` 随即完成真实浏览器验收，无新下载。
- Viewport：1366×768、1600×900。
- 正式Uvicorn只读检查：工作台、情报、人物/企业、Resource、Opportunity、Q-BAY和搜索正常。
- 临时测试库浏览器写链：Intelligence → Subject → Resource → Match Candidate → Confirm → Opportunity → FollowUp → Outcome → Evidence → Relationship完整通过。
- 非预期404/500：0；Console Error：0；Page Error：0；关键Network Failure：0；横向溢出：0。
- 截图和结构化结果位于 `docs/audit/evidence/mvp_r4/`。

## 16. Remaining Product Problems

- 当前29条正式Resource中，历史导入记录的信息完整度不同；缺失owner、来源或有效期时应由真实运营补全，本轮不伪造。
- 正式库当前没有持久化Match Candidate；确定性规则会按真实资源信息展示合理候选，没有候选时显示产品化空状态。
- 历史pytest仍有既有15 failed / 3 errors债务；本轮不恢复Legacy契约。
- R4开始前已有一个旧reload实例占用端口8000及陈旧PID文件。进程强制终止未获授权；R4候选实例使用8014并已停止，测试实例8015及所有临时数据库均已清理。该项是本地运行运维债务，不是产品路径依赖。
- 数据库文件级SHA受SQLite连接/checkpoint影响；发布判断以业务行数快照与integrity_check共同确认。

R4全部24项PASS硬条件满足：新增业务表0、新增Model 0、新版本目录0、新业务Service 0、Legacy正式读写0、正式核心入口500为0、无虚假正式业务数据、无运行依赖文件被误删。
