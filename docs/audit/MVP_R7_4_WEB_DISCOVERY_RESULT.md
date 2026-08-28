# MVP-R7.4 Web Assisted Official Source Discovery Result

## 1. 一句话结论

**PASS（验证任务）— `REJECT_EXTERNAL_SEARCH`。** Brave Search API 认证与请求链路可用，但针对当前 12 个未覆盖 Priority Subject 的受控 PoC 在 20 次总请求内得到 **0 个 VERIFIED_CANDIDATE、0 个有效官方 Source、0 个新增覆盖**，未达到 ≥90% 精度、≥4 个可信官网和 ≥2 个有效官方 Source 的准入门。按任务规则删除全部 PoC 实现和原始响应，不进入生产产品。

## 2. 正式基线

- Branch：`release/mvp-rc1.2`
- Baseline HEAD：`0b31b8fa0e999774be8120825b80f1102566a913`
- Baseline Commit：`MVP-R7.3 priority source coverage`
- Working Tree（任务开始）：除本任务未提交 PARTIAL 报告外无修改；该报告未单独提交，现已由本报告替换。
- DB：`data/app.db`
- DB SHA256（前）：`746D8432EC3A3336F21C236EF89A9BE46F814B20089AF2ACF8B3A25850BA8CCE`
- `integrity_check`（前）：`ok`

## 3. 配置与认证

- `BRAVE_SEARCH_CONFIGURED=true`。
- 真实认证连通测试：HTTP成功，JSON响应可解析。
- 密钥只从项目根目录未提交 `.env` 读取。
- 密钥值、前后字符和认证请求头内容均未输出或落盘。
- 认证测试无重试；失败供应商切换 0。

## 4. PoC设计

- 唯一供应商：Brave Search API。
- 先对 12 个未覆盖主体各执行 1 次完整主体名查询：12 requests。
- 首轮因完整名称、历史描述和错误主体质量仅得到 11 个 NO_RESULT、1 个 REJECTED。
- 为区分供应商覆盖不足与查询过窄，仅对 7 个 Organization 各追加 1 次短别名查询：7 requests。
- Person、系统角色和群体追加查询：0。
- 连通测试 1 + 首轮 12 + 复查 7 = **20 requests**，低于 65 上限。
- 所有查询无自动重试，无 401/403、429、timeout 或 Search HTTP错误。
- 候选首页验证检查域名类型、公开可解析性、跳转、标题/品牌、Schema.org Organization、About/Contact、版权与 canonical；仅名称命中不足以通过。
- 未确认结果不写 Organization、official_domain、Source、Intelligence 或任何正式业务对象。

## 5. PoC结果

### 第一轮

- 12 / 12 未覆盖 Priority Subject 已完成真实查询。
- VERIFIED_CANDIDATE：0。
- AMBIGUOUS：0。
- REJECTED：1。
- NO_RESULT：11。

### Organization短别名复查

- 查询：7。
- VERIFIED_CANDIDATE：0。
- AMBIGUOUS：5。
- REJECTED：2。
- NO_RESULT：0。

### 主要证据

| Subject | 搜索候选证据 | 最终判断 |
|---|---|---|
| Q-BAY赫利克斯菁英俱乐部 | 主要命中知乎、杭州日报、搜狐、QQ等第三方或不相关站点 | NO_RELIABLE_DOMAIN_FOUND |
| 杭州钱塘区和达高科相关平台 | `hedagroup.com.cn` 无法公开解析；`tsientang.org.cn` 首页抓取失败；其他为不匹配站点 | NO_RELIABLE_DOMAIN_FOUND |
| 上市公司俱乐部 | 命中活动平台、行业协会、百科及多个无法验证站点；名称不唯一 | NO_RELIABLE_DOMAIN_FOUND |
| 上市公司俱乐部创投分会 | 命中活动平台、协会和创投机构，但不能证明属于该分会 | NO_RELIABLE_DOMAIN_FOUND |
| WLA Labs相关历史网络 | `wla.cn` 等候选首页无法验证，其他站点与当前“历史网络”Canonical主体不匹配 | NO_RELIABLE_DOMAIN_FOUND |
| 履历句子误抽Organization | 搜索能找到句中多个真实机构，但不能绑定到该错误主体 | NO_RELIABLE_DOMAIN_FOUND |
| 某细胞治疗生物科技公司 | 搜索能找到多家细胞治疗企业，但匿名主体禁止反推 | NO_RELIABLE_DOMAIN_FOUND |
| 4个Person/系统角色及链接官群体 | 不适用企业官网绑定；没有强行转成Organization | NO_RELIABLE_DOMAIN_FOUND |

候选域名、标题和snippet只在临时PoC内用于判断；原始JSON和临时脚本均已删除，不进入Git或SQLite。

## 6. 13个Priority Subject最终状态

| Priority Subject | R7.4状态 |
|---|---|
| Q-BAY（上海）生物医药孵化器 | COVERED_ACTIVE |
| Q-BAY赫利克斯菁英俱乐部 | NO_RELIABLE_DOMAIN_FOUND |
| 杭州钱塘区和达高科相关平台 | NO_RELIABLE_DOMAIN_FOUND |
| 上市公司俱乐部 | NO_RELIABLE_DOMAIN_FOUND |
| 上市公司俱乐部创投分会 | NO_RELIABLE_DOMAIN_FOUND |
| 世界顶尖科学家国际联合科学实验室（WLA Labs）相关历史网络 | NO_RELIABLE_DOMAIN_FOUND |
| 并就相关话题受邀深圳中欧创新实验室、华创证券、丹纳赫行业交流、长三角创新中心 | NO_RELIABLE_DOMAIN_FOUND |
| 某细胞治疗生物科技公司 | NO_RELIABLE_DOMAIN_FOUND |
| 陈绵辉 | NO_RELIABLE_DOMAIN_FOUND |
| 陶伟龙 | NO_RELIABLE_DOMAIN_FOUND |
| Admin | NO_RELIABLE_DOMAIN_FOUND |
| 许毛毛 | NO_RELIABLE_DOMAIN_FOUND |
| 链接官群体 | NO_RELIABLE_DOMAIN_FOUND |

