# MVP-R7.3 Priority Source Coverage Result

## 1. 一句话结果

**PASS**：13 个 Priority Subject 已逐一完成真实覆盖诊断；Organization 详情已打通“监测状态 → 官网候选验证 → 人工确认/忽略 → R7.1 Source Discovery → Candidate真实样本 → 人工启用”，没有猜测官网、自动激活或制造 Source/Intelligence。

## 2. Why Coverage Was 1 / 13

- 13 个主体中 8 个 Organization、5 个 Person；Person 不适用企业官网 Source 监测。
- 8 个 Organization 仅 Q-BAY（上海）生物医药孵化器有已验证、已绑定的 ACTIVE Source。
- 其余 Organization 没有 approved official domain 或可靠官方链接；其中 6 个还是匿名名、泛称、分会或历史网络描述。
- 根因是 Canonical 官网事实和主体质量不足，不是缺少第二套 Discovery。
- 明细见 `MVP_R7_3_COVERAGE_GAP.md`。

## 3. Priority Subjects

- 总计：13；全部已诊断，未知状态 0。
- `COVERED_ACTIVE`：1。
- `COVERED_CANDIDATE`：0（正式库未擅自生成/确认候选）。
- `MANUAL_DOMAIN_REQUIRED`：1。
- `NO_PUBLIC_SOURCE`：0。
- `NOT_MONITORABLE`：11。
- 矩阵见 `MVP_R7_3_PRIORITY_MONITORING_MATRIX.csv`。

## 4. Official Domain Resolution

- 复用现有 `p3_entity_external_identifiers` 和 `official_domain` 类型；新增表 0、Model 0。
- 候选保持 `pending`；管理员确认后为 `approved`，忽略后为 `rejected`，刷新/重启后仍持久化。
- 验证依据：页面标题、`og:site_name`/应用品牌、Schema.org Organization 或首页明显品牌文字。
- 媒体、百科、社交、招聘、企业数据库等第三方域名直接拒绝。
- 正式 Domain Resolution Success Rate：1 / 8 Organization = **12.50%**（来自已确认 Source domain）；没有把未知域名写成正式事实。

## 5. Source Discovery

- 官网确认后直接调用 R7.1 `discover_source_candidates`，未写第二套 Discovery。
- 新 Candidate 使用 Canonical Organization external ID 绑定，同时兼容读取历史内部 ID 绑定。
- 排序：Press/Newsroom → IR/Announcement → Product/R&D Update → Blog/Insight → 其他。
- Homepage 只作为 Discovery 起点，不自动成为高质量 Candidate。
- 隔离真实 HTTP 验收：1 个验证域名触发 Discovery，成功 1 / 1；产生 2 个 disabled Candidate。

## 6. Source Candidate Quality

- 2 / 2 Candidate 可真实 Fetch/Extract，并显示 Organization、URL、发现方式、测试状态、采集方式和最近内容。
- RSS Candidate 显示样本 `Q-BAY产业服务公开更新样本` 和发布时间 `Fri, 28 Aug 2026 08:00:00 GMT`。
- 管理员确认前 Candidate ACTIVE=0；浏览器人工启用后刷新仍为 ACTIVE。
- 重复执行同一 Discovery：新增 0、识别重复 3、无效 4；重复 Source 实际新增 0，去重有效。

## 7. Official Source Coverage

- 正式 Priority Subject Coverage：1 / 13 = **7.69%**，与 R7.2 相同。
- Official Organization Source Coverage：1 / 8 = **12.50%**。
- 没有为了达到建议的 8 / 13 制造官网或 Source；其余 12 个主体都有明确 `MANUAL_DOMAIN_REQUIRED` 或 `NOT_MONITORABLE` 原因，因此不再存在“不知道为什么没覆盖”。

## 8. Priority Monitoring Matrix

- Organization 详情显示已覆盖来源数、最近更新、已确认官网、Candidate、真实样本和最新关联 Intelligence。
- Admin 可直接从 Organization 触发发现、确认或忽略，不需要回到 Source 管理页手输公司名称。
- viewer 看不到写按钮，且同一路径后端真实返回 403。

## 9. Priority Subject Hit Rate

- 对正式 Q-BAY Priority Source 执行 7 个受控周期：5 次 duplicate/unchanged，2 次页面 hash changed，失败 0。
- 新正式 Intelligence：0；因此本轮新增样本的 Priority Subject Hit Rate 分母为 0，记 **N/A**，不得伪造百分比。
- 累计正式指标沿用 R7.2：Priority Subject Hit Rate 9.09%。
- 2 次 hash changed 没有形成新正式 Intelligence，说明通用页面存在动态噪声，后续运营应优先确认真正 News/RSS，而不是降低质量门槛。

