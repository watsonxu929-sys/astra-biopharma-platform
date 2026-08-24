# MVP-R3 Legacy Migration Result

## 1. 一句话结果

**PASS** — 真实有价值的 Legacy 数据已按逐记录映射迁入 Canonical，正式产品读已切换为 Canonical，Legacy 表保留为只读历史且未物理删除。

## 2. Preflight

入口分支 `release/mvp-rc1.2`，入口 HEAD `ce470ad95b86e69a1e7eb03293bbfa7f9a12348a`，入口工作区 clean。

任务说明中的 R2 `+2496/-0` 无法由 Git 复现。`git show --numstat ce470ad...` 的可复现结果为 `+967/-877`：Production Service `+480/-704`、Route/Adapter `+82/-173`、Tests `+111`、Audit docs `+294`。没有新增 Repository、Registry、Command Bus、Compatibility Layer、业务表、业务 Model 或版本目录；唯一新增 `CanonicalRelationshipService` 是 Single Write Owner，结论 `NO_R2_SCOPE_VIOLATION`。

## 3. Migration Inventory

| Decision | 数据 |
|---|---|
| MIGRATE | `relations` 25条；`resources` 8条；`v04f_club_offerings` 1条 |
| MANUAL_REVIEW | `relations.id=18` 1条，source `PER-20260630-000010` 不存在，禁止猜测主体 |
| ARCHIVE_ONLY | `actions` 7条，均为资料核验/名单/导入/试跑类任务且无 Opportunity 关联 |
| EMPTY_IGNORE | `v04f_club_needs`、`v04f_club_matches`、所有 Legacy Lead/History/Suggestion/Candidate 表、scheduler实验表 |
| 明确排除 | AI、Recommendation、Research、P2、Favorites、Follows、Subscription、测试和 migration 历史 |

逐记录证据见 `docs/audit/evidence/MVP_R3_RELATIONSHIP_MAPPING.csv` 和 `MVP_R3_RESOURCE_MAPPING.csv`。

## 4. Relationship

数学闭环：原 Canonical `0` + Legacy真实有效 `25` - 语义重复 `0` = 最终 Canonical `25`。另有 `1` 条明确 `MANUAL_REVIEW`，未伪造主体。迁入 Evidence `25`；内容来自旧行已有来源/表述，不把“legacy migration”伪装为业务证据。

迁移前按 subject/object/type/direction/business semantics 去重，不只依赖 Legacy ID。专门测试证明已有等价关系时 Canonical 行不增加，证据按 hash 幂等补充。

## 5. Resource

数学闭环：原 `v06_market_resources=20` + Legacy有效 Resource `8` + Offering `1` - 重复 `0` = 最终 `29`。Need 为 `0`；Offering 映射 `direction=supply`，Need规则固定为 `direction=demand`。所有迁入对象均保留 `legacy_source_type/id` 追溯，不把 Legacy ID显示为产品主编号。

## 6. Match

`v04f_club_matches=0`，`p4_resource_match_candidates=0`，结论 `EMPTY_IGNORE`；未制造正式测试 Match，未产生引用 Legacy Resource ID 的半残对象。

## 7. Opportunity

所有 Legacy Lead相关表均为 `0`，`v06_opportunities` 前后均为 `11`，结论 `EMPTY_IGNORE`。旧 `/collaboration/leads` 读写入口已退役并 303 到 `/opportunities`；正式协作指标读取 `v06_opportunities`。

## 8. FollowUp / Task

无 Legacy真实商务 FollowUp 可迁，`v06_follow_ups` 前后均为 `4`。`actions=7` 均无 Opportunity 关联，判定 `ARCHIVE_ONLY`，未强行迁成商务 Task；`v06_collab_tasks` 前后均为 `4`。正式 Subject、Dashboard、协作与 Q-BAY Task统计已切换 `v06_collab_tasks`。

## 9. Canonical Read Cutover

