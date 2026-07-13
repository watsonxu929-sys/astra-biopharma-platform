# P2.3 受控试点结果

执行日期：2026-07-13  
批次：`P23-20260713-CODEX`  
数据库副本：`C:\tmp\p2_3_research_pilot_20260713.db`  
来源副本：P2.2 受控试点副本；未访问网络，未写正式库。

## 试点专题

“2025 FDA 创新药审批多来源研究试点”。复用两份真实 FDA 文档：

1. `2025 New Drug Therapy Approvals`（Snapshot 10 / RawIntelligence 9）
2. `Compilation of CDER New Molecular Entity Drug and New Biologic Approvals`（Snapshot 11 / RawIntelligence 10）

试点企业为 Vertex Pharmaceuticals、Daiichi Sankyo、GlaxoSmithKline。三条主体只存在于试点副本，来源标记为 P2.3 pilot，待后续正式主体匹配。

## 结果

| 指标 | 结果 |
|---|---:|
| 专题 | 1 |
| 企业 | 3 |
| 事件 | 3 |
| 已通过事件 | 2 |
| 待审核事件 | 1 |
| 多来源事件 | 3 |
| 事件证据 | 6 |
| 已通过事实断言 | 2 |
| 已通过研究发现 | 2 |
| 冲突 | 1（明确标识的模拟日期冲突） |
| 正式时间线事件 | 2 |
| 企业对比 | 1 份，3 家企业 |
| 专题报告草稿 | 1 |
| 报告版本 | 1 |
| 引用完整率 | 100% |
| 正式发布 | 0 |

Blujepa 事件保留模拟日期冲突，状态为 pending_review；系统未自动选值、未自动通过。报告保持 draft，未提交、未批准、未发布。

## 复现

```bat
python scripts/run_p2_3_research_pilot.py --db C:\tmp\p2_3_research_pilot_20260713.db --replace-copy --confirm-human-reviewed --batch-id P23-20260713-CODEX --report C:\tmp\p2_3_pilot_result.json
```

脚本拒绝正式数据库路径；目标已存在时也默认拒绝覆盖。