UNKNOWN：0。

## 7. 准入指标

| 指标 | 结果 | 门槛 |
|---|---:|---:|
| 未覆盖主体真实查询完成度 | 12 / 12 | 12 / 12 |
| 新 VERIFIED_CANDIDATE | 0 | 建议至少4 |
| Domain Candidate Precision | N/A（没有可接受预测） | ≥90% |
| Usable Domain Discovery Yield | 0 / 12 = 0% | 必须突破现状 |
| Source Discovery Yield | 0 | 建议至少2 |
| Final Priority Source Coverage | 1 / 13 = 7.69% | 必须高于1/13 |
| 自动正式写入 | 0 | 必须0 |
| 新增业务表 / Model / Server / Worker | 0 | 必须0 |
| 保留生产适配代码 | 0 LOC | 失败时必须删除 |

Domain Candidate Precision不能用0条已接受预测伪造为100%；没有可验证候选即不满足精度准入。

## 8. Source Discovery与业务价值

- VERIFIED_CANDIDATE为0，因此没有调用既有 R7.1/R7.3 Source Discovery。
- 新 RSS / Sitemap / Newsroom / Press / IR Candidate：0。
- 有效近期样本：0。
- 新 Source Candidate / ACTIVE Source：0。
- Priority Subject覆盖仍为1/13，没有业务覆盖突破。
- Brave能返回若干宽泛候选，但当前主要瓶颈是Canonical主体质量和官网可验证性，不是“缺少一个搜索API”。

## 9. 成本

- 实际请求：20。
- 当前官方 Search 单价基线：USD 5 / 1,000 requests。
- 估算成本：**USD 0.100**。
- 有效官网单位成本：N/A（0个）。
- 有效Source单位成本：N/A（0个）。
- 因产出为0，不允许用低绝对成本掩盖业务ROI为0。

官方参考：<https://api-dashboard.search.brave.com/api-reference/web/search/get>、<https://api-dashboard.search.brave.com/documentation/pricing>、<https://brave.com/search/api/>。

## 10. 数据库与安全

| 对象 | 前 | 后 |
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
| official_domain identifiers | 0 | 0 |

- DB SHA256（后）：`746D8432EC3A3336F21C236EF89A9BE46F814B20089AF2ACF8B3A25850BA8CCE`。
- `integrity_check`（后）：`ok`。
- 正式采集运行新增：0；正式 Scheduler运行：0。
- 正式 Source / Intelligence / Candidate / Organization写入：0。
- 测试账号、临时数据库、PoC原始响应、临时脚本残留：0。

## 11. 产品与Chromium

- 准入失败后已删除全部PoC实现；没有新增 Organization Web Search 按钮、页面、路由或第二控制台。
- 现有 R7.3 `[发现官方来源]`、人工官网候选、人工确认与 Source Discovery 保持原状。
- 被拒绝的功能没有可验收UI，因此 R7.4 Chromium路径不适用；未用既有R7.3截图冒充R7.4验收。
- R7.3最近真实Chromium基线仍为 Console/Page/Network/404/500/横向溢出均0，viewer写入403；本轮没有产品代码或页面变化。

## 12. Tests

- R7.3官网候选与 Source Discovery 定向：3 / 3 PASS。
- 全量 pytest：**15 failed / 3 errors / 1 skipped**。
- 失败/ERROR数量与R7.3历史基线一致；失败文件集合仍为既有migration/idempotency、v06i runtime baseline、v06j migration chain、P4/v06k旧契约。
- 新增失败/ERROR：0。
- pytest期间 Brave请求：0；正式采集新增：0；正式数据库SHA与核心计数不变。

## 13. 准入决定与后续边界

### 决定：REJECT_EXTERNAL_SEARCH

拒绝原因：

1. 0个 VERIFIED_CANDIDATE，无法满足≥90%精度门。
2. 没有达到建议的≥4个可信官网、≥2个有效官方Source。
3. Final Priority Source Coverage仍为1/13，没有覆盖突破。
4. 继续增加查询或降低验证标准只会放大错误主体绑定风险。
5. 当前瓶颈应先通过主体治理解决：拆分误抽履历句子、确认匿名主体、明确俱乐部运营法人、把Person关联到已确认任职Organization。

- Brave Search API不进入生产依赖或产品配置。
- `.env.example`不新增Key；requirements不新增SDK。
- 不安装第二搜索供应商，不进入R8，不接入LLM。
- 若未来主体质量显著改善，应以新的独立准入任务重新评估，而不是恢复本轮临时代码。

## 14. 变更与回滚

- 最终变更仅本审计报告；生产代码净新增0 LOC。
- 未提交密钥、`.env`、原始响应、临时脚本、数据库、日志或浏览器缓存。
- 回滚本轮验证记录：常规 `git revert` 最终审计提交即可；无数据库回滚步骤。

**最终结果：REJECT_EXTERNAL_SEARCH。R7.4验证任务PASS，停止，不进入R8。**