- Relationship API、Subject API、关系路径及正式人物/机构页：`p3_canonical_relationships` / Evidence。
- Resource列表/详情/API/搜索/Q-BAY：`v06_market_resources`。
- Match正式页/Q-BAY：`p4_resource_match_candidates`。
- Opportunity列表/详情/API/协作首页：`v06_opportunities`。
- FollowUp / Task：`v06_follow_ups` / `v06_collab_tasks`。
- `unified_resource_service` 不再查询或 fallback Legacy；保留 inert `include_legacy=False` 参数仅用于既有调用签名。
- 正式 `PRODUCT_READ=0`；详细分类见 `MVP_R3_LEGACY_READ_MAP_AFTER.md`。

R3运行时代码 `+123/-461`，净减少 `338 LOC`；一次性 migration script `380 LOC`，R3 tests `179 LOC`。新增业务 Model `0`、业务表 `0`、业务 Service `0`、版本目录 `0`、依赖 `0`。

## 10. Legacy状态

`relations`、`resources`、`v04f_club_needs`、`v04f_club_offerings`、`v04f_club_matches`、`v04f_lead_records`、`actions` 均为：

`LEGACY / READ ONLY / HISTORICAL / NO PRODUCT WRITE / NO FORMAL PRODUCT READ`

所有表仍存在，所有旧行数不变，未执行任何 DROP。旧 ORM页面、Research/Recommendation、旧 Lead/Action模板和历史聚合已归类 `DEAD_CODE/FROZEN`。

## 11. Idempotency

- 正式迁移第一次：`created=34`（Relationship 25 + Resource 9），Evidence 25，Manual Review 1。
- 正式迁移第二次：`created=0`、`duplicate_created=0`、`duplicates=34`、Manual Review 1、`integrity_check=ok`。
- 隔离副本也完成两次执行及失败整体 rollback 演练。

迁移工具默认 Dry Run；Apply 要求精确 `--confirm-db`；正式库还要求 `--allow-formal-db`。脚本不在 import、启动或页面访问时执行。

## 12. Data Sampling

程序抽样并人工核对 5条 Relationship：

1. `PER-20260626-000001 → ORG-20260626-000001 / executive_of / approved`；
2. `PER-20260626-000002 → ORG-20260626-000002 / cofounder_of / approved`；
3. `PER-20260626-000002 → ORG-20260626-000003 / contact_for / approved`；
4. `ORG-20260626-000001 ↔ ORG-20260626-000003 / strategic_partner_of / pending_review`；
5. `ORG-20260626-000003 → ORG-20260626-000004 / located_in_park / pending_review`。

5条 Resource：空间、技术平台、政策与落地、品牌与活动、资本与产业网络，均为 `supply/published`，机构所有者分别可解析。全部25条迁入关系端点缺失数 `0`，迁入Evidence数 `25`；ASCII Unicode复核确认中文为真实UTF-8，终端首轮显示的替换字符只是 PowerShell 输出编码，不是数据库乱码。真实 Match与迁移 Opportunity均为0，因此无伪造抽样。

## 13. DB Evidence

| 证据 | Before | After |
|---|---|---|
| 正式DB SHA256 | `6BDDFF2C592EB671D219F0E88CF2D8778FD9A18D6CD891AB861C62D70685B402` | `7A36C67B16925C69C708E7DD7B3040A6B8C3C48C02E956D76CDA291871A980E7` |
| integrity_check | `ok` | `ok` |
| 非内部表数量 | `187` | `187` |
| Canonical Relationship | `0` | `25` |
| Relationship Evidence | `0` | `25` |
| Canonical Resource | `20` | `29` |

迁移前备份：`E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\migration_backup\pre_mvp_r3_20260824_093559.db`，大小 `6,156,288 bytes`，SHA256 `E2C8ABB64D55A143829293B3005E9D6D846B9F84FAD674392D717C5F9071C11C`，integrity `ok`。

