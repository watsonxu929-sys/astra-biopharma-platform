# P2.1 试点报告

执行日期：2026-07-10。执行数据库：`data/app.db` 的临时副本，正式数据库未写入。批次：`P2P-20260710-WUXI`。

## 样本

- 已执行 1 条公开网页快照：药明康德官网首页，URL `https://prod-alb-officialsite.wuxiapptec.com/`，现有 Snapshot #1。
- 样本数量 1，小于 20；未重抓或批量重跑历史数据。
- 本机 Playwright 不可用，动态页 PoC 状态明确为 unavailable；未绕过 36Kr 的安全检测。
- 本机 Docling 不可用，文档 PoC 状态明确为 unavailable；未将未解析附件写入数据库。
- RSS 与额外网页来源本轮未联网扩量，留在后续经批准的独立采集批次，不影响接口和证据链验收。

## 结果

| 阶段 | 数量/结果 |
|---|---|
| EvidenceSnapshot | 复用 1 |
| 解析 | 1，`plain_text_v1` |
| RawIntelligence | 新建 1 |
| AI/规则运行 | 1，RuleProvider `p2.1-rule-v1` |
| FactCandidate | 1，事件类型 `recognition` |
| 人工审核 | 批准 1、拒绝 0、待审核 0 |
| IntelligenceProduct | 发布 1（副本内 ID 21） |
| 证据回溯 | 产品 → 候选 #1 → Snapshot #1 → 原 URL/抓取时间/SHA256 成功 |

删除副本内试验产品的自动化测试确认不会删除 EvidenceSnapshot。试点批次由 `p2_pilot_batches` 标识，可按 batch ID 定位清理；正式库中不存在该批次。

## 限制

这是一条主链验收样本，不代表大规模采集质量结论。动态网页和文档解析仍是可选适配器状态；真实 RSS、多网页、动态页和附件的外网 PoC 应在独立维护窗口、明确来源条款并安装可选依赖后执行。

## 续作验收

2026-07-10 在新的 `data/app.db` 临时副本复跑 003 dry-run、apply 和第二次 apply，缺失字段从计划集收敛到 0，第二次执行表/字段/记录计数不变。受控批次 `P2P-20260710-CONTINUE` 结果为：

- 1 个 RawIntelligence、1 个已批准 FactCandidate、1 个 IntelligenceProduct；
- Raw、Candidate、Product 均保存相同 `is_pilot=1` 与 `pilot_batch_id`；
- 批次清单保存 snapshot、raw、candidate、product ID；
- 候选证据、产品候选、产品证据关联各 1 条；
- P2 专项验证完整性、外键、不可变触发器、导航唯一性和只读哈希检查全部通过；
- 正式数据库未执行 003 apply；主链关键表计数保持来源 3、任务 6、快照 2、Raw 1、候选 0、产品 20，`integrity_check=ok`。
- 一次最终兼容读取因旧连接助手执行 `journal_mode=WAL` 改写了正式库文件头；未恢复或覆盖数据库。P2 产品证据追踪已改为 `mode=ro`，后续以新基线验证字节哈希稳定。
