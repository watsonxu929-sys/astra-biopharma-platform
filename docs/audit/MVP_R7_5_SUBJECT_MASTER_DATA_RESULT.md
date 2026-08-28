# MVP-R7.5 Subject Master Data Result

## 1. Conclusion

**PASS**

13 个 Priority Subject 已逐项完成身份、Priority 依据、官网、监测种子、Source 覆盖和管理员动作审计；没有任何主体继续停留在 `UNKNOWN`。系统复用既有 Canonical Organization、别名、外部标识、Source Discovery 和权限体系，补齐管理员官网/别名治理、Website Candidate、CSV Preview/Confirm 与治理筛选能力。没有猜测官网、自动合并主体、制造 Source 或改写正式主数据。

本轮真实结果不是“主体资料已经补齐”，而是“主体主数据问题已被准确识别，并且管理员可以在正式 UI 中安全补齐”。当前应进入管理员真实资料补全，不进入 R8。

## 2. Why Search Failed

R7.4 的 Brave Search 配置、认证和真实连通均成功；20 次真实请求得到 `VERIFIED_CANDIDATE=0`。主要瓶颈不是认证或 Search API 不可用，而是 Priority Subject 主数据不足：多个名称是俱乐部泛称、历史网络描述、履历句子、系统角色或匿名企业，缺少唯一法定名称、常用别名和可核验域名。搜索结果无法在不猜测的前提下与 Canonical 主体形成确定性绑定。

因此 R7.5 不接入第二个 Search Provider。正式官网改为管理员确认的主数据；现有业务资料只能产生 `WEBSITE_CANDIDATE`，不能自动确认。

## 3. 13 Subject Identity Audit

完整逐项结果见 [MVP_R7_5_SUBJECT_IDENTITY_AUDIT.csv](MVP_R7_5_SUBJECT_IDENTITY_AUDIT.csv) 和 [MVP_R7_5_PRIORITY_SUBJECT_MASTER_MATRIX.csv](MVP_R7_5_PRIORITY_SUBJECT_MASTER_MATRIX.csv)。

| Identity Status | Count | Rate |
|---|---:|---:|
| `IDENTITY_CONFIRMED` | 0 | 0.00% |
| `IDENTITY_PARTIAL` | 5 | 38.46% |
| `IDENTITY_AMBIGUOUS` | 4 | 30.77% |
| `WRONG_ENTITY` | 3 | 23.08% |
| `INSUFFICIENT_DATA` | 1 | 7.69% |
| `UNKNOWN` | 0 | 0.00% |

每一行都记录了 Canonical ID、当前名称、主体类型、Q-BAY/Resource/Relationship/Intelligence 上下文、问题原因和建议动作。正式库没有因审计发生主数据写入。

## 4. Duplicate / Ambiguous Subjects

使用现有 RapidFuzz 和确定性规则只产生只读候选，不自动 Merge：

- `上市公司俱乐部` ↔ `上市公司俱乐部专家组`：82%，保留为歧义候选。
- `上市公司俱乐部` ↔ `上市公司俱乐部创投分会`：78%，低于自动判断阈值。
- `杭州钱塘区和达高科相关平台`、`WLA Labs 相关历史网络`：名称描述业务网络，不能唯一确认法人。
- 新增 Alias 时会检查与其他 Canonical 主体的已批准别名冲突；冲突时拒绝写入。

Precision 优先，未降低匹配阈值，未执行自动合并。

## 5. Priority Validity

13 个主体的 Priority 来源均追溯到 Q-BAY 会员/生态、Canonical Resource 或已审核 Canonical Relationship：

- `NEEDS_ADMIN_CONFIRMATION`：9 个。
- `REMOVE_FROM_PRIORITY` 建议：4 个，但本轮没有删除。
  - 履历句子被错误抽取为 Organization。
  - 匿名的“某细胞治疗生物科技公司”。
  - `Admin` 系统角色。
  - `链接官群体` 群体角色。

Priority 调整仍由管理员决定。

## 6. Website Coverage

| Metric | Result |
|---|---:|
| Confirmed Official Website | 0 / 13（0.00%） |
| Existing-data Website Candidate | 1 / 13 |
| Official Source Coverage | 1 / 13（7.69%） |