对全部187张表逐表比较，仅 `p3_canonical_relationships 0→25`、`p3_relationship_evidence 0→25`、`v06_market_resources 20→29` 行数变化；所有Legacy表和其他正式业务表行数不变。正式服务回归及pytest前后DB SHA均保持 After 值。

## 14. Test Result

- R3 migration/read tests + R2 Single Write Contract：`9 passed`。
- R3/R2/R1/RC1.2/Golden Loop最终关键集合：`21 passed`。
- 较广定向集合：`64 passed / 1 skipped / 0 failed`（Lead退役后的关键集合再次通过）。
- 全量基线：R2为 `107 passed / 1 skipped / 15 failed / 3 errors`；当前最终代码为 `112 passed / 1 skipped / 15 failed / 3 errors`。历史15失败/3错误的测试名称集合未变化，R3新增失败 `0`。
- 历史失败仍为 migration idempotency、v06i/v06j/v06k/P4旧契约；未恢复 Legacy行为“救绿”。
- Golden Loop完整回归通过，R2 Single Write Contract继续通过，正式库保护测试通过。

## 15. Product Regression

正式 Uvicorn + 签名只读 session 验证：`/platform`、`/intelligence`、`/network`、`/resources`、`/opportunities`、`/collaboration`、`/club`、`/platform/golden-loop` 均 HTTP 200；`/collaboration/leads` 为 303 → `/opportunities`。Relationship API与Relationship Path API均200，人物页可见迁入关系，Q-BAY会员页可见迁入资源，Golden Loop页可见迁入数据。

协作首页显示“新机会/待确认机会”，不显示“线索审核”。正式Server回归前后DB SHA一致，未产生业务写入。R1真实浏览器债务仍维持 `PARTIAL / manual_browser_acceptance_pending / TOOLING_BLOCKED`；这是任务明确保留的既知债务，不在R3继续处理。

## 16. Remaining Legacy Debt

- `relations.id=18` 需人工确认已不存在的来源人物；在确认前只保留Legacy历史。
- `actions` 7条仅归档，未转换商务Task。
- Legacy表和Frozen代码尚未物理删除；至少经过一个真实运营周期后才能以独立Housekeeping任务处理。
- Q-BAY活动当前 Canonical Task schema没有 event-specific关联列，因此活动详情Task统计明确为0，不回退 `actions`，不猜测关联。
- R1真实浏览器验收工具债务和全量pytest历史债务均未扩大。

## Rollback

### Code

在R3单一提交完成后执行：

```powershell
git revert <R3_COMMIT_SHA>
```

### Database

先停止Web/Worker并另存当前数据库，然后验证备份：

```powershell
Get-FileHash -Algorithm SHA256 -LiteralPath 'E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\migration_backup\pre_mvp_r3_20260824_093559.db'
```

确认输出为 `E2C8ABB64D55A143829293B3005E9D6D846B9F84FAD674392D717C5F9071C11C` 后恢复：

```powershell
Copy-Item -LiteralPath 'E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\migration_backup\pre_mvp_r3_20260824_093559.db' -Destination 'E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db' -Force
```

恢复后验证：

```powershell
.\.venv\Scripts\python.exe -c "import sqlite3; c=sqlite3.connect(r'E:\Codex项目设计\招商一体化平台系统\biopharma-intelligence-mvp-rc1\data\app.db'); print(c.execute('PRAGMA integrity_check').fetchone()[0]); print(c.execute('SELECT COUNT(*) FROM p3_canonical_relationships').fetchone()[0]); c.close()"
```

预期输出 `ok` 和 `0`。恢复操作会覆盖当前正式库，必须由用户明确确认后执行；本任务未执行回滚。

## PASS硬条件

22项硬条件全部满足：数据决策完整、MIGRATE已完成、幂等、无重复、六个正式领域和Q-BAY读Canonical、Legacy正式写入0、Legacy表未删除、Golden Loop/R2 contract/integrity/数学闭环/语义抽样通过，且新增业务表/Model/Service/版本目录均为0。