## 10. Subject Candidate Precision / Coverage

- 本轮没有新增正式 Intelligence，也没有自动创建 Subject Link。
- Precision 保持 R7.2 的 **100%**；Coverage 保持 **66.67%**，没有因为官网绑定降低阈值。

## 11. Database Changes

- 正式库前 SHA256：`FED66707481C994A2BF012AA95DC1F9D3B625F5583A36132D56F16CF355410A2`。
- 正式库后 SHA256：`746D8432EC3A3336F21C236EF89A9BE46F814B20089AF2ACF8B3A25850BA8CCE`。
- 变化仅来自 7 条真实 Monitoring Run 和 7 条可追溯 Collection Item；其中 5 条 ignored/unchanged、2 条 changed，正式 Intelligence +0。
- Monitoring Runs：133 → 140；Collection Items：514 → 521；Intelligence：31 → 31；Source：15 → 15。
- Organization 24、People 44、Resource 30、Match 0、Opportunity 11、FollowUp 4、Relationship 25、Evidence 25，前后完全一致。
- 正式 `official_domain` 候选/确认新增 0；测试账号和测试 Source 进入正式库 0。
- 最终 `integrity_check=ok`。
- 保护备份：`data/backups/MVP_R7_3_PRE_COLLECTION_20260828.db`，SHA256 `C4968A1556A7ABB0B10B894397ED3A45C3D27F693BF9A3C83D500D1710E895A9`（忽略交付，不提交）。
- pytest 前后正式 SHA、运行数、Collection、核心计数完全一致；pytest 正式 Scheduler运行 0、正式采集新增 0。

## 12. Tests

- R7.3 定向：3 / 3 PASS。
- R2–R7.3 联合回归：67 / 67 PASS。
- 全量 pytest：**15 failed / 3 errors / 1 skipped**，与 R7.2 历史债务数量和失败文件集合一致；新增失败/错误 0。
- 历史债务仍为 migration/idempotency、v06i runtime baseline、v06j migration chain、P4/v06k 旧契约，本轮未清理。

## 13. Chromium

- 首选浏览器插件通道被 Windows ACL helper 阻断；按规则切换项目现有 Playwright，不修改业务代码。
- 真实 Chromium：**151.0.7922.34**；viewport：1366×768、1600×900。
- 实际验收：Organization详情、Priority Monitoring、官网候选、确认/忽略能力、自动 Source Discovery、Source Candidate、Candidate样本、Source启用、Source管理、Intelligence、Q-BAY企业场景、viewer只读。
- Candidate确认/启用在正式库副本完成；刷新后官网与 ACTIVE 状态持久化；重复发现不新增重复 Source。
- Console Error 0；Page Error 0；Network Failure 0；非预期 404/500 0；横向溢出 0；viewer写请求 403。
- 证据：`docs/audit/evidence/mvp_r7_3/browser_acceptance.json` 和 9 张截图。

## 14. AI Readiness

**NOT_READY**。本轮解决的是确定性来源覆盖和主体数据质量；没有新增足够语义失败样本，不进入 AI Assisted Pilot，不安装 OSS。

## 15. Remaining Gaps

1. Q-BAY赫利克斯菁英俱乐部仍需管理员提供并确认官网候选。
2. 6 个 Organization 和 5 个 Person/群体需要先做主体治理或明确任职 Organization，不能直接做官网监测。
3. 正式库尚无新的 Source Candidate，因为没有可验证官网事实；这是数据真实性约束，不是产品功能缺失。
4. Q-BAY 当前通用页面在 7 次周期中出现 2 次 hash drift；应由管理员优先确认稳定 News/RSS 栏目。
5. 本轮无新增正式 Intelligence，无法重新估计新增样本 Priority Hit Rate。

## 16. Scope and rollback

- 新增业务表 0；Model 0；Service体系 0；Scheduler 0；版本目录 0；大型依赖 0。
- Production Python 净新增约 315 LOC，低于 400 LOC 目标。
- 回滚代码：对提交 `MVP-R7.3 priority source coverage` 执行常规 `git revert`。
- 如必须回滚本轮 7 次正式运营记录，可在停服并经用户确认后使用上述 SQLite 备份；默认保留可追溯真实运行历史。

**最终结论：PASS。停止，不进入 R8。**