唯一候选来自既有 Intelligence 链接证据，只作为候选展示，没有自动确认为官网。没有使用搜索结果猜测官网，也没有向正式库写入测试域名。

## 7. Monitoring Seed Coverage

Monitoring Seed 定义为“已确认官网或已确认官方 Source”，不新增业务表。

- Monitoring Seed：1 / 13（7.69%）。
- 未达到建议值 10/13，原因是 13 个主体中有 4 个本身不是有效、可唯一识别的主体，另外 8 个仍需要管理员提供真实身份或官网材料。
- 建议值不是造数据式硬 PASS 条件；本轮不伪造官网或 Source。

## 8. Source Discovery After Master Data

复用 R7.1/R7.3 的既有链路：

`Admin Confirm Website → Existing Source Discovery → Source Candidate → Admin Enable/Ignore`

隔离测试库和真实 Chromium 已验证：管理员确认官网后可以进入既有 Source Discovery；发现结果仍保持 Candidate，不会自动 ACTIVE。由于正式库没有新增已确认官网，本轮正式 Source Discovery 新运行为 0，正式 Source Candidate 新增为 0，正式 Source 总数仍为 15。

## 9. Subject Candidate Precision / Coverage

本轮没有新增正式人工评审样本，也没有降低匹配阈值，因此沿用可比较的 R7.2/R7.4运营口径：

| KPI | Result |
|---|---:|
| Subject Candidate Precision | 100.00% |
| Subject Candidate Coverage | 66.67% |
| Priority Subject Hit Rate | 9.09% |

Alias、简称、英文名和品牌名现在统一命中同一 Canonical Organization；这是后续管理员补全真实别名后自然改善 Coverage 的入口。本轮不把测试别名计入正式 KPI，也不虚报 Coverage 改善。

## 10. Q-BAY Canonical Alignment

Q-BAY 会员/生态上下文、Organization、Resource、Relationship 和 Intelligence 继续复用同一 Canonical ID。Chromium 验证从 Priority Subject 治理页、Organization 详情和 Q-BAY 会员页看到的是同一主体；本轮没有创建 Q-BAY 专用 Organization、Subject 或第二套身份体系。

## 11. Admin UX

在现有 Organization 管理和详情路径内完成，无新增一级导航：

- Priority Subject 筛选与“待完善主体资料”计数。
- 查看 Identity、Website、Monitoring Seed、正式 Source 和候选 Source 状态。
- Admin/Operator 通过既有 Organization 写路径维护名称、简称和别名。
- 管理员录入并确认 Official Website；Viewer 后端写请求返回 403。
- 从 Existing Data 展示 Website Candidate、证据和对应记录；候选不自动确认。
- CSV 支持 `organization_id,website` 或 `organization_name,website`，必须 Preview → Entity Match → Duplicate Check → Admin Confirm → Save；歧义、冲突和非法网址跳过。
- Confirmed Website 直接复用现有 Source Discovery。
- 中文名、英文名、简称、品牌/已批准别名统一搜索 Canonical Organization。

## 12. Database Safety

正式数据库：`data/app.db`。

| Core object | Before | After |
|---|---:|---:|
| Intelligence | 31 | 31 |
| People | 44 | 44 |
| Organizations | 24 | 24 |
| Projects | 5 | 5 |
| Subject Links | 1 | 1 |
| Resources | 30 | 30 |
| Match Candidates | 0 | 0 |
| Opportunities | 11 | 11 |
| FollowUps | 4 | 4 |
| Relationships | 25 | 25 |
| Relationship Evidence | 25 | 25 |
| Monitoring Sources | 15 | 15 |
| approved `official_domain` | 0 | 0 |
| R7.5/test users | 0 | 0 |

- R7.5任务入口 SHA256：`746D8432EC3A3336F21C236EF89A9BE46F814B20089AF2ACF8B3A25850BA8CCE`。
- 一次历史全量测试隔离缺陷曾污染 12 张 processing/history 表；用户授权后已逐表从污染前快照恢复。
- 恢复前保护备份：`data/backups/MVP_R7_5_PRE_TEST_POLLUTION_REPAIR_20260828_233911.db`，SHA256 `37494245BEC5BB7D78CF30B7D4BC6EA675578AF216B892DBF951C02BE6E5ACE6`（本地备份，不提交）。
- 12 张恢复表的行数、列结构和逻辑 SHA256 与污染前快照逐表一致。
- SQLite 页布局使恢复后的文件级 SHA256 为 `6F3567416C76A33F566FC725B0DB17D4FA81A7722E49C3B3CA6C8F853CAD134D`，不会仅凭物理哈希伪称回到旧值；业务逻辑内容和核心计数已恢复。
- `PRAGMA integrity_check=ok`。
- `PRAGMA foreign_key_check` 的 30 条结果与污染前快照集合完全一致，是既有历史状态，本次恢复新增 0。
- 新增会话级 pytest 隔离后，全量回归和联合定向回归前后正式库 SHA256 均保持 `6F356...134D`，核心计数完全一致，正式 Scheduler/采集运行新增 0。
- 浏览器验收数据库、测试账号、测试官网、测试 Alias、临时 pytest 数据库和浏览器数据库均已清理。

## 13. Tests

- R7.5新增定向测试：6/6通过，覆盖 Official Website 写入现有 identifier 表、Alias 唯一性与搜索、Identity/Duplicate 规则、CSV Preview安全、Existing Evidence Candidate、Viewer后端403。
- R2–R7.5联合定向回归：73/73通过。
- 全量 pytest：历史基线保持 `15 failed / 3 errors / 1 skipped`；失败和错误仍来自已分类的 migration/idempotency、v06i、v06j、v06k/P4历史债务。
- R7.5新增失败：0；历史失败/错误集合新增：0。
- 代表性 processing + R7.5隔离验证：24/24通过，正式数据库哈希不变。
- Python语法编译通过，`git diff --check`通过。

## 14. Chromium

首选应用内浏览器控制因 Windows ACL/orchestrator 通道异常不可用；没有据此判产品失败，也没有修改业务代码绕过工具问题。随后使用项目可控的真实 Chromium/Playwright 完成验收。

- Chromium：151.0.7922.34。
- Priority Subject列表、Organization详情/编辑、官网候选/管理员确认、Source Discovery、Source Candidate、Alias搜索、CSV Preview/Confirm、Q-BAY对齐、Viewer权限均通过。
- Console Error：0。
- Page Error：0。
- Network Failure：0。
- HTTP 404/500：0。
- 横向溢出：0。
- Viewer关键写请求：403。

机器可读结果见 [browser_acceptance.json](evidence/mvp_r7_5/browser_acceptance.json)，截图证据位于 [evidence/mvp_r7_5](evidence/mvp_r7_5/)。所有写操作均发生在隔离数据库。

## 15. AI Readiness

**NOT_READY**。

当前主要瓶颈仍是主体主数据缺失和无效 Priority Subject，而不是已证明的语义实体识别能力不足。应先由管理员补齐真实法定名称、别名和官网，并重新观察 Subject Candidate Coverage；不得因为阶段推进而进入 R8。

## 16. Remaining Gaps

1. 9 个主体需要管理员确认真实身份、法定名称、别名或官网。
2. 4 个主体建议从 Priority Universe 移除，但必须由管理员决定。
3. Official Website Coverage 仍为 0/13，Monitoring Seed Coverage 仍为 1/13。
4. 主数据补齐前，不应再增加 Search Provider，也不应把模糊搜索结果自动绑定主体。
5. 正式库污染已逻辑恢复，但文件级 SHA 因 SQLite 页布局不同于任务入口；保护备份保留供回滚。
6. 30 条既有外键检查结果没有扩大，属于后续独立历史数据治理范围，不在 R7.5 扩展处理。

## Constraints and Change Size

- 新增业务表：0。
- 新增业务 Model：0（仅映射既有 `organizations.short_name` 列）。
- 新增第二套 Service：0。
- 新增 Scheduler：0。
- 新增 Search Provider：0。
- 新增大型依赖：0。
- 新增版本目录：0。
- Production Python：`+343 / -48`，净新增 `295 LOC`，满足目标 `≤300 LOC`。
- 正式业务数据新增/修改：0。

## Rollback

代码回滚使用本次单一提交的 `git revert <R7.5 commit>`。数据库无需执行R7.5业务数据回滚；如需回退本次12表恢复，应先停止Web，再使用上述恢复前保护备份并重新执行 `integrity_check`、核心计数和逐表比对，禁止直接覆盖运行中的数据库。